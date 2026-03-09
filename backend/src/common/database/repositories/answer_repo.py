"""
Repository for Answer database operations.
"""

from typing import List, Optional, TYPE_CHECKING
from sqlalchemy.orm import Session, joinedload

from src.common.database.models import Answer
from src.common.models.answer import AnswerSelection


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
    def get_by_ids(db: Session, answer_ids: List[int]) -> List[Answer]:
        """Get multiple answers by IDs."""
        if not answer_ids:
            return []
        return db.query(Answer).filter(Answer.id.in_(answer_ids)).all()

    @staticmethod
    def get_by_question(db: Session, question_id: int) -> List[Answer]:
        """Get all answers for a question."""
        return db.query(Answer).filter(Answer.question_id == question_id).all()

    @staticmethod
    def get_by_snapshot(
        db: Session,
        snapshot_id: int,
        skip: int = 0,
        limit: int = 100,
        eager_load: bool = False
    ) -> List[Answer]:
        """Get answers for a snapshot with pagination.

        Args:
            db: Database session
            snapshot_id: Snapshot ID to filter by
            skip: Pagination offset
            limit: Pagination limit
            eager_load: If True, eagerly load question and annotation relationships

        Returns:
            List of Answer objects
        """
        query = db.query(Answer).filter(Answer.snapshot_id == snapshot_id)
        if eager_load:
            query = query.options(
                joinedload(Answer.question),
                joinedload(Answer.annotation)
            )
        return query.order_by(Answer.id).offset(skip).limit(limit).all()

    @staticmethod
    def get_by_question_and_snapshot(
        db: Session,
        question_id: int,
        snapshot_id: int
    ) -> Optional[Answer]:
        """Get most recent answer for a specific question in a snapshot."""
        return (
            db.query(Answer)
            .filter(
                Answer.snapshot_id == snapshot_id,
                Answer.question_id == question_id
            )
            .order_by(Answer.created_at.desc())
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
    def update(db: Session, answer_id: int, answer_data: dict) -> Optional[Answer]:
        """Update an answer."""
        answer = db.query(Answer).filter(Answer.id == answer_id).first()
        if not answer:
            return None

        for key, value in answer_data.items():
            if value is not None:
                setattr(answer, key, value)

        db.commit()
        db.refresh(answer)
        return answer

    @staticmethod
    def update_annotation_selection(
        db: Session,
        selections: List[AnswerSelection]
    ) -> List[Answer]:
        """
        Update annotation selection with individual values per answer.

        Args:
            db: Database session
            selections: List of AnswerSelection models with answer_id and is_selected

        Returns:
            List of updated Answer objects
        """
        selection_map = {selection.answer_id: selection.is_selected for selection in selections}
        answer_ids = list(selection_map.keys())

        answers = db.query(Answer).filter(Answer.id.in_(answer_ids)).all()

        for answer in answers:
            answer.is_selected_for_annotation = selection_map[answer.id]

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
