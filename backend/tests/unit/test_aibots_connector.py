"""
Unit tests for the AIBots connector.
"""

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, Mock

from src.extensions.aibots.connector import AibotsConnector
from src.common.connectors.base import ConnectorResponse


SAMPLE_AIBOTS_RESPONSE = {
    "id": "msg_456",
    "response": {
        "content": "MediShield Life is a basic health insurance plan.",
        "guardrails": {
            "message": {"status": "completed", "results": {}},
            "pass": True,
            "blocked": False,
        },
    },
    "systemPrompt": {"content": "You are a helpful assistant."},
    "model": "azure~openai.gpt-5-mini",
    "tokens": {"query": 10, "systemPrompt": 500, "response": 50},
    "rag": {
        "chunks": [
            {"id": "c1", "source": "doc.txt", "chunk": "some text", "score": 0.9}
        ]
    },
}


@pytest.mark.unit
class TestAibotsConnector:
    """Tests for AibotsConnector."""

    def test_init_requires_api_key(self):
        """Connector raises if api_key is missing."""
        with pytest.raises(ValueError, match="api_key is required"):
            AibotsConnector("https://api.test.com", {})

    def test_init_succeeds_with_api_key(self):
        """Connector initialises with valid config."""
        conn = AibotsConnector("https://api.test.com", {"api_key": "k"})
        assert conn.api_key == "k"
        assert conn.endpoint_url == "https://api.test.com"

    @pytest.mark.asyncio
    async def test_send_message_full_flow(self):
        """send_message creates a chat then sends the prompt."""
        conn = AibotsConnector(
            "https://api.test.com/v1/api",
            {"api_key": "test_key"},
        )

        # Mock httpx.AsyncClient
        mock_client = MagicMock()

        # Chat creation response
        chat_resp = Mock()
        chat_resp.json.return_value = {"id": "chat_123"}
        chat_resp.raise_for_status = Mock()

        # Message response
        msg_resp = Mock()
        msg_resp.json.return_value = SAMPLE_AIBOTS_RESPONSE
        msg_resp.raise_for_status = Mock()

        call_count = 0

        async def mock_post(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if "/chats" in url and "/messages" not in url:
                return chat_resp
            return msg_resp

        mock_client.post = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        original = httpx.AsyncClient

        try:
            httpx.AsyncClient = lambda **kw: mock_client
            result = await conn.send_message("What is MediShield?")
        finally:
            httpx.AsyncClient = original

        assert isinstance(result, ConnectorResponse)
        assert result.content == "MediShield Life is a basic health insurance plan."
        assert result.model == "azure~openai.gpt-5-mini"
        assert result.tokens == {"query": 10, "systemPrompt": 500, "response": 50}
        assert result.metadata["chat_id"] == "chat_123"
        assert result.metadata["message_id"] == "msg_456"
        assert result.metadata["system_prompt"] == "You are a helpful assistant."
        assert result.metadata["guardrails"]["pass"] is True
        assert len(result.metadata["rag_citations"]) == 1
        assert result.raw_response == SAMPLE_AIBOTS_RESPONSE

    def test_parse_response_handles_missing_fields(self):
        """Parsing works when optional fields are absent."""
        conn = AibotsConnector("https://api.test.com", {"api_key": "k"})
        minimal = {
            "id": "msg_1",
            "response": {"content": "Hello"},
        }
        result = conn._parse_response("chat_1", minimal)
        assert result.content == "Hello"
        assert result.model is None
        assert result.tokens is None
        assert result.metadata["guardrails"] is None
        assert result.metadata["rag_citations"] == []

    def test_parse_response_empty_content(self):
        """Parsing returns empty string when content is missing."""
        conn = AibotsConnector("https://api.test.com", {"api_key": "k"})
        result = conn._parse_response("chat_1", {"response": {}})
        assert result.content == ""

    def test_optional_config_fields(self):
        """Config fields like agents, model, params are stored."""
        conn = AibotsConnector(
            "https://api.test.com",
            {
                "api_key": "k",
                "agents": ["uuid1"],
                "model": "azure~openai.gpt-5",
                "params": {"temperature": 0.0},
            },
        )
        assert conn.config["agents"] == ["uuid1"]
        assert conn.config["model"] == "azure~openai.gpt-5"
