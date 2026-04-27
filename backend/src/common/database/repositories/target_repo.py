"""
Repository for Target database operations.
"""

import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, text

from src.common.database.models import Target, Persona, Question, Job, StatusEnum

logger = logging.getLogger(__name__)


class TargetRepository:
    """Repository for Target CRUD operations."""

    @staticmethod
    def create(db: Session, target_data: dict) -> Target:
        """Create a new target."""
        target = Target(**target_data)
        db.add(target)
        db.commit()
        db.refresh(target)
        return target

    @staticmethod
    def get_by_id(db: Session, target_id: int) -> Optional[Target]:
        """Get target by ID."""
        return db.query(Target).filter(Target.id == target_id).first()

    @staticmethod
    def get_all(db: Session, skip: int = 0, limit: int = 100) -> List[Target]:
        """Get all targets with pagination."""
        return db.query(Target).offset(skip).limit(limit).all()

    @staticmethod
    def update(db: Session, target_id: int, target_data: dict) -> Optional[Target]:
        """Update a target."""
        target = db.query(Target).filter(Target.id == target_id).first()
        if not target:
            return None

        for key, value in target_data.items():
            if value is not None:
                setattr(target, key, value)

        db.commit()
        db.refresh(target)
        return target

    @staticmethod
    def delete(db: Session, target_id: int) -> bool:
        """Delete a target using raw SQL to leverage database-level CASCADE.

        ORM-level cascade loads all related objects into memory before deleting,
        which can be extremely slow for targets with lots of data and cause
        gateway timeouts. Raw SQL lets PostgreSQL handle cascades efficiently.
        """
        exists = db.query(Target.id).filter(Target.id == target_id).first()
        if not exists:
            return False

        db.execute(
            text("DELETE FROM targets WHERE id = :id"),
            {"id": target_id}
        )
        db.commit()
        logger.info(f"Deleted target {target_id} (database CASCADE handled related data)")
        return True

    @staticmethod
    def get_stats(db: Session, target_id: int) -> dict:
        """Get statistics for a target."""
        # Get persona counts by status
        persona_counts = (
            db.query(Persona.status, func.count(Persona.id))
            .filter(Persona.target_id == target_id)
            .group_by(Persona.status)
            .all()
        )
        personas = {status.value: count for status, count in persona_counts}

        # Get question counts by status
        question_counts = (
            db.query(Question.status, func.count(Question.id))
            .filter(Question.target_id == target_id)
            .group_by(Question.status)
            .all()
        )
        questions = {status.value: count for status, count in question_counts}

        # Get total cost from all jobs
        total_cost = (
            db.query(func.sum(Job.total_cost))
            .filter(Job.target_id == target_id)
            .scalar()
        ) or 0.0

        return {
            "personas": personas,
            "questions": questions,
            "total_cost": float(total_cost)
        }
