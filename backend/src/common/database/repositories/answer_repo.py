"""
Repository for Answer database operations.
"""

from typing import List, Optional
from sqlalchemy.orm import Session, joinedload

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
    def get_by_snapshot(
        db: Session,
        snapshot_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[Answer]:
        """Get answers for a snapshot with pagination."""
        return (
            db.query(Answer)
            .filter(Answer.snapshot_id == snapshot_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_by_question_and_snapshot(
        db: Session,
        question_id: int,
        snapshot_id: int
    ) -> Optional[Answer]:
        """Get answer for a specific question in a snapshot."""
        return (
            db.query(Answer)
            .filter(
                Answer.snapshot_id == snapshot_id,
                Answer.question_id == question_id
            )
            .first()
        )

    @staticmethod
    def get_selected_for_annotation(
        db: Session,
        snapshot_id: int
    ) -> List[Answer]:
        """Get all answers selected for annotation in a snapshot."""
        return (
            db.query(Answer)
            .filter(
                Answer.snapshot_id == snapshot_id,
                Answer.is_selected_for_annotation == True
            )
            .all()
        )

    @staticmethod
    def update_annotation_selection(
        db: Session,
        answer_ids: List[int],
        is_selected: bool
    ) -> List[Answer]:
        """Update annotation selection status for multiple answers."""
        answers = db.query(Answer).filter(Answer.id.in_(answer_ids)).all()
        for answer in answers:
            answer.is_selected_for_annotation = is_selected
        db.commit()
        return answers

    @staticmethod
    def count_by_snapshot(db: Session, snapshot_id: int) -> int:
        """Count answers for a snapshot."""
        return db.query(Answer).filter(Answer.snapshot_id == snapshot_id).count()

    @staticmethod
    def get_with_scores_and_annotation(
        db: Session,
        snapshot_id: int
    ) -> List[Answer]:
        """
        Get all answers for a snapshot with their scores and annotations eagerly loaded.
        Each answer has 1 question, 1 annotation, and X judge scores. 
        Useful for displaying results with judge evaluations.
        """
        return (
            db.query(Answer)
            .options(
                joinedload(Answer.scores),
                joinedload(Answer.annotation),
                joinedload(Answer.question)
            )
            .filter(Answer.snapshot_id == snapshot_id)
            .all()
        )

    @staticmethod
    def delete(db: Session, answer_id: int) -> bool:
        """Delete an answer."""
        answer = db.query(Answer).filter(Answer.id == answer_id).first()
        if not answer:
            return False
        db.delete(answer)
        db.commit()
        return True
