"""
Base classes for target connectors.

A connector encapsulates how Kaleidoscope communicates with a target
application endpoint — sending a prompt and receiving a response.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


class TargetHttpError(Exception):
    """Raised when a target endpoint responds with a non-success HTTP status.

    Carries the response body and headers so callers (probe, test-connection,
    evaluation pipeline) can surface the endpoint's own error message instead
    of a bare status line.
    """

    def __init__(self, status_code: int, body: str, headers: Dict[str, str]):
        self.status_code = status_code
        self.body = body
        self.headers = headers
        super().__init__(f"Target endpoint returned HTTP {status_code}")

    def __str__(self) -> str:
        snippet = self.body[:200] + ("…" if len(self.body) > 200 else "")
        return f"Target endpoint returned HTTP {self.status_code}: {snippet}"


@dataclass
class ConnectorResponse:
    """Standardised response from any target connector.

    Attributes:
        content: The answer text extracted from the target's response.
        raw_response: The full, unmodified response for traceability.
        model: Model identifier reported by the target (if available).
        tokens: Token usage dict (keys vary by target).
        metadata: Connector-specific extras (e.g. chat_id, guardrails,
                  rag_citations, system_prompt, message_id).
    """
    content: str
    raw_response: Dict[str, Any]
    model: Optional[str] = None
    tokens: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class TargetConnector(ABC):
    """Abstract base for all target connectors.

    Subclasses implement the details of talking to a specific kind of
    endpoint (AIBots two-step chat, generic HTTP, etc.).
    """

    def __init__(self, endpoint_url: str, config: Dict[str, Any]):
        self.endpoint_url = endpoint_url.rstrip("/")
        self.config = config

    @classmethod
    def validate_config(cls, config: dict) -> None:
        """Validate endpoint_config for this connector type.

        Subclasses override to enforce required config keys.
        Raises ValueError for invalid configuration.
        """

    @abstractmethod
    async def send_message(self, prompt: str) -> ConnectorResponse:
        """Send a prompt to the target and return the response."""
        ...

    async def probe(self, prompt: str) -> Any:
        """Probe mode — send the prompt and return the raw response body.

        Default implementation calls send_message and returns its raw_response,
        which means connector-specific parsing still runs. Subclasses should
        override to skip parsing when the whole point of probing is to inspect
        the response shape before declaring any extraction path.
        """
        result = await self.send_message(prompt)
        return result.raw_response
