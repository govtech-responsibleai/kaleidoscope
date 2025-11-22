"""
Repository for Answer database operations.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from src.common.database.models import Answer


class AnswerRepository:
    """Repository for Answer CRUD operations."""

    @staticmethod
    def create(db: Session, answer_data: dict) -> Answer:
        """Create a new answer."""
        answer = Answer(**answer_data)
        db.add(answer)
        db.commit()
        db.refresh(answer)
        return answer

    @staticmethod
    def get_by_id(db: Session, answer_id: int) -> Optional[Answer]:
        """Get answer by ID."""
        return db.query(Answer).filter(Answer.id == answer_id).first()

    @staticmethod
    def get_by_question(db: Session, question_id: int) -> List[Answer]:
        """Get all answers for a question."""
        return db.query(Answer).filter(Answer.question_id == question_id).all()

    @staticmethod
    def get_by_target(
        db: Session,
        target_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[Answer]:
        """Get answers for a target."""
        return (
            db.query(Answer)
            .filter(Answer.target_id == target_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def count_by_target(db: Session, target_id: int) -> int:
        """Count answers for a target."""
        return db.query(Answer).filter(Answer.target_id == target_id).count()

    @staticmethod
    def delete(db: Session, answer_id: int) -> bool:
        """Delete an answer."""
        answer = db.query(Answer).filter(Answer.id == answer_id).first()
        if not answer:
            return False
        db.delete(answer)
        db.commit()
        return True
