"""
AIBots connector — implements the two-step chat flow
(create session → send message) used by the AIBots platform.
"""

import logging
from typing import Any, Dict

import httpx

from src.common.connectors.base import ConnectorResponse, TargetConnector

logger = logging.getLogger(__name__)


class AibotsConnector(TargetConnector):
    """Connector for AIBots (https://aibots.gov.sg).

    Required config keys:
        api_key: X-ATLAS-Key for authentication.

    Optional config keys:
        agents: List of bot agent UUIDs (default: []).
        model: LLM identifier, e.g. "azure~openai.gpt-5-mini".
        params: Dict of model params, e.g. {"temperature": 0.0}.
        chat_timeout: Timeout in seconds for chat creation (default: 30).
        message_timeout: Timeout in seconds for message send (default: 60).
    """

    def __init__(self, endpoint_url: str, config: Dict[str, Any]):
        super().__init__(endpoint_url, config)
        self.api_key = config.get("api_key")
        if not self.api_key:
            raise ValueError("api_key is required in endpoint_config for AIBots connector")

    @classmethod
    def validate_config(cls, config: dict) -> None:
        """Require api_key in endpoint_config."""
        if not config.get("api_key"):
            raise ValueError("api_key is required in endpoint_config for aibots endpoint")

    async def send_message(self, prompt: str) -> ConnectorResponse:
        """Create a chat session, send the prompt, and return the response."""
        chat_id = await self._create_chat(prompt)
        raw_response = await self._send_chat_message(chat_id, prompt)
        return self._parse_response(chat_id, raw_response)

    async def _create_chat(self, prompt: str) -> str:
        """Create a new chat session and return the chat ID."""
        url = f"{self.endpoint_url}/chats"
        timeout = self.config.get("chat_timeout", 30)

        payload: Dict[str, Any] = {
            "name": "Kaleidoscope eval",
            "agents": self.config.get("agents", []),
        }
        # Include model and params if configured (doc-compliant)
        if "model" in self.config:
            payload["model"] = self.config["model"]
        if "params" in self.config:
            payload["params"] = self.config["params"]

        headers = {
            "X-ATLAS-Key": self.api_key,
            "Content-Type": "application/json",
        }

        logger.debug(f"AIBots: creating chat at {url}")

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        logger.debug(f"AIBots: chat created with id={data['id']}")
        return data["id"]

    async def _send_chat_message(self, chat_id: str, content: str) -> Dict[str, Any]:
        """Send a message to an existing chat session."""
        url = f"{self.endpoint_url}/chats/{chat_id}/messages?streaming=false&cloak=false"
        timeout = self.config.get("message_timeout", 60)

        headers = {"X-ATLAS-Key": self.api_key}
        data = {"content": content}

        logger.debug(f"AIBots: sending message to chat {chat_id}")

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, data=data, headers=headers)
            response.raise_for_status()

        return response.json()

    def _parse_response(self, chat_id: str, raw: Dict[str, Any]) -> ConnectorResponse:
        """Extract structured fields from the AIBots response."""
        response_obj = raw.get("response", {})
        system_prompt_obj = raw.get("systemPrompt", {})
        rag_obj = raw.get("rag", {})

        return ConnectorResponse(
            content=response_obj.get("content", ""),
            raw_response=raw,
            model=raw.get("model"),
            tokens=raw.get("tokens"),
            metadata={
                "chat_id": chat_id,
                "message_id": raw.get("id"),
                "system_prompt": system_prompt_obj.get("content"),
                "guardrails": response_obj.get("guardrails"),
                "rag_citations": rag_obj.get("chunks", []),
            },
        )
