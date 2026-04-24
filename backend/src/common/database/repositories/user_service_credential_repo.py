"""Repository helpers for user-scoped service credentials."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.common.database.models import UserServiceCredential


class UserServiceCredentialRepository:
    """CRUD helpers for user-managed service credentials."""

    @staticmethod
    def get_by_user_and_service(
        db: Session,
        user_id: int,
        service_key: str,
    ) -> Optional[UserServiceCredential]:
        return (
            db.query(UserServiceCredential)
            .filter(
                UserServiceCredential.user_id == user_id,
                UserServiceCredential.service_key == service_key,
            )
            .first()
        )

    @staticmethod
    def list_by_user(db: Session, user_id: int) -> list[UserServiceCredential]:
        return (
            db.query(UserServiceCredential)
            .filter(UserServiceCredential.user_id == user_id)
            .order_by(UserServiceCredential.service_key.asc())
            .all()
        )

    @staticmethod
    def upsert(
        db: Session,
        user_id: int,
        service_key: str,
        encrypted_credentials: str,
    ) -> UserServiceCredential:
        record = UserServiceCredentialRepository.get_by_user_and_service(db, user_id, service_key)
        if record:
            record.encrypted_credentials = encrypted_credentials
        else:
            record = UserServiceCredential(
                user_id=user_id,
                service_key=service_key,
                encrypted_credentials=encrypted_credentials,
            )
            db.add(record)
        db.flush()
        return record

    @staticmethod
    def delete_by_user_and_service(db: Session, user_id: int, service_key: str) -> None:
        record = UserServiceCredentialRepository.get_by_user_and_service(db, user_id, service_key)
        if record:
            db.delete(record)
            db.flush()
