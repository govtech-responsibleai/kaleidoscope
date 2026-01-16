"""
Unit tests for auth utilities.
"""

import pytest
from datetime import datetime, timedelta
from jose import jwt
from unittest.mock import patch, MagicMock

from src.common.auth.utils import hash_password, verify_password, create_access_token
from src.common.config import get_settings


settings = get_settings()


@pytest.mark.unit
class TestHashPassword:
    """Tests for hash_password function."""

    @patch('src.common.auth.utils.pwd_context')
    def test_produces_valid_bcrypt_hash(self, mock_pwd_context):
        """Test that hash_password calls pwd_context.hash."""
        mock_pwd_context.hash.return_value = "$2b$12$mockedhashvalue123456789012345678901234567890"
        password = "mypassword123"
        hashed = hash_password(password)

        mock_pwd_context.hash.assert_called_once_with(password)
        assert hashed.startswith("$2b$")

    @patch('src.common.auth.utils.pwd_context')
    def test_different_passwords_call_hash_with_different_values(self, mock_pwd_context):
        """Test that different passwords are passed to the hash function."""
        mock_pwd_context.hash.side_effect = lambda p: f"$2b$12$hash_{p}"

        hash1 = hash_password("password1")
        hash2 = hash_password("password2")

        assert hash1 != hash2
        assert mock_pwd_context.hash.call_count == 2


@pytest.mark.unit
class TestVerifyPassword:
    """Tests for verify_password function."""

    @patch('src.common.auth.utils.pwd_context')
    def test_returns_true_for_correct_password(self, mock_pwd_context):
        """Test verify_password returns True for correct password."""
        mock_pwd_context.verify.return_value = True

        result = verify_password("correctpassword", "$2b$12$somehash")

        assert result is True
        mock_pwd_context.verify.assert_called_once_with("correctpassword", "$2b$12$somehash")

    @patch('src.common.auth.utils.pwd_context')
    def test_returns_false_for_wrong_password(self, mock_pwd_context):
        """Test verify_password returns False for wrong password."""
        mock_pwd_context.verify.return_value = False

        result = verify_password("wrongpassword", "$2b$12$somehash")

        assert result is False

    @patch('src.common.auth.utils.pwd_context')
    def test_returns_false_for_empty_password(self, mock_pwd_context):
        """Test verify_password returns False for empty password."""
        mock_pwd_context.verify.return_value = False

        result = verify_password("", "$2b$12$somehash")

        assert result is False


@pytest.mark.unit
class TestCreateAccessToken:
    """Tests for create_access_token function."""

    def test_produces_valid_jwt(self):
        """Test that create_access_token produces a valid JWT."""
        user_id = 123
        token = create_access_token(user_id)

        # Decode the token
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )

        assert payload["sub"] == str(user_id)
        assert "exp" in payload

    def test_token_contains_correct_user_id(self):
        """Test that token contains the correct user ID."""
        user_id = 456
        token = create_access_token(user_id)

        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )

        assert payload["sub"] == "456"

    def test_token_has_expiration(self):
        """Test that token has an expiration time."""
        token = create_access_token(1)

        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )

        # Check expiration is in the future
        exp_datetime = datetime.utcfromtimestamp(payload["exp"])
        assert exp_datetime > datetime.utcnow()

    def test_different_users_get_different_tokens(self):
        """Test that different user IDs produce different tokens."""
        token1 = create_access_token(1)
        token2 = create_access_token(2)

        assert token1 != token2
