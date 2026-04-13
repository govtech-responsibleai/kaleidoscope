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
        """Create or replace a rubric answer score."""
        score = (
            db.query(RubricAnswerScore)
            .filter(
                RubricAnswerScore.answer_id == data["answer_id"],
                RubricAnswerScore.rubric_id == data["rubric_id"],
                RubricAnswerScore.judge_id == data["judge_id"],
            )
            .first()
        )
        if score is None:
            score = RubricAnswerScore(**data)
            db.add(score)
        else:
            for key, value in data.items():
                setattr(score, key, value)
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

    @staticmethod
    def get_by_snapshot_and_rubric_and_judge(
        db: Session, snapshot_id: int, rubric_id: int, judge_id: int
    ) -> List[RubricAnswerScore]:
        """Get all rubric scores for a judge on a rubric in a snapshot."""
        from src.common.database.models import Answer
        return (
            db.query(RubricAnswerScore)
            .join(Answer, RubricAnswerScore.answer_id == Answer.id)
            .filter(
                Answer.snapshot_id == snapshot_id,
                RubricAnswerScore.rubric_id == rubric_id,
                RubricAnswerScore.judge_id == judge_id,
            )
            .all()
        )

    @staticmethod
    def get_by_snapshot_and_rubric_and_judge_selected(
        db: Session, snapshot_id: int, rubric_id: int, judge_id: int
    ) -> List[RubricAnswerScore]:
        """Same but only for selected-for-annotation answers."""
        from src.common.database.models import Answer
        return (
            db.query(RubricAnswerScore)
            .join(Answer, RubricAnswerScore.answer_id == Answer.id)
            .filter(
                Answer.snapshot_id == snapshot_id,
                Answer.is_selected_for_annotation == True,
                RubricAnswerScore.rubric_id == rubric_id,
                RubricAnswerScore.judge_id == judge_id,
            )
            .all()
        )

    @staticmethod
    def get_human_labels_by_snapshot_selected(db: Session, snapshot_id: int, rubric_id: int):
        """Get human rubric labels for selected answers in a snapshot."""
        from src.common.database.models import Answer, RubricAnnotation
        return (
            db.query(RubricAnnotation)
            .join(Answer, RubricAnnotation.answer_id == Answer.id)
            .filter(
                Answer.snapshot_id == snapshot_id,
                Answer.is_selected_for_annotation == True,
                RubricAnnotation.rubric_id == rubric_id,
            )
            .all()
        )

    @staticmethod
    def get_human_labels_by_snapshot(db: Session, snapshot_id: int, rubric_id: int):
        """Get ALL human rubric labels for answers in a snapshot."""
        from src.common.database.models import Answer, RubricAnnotation
        return (
            db.query(RubricAnnotation)
            .join(Answer, RubricAnnotation.answer_id == Answer.id)
            .filter(
                Answer.snapshot_id == snapshot_id,
                RubricAnnotation.rubric_id == rubric_id,
            )
            .all()
        )

    @staticmethod
    def delete_scores_by_rubric(db: Session, rubric_id: int) -> int:
        """Delete all judge scores for a rubric.

        Called when rubric options change so stale option_chosen values
        don't linger in the database.

        Args:
            db: Database session
            rubric_id: The rubric whose scores should be purged

        Returns:
            Number of scores deleted
        """
        score_count = (
            db.query(RubricAnswerScore)
            .filter(RubricAnswerScore.rubric_id == rubric_id)
            .delete()
        )
        db.commit()
        return score_count
