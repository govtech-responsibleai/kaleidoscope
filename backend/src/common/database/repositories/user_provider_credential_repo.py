"""Repository helpers for user-scoped provider credentials."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.common.database.models import UserProviderCredential


class UserProviderCredentialRepository:
    """CRUD helpers for user-managed provider credentials."""

    @staticmethod
    def get_by_user_and_provider(
        db: Session,
        user_id: int,
        provider_key: str,
    ) -> Optional[UserProviderCredential]:
        return (
            db.query(UserProviderCredential)
            .filter(
                UserProviderCredential.user_id == user_id,
                UserProviderCredential.provider_key == provider_key,
            )
            .first()
        )

    @staticmethod
    def list_by_user(db: Session, user_id: int) -> list[UserProviderCredential]:
        return (
            db.query(UserProviderCredential)
            .filter(UserProviderCredential.user_id == user_id)
            .order_by(UserProviderCredential.provider_key.asc())
            .all()
        )

    @staticmethod
    def upsert(
        db: Session,
        user_id: int,
        provider_key: str,
        encrypted_credentials: str,
    ) -> UserProviderCredential:
        record = UserProviderCredentialRepository.get_by_user_and_provider(db, user_id, provider_key)
        if record:
            record.encrypted_credentials = encrypted_credentials
        else:
            record = UserProviderCredential(
                user_id=user_id,
                provider_key=provider_key,
                encrypted_credentials=encrypted_credentials,
            )
            db.add(record)
        db.flush()
        return record

    @staticmethod
    def delete_by_user_and_provider(db: Session, user_id: int, provider_key: str) -> None:
        record = UserProviderCredentialRepository.get_by_user_and_provider(db, user_id, provider_key)
        if record:
            db.delete(record)
            db.flush()
