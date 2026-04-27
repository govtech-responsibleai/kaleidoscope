"""Repository for target-scoped managed HTTP auth secrets."""

from typing import Optional

from sqlalchemy.orm import Session

from src.common.database.models import TargetHttpAuthSecret


class TargetHttpAuthSecretRepository:
    """CRUD helpers for managed HTTP auth secrets."""

    @staticmethod
    def get_by_target_id(db: Session, target_id: int) -> Optional[TargetHttpAuthSecret]:
        return db.query(TargetHttpAuthSecret).filter(TargetHttpAuthSecret.target_id == target_id).first()

    @staticmethod
    def upsert(db: Session, target_id: int, encrypted_secret: str) -> TargetHttpAuthSecret:
        secret = TargetHttpAuthSecretRepository.get_by_target_id(db, target_id)
        if secret:
            secret.encrypted_secret = encrypted_secret
        else:
            secret = TargetHttpAuthSecret(target_id=target_id, encrypted_secret=encrypted_secret)
            db.add(secret)
        db.flush()
        return secret

    @staticmethod
    def delete_by_target_id(db: Session, target_id: int) -> None:
        secret = TargetHttpAuthSecretRepository.get_by_target_id(db, target_id)
        if secret:
            db.delete(secret)
            db.flush()
