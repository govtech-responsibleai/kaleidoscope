"""
Generic HTTP connector — sends a prompt to any REST endpoint.
"""

import logging
from typing import Any, Dict

import httpx

from src.common.connectors.base import ConnectorResponse, TargetConnector

logger = logging.getLogger(__name__)


def _extract_by_path(data: Any, path: str) -> Any:
    """Extract a value from nested data using dot-notation.

    Supports dict keys and integer list indices.
    Example: "choices.0.message.content" extracts
             data["choices"][0]["message"]["content"]
    """
    current = data
    for part in path.split("."):
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, dict):
            current = current[part]
        else:
            raise KeyError(f"Cannot traverse into {type(current).__name__} with key '{part}'")
    return current


class HttpConnector(TargetConnector):
    """Connector for any HTTP endpoint.

    The endpoint URL comes from `target.api_endpoint`.

    Required config keys:
        response_content_path: Dot-notation path to extract the answer
                               text from the JSON response. E.g.
                               "choices.0.message.content" or just "output".

    Optional config keys:
        method: HTTP method (default: "POST").
        headers: Dict of extra headers to send.
        body_template: JSON-serialisable body. The string "{{prompt}}"
                       anywhere in a string value is replaced with the
                       actual prompt text. If omitted, sends
                       {"prompt": "<text>"}.
        timeout: Request timeout in seconds (default: 60).
        response_model_path: Dot-notation path to extract model name.
        response_tokens_path: Dot-notation path to extract token usage dict.
    """

    @classmethod
    def validate_config(cls, config: dict) -> None:
        """Require response_content_path in endpoint_config."""
        if not config.get("response_content_path"):
            raise ValueError("response_content_path is required in endpoint_config for http endpoint")

    async def send_message(self, prompt: str) -> ConnectorResponse:
        """Send the prompt to the configured HTTP endpoint."""
        method = self.config.get("method", "POST").upper()
        timeout = self.config.get("timeout", 60)
        headers = dict(self.config.get("headers", {}))

        body = self._build_body(prompt)

        logger.debug(f"HTTP connector: {method} {self.endpoint_url}")

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method,
                self.endpoint_url,
                json=body,
                headers=headers,
            )
            response.raise_for_status()

        raw = response.json()
        return self._parse_response(raw)

    def _build_body(self, prompt: str) -> Any:
        """Build the request body, substituting {{prompt}}."""
        template = self.config.get("body_template")
        if template is None:
            return {"prompt": prompt}
        return self._substitute(template, prompt)

    def _substitute(self, obj: Any, prompt: str) -> Any:
        """Recursively replace '{{prompt}}' in strings within the body."""
        if isinstance(obj, str):
            return obj.replace("{{prompt}}", prompt)
        if isinstance(obj, dict):
            return {k: self._substitute(v, prompt) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._substitute(item, prompt) for item in obj]
        return obj

    def _parse_response(self, raw: Dict[str, Any]) -> ConnectorResponse:
        """Extract content and optional fields from the response."""
        content_path = self.config.get("response_content_path")
        if not content_path:
            raise ValueError("response_content_path is required in endpoint_config for HTTP connector")

        content = _extract_by_path(raw, content_path)
        if not isinstance(content, str):
            content = str(content)

        model = None
        model_path = self.config.get("response_model_path")
        if model_path:
            try:
                model = _extract_by_path(raw, model_path)
            except (KeyError, IndexError, TypeError):
                pass

        tokens = None
        tokens_path = self.config.get("response_tokens_path")
        if tokens_path:
            try:
                tokens = _extract_by_path(raw, tokens_path)
            except (KeyError, IndexError, TypeError):
                pass

        return ConnectorResponse(
            content=content,
            raw_response=raw,
            model=model,
            tokens=tokens,
        )
