"""
Repository for User database operations.
"""

from typing import Optional
from sqlalchemy.orm import Session

from src.common.database.models import User


class UserRepository:
    """Repository for User CRUD operations."""

    @staticmethod
    def create(db: Session, username: str, hashed_password: str, is_admin: bool = False) -> User:
        """Create a new user."""
        user = User(username=username, hashed_password=hashed_password, is_admin=is_admin)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def get_by_id(db: Session, user_id: int) -> Optional[User]:
        """Get user by ID."""
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def get_by_username(db: Session, username: str) -> Optional[User]:
        """Get user by username."""
        return db.query(User).filter(User.username == username).first()
