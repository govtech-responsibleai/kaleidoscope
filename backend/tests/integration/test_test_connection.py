"""
Integration tests for the POST /targets/test-connection endpoint.
"""

import pytest
from unittest.mock import AsyncMock, patch

from src.common.connectors.base import ConnectorResponse


@pytest.mark.integration
class TestTestConnectionEndpoint:

    def test_success_returns_content_and_model(self, auth_client, auth_headers):
        mock_response = ConnectorResponse(
            content="Hello! I'm an AI assistant.",
            raw_response={"choices": [{"message": {"content": "Hello! I'm an AI assistant."}}]},
            model="gpt-4",
            tokens={"prompt_tokens": 5, "completion_tokens": 10},
        )

        with patch("src.query_generation.api.routes.targets.get_connector") as mock_get:
            mock_connector = AsyncMock()
            mock_connector.send_message.return_value = mock_response
            mock_get.return_value = mock_connector

            resp = auth_client.post(
                "/api/v1/targets/test-connection",
                json={
                    "endpoint_type": "http",
                    "api_endpoint": "https://api.example.com/v1/chat/completions",
                    "endpoint_config": {
                        "response_content_path": "choices.0.message.content",
                        "body_template": {"model": "gpt-4", "messages": [{"role": "user", "content": "{{prompt}}"}]},
                        "response_model_path": "model",
                        "response_tokens_path": "usage",
                    },
                },
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "Hello" in data["content"]
        assert data["model"] == "gpt-4"

    def test_connection_error_returns_failure(self, auth_client, auth_headers):
        with patch("src.query_generation.api.routes.targets.get_connector") as mock_get:
            mock_connector = AsyncMock()
            mock_connector.send_message.side_effect = Exception("Connection refused")
            mock_get.return_value = mock_connector

            resp = auth_client.post(
                "/api/v1/targets/test-connection",
                json={
                    "endpoint_type": "http",
                    "api_endpoint": "https://bad-host.example.com",
                    "endpoint_config": {"response_content_path": "output"},
                },
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "Connection refused" in data["error"]

    def test_validation_error_returns_failure(self, auth_client, auth_headers):
        with patch("src.query_generation.api.routes.targets.validate_connector_config") as mock_val:
            mock_val.side_effect = ValueError("Missing required field: api_key")

            resp = auth_client.post(
                "/api/v1/targets/test-connection",
                json={
                    "endpoint_type": "http",
                    "api_endpoint": "https://api.example.com",
                    "endpoint_config": {},
                },
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "api_key" in data["error"]

    def test_requires_auth(self, auth_client):
        resp = auth_client.post(
            "/api/v1/targets/test-connection",
            json={
                "endpoint_type": "http",
                "api_endpoint": "https://api.example.com",
                "endpoint_config": {},
            },
        )
        assert resp.status_code == 401

    def test_truncates_long_content(self, auth_client, auth_headers):
        long_content = "A" * 500
        mock_response = ConnectorResponse(
            content=long_content,
            raw_response={"output": long_content},
        )

        with patch("src.query_generation.api.routes.targets.get_connector") as mock_get:
            mock_connector = AsyncMock()
            mock_connector.send_message.return_value = mock_response
            mock_get.return_value = mock_connector

            resp = auth_client.post(
                "/api/v1/targets/test-connection",
                json={
                    "endpoint_type": "http",
                    "api_endpoint": "https://api.example.com",
                    "endpoint_config": {"response_content_path": "output"},
                },
                headers=auth_headers,
            )

        data = resp.json()
        assert data["success"] is True
        assert len(data["content"]) == 200
