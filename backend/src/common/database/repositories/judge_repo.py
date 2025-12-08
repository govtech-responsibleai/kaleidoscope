"""
Repository for Judge database operations.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from src.common.database.models import Judge


class JudgeRepository:
    """Repository for Judge CRUD operations."""

    @staticmethod
    def create(db: Session, judge_data: dict) -> Judge:
        """Create a new judge."""
        judge = Judge(**judge_data)
        db.add(judge)
        db.commit()
        db.refresh(judge)
        return judge

    @staticmethod
    def get_by_id(db: Session, judge_id: int) -> Optional[Judge]:
        """Get judge by ID."""
        return db.query(Judge).filter(Judge.id == judge_id).first()

    @staticmethod
    def get_all(db: Session) -> List[Judge]:
        """Get all judges."""
        return db.query(Judge).all()

    @staticmethod
    def get_baseline(db: Session) -> Optional[Judge]:
        """Get the baseline judge."""
        return db.query(Judge).filter(Judge.is_baseline == True).first()

    @staticmethod
    def get_editable_judges(db: Session) -> List[Judge]:
        """Get all editable judges (non-baseline or explicitly marked editable)."""
        return db.query(Judge).filter(Judge.is_editable == True).all()

    @staticmethod
    def update(db: Session, judge_id: int, judge_data: dict) -> Optional[Judge]:
        """Update a judge."""
        judge = db.query(Judge).filter(Judge.id == judge_id).first()
        if not judge:
            return None

        for key, value in judge_data.items():
            if value is not None:
                setattr(judge, key, value)

        db.commit()
        db.refresh(judge)
        return judge

    @staticmethod
    def delete(db: Session, judge_id: int) -> bool:
        """Delete a judge."""
        judge = db.query(Judge).filter(Judge.id == judge_id).first()
        if not judge:
            return False

        db.delete(judge)
        db.commit()
        return True

    @staticmethod
    def duplicate(db: Session, judge_id: int, new_name: str) -> Optional[Judge]:
        """
        Duplicate an existing judge configuration.
        Creates a copy with a new name, keeping all other config the same.
        The duplicate is always editable and not a baseline.
        """
        source_judge = db.query(Judge).filter(Judge.id == judge_id).first()
        if not source_judge:
            return None

        new_judge = Judge(
            name=new_name,
            model_name=source_judge.model_name,
            prompt_template=source_judge.prompt_template,
            params=source_judge.params,
            judge_type=source_judge.judge_type,
            is_baseline=False,
            is_editable=True
        )

        db.add(new_judge)
        db.commit()
        db.refresh(new_judge)
        return new_judge
