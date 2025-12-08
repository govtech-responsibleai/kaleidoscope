"""
Repository for AnswerScore database operations.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from src.common.database.models import AnswerScore, Answer


class AnswerScoreRepository:
    """Repository for AnswerScore CRUD operations."""

    @staticmethod
    def create(db: Session, score_data: dict) -> AnswerScore:
        """Create a new answer score."""
        score = AnswerScore(**score_data)
        db.add(score)
        db.commit()
        db.refresh(score)
        return score

    @staticmethod
    def create_many(db: Session, scores_data: List[dict]) -> List[AnswerScore]:
        """Create multiple answer scores."""
        scores = [AnswerScore(**data) for data in scores_data]
        db.add_all(scores)
        db.commit()
        for score in scores:
            db.refresh(score)
        return scores

    @staticmethod
    def get_by_id(db: Session, score_id: int) -> Optional[AnswerScore]:
        """Get answer score by ID."""
        return db.query(AnswerScore).filter(AnswerScore.id == score_id).first()

    @staticmethod
    def get_by_answer_and_judge(
        db: Session,
        answer_id: int,
        judge_id: int
    ) -> Optional[AnswerScore]:
        """Get score for a specific answer and judge combination."""
        return (
            db.query(AnswerScore)
            .filter(
                AnswerScore.answer_id == answer_id,
                AnswerScore.judge_id == judge_id
            )
            .first()
        )

    @staticmethod
    def get_by_answer(db: Session, answer_id: int) -> List[AnswerScore]:
        """Get all scores for a specific answer (from different judges)."""
        return (
            db.query(AnswerScore)
            .filter(AnswerScore.answer_id == answer_id)
            .all()
        )

    @staticmethod
    def get_by_snapshot_and_judge(
        db: Session,
        snapshot_id: int,
        judge_id: int
    ) -> List[AnswerScore]:
        """Get all scores for a snapshot evaluated by a specific judge."""
        return (
            db.query(AnswerScore)
            .join(Answer)
            .filter(
                Answer.snapshot_id == snapshot_id,
                AnswerScore.judge_id == judge_id
            )
            .all()
        )

    @staticmethod
    def get_by_snapshot_and_judge_selected(
        db: Session,
        snapshot_id: int,
        judge_id: int
    ) -> List[AnswerScore]:
        """
        Get scores for a judge on answers that are selected for annotation.
        Used for judge alignment metric calculation in service layer.
        """
        return (
            db.query(AnswerScore)
            .join(Answer)
            .filter(
                Answer.snapshot_id == snapshot_id,
                Answer.is_selected_for_annotation == True,
                AnswerScore.judge_id == judge_id
            )
            .all()
        )

    @staticmethod
    def delete(db: Session, score_id: int) -> bool:
        """Delete an answer score."""
        score = db.query(AnswerScore).filter(AnswerScore.id == score_id).first()
        if not score:
            return False

        db.delete(score)
        db.commit()
        return True
