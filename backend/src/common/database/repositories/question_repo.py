"""
Repository for Question database operations.
"""

from typing import List, Optional
from sqlalchemy.orm import Session, joinedload

from src.common.database.models import Question, StatusEnum


class QuestionRepository:
    """Repository for Question CRUD operations."""

    @staticmethod
    def create(db: Session, question_data: dict) -> Question:
        """Create a new question."""
        question = Question(**question_data)
        db.add(question)
        db.commit()
        db.refresh(question)
        return question

    @staticmethod
    def create_many(db: Session, questions_data: List[dict]) -> List[Question]:
        """Create multiple questions."""
        questions = [Question(**data) for data in questions_data]
        db.add_all(questions)
        db.commit()
        for question in questions:
            db.refresh(question)
        return questions

    @staticmethod
    def get_by_id(db: Session, question_id: int) -> Optional[Question]:
        """Get question by ID."""
        return db.query(Question).filter(Question.id == question_id).first()

    @staticmethod
    def get_by_persona(
        db: Session,
        persona_id: int,
        status: Optional[StatusEnum] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Question]:
        """Get questions for a persona, optionally filtered by status."""
        query = db.query(Question).options(joinedload(Question.persona)).filter(Question.persona_id == persona_id)
        if status:
            query = query.filter(Question.status == status)
        return query.offset(skip).limit(limit).all()

    @staticmethod
    def get_by_target(
        db: Session,
        target_id: int,
        status: Optional[StatusEnum] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Question]:
        """Get questions for a target, optionally filtered by status."""
        query = db.query(Question).options(joinedload(Question.persona)).filter(Question.target_id == target_id)
        if status:
            query = query.filter(Question.status == status)
        return query.offset(skip).limit(limit).all()

    @staticmethod
    def get_by_job(db: Session, job_id: int) -> List[Question]:
        """Get all questions from a specific job."""
        return db.query(Question).filter(Question.job_id == job_id).all()

    @staticmethod
    def update(db: Session, question_id: int, question_data: dict) -> Optional[Question]:
        """Update a question."""
        question = db.query(Question).filter(Question.id == question_id).first()
        if not question:
            return None

        for key, value in question_data.items():
            if value is not None:
                setattr(question, key, value)

        # Mark as edited if text changed
        if 'text' in question_data:
            question.status = StatusEnum.edited

        db.commit()
        db.refresh(question)
        return question

    @staticmethod
    def approve(db: Session, question_id: int) -> Optional[Question]:
        """Approve a question."""
        question = db.query(Question).filter(Question.id == question_id).first()
        if not question:
            return None

        question.status = StatusEnum.approved
        db.commit()
        db.refresh(question)
        return question

    @staticmethod
    def reject(db: Session, question_id: int) -> Optional[Question]:
        """Reject a question."""
        question = db.query(Question).filter(Question.id == question_id).first()
        if not question:
            return None

        question.status = StatusEnum.rejected
        db.commit()
        db.refresh(question)
        return question

    @staticmethod
    def bulk_approve(db: Session, question_ids: List[int]) -> List[Question]:
        """Approve multiple questions."""
        questions = db.query(Question).filter(Question.id.in_(question_ids)).all()
        for question in questions:
            question.status = StatusEnum.approved
        db.commit()
        return questions

    @staticmethod
    def get_approved_by_target(db: Session, target_id: int) -> List[Question]:
        """Get all approved questions for a target."""
        return (
            db.query(Question)
            .filter(
                Question.target_id == target_id,
                Question.status == StatusEnum.approved
            )
            .all()
        )
