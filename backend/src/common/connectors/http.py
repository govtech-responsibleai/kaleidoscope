"""
Generic HTTP connector — sends a prompt to any REST endpoint.
"""

import logging
from typing import Any, Dict

import httpx

from src.common.connectors.base import ConnectorResponse, TargetConnector, TargetHttpError

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
        response_model_path: Dot-notation path to extract the model name.
        metadata_fields: Dict of {label: dot_path} pairs. Each named field
                         is extracted from the response and stored in
                         ConnectorResponse.metadata. Missing paths are
                         silently ignored. E.g.
                         {"tokens": "usage", "finish": "choices.0.finish_reason"}
    """

    @classmethod
    def validate_config(cls, config: dict) -> None:
        """Require response_content_path in endpoint_config."""
        if not config.get("response_content_path"):
            raise ValueError("response_content_path is required in endpoint_config for http endpoint")

    async def send_message(self, prompt: str) -> ConnectorResponse:
        """Send the prompt to the configured HTTP endpoint."""
        raw = await self._request(prompt)
        return self._parse_response(raw)

    async def probe(self, prompt: str) -> Any:
        """Probe mode — send the prompt and return the raw parsed body.

        Bypasses _parse_response so the caller can inspect the response shape
        without having to declare response_content_path first.
        """
        return await self._request(prompt)

    async def _request(self, prompt: str) -> Any:
        """Build body, dispatch request, return parsed body.

        Raises:
            TargetHttpError: if the endpoint responds with a 4xx or 5xx.
        """
        method = self.config.get("method", "POST").upper()
        timeout = self.config.get("timeout", 60)
        headers = dict(self.config.get("headers", {}))

        body = self._build_body_from(self.config, prompt)

        logger.debug(f"HTTP connector: {method} {self.endpoint_url}")

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method,
                self.endpoint_url,
                json=body,
                headers=headers,
            )

        if response.status_code >= 400:
            raise TargetHttpError(
                status_code=response.status_code,
                body=response.text,
                headers=dict(response.headers),
            )

        try:
            return response.json()
        except ValueError:
            # Non-JSON response — return raw text so probe can still show it.
            return response.text

    def _build_body(self, prompt: str) -> Any:
        """Build the request body from self.config, substituting {{prompt}}.

        Kept for test compatibility — production path uses _build_body_from
        with an env-resolved config.
        """
        return self._build_body_from(self.config, prompt)

    def _build_body_from(self, cfg: Dict[str, Any], prompt: str) -> Any:
        """Build the request body from the given config dict."""
        template = cfg.get("body_template")
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

        try:
            content = _extract_by_path(raw, content_path)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ValueError(
                f"response_content_path '{content_path}' was not found in the response."
            ) from exc
        if not isinstance(content, str):
            content = str(content)

        model = None
        model_path = self.config.get("response_model_path")
        if model_path:
            try:
                model = _extract_by_path(raw, model_path)
            except (KeyError, IndexError, TypeError):
                pass

        metadata: Dict[str, Any] = {}
        for label, path in (self.config.get("metadata_fields") or {}).items():
            try:
                metadata[label] = _extract_by_path(raw, path)
            except (KeyError, IndexError, TypeError):
                pass

        return ConnectorResponse(
            content=content,
            raw_response=raw,
            model=model,
            metadata=metadata,
        )
