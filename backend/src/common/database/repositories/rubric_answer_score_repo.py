"""
Repository for RubricAnswerScore database operations.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from src.common.database.models import RubricAnswerScore


class RubricAnswerScoreRepository:
    """Repository for RubricAnswerScore CRUD operations."""

    @staticmethod
    def create(db: Session, data: dict) -> RubricAnswerScore:
        """Create a new rubric answer score."""
        score = RubricAnswerScore(**data)
        db.add(score)
        db.commit()
        db.refresh(score)
        return score

    @staticmethod
    def get_by_answer_and_rubric(
        db: Session, answer_id: int, rubric_id: int
    ) -> List[RubricAnswerScore]:
        """Get all rubric scores for a specific answer and rubric (one per judge)."""
        return (
            db.query(RubricAnswerScore)
            .filter(
                RubricAnswerScore.answer_id == answer_id,
                RubricAnswerScore.rubric_id == rubric_id,
            )
            .all()
        )

    @staticmethod
    def get_by_answer_rubric_judge(
        db: Session, answer_id: int, rubric_id: int, judge_id: int
    ) -> Optional[RubricAnswerScore]:
        """Get score for a specific (answer, rubric, judge) triple."""
        return (
            db.query(RubricAnswerScore)
            .filter(
                RubricAnswerScore.answer_id == answer_id,
                RubricAnswerScore.rubric_id == rubric_id,
                RubricAnswerScore.judge_id == judge_id,
            )
            .first()
        )
