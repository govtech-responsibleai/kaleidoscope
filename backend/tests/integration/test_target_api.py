"""
Integration tests for target API endpoints.
"""

import pytest

from src.common.connectors.http_auth import decrypt_http_auth_secret
from src.common.database.repositories import TargetHttpAuthSecretRepository, TargetRepository


@pytest.mark.integration
class TestTargetAPI:
    """Integration tests for target API."""

    def test_target_crud_flow(self, auth_client, auth_headers):
        """
        Test complete target CRUD flow with authentication.

        Tests:
        1. Create a new target
        2. List targets (user sees own targets)
        3. Get target by ID
        4. Update target
        5. Delete target
        """
        # 1. Create target
        create_response = auth_client.post(
            "/api/v1/targets",
            json={
                "name": "Test Bot",
                "agency": "Test Agency",
                "purpose": "Testing purposes",
                "target_users": "Test users"
            },
            headers=auth_headers
        )

        assert create_response.status_code == 201
        target_data = create_response.json()
        assert target_data["name"] == "Test Bot"
        assert target_data["agency"] == "Test Agency"
        target_id = target_data["id"]

        # 2. List targets
        list_response = auth_client.get(
            "/api/v1/targets",
            headers=auth_headers
        )

        assert list_response.status_code == 200
        targets = list_response.json()
        assert len(targets) >= 1
        target_names = [t["name"] for t in targets]
        assert "Test Bot" in target_names

        # 3. Get target by ID
        get_response = auth_client.get(
            f"/api/v1/targets/{target_id}",
            headers=auth_headers
        )

        assert get_response.status_code == 200
        assert get_response.json()["id"] == target_id

        # 4. Update target
        update_response = auth_client.put(
            f"/api/v1/targets/{target_id}",
            json={"name": "Updated Bot"},
            headers=auth_headers
        )

        assert update_response.status_code == 200
        assert update_response.json()["name"] == "Updated Bot"

        # 5. Delete target
        delete_response = auth_client.delete(
            f"/api/v1/targets/{target_id}",
            headers=auth_headers
        )

        assert delete_response.status_code == 204

        # Verify deleted
        get_deleted = auth_client.get(
            f"/api/v1/targets/{target_id}",
            headers=auth_headers
        )
        assert get_deleted.status_code == 404

    def test_create_target_without_auth_returns_401(self, auth_client):
        """Test that creating a target without authentication returns 401."""
        response = auth_client.post(
            "/api/v1/targets",
            json={
                "name": "Test Bot",
                "agency": "Test Agency",
                "purpose": "Testing",
                "target_users": "Users"
            }
        )

        assert response.status_code == 401

    def test_list_targets_without_auth_returns_401(self, auth_client):
        """Test that listing targets without authentication returns 401."""
        response = auth_client.get("/api/v1/targets")

        assert response.status_code == 401

    def test_get_target_not_found(self, auth_client, auth_headers):
        """Test error handling when target doesn't exist."""
        response = auth_client.get(
            "/api/v1/targets/99999",
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_update_target_not_found(self, auth_client, auth_headers):
        """Test error handling when updating non-existent target."""
        response = auth_client.put(
            "/api/v1/targets/99999",
            json={"name": "New Name"},
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_delete_target_not_found(self, auth_client, auth_headers):
        """Test error handling when deleting non-existent target."""
        response = auth_client.delete(
            "/api/v1/targets/99999",
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_create_target_with_managed_http_auth(self, auth_client, auth_headers, test_db_factory):
        response = auth_client.post(
            "/api/v1/targets",
            json={
                "name": "Managed Auth Bot",
                "api_endpoint": "https://api.example.com",
                "endpoint_type": "http",
                "endpoint_config": {
                    "response_content_path": "output",
                    "auth": {
                        "preset": "x-api-key",
                        "secret_value": "sk-secret-1234",
                    },
                },
            },
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["endpoint_config"]["auth"]["preset"] == "x-api-key"
        assert data["endpoint_config"]["auth"]["is_configured"] is True
        assert data["endpoint_config"]["auth"]["masked_value"] != "sk-secret-1234"
        assert "secret_value" not in data["endpoint_config"]["auth"]

        db = test_db_factory()
        try:
            target = TargetRepository.get_by_id(db, data["id"])
            secret = TargetHttpAuthSecretRepository.get_by_target_id(db, data["id"])
            assert target is not None
            assert target.endpoint_config["auth"]["masked_value"] == data["endpoint_config"]["auth"]["masked_value"]
            assert secret is not None
            assert decrypt_http_auth_secret(secret.encrypted_secret) == "sk-secret-1234"
        finally:
            db.close()

    def test_update_target_can_clear_managed_http_auth(self, auth_client, auth_headers, test_db_factory):
        create_response = auth_client.post(
            "/api/v1/targets",
            json={
                "name": "Managed Auth Bot",
                "api_endpoint": "https://api.example.com",
                "endpoint_type": "http",
                "endpoint_config": {
                    "response_content_path": "output",
                    "auth": {
                        "preset": "bearer",
                        "secret_value": "sk-secret-1234",
                    },
                },
            },
            headers=auth_headers,
        )
        target_id = create_response.json()["id"]

        update_response = auth_client.put(
            f"/api/v1/targets/{target_id}",
            json={
                "endpoint_type": "http",
                "endpoint_config": {
                    "response_content_path": "output",
                    "auth": {
                        "preset": "bearer",
                        "clear_secret": True,
                    },
                },
            },
            headers=auth_headers,
        )

        assert update_response.status_code == 200
        data = update_response.json()
        assert "auth" not in (data["endpoint_config"] or {})

        db = test_db_factory()
        try:
            target = TargetRepository.get_by_id(db, target_id)
            secret = TargetHttpAuthSecretRepository.get_by_target_id(db, target_id)
            assert target is not None
            assert "auth" not in (target.endpoint_config or {})
            assert secret is None
        finally:
            db.close()
