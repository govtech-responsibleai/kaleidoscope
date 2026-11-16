from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel

from src.common.llm.client import LLMClient
from src.common.llm.provider_service import ProviderRuntimeConfig


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

    @patch("src.common.llm.client.litellm.completion_cost", return_value=0.0)
    @patch("src.common.llm.client.litellm.completion")
    def test_generate_sends_litellm_model_on_the_wire(self, mock_completion, _mock_cost):
        mock_completion.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="hi"))],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            model="gpt-5.6-luna",
        )
        client = LLMClient(
            model="govtech/gpt-5.6-luna",
            litellm_model="openai/gpt-5.6-luna",
            provider_kwargs={"api_key": "k", "api_base": "https://platform.example/v1"},
        )
        client.generate("hello")

        assert mock_completion.call_args.kwargs["model"] == "openai/gpt-5.6-luna"
        assert client.model == "govtech/gpt-5.6-luna"

    @pytest.mark.asyncio
    @patch("src.common.llm.client.litellm.completion_cost", return_value=0.0)
    @patch("src.common.llm.client.litellm.acompletion", new_callable=AsyncMock)
    async def test_async_sends_litellm_model_and_keeps_display_model_in_semaphore_key(self, mock_acompletion, _mock_cost):
        mock_acompletion.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"value":"ok"}'))],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            model="gpt-5.6-luna",
        )
        client = LLMClient(model="govtech/gpt-5.6-luna", litellm_model="openai/gpt-5.6-luna")
        await client.generate_structured_async(prompt="p", response_model=_DummyStructuredResponse)

        assert mock_acompletion.call_args.kwargs["model"] == "openai/gpt-5.6-luna"
        assert any(key[0] == "govtech/gpt-5.6-luna" for key in LLMClient._semaphores)

    def test_from_runtime_config_round_trips(self):
        config = ProviderRuntimeConfig(
            provider_key="govtech",
            model_name="govtech/gpt-5.6-luna",
            litellm_kwargs={"api_key": "k", "api_base": "https://platform.example/v1"},
            litellm_model="openai/gpt-5.6-luna",
        )
        client = LLMClient.from_runtime_config(config)
        assert client.model == "govtech/gpt-5.6-luna"
        assert client.litellm_model == "openai/gpt-5.6-luna"
        assert client.provider_kwargs == config.litellm_kwargs

    def test_litellm_model_defaults_to_model(self):
        client = LLMClient(model="gemini/gemini-3.1-flash-lite")
        assert client.litellm_model == "gemini/gemini-3.1-flash-lite"

    @pytest.mark.asyncio
    @patch("src.common.llm.client.litellm.completion_cost", return_value=0.0)
    @patch("src.common.llm.client.litellm.acompletion", new_callable=AsyncMock)
    async def test_async_respects_requested_temperature_for_normal_models(self, mock_acompletion, _mock_cost):
        mock_acompletion.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"value":"ok"}'))],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            model="gemini/gemini-3.1-flash-lite",
        )
        client = LLMClient(model="gemini/gemini-3.1-flash-lite")
        await client.generate_structured_async(prompt="p", response_model=_DummyStructuredResponse, temperature=0.0)
        assert mock_acompletion.call_args.kwargs["temperature"] == 0.0
