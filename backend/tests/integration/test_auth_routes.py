"""
Integration tests for auth API endpoints.
"""

import pytest
from unittest.mock import patch

from src.common.config import get_settings


settings = get_settings()


@pytest.mark.integration
class TestLoginEndpoint:
    """Tests for POST /api/v1/auth/login endpoint."""

    @patch('src.common.auth.routes.verify_password')
    def test_login_with_valid_credentials_returns_token(self, mock_verify, auth_client, test_user):
        """Test login with valid credentials returns access token."""
        mock_verify.return_value = True

        response = auth_client.post(
            "/api/v1/auth/login",
            data={"username": "testuser", "password": "testpassword"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @patch('src.common.auth.routes.verify_password')
    def test_login_with_invalid_password_returns_401(self, mock_verify, auth_client, test_user):
        """Test login with invalid password returns 401."""
        mock_verify.return_value = False

        response = auth_client.post(
            "/api/v1/auth/login",
            data={"username": "testuser", "password": "wrongpassword"}
        )

        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]

    def test_login_with_unknown_user_returns_401(self, auth_client):
        """Test login with unknown username returns 401."""
        response = auth_client.post(
            "/api/v1/auth/login",
            data={"username": "unknownuser", "password": "anypassword"}
        )

        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]

@pytest.mark.integration
class TestCreateUserEndpoint:
    """Tests for POST /api/v1/auth/admin/create-user endpoint."""

    @patch('src.common.auth.routes.hash_password')
    def test_create_user_with_valid_admin_key(self, mock_hash, auth_client):
        """Test creating user with valid admin key succeeds."""
        mock_hash.return_value = "$2b$12$mockedhash"

        response = auth_client.post(
            "/api/v1/auth/admin/create-user",
            json={"username": "newuser", "password": "newpassword", "is_admin": False},
            headers={"X-Admin-Key": settings.admin_api_key}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "newuser"
        assert "created successfully" in data["message"]

    @patch('src.common.auth.routes.hash_password')
    def test_create_admin_user(self, mock_hash, auth_client):
        """Test creating admin user with valid admin key."""
        mock_hash.return_value = "$2b$12$mockedhash"

        response = auth_client.post(
            "/api/v1/auth/admin/create-user",
            json={"username": "newadmin", "password": "adminpass", "is_admin": True},
            headers={"X-Admin-Key": settings.admin_api_key}
        )

        assert response.status_code == 200
        data = response.json()
        assert "(admin)" in data["message"]

    def test_create_user_with_invalid_admin_key_returns_403(self, auth_client):
        """Test creating user with invalid admin key returns 403."""
        response = auth_client.post(
            "/api/v1/auth/admin/create-user",
            json={"username": "newuser", "password": "newpassword"},
            headers={"X-Admin-Key": "invalid-key"}
        )

        assert response.status_code == 403
        assert "Invalid admin key" in response.json()["detail"]

    def test_create_user_without_admin_key_returns_422(self, auth_client):
        """Test creating user without admin key returns 422."""
        response = auth_client.post(
            "/api/v1/auth/admin/create-user",
            json={"username": "newuser", "password": "newpassword"}
        )

        assert response.status_code == 422  # Missing required header

    def test_create_duplicate_username_returns_400(self, auth_client, test_user):
        """Test creating user with existing username returns 400."""
        response = auth_client.post(
            "/api/v1/auth/admin/create-user",
            json={"username": "testuser", "password": "anypassword"},
            headers={"X-Admin-Key": settings.admin_api_key}
        )

        assert response.status_code == 400
        assert "Username already exists" in response.json()["detail"]


@pytest.mark.integration
class TestDeleteUserEndpoint:
    """Tests for DELETE /api/v1/auth/admin/delete-user/{username} endpoint."""

    def test_delete_user_with_valid_admin_key(self, auth_client, test_user):
        """Test deleting user with valid admin key succeeds."""
        response = auth_client.delete(
            "/api/v1/auth/admin/delete-user/testuser",
            headers={"X-Admin-Key": settings.admin_api_key}
        )

        assert response.status_code == 200
        assert "deleted successfully" in response.json()["message"]

    def test_delete_user_with_invalid_admin_key_returns_403(self, auth_client, test_user):
        """Test deleting user with invalid admin key returns 403."""
        response = auth_client.delete(
            "/api/v1/auth/admin/delete-user/testuser",
            headers={"X-Admin-Key": "invalid-key"}
        )

        assert response.status_code == 403
        assert "Invalid admin key" in response.json()["detail"]

    def test_delete_nonexistent_user_returns_404(self, auth_client):
        """Test deleting nonexistent user returns 404."""
        response = auth_client.delete(
            "/api/v1/auth/admin/delete-user/nonexistentuser",
            headers={"X-Admin-Key": settings.admin_api_key}
        )

        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]
