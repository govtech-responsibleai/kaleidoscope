from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel

from src.common.llm.client import LLMClient


class _DummyStructuredResponse(BaseModel):
    value: str


class TestLLMClientProviderKwargs:
    @patch("src.common.llm.client.litellm.completion_cost", return_value=0.25)
    @patch("src.common.llm.client.litellm.completion")
    def test_generate_passes_provider_kwargs(self, mock_completion, _mock_cost):
        mock_completion.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="hello"))],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=2, total_tokens=3),
            model="openai/gpt-4.1-mini",
        )

        client = LLMClient(
            model="openai/gpt-4.1-mini",
            provider_kwargs={"api_key": "sk-provider", "api_base": "https://example.test"},
        )
        result = client.generate("hello")

        assert result["content"] == "hello"
        mock_completion.assert_called_once()
        assert mock_completion.call_args.kwargs["api_key"] == "sk-provider"
        assert mock_completion.call_args.kwargs["api_base"] == "https://example.test"

    @pytest.mark.asyncio
    @patch("src.common.llm.client.litellm.completion_cost", return_value=0.25)
    @patch("src.common.llm.client.litellm.acompletion", new_callable=AsyncMock)
    async def test_generate_structured_async_passes_provider_kwargs(self, mock_acompletion, _mock_cost):
        mock_acompletion.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"value":"ok"}'))],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=2, total_tokens=3),
            model="openai/gpt-5.4-mini",
        )

        client = LLMClient(
            model="openai/gpt-5.4-mini",
            provider_kwargs={"api_key": "sk-provider", "api_base": "https://example.test"},
        )
        result, metadata = await client.generate_structured_async(
            prompt="hello",
            response_model=_DummyStructuredResponse,
        )

        assert result.value == "ok"
        assert metadata["model"] == "openai/gpt-5.4-mini"
        mock_acompletion.assert_awaited_once()
        assert mock_acompletion.call_args.kwargs["api_key"] == "sk-provider"
        assert mock_acompletion.call_args.kwargs["api_base"] == "https://example.test"
