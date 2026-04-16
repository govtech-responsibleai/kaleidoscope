"""
Integration tests for POST /targets/probe.

Probe returns the raw response body for inspection, without requiring
response_content_path — so the user can see the endpoint's actual shape
before declaring an extraction path.
"""

import pytest
from unittest.mock import AsyncMock, patch

from src.common.connectors.base import TargetHttpError
from src.common.database.models import Target


@pytest.mark.integration
class TestProbeEndpoint:

    def test_probe_success_returns_raw_body(self, auth_client, auth_headers):
        raw_body = {
            "request_id": "abc-123",
            "status": "completed",
            "results": {"refusal": {"score": 0.8, "reasoning": "refused"}},
        }

        with patch("src.query_generation.api.routes.targets.get_connector") as mock_get:
            mock_connector = AsyncMock()
            mock_connector.probe.return_value = raw_body
            mock_get.return_value = mock_connector

            resp = auth_client.post(
                "/api/v1/targets/probe",
                json={
                    "endpoint_type": "http",
                    "api_endpoint": "https://api.example.com/validate",
                    "endpoint_config": {
                        "headers": {"x-api-key": "test-key"},
                        "body_template": {"input": "{{prompt}}"},
                    },
                    "prompt": "test probe prompt",
                },
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["status_code"] == 200
        assert data["raw_body"] == raw_body
        mock_connector.probe.assert_awaited_once_with("test probe prompt")

    def test_probe_without_response_content_path(self, auth_client, auth_headers):
        """Probe must succeed even when endpoint_config lacks response_content_path."""
        with patch("src.query_generation.api.routes.targets.get_connector") as mock_get:
            mock_connector = AsyncMock()
            mock_connector.probe.return_value = {"foo": "bar"}
            mock_get.return_value = mock_connector

            resp = auth_client.post(
                "/api/v1/targets/probe",
                json={
                    "endpoint_type": "http",
                    "api_endpoint": "https://api.example.com",
                    "endpoint_config": {},
                },
                headers=auth_headers,
            )

        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_probe_4xx_surfaces_response_body(self, auth_client, auth_headers):
        """A 422 from the target returns success=false with the body preserved."""
        err_body = '{"error": "field missing", "detail": "input is required"}'

        with patch("src.query_generation.api.routes.targets.get_connector") as mock_get:
            mock_connector = AsyncMock()
            mock_connector.probe.side_effect = TargetHttpError(
                status_code=422,
                body=err_body,
                headers={"content-type": "application/json"},
            )
            mock_get.return_value = mock_connector

            resp = auth_client.post(
                "/api/v1/targets/probe",
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
        assert data["status_code"] == 422
        assert data["raw_body"] == {"error": "field missing", "detail": "input is required"}
        assert data["headers"]["content-type"] == "application/json"

    def test_probe_4xx_non_json_body_passes_through_as_string(self, auth_client, auth_headers):
        with patch("src.query_generation.api.routes.targets.get_connector") as mock_get:
            mock_connector = AsyncMock()
            mock_connector.probe.side_effect = TargetHttpError(
                status_code=500,
                body="Internal Server Error",
                headers={},
            )
            mock_get.return_value = mock_connector

            resp = auth_client.post(
                "/api/v1/targets/probe",
                json={
                    "endpoint_type": "http",
                    "api_endpoint": "https://api.example.com",
                    "endpoint_config": {},
                },
                headers=auth_headers,
            )

        data = resp.json()
        assert data["success"] is False
        assert data["status_code"] == 500
        assert data["raw_body"] == "Internal Server Error"

    def test_probe_unknown_endpoint_type_returns_400(self, auth_client, auth_headers):
        resp = auth_client.post(
            "/api/v1/targets/probe",
            json={
                "endpoint_type": "not-a-real-type",
                "api_endpoint": "https://api.example.com",
                "endpoint_config": {},
            },
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "Unknown endpoint type" in resp.json()["detail"]

    def test_probe_requires_auth(self, auth_client):
        resp = auth_client.post(
            "/api/v1/targets/probe",
            json={
                "endpoint_type": "http",
                "api_endpoint": "https://api.example.com",
                "endpoint_config": {},
            },
        )
        assert resp.status_code == 401

    def test_probe_transport_failure_returns_error(self, auth_client, auth_headers):
        with patch("src.query_generation.api.routes.targets.get_connector") as mock_get:
            mock_connector = AsyncMock()
            mock_connector.probe.side_effect = Exception("DNS resolution failed")
            mock_get.return_value = mock_connector

            resp = auth_client.post(
                "/api/v1/targets/probe",
                json={
                    "endpoint_type": "http",
                    "api_endpoint": "https://nope.example.com",
                    "endpoint_config": {},
                },
                headers=auth_headers,
            )

        data = resp.json()
        assert data["success"] is False
        assert "DNS resolution failed" in data["error"]

    def test_probe_reuses_saved_auth_only_for_authorized_target(
        self, auth_client, auth_headers, test_db, test_user
    ):
        owned_target = Target(
            name="Owned Target",
            user_id=test_user.id,
            api_endpoint="https://owned.example.com",
            endpoint_type="http",
            endpoint_config={"response_content_path": "output"},
        )
        test_db.add(owned_target)
        test_db.commit()
        test_db.refresh(owned_target)

        observed_ids = []

        def fake_get_connector(target_stub, db=None):
            observed_ids.append(target_stub.id)
            mock_connector = AsyncMock()
            mock_connector.probe.return_value = {"ok": True}
            return mock_connector

        with patch("src.query_generation.api.routes.targets.get_connector", side_effect=fake_get_connector):
            resp = auth_client.post(
                "/api/v1/targets/probe",
                json={
                    "target_id": owned_target.id,
                    "endpoint_type": "http",
                    "api_endpoint": "https://api.example.com",
                    "endpoint_config": {},
                },
                headers=auth_headers,
            )

        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert observed_ids == [owned_target.id]
