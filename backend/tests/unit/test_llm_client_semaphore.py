"""
Test that LLMClient semaphore works across multiple event loops.

Regression test for bug where asyncio.run() creates a new event loop each time,
but a cached Semaphore stayed bound to the old (dead) loop, causing:
  "Semaphore object is bound to a different event loop"

Python 3.12+ removed the runtime check, so we test structurally:
each event loop must get its own semaphore instance.
"""

import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from src.common.llm.client import LLMClient


@pytest.mark.unit
class TestLLMClientSemaphore:
    """Tests for semaphore event-loop safety in LLMClient."""

    def setup_method(self):
        """Clear cached semaphores between tests."""
        LLMClient._semaphores.clear()

    @patch("src.common.llm.client.litellm")
    def test_each_event_loop_gets_its_own_semaphore(self, mock_litellm):
        """
        Simulate the qa_jobs.py pattern: multiple asyncio.run() calls
        reusing the same model. Each asyncio.run() creates a new event
        loop — verify each gets a distinct semaphore so there's no
        cross-loop binding (which causes errors on Python <3.12).
        """
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"value": "ok"}'))]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        mock_litellm.acompletion = AsyncMock(return_value=mock_response)
        mock_litellm.completion_cost.return_value = 0.001

        from pydantic import BaseModel

        class SimpleResponse(BaseModel):
            value: str

        semaphores_seen = []

        async def do_llm_call():
            client = LLMClient(model="test-model")
            await client.generate_structured_async(
                prompt="test prompt",
                response_model=SimpleResponse,
            )
            semaphores_seen.append(client._get_semaphore())

        # Each asyncio.run() creates a brand-new event loop
        asyncio.run(do_llm_call())
        asyncio.run(do_llm_call())
        asyncio.run(do_llm_call())

        # Each loop must have gotten a DIFFERENT semaphore object
        assert len(semaphores_seen) == 3
        assert semaphores_seen[0] is not semaphores_seen[1], \
            "Loops 1 and 2 should have different semaphores"
        assert semaphores_seen[1] is not semaphores_seen[2], \
            "Loops 2 and 3 should have different semaphores"

    @patch("src.common.llm.client.litellm")
    def test_same_loop_reuses_semaphore(self, mock_litellm):
        """
        Within a single event loop, multiple LLMClient instances for the
        same model should share the same semaphore.
        """
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"value": "ok"}'))]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        mock_litellm.acompletion = AsyncMock(return_value=mock_response)
        mock_litellm.completion_cost.return_value = 0.001

        from pydantic import BaseModel

        class SimpleResponse(BaseModel):
            value: str

        async def check_shared():
            client_a = LLMClient(model="test-model")
            client_b = LLMClient(model="test-model")
            await client_a.generate_structured_async(
                prompt="test", response_model=SimpleResponse)
            await client_b.generate_structured_async(
                prompt="test", response_model=SimpleResponse)
            assert client_a._get_semaphore() is client_b._get_semaphore()

        asyncio.run(check_shared())

    @patch("src.common.llm.client.litellm")
    def test_concurrent_calls_respect_semaphore_limit(self, mock_litellm):
        """
        Verify the semaphore still limits concurrency within a single loop.
        """
        call_count = 0
        max_concurrent = 0

        async def mock_acompletion(*args, **kwargs):
            nonlocal call_count, max_concurrent
            call_count += 1
            max_concurrent = max(max_concurrent, call_count)
            await asyncio.sleep(0.01)
            call_count -= 1

            response = MagicMock()
            response.choices = [MagicMock(message=MagicMock(content='{"value": "ok"}'))]
            response.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
            return response

        mock_litellm.acompletion = AsyncMock(side_effect=mock_acompletion)
        mock_litellm.completion_cost.return_value = 0.001

        from pydantic import BaseModel

        class SimpleResponse(BaseModel):
            value: str

        async def run_batch():
            client = LLMClient(model="test-model")
            tasks = [
                client.generate_structured_async(
                    prompt=f"prompt {i}",
                    response_model=SimpleResponse,
                )
                for i in range(20)
            ]
            results = await asyncio.gather(*tasks)
            assert len(results) == 20

        asyncio.run(run_batch())

        from src.common.config import get_settings
        assert max_concurrent <= get_settings().llm_max_concurrent
