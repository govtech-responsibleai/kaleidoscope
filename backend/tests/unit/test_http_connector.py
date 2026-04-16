"""
Unit tests for the generic HTTP connector.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock

import httpx

from src.common.connectors.http import HttpConnector, _extract_by_path
from src.common.connectors.base import ConnectorResponse, TargetHttpError


@pytest.mark.unit
class TestExtractByPath:
    """Tests for the dot-notation path extractor."""

    def test_simple_key(self):
        assert _extract_by_path({"output": "hello"}, "output") == "hello"

    def test_nested_keys(self):
        data = {"choices": [{"message": {"content": "hi"}}]}
        assert _extract_by_path(data, "choices.0.message.content") == "hi"

    def test_list_index(self):
        data = {"items": ["a", "b", "c"]}
        assert _extract_by_path(data, "items.1") == "b"

    def test_missing_key_raises(self):
        with pytest.raises(KeyError):
            _extract_by_path({"a": 1}, "b")

    def test_index_out_of_range_raises(self):
        with pytest.raises(IndexError):
            _extract_by_path({"items": [1]}, "items.5")


@pytest.mark.unit
class TestHttpConnector:
    """Tests for HttpConnector."""

    def _make_connector(self, **config_overrides):
        config = {
            "response_content_path": "output",
            **config_overrides,
        }
        return HttpConnector("https://api.example.com/generate", config)

    @pytest.mark.asyncio
    async def test_send_message_default_body(self):
        """Default body sends {"prompt": "<text>"}."""
        conn = self._make_connector()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"output": "The answer is 42"}

        mock_client = MagicMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        original = httpx.AsyncClient
        try:
            httpx.AsyncClient = lambda **kw: mock_client
            result = await conn.send_message("What is the meaning of life?")
        finally:
            httpx.AsyncClient = original

        assert isinstance(result, ConnectorResponse)
        assert result.content == "The answer is 42"

        # Verify the request was made with default body
        mock_client.request.assert_called_once()
        call_kwargs = mock_client.request.call_args
        assert call_kwargs.kwargs["json"] == {"prompt": "What is the meaning of life?"}

    @pytest.mark.asyncio
    async def test_send_message_custom_body_template(self):
        """Custom body_template substitutes {{prompt}}."""
        conn = self._make_connector(
            body_template={
                "messages": [{"role": "user", "content": "{{prompt}}"}],
                "temperature": 0.5,
            },
            response_content_path="choices.0.message.content",
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "response text"}}]
        }

        mock_client = MagicMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        original = httpx.AsyncClient
        try:
            httpx.AsyncClient = lambda **kw: mock_client
            result = await conn.send_message("Hello")
        finally:
            httpx.AsyncClient = original

        assert result.content == "response text"

        call_kwargs = mock_client.request.call_args
        expected_body = {
            "messages": [{"role": "user", "content": "Hello"}],
            "temperature": 0.5,
        }
        assert call_kwargs.kwargs["json"] == expected_body

    @pytest.mark.asyncio
    async def test_send_message_with_headers(self):
        """Custom headers are sent with the request."""
        conn = self._make_connector(
            headers={"Authorization": "Bearer my-token", "X-Custom": "val"},
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"output": "ok"}

        mock_client = MagicMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        original = httpx.AsyncClient
        try:
            httpx.AsyncClient = lambda **kw: mock_client
            await conn.send_message("test")
        finally:
            httpx.AsyncClient = original

        call_kwargs = mock_client.request.call_args
        assert call_kwargs.kwargs["headers"]["Authorization"] == "Bearer my-token"
        assert call_kwargs.kwargs["headers"]["X-Custom"] == "val"

    @pytest.mark.asyncio
    async def test_send_message_extracts_model_and_metadata(self):
        """response_model_path and metadata_fields are extracted independently."""
        conn = self._make_connector(
            response_content_path="result.text",
            response_model_path="result.model",
            metadata_fields={
                "tokens": "usage",
                "finish": "choices.0.finish_reason",
            },
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {"text": "answer", "model": "gpt-4"},
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            "choices": [{"finish_reason": "stop"}],
        }

        mock_client = MagicMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        original = httpx.AsyncClient
        try:
            httpx.AsyncClient = lambda **kw: mock_client
            result = await conn.send_message("test")
        finally:
            httpx.AsyncClient = original

        assert result.content == "answer"
        assert result.model == "gpt-4"
        assert result.metadata["tokens"] == {"prompt_tokens": 10, "completion_tokens": 20}
        assert result.metadata["finish"] == "stop"

    @pytest.mark.asyncio
    async def test_metadata_fields_missing_path_is_ignored(self):
        """A metadata_fields path that doesn't exist is silently skipped."""
        conn = self._make_connector(
            metadata_fields={"present": "output", "missing": "does.not.exist"},
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"output": "hello"}

        mock_client = MagicMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        original = httpx.AsyncClient
        try:
            httpx.AsyncClient = lambda **kw: mock_client
            result = await conn.send_message("test")
        finally:
            httpx.AsyncClient = original

        assert result.metadata["present"] == "hello"
        assert "missing" not in result.metadata

    def test_missing_response_content_path_raises(self):
        """Parsing raises if response_content_path is not configured."""
        conn = HttpConnector("https://api.test.com", {})
        with pytest.raises(ValueError, match="response_content_path is required"):
            conn._parse_response({"output": "test"})

    def test_missing_response_content_path_value_raises_clearly(self):
        """Missing extraction path should return a readable error."""
        conn = self._make_connector(response_content_path="results.refusal.reasoning")
        with pytest.raises(ValueError, match="response_content_path 'results.refusal.reasoning' was not found"):
            conn._parse_response({"results": {"score": 1}})

    def test_build_body_default(self):
        """Default body when no template is given."""
        conn = self._make_connector()
        assert conn._build_body("hello") == {"prompt": "hello"}

    def test_build_body_nested_substitution(self):
        """{{prompt}} is replaced at any nesting level."""
        conn = self._make_connector(
            body_template={"a": {"b": "prefix: {{prompt}}"}, "c": ["{{prompt}}"]}
        )
        result = conn._build_body("test")
        assert result == {"a": {"b": "prefix: test"}, "c": ["test"]}

    @pytest.mark.asyncio
    async def test_raises_target_http_error_with_body(self):
        """4xx response raises TargetHttpError carrying status_code, body, headers."""
        conn = self._make_connector()

        mock_response = Mock()
        mock_response.status_code = 422
        mock_response.text = '{"error": "invalid payload", "detail": "field X missing"}'
        mock_response.headers = {"content-type": "application/json"}

        mock_client = MagicMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        original = httpx.AsyncClient
        try:
            httpx.AsyncClient = lambda **kw: mock_client
            with pytest.raises(TargetHttpError) as exc_info:
                await conn.send_message("test")
        finally:
            httpx.AsyncClient = original

        err = exc_info.value
        assert err.status_code == 422
        assert "invalid payload" in err.body
        assert err.headers["content-type"] == "application/json"
