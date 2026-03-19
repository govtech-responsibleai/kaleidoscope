"""
Repository for TargetRubric database operations.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from src.common.database.models import TargetRubric


class TargetRubricRepository:
    """Repository for TargetRubric CRUD operations."""

    @staticmethod
    def create(db: Session, target_id: int, data: dict) -> TargetRubric:
        """Create a new custom rubric for a target."""
        max_pos = (
            db.query(TargetRubric)
            .filter(TargetRubric.target_id == target_id)
            .count()
        )
        rubric = TargetRubric(target_id=target_id, position=max_pos, **data)
        db.add(rubric)
        db.commit()
        db.refresh(rubric)
        return rubric

    @staticmethod
    def get_by_target(db: Session, target_id: int) -> List[TargetRubric]:
        """Get all custom rubrics for a target, ordered by position."""
        return (
            db.query(TargetRubric)
            .filter(TargetRubric.target_id == target_id)
            .order_by(TargetRubric.position)
            .all()
        )

    @staticmethod
    def get_by_id(db: Session, rubric_id: int) -> Optional[TargetRubric]:
        """Get a rubric by ID."""
        return db.query(TargetRubric).filter(TargetRubric.id == rubric_id).first()

    @staticmethod
    def update(db: Session, rubric_id: int, data: dict) -> Optional[TargetRubric]:
        """Update a rubric's fields."""
        rubric = db.query(TargetRubric).filter(TargetRubric.id == rubric_id).first()
        if not rubric:
            return None
        for key, value in data.items():
            setattr(rubric, key, value)
        db.commit()
        db.refresh(rubric)
        return rubric

    @staticmethod
    def delete(db: Session, rubric_id: int) -> bool:
        """Delete a rubric."""
        rubric = db.query(TargetRubric).filter(TargetRubric.id == rubric_id).first()
        if not rubric:
            return False
        db.delete(rubric)
        db.commit()
        return True
