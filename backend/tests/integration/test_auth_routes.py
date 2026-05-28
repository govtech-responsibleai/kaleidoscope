"""
Integration tests for auth API endpoints.
"""

import pytest
from unittest.mock import patch

from src.common.config import get_settings
from src.common.connectors.http_auth import decrypt_http_auth_secret
from src.common.database.models import Target, User
from src.common.database.repositories import TargetHttpAuthSecretRepository
from tests.conftest import override_settings


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

    def test_login_with_null_hashed_password_returns_401(self, auth_client, test_db):
        """Test password login rejects Google-only accounts cleanly."""
        test_db.add(User(username="google.user@gov.sg", hashed_password=None, is_active=True))
        test_db.commit()

        response = auth_client.post(
            "/api/v1/auth/login",
            data={"username": "google.user@gov.sg", "password": "anypassword"}
        )

        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]


@pytest.mark.integration
class TestGoogleLoginEndpoint:
    """Tests for POST /api/v1/auth/google endpoint."""

    @patch("src.common.auth.routes.verify_oauth2_token", create=True)
    def test_google_login_valid_token_allowed_domain_creates_user_and_returns_token(
        self, mock_verify, auth_client, test_db_factory
    ):
        """Valid Google token creates a user and returns the normal token shape."""
        mock_verify.return_value = {"email": "alice@gov.sg", "email_verified": True}

        with override_settings(google_client_id="google-client", allowed_email_domains="gov.sg"):
            response = auth_client.post(
                "/api/v1/auth/google",
                json={"credential": "valid-google-id-token"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["access_token"]
        assert data["token_type"] == "bearer"
        assert data["is_admin"] is False
        assert data["username"] == "alice@gov.sg"

        db = test_db_factory()
        try:
            user = db.query(User).filter(User.username == "alice@gov.sg").one()
            assert user.hashed_password is None
        finally:
            db.close()

    @patch("src.common.auth.routes.verify_oauth2_token", create=True)
    def test_google_login_disallowed_domain_returns_403(self, mock_verify, auth_client):
        """Valid Google token from a disallowed domain is rejected."""
        mock_verify.return_value = {"email": "alice@example.com", "email_verified": True}

        with override_settings(google_client_id="google-client", allowed_email_domains="gov.sg"):
            response = auth_client.post(
                "/api/v1/auth/google",
                json={"credential": "valid-google-id-token"},
            )

        assert response.status_code == 403
        assert "authorised email domains" in response.json()["detail"]

    @patch("src.common.auth.routes.verify_oauth2_token", create=True)
    def test_google_login_invalid_token_returns_401(self, mock_verify, auth_client):
        """Invalid Google tokens return 401."""
        mock_verify.side_effect = ValueError("invalid token")

        with override_settings(google_client_id="google-client", allowed_email_domains="gov.sg"):
            response = auth_client.post(
                "/api/v1/auth/google",
                json={"credential": "invalid-google-id-token"},
            )

        assert response.status_code == 401

    @patch("src.common.auth.routes.verify_oauth2_token", create=True)
    def test_google_login_empty_allowlist_returns_403(self, mock_verify, auth_client):
        """An empty allowlist rejects all Google sign-ins."""
        mock_verify.return_value = {"email": "alice@gov.sg", "email_verified": True}

        with override_settings(google_client_id="google-client", allowed_email_domains=""):
            response = auth_client.post(
                "/api/v1/auth/google",
                json={"credential": "valid-google-id-token"},
            )

        assert response.status_code == 403
        assert "authorised email domains" in response.json()["detail"]

    @patch("src.common.auth.routes.verify_oauth2_token", create=True)
    def test_google_login_returning_user_does_not_create_duplicate_user_or_target(
        self, mock_verify, auth_client, test_db, test_db_factory
    ):
        """Returning Google sign-in reuses the existing user and does not seed again."""
        existing = User(username="alice@gov.sg", hashed_password=None, is_active=True)
        test_db.add(existing)
        test_db.commit()
        test_db.refresh(existing)
        test_db.add(
            Target(
                user_id=existing.id,
                name="Existing Demo",
                api_endpoint="https://example.com/chat",
                endpoint_type="http",
                endpoint_config={"response_content_path": "answer"},
            )
        )
        test_db.commit()
        mock_verify.return_value = {"email": "alice@gov.sg", "email_verified": True}

        with override_settings(
            google_client_id="google-client",
            allowed_email_domains="gov.sg",
            demo_target_endpoint="https://example.com/chat",
            demo_target_response_path="answer",
        ):
            response = auth_client.post(
                "/api/v1/auth/google",
                json={"credential": "valid-google-id-token"},
            )

        assert response.status_code == 200
        db = test_db_factory()
        try:
            assert db.query(User).filter(User.username == "alice@gov.sg").count() == 1
            assert db.query(Target).filter(Target.user_id == existing.id).count() == 1
        finally:
            db.close()


@pytest.mark.integration
class TestDemoTargetSeeding:
    """Tests for demo target seeding helper."""

    def test_seed_demo_target_creates_configured_http_target(self, test_db, test_user):
        """Full DEMO_TARGET config creates the expected HTTP target."""
        from src.common.auth.demo_target_seed import seed_demo_target

        with override_settings(
            demo_target_endpoint="https://example.com/chat",
            demo_target_name="Singapore Information Chatbot",
            demo_target_agency="GovTech",
            demo_target_purpose="Helps users learn about Singapore.",
            demo_target_target_users="Curious users.",
            demo_target_response_path="answer",
            demo_target_retrieved_context_path="sources",
            demo_target_headers='{"Content-Type":"application/json","X-API-Key":"test-api13579"}',
            demo_target_body_template='{"question":"{{prompt}}"}',
        ):
            target = seed_demo_target(test_db, test_user.id)

        assert target is not None
        assert target.user_id == test_user.id
        assert target.name == "Singapore Information Chatbot"
        assert target.agency == "GovTech"
        assert target.purpose == "Helps users learn about Singapore."
        assert target.target_users == "Curious users."
        assert target.api_endpoint == "https://example.com/chat"
        assert target.endpoint_type == "http"
        assert target.endpoint_config == {
            "headers": {"Content-Type": "application/json"},
            "auth": {
                "preset": "x-api-key",
                "is_configured": True,
                "masked_value": "•••••••••3579",
            },
            "body_template": {"question": "{{prompt}}"},
            "response_content_path": "answer",
            "retrieved_context_path": "sources",
        }
        secret = TargetHttpAuthSecretRepository.get_by_target_id(test_db, target.id)
        assert secret is not None
        assert decrypt_http_auth_secret(secret.encrypted_secret) == "test-api13579"

    def test_seed_demo_target_noops_when_endpoint_absent(self, test_db, test_user):
        """No DEMO_TARGET_ENDPOINT means no target is created."""
        from src.common.auth.demo_target_seed import seed_demo_target

        with override_settings(demo_target_endpoint=None, demo_target_response_path="answer"):
            target = seed_demo_target(test_db, test_user.id)

        assert target is None
        assert test_db.query(Target).filter(Target.user_id == test_user.id).count() == 0

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
