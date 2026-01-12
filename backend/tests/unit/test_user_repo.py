"""
Unit tests for UserRepository.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from src.common.database.repositories.user_repo import UserRepository
from src.common.database.models import User
from tests.conftest import get_test_password_hash


@pytest.mark.unit
class TestUserRepository:
    """Tests for UserRepository class."""

    def test_create_user(self, test_db):
        """Test creating a new user."""
        hashed_password = get_test_password_hash("testpassword")
        user = UserRepository.create(test_db, "newuser", hashed_password)

        assert user.id is not None
        assert user.username == "newuser"
        assert user.hashed_password == hashed_password
        assert user.is_active is True
        assert user.is_admin is False

    def test_create_admin_user(self, test_db):
        """Test creating an admin user."""
        hashed_password = get_test_password_hash("adminpassword")
        user = UserRepository.create(test_db, "adminuser", hashed_password, is_admin=True)

        assert user.is_admin is True

    def test_create_duplicate_username_raises_error(self, test_db):
        """Test that creating a user with duplicate username raises error."""
        hashed_password = get_test_password_hash("password")
        UserRepository.create(test_db, "duplicateuser", hashed_password)

        with pytest.raises(IntegrityError):
            UserRepository.create(test_db, "duplicateuser", hashed_password)

    def test_get_by_id_returns_user(self, test_db, test_user):
        """Test getting user by ID returns the user."""
        user = UserRepository.get_by_id(test_db, test_user.id)

        assert user is not None
        assert user.id == test_user.id
        assert user.username == test_user.username

    def test_get_by_id_returns_none_for_nonexistent(self, test_db):
        """Test getting user by nonexistent ID returns None."""
        user = UserRepository.get_by_id(test_db, 99999)

        assert user is None

    def test_get_by_username_returns_user(self, test_db, test_user):
        """Test getting user by username returns the user."""
        user = UserRepository.get_by_username(test_db, test_user.username)

        assert user is not None
        assert user.id == test_user.id
        assert user.username == test_user.username

    def test_get_by_username_returns_none_for_nonexistent(self, test_db):
        """Test getting user by nonexistent username returns None."""
        user = UserRepository.get_by_username(test_db, "nonexistentuser")

        assert user is None
