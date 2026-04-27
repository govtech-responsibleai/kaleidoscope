"""Repository for TargetRubric database operations."""

from typing import List, Optional
from sqlalchemy import case
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
    def get_by_target(
        db: Session,
        target_id: int,
        group: Optional[str] = None,
        name: Optional[str] = None,
    ) -> List[TargetRubric]:
        """Get target rubrics in stable backend display order, optionally filtered."""
        query = db.query(TargetRubric).filter(TargetRubric.target_id == target_id)
        if group is not None:
            query = query.filter(TargetRubric.group == group)
        if name is not None:
            query = query.filter(TargetRubric.name == name)

        return query.order_by(
            case(
                (TargetRubric.group == "fixed", 0),
                (TargetRubric.group == "preset", 1),
                else_=2,
            ),
            TargetRubric.created_at.asc(),
            TargetRubric.id.asc(),
        ).all()

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
