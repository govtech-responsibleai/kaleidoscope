"""
Repository for User database operations.
"""

from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.common.database.models import User, Target


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

    @staticmethod
    def get_all_with_target_counts(db: Session) -> List[dict]:
        """Get all users with their target counts.

        Returns:
            List of dicts with user fields and target_count.
        """
        target_count = func.count(Target.id).label("target_count")
        rows = (
            db.query(User, target_count)
            .outerjoin(Target, Target.user_id == User.id)
            .group_by(User.id)
            .order_by(User.id)
            .all()
        )
        results = []
        for user, count in rows:
            results.append({
                "id": user.id,
                "username": user.username,
                "is_active": user.is_active,
                "is_admin": user.is_admin,
                "created_at": user.created_at,
                "target_count": count,
            })
        return results
