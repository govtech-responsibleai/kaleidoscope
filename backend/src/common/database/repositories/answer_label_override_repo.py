"""
Repository for AnswerLabelOverride database operations.
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session

from src.common.database.models import AnswerLabelOverride, Answer


class AnswerLabelOverrideRepository:
    """Repository for AnswerLabelOverride CRUD operations."""

    @staticmethod
    def create_or_update(
        db: Session, answer_id: int, edited_label: bool, metric_name: str = "accuracy"
    ) -> AnswerLabelOverride:
        """
        Create or update a label override for an answer.

        Args:
            db: Database session
            answer_id: Answer ID to override
            edited_label: The new label (True=Accurate, False=Inaccurate)
            metric_name: Name of the metric being overridden (default: "accuracy")

        Returns:
            The created or updated AnswerLabelOverride
        """
        override = (
            db.query(AnswerLabelOverride)
            .filter(AnswerLabelOverride.answer_id == answer_id)
            .first()
        )

        if override:
            override.edited_label = edited_label
            override.edited_at = datetime.utcnow()
            override.metric_name = metric_name
        else:
            override = AnswerLabelOverride(
                answer_id=answer_id,
                edited_label=edited_label,
                metric_name=metric_name,
                edited_at=datetime.utcnow()
            )
            db.add(override)

        db.commit()
        db.refresh(override)
        return override

    @staticmethod
    def get_by_answer(db: Session, answer_id: int) -> Optional[AnswerLabelOverride]:
        """Get label override for a specific answer."""
        return (
            db.query(AnswerLabelOverride)
            .filter(AnswerLabelOverride.answer_id == answer_id)
            .first()
        )

    @staticmethod
    def get_by_snapshot(db: Session, snapshot_id: int) -> List[AnswerLabelOverride]:
        """Get all label overrides for a snapshot (join with answers)."""
        return (
            db.query(AnswerLabelOverride)
            .join(Answer)
            .filter(Answer.snapshot_id == snapshot_id)
            .all()
        )

    @staticmethod
    def count_by_snapshot(db: Session, snapshot_id: int) -> int:
        """Count total label overrides for a snapshot."""
        return (
            db.query(AnswerLabelOverride)
            .join(Answer)
            .filter(Answer.snapshot_id == snapshot_id)
            .count()
        )

    @staticmethod
    def delete(db: Session, answer_id: int) -> bool:
        """
        Delete a label override by answer ID (reset to original).

        Args:
            db: Database session
            answer_id: Answer ID whose override should be deleted

        Returns:
            True if deleted, False if not found
        """
        override = (
            db.query(AnswerLabelOverride)
            .filter(AnswerLabelOverride.answer_id == answer_id)
            .first()
        )
        if not override:
            return False

        db.delete(override)
        db.commit()
        return True
