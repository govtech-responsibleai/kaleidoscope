"""Repository for rubric-keyed AnswerLabelOverride database operations."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from src.common.database.models import Answer, AnswerLabelOverride, TargetRubric
from src.common.services.system_rubrics import canonicalize_rubric_option_value, rubric_option_values


class AnswerLabelOverrideRepository:
    """Repository for rubric-keyed answer label overrides."""

    @staticmethod
    def create_or_update(
        db: Session,
        answer_id: int,
        rubric_id: int,
        edited_value: str,
    ) -> AnswerLabelOverride:
        rubric = db.query(TargetRubric).filter(TargetRubric.id == rubric_id).first()
        if rubric is None:
            raise ValueError(f"Rubric {rubric_id} not found")

        canonical_value = canonicalize_rubric_option_value(rubric, edited_value)
        if canonical_value is None:
            raise ValueError("edited_value must be a non-empty rubric option")

        if canonical_value not in rubric_option_values(rubric):
            raise ValueError(
                f"edited_value must match one of the rubric options for rubric {rubric_id}"
            )

        override = (
            db.query(AnswerLabelOverride)
            .filter(
                AnswerLabelOverride.answer_id == answer_id,
                AnswerLabelOverride.rubric_id == rubric_id,
            )
            .first()
        )

        if override:
            override.edited_value = canonical_value
            override.edited_at = datetime.utcnow()
        else:
            override = AnswerLabelOverride(
                answer_id=answer_id,
                rubric_id=rubric_id,
                edited_value=canonical_value,
                edited_at=datetime.utcnow(),
            )
            db.add(override)

        try:
            db.commit()
            db.refresh(override)
        except Exception:
            db.rollback()
            raise
        return override

    @staticmethod
    def get_by_answer_and_rubric(
        db: Session,
        answer_id: int,
        rubric_id: int,
    ) -> Optional[AnswerLabelOverride]:
        return (
            db.query(AnswerLabelOverride)
            .filter(
                AnswerLabelOverride.answer_id == answer_id,
                AnswerLabelOverride.rubric_id == rubric_id,
            )
            .first()
        )

    @staticmethod
    def get_by_answer(db: Session, answer_id: int) -> List[AnswerLabelOverride]:
        return (
            db.query(AnswerLabelOverride)
            .filter(AnswerLabelOverride.answer_id == answer_id)
            .all()
        )

    @staticmethod
    def get_by_snapshot(db: Session, snapshot_id: int) -> List[AnswerLabelOverride]:
        return (
            db.query(AnswerLabelOverride)
            .join(Answer)
            .filter(Answer.snapshot_id == snapshot_id)
            .all()
        )

    @staticmethod
    def count_by_snapshot(db: Session, snapshot_id: int) -> int:
        return (
            db.query(AnswerLabelOverride)
            .join(Answer)
            .filter(Answer.snapshot_id == snapshot_id)
            .count()
        )

    @staticmethod
    def delete(db: Session, answer_id: int, rubric_id: int) -> bool:
        override = (
            db.query(AnswerLabelOverride)
            .filter(
                AnswerLabelOverride.answer_id == answer_id,
                AnswerLabelOverride.rubric_id == rubric_id,
            )
            .first()
        )
        if not override:
            return False

        db.delete(override)
        db.commit()
        return True
