"""
Repository for Judge database operations.
"""

from typing import List, Optional
from sqlalchemy import case, or_
from sqlalchemy.orm import Session

from src.common.database.models import Judge


class JudgeRepository:
    """Repository for Judge CRUD operations."""

    @staticmethod
    def _apply_list_ordering(query):
        """Order seeded defaults before custom judges."""
        return query.order_by(
            case((Judge.is_editable.is_(False), 0), else_=1),
            case(
                (Judge.name == "Judge 1 (Recommended)", 0),
                (Judge.name == "Judge 2", 1),
                (Judge.name == "Judge 3", 2),
                else_=3,
            ),
            Judge.created_at.asc(),
            Judge.id.asc(),
        )

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
    def get_all(db: Session, target_id: Optional[int] = None) -> List[Judge]:
        """Get all judges, optionally filtered by target_id (always includes global defaults)."""
        query = db.query(Judge)
        if target_id is not None:
            query = query.filter(
                or_(Judge.target_id == target_id, Judge.target_id.is_(None))
            )
        return JudgeRepository._apply_list_ordering(query).all()

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
    def get_by_category(db: Session, category: str, target_id: Optional[int] = None) -> List[Judge]:
        """Get judges that match a given category, optionally filtered by target_id."""
        query = db.query(Judge).filter(Judge.category == category)
        if target_id is not None:
            query = query.filter(
                or_(Judge.target_id == target_id, Judge.target_id.is_(None))
            )
        return JudgeRepository._apply_list_ordering(query).all()

    @staticmethod
    def delete(db: Session, judge_id: int) -> bool:
        """Delete a judge."""
        judge = db.query(Judge).filter(Judge.id == judge_id).first()
        if not judge:
            return False
        db.delete(judge)
        db.commit()
        return True
