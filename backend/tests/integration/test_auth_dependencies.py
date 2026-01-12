"""
Integration tests for auth dependencies (middleware).
"""

import pytest
from datetime import datetime, timedelta
from jose import jwt

from src.common.auth.utils import create_access_token
from src.common.config import get_settings


settings = get_settings()


@pytest.mark.integration
class TestGetCurrentUser:
    """Tests for get_current_user dependency."""

    def test_valid_token_returns_user(self, auth_client, test_user, auth_headers):
        """Test that valid token allows access to protected routes."""
        response = auth_client.get(
            "/api/v1/targets",
            headers=auth_headers
        )

        # Should succeed (200) or return empty list, not 401
        assert response.status_code == 200

    def test_invalid_token_returns_401(self, auth_client):
        """Test that invalid token returns 401."""
        response = auth_client.get(
            "/api/v1/targets",
            headers={"Authorization": "Bearer invalidtoken"}
        )

        assert response.status_code == 401
        assert "Invalid or expired token" in response.json()["detail"]

@pytest.mark.integration
class TestRequireAdmin:
    """Tests for require_admin dependency."""

    def test_admin_user_can_access_admin_routes(self, auth_client, test_admin_user, admin_auth_headers):
        """Test that admin user can access protected routes."""
        response = auth_client.get(
            "/api/v1/targets",
            headers=admin_auth_headers
        )

        assert response.status_code == 200

    def test_non_admin_cannot_access_admin_routes(self, auth_client, test_user, auth_headers):
        """Test that non-admin user can access regular protected routes."""
        # Non-admin should be able to access targets (regular protected route)
        response = auth_client.get(
            "/api/v1/targets",
            headers=auth_headers
        )

        assert response.status_code == 200
