"""
Repository for AnswerClaim database operations.
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session

from src.common.database.models import AnswerClaim


class AnswerClaimRepository:
    """Repository for AnswerClaim CRUD operations."""

    @staticmethod
    def create(db: Session, claim_data: dict) -> AnswerClaim:
        """Create a new answer claim."""
        claim = AnswerClaim(**claim_data)
        db.add(claim)
        db.commit()
        db.refresh(claim)
        return claim

    @staticmethod
    def create_many(db: Session, claims_data: List[dict]) -> List[AnswerClaim]:
        """Create multiple answer claims."""
        claims = [AnswerClaim(**data) for data in claims_data]
        db.add_all(claims)
        db.flush()
        db.commit()
        return claims

    @staticmethod
    def get_by_id(db: Session, claim_id: int) -> Optional[AnswerClaim]:
        """Get answer claim by ID."""
        return db.query(AnswerClaim).filter(AnswerClaim.id == claim_id).first()

    @staticmethod
    def get_by_answer(db: Session, answer_id: int) -> List[AnswerClaim]:
        """Get all claims for a specific answer, ordered by claim_index."""
        return (
            db.query(AnswerClaim)
            .filter(AnswerClaim.answer_id == answer_id)
            .order_by(AnswerClaim.claim_index)
            .all()
        )

    @staticmethod
    def delete_by_answer(db: Session, answer_id: int) -> bool:
        """
        Delete all claims for a specific answer.
        Useful when reprocessing an answer and extracting new claims.
        """
        claims = db.query(AnswerClaim).filter(AnswerClaim.answer_id == answer_id).all()
        if not claims:
            return False

        for claim in claims:
            db.delete(claim)
        db.commit()
        return True

    @staticmethod
    def update_checkworthy(
        db: Session,
        claim_id: int,
        checkworthy: bool,
        checked_at: datetime,
    ) -> Optional[AnswerClaim]:
        """Update the checkworthy flag and checked_at timestamp for a claim.

        Args:
            db: Database session
            claim_id: Claim ID
            checkworthy: New checkworthy value
            checked_at: Timestamp of the check

        Returns:
            Updated AnswerClaim or None if not found
        """
        claim = db.query(AnswerClaim).filter(AnswerClaim.id == claim_id).first()
        if not claim:
            return None
        claim.checkworthy = checkworthy
        claim.checked_at = checked_at
        db.commit()
        db.refresh(claim)
        return claim

    @staticmethod
    def delete(db: Session, claim_id: int) -> bool:
        """Delete a single claim."""
        claim = db.query(AnswerClaim).filter(AnswerClaim.id == claim_id).first()
        if not claim:
            return False

        db.delete(claim)
        db.commit()
        return True
