"""
Repository for AnswerClaimScore database operations.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from src.common.database.models import AnswerClaimScore


class AnswerClaimScoreRepository:
    """Repository for AnswerClaimScore CRUD operations."""

    @staticmethod
    def create(db: Session, claim_score_data: dict) -> AnswerClaimScore:
        """Create a new answer claim score."""
        claim_score = AnswerClaimScore(**claim_score_data)
        db.add(claim_score)
        db.commit()
        db.refresh(claim_score)
        return claim_score

    @staticmethod
    def create_many(db: Session, claim_scores_data: List[dict]) -> List[AnswerClaimScore]:
        """Create multiple answer claim scores."""
        claim_scores = [AnswerClaimScore(**data) for data in claim_scores_data]
        db.add_all(claim_scores)
        db.commit()
        for claim_score in claim_scores:
            db.refresh(claim_score)
        return claim_scores

    @staticmethod
    def get_by_id(db: Session, claim_score_id: int) -> Optional[AnswerClaimScore]:
        """Get answer claim score by ID."""
        return db.query(AnswerClaimScore).filter(AnswerClaimScore.id == claim_score_id).first()

    @staticmethod
    def get_by_answer_score(db: Session, answer_score_id: int) -> List[AnswerClaimScore]:
        """
        Get all claim scores for a specific answer score.
        Used for retrieving individual claim evaluations that roll up to an answer-level score.
        """
        return (
            db.query(AnswerClaimScore)
            .filter(AnswerClaimScore.answer_score_id == answer_score_id)
            .all()
        )

    @staticmethod
    def get_by_claim(db: Session, claim_id: int) -> List[AnswerClaimScore]:
        """
        Get all scores for a specific claim across different judges.
        Useful for comparing how different judges evaluated the same claim.
        """
        return (
            db.query(AnswerClaimScore)
            .filter(AnswerClaimScore.claim_id == claim_id)
            .all()
        )

    @staticmethod
    def delete(db: Session, claim_score_id: int) -> bool:
        """Delete an answer claim score."""
        claim_score = db.query(AnswerClaimScore).filter(AnswerClaimScore.id == claim_score_id).first()
        if not claim_score:
            return False

        db.delete(claim_score)
        db.commit()
        return True
