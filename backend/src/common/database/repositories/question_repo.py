"""
Repository for Question database operations.
"""

from typing import List, Optional
from sqlalchemy import and_, not_, exists, func
from sqlalchemy.orm import Session, joinedload

from src.common.database.models import Question, QAJob, Answer, AnswerScore, StatusEnum


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
        db.flush()
        db.commit()
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
        query = (
            db.query(Question)
            .options(joinedload(Question.persona))
            .filter(Question.persona_id == persona_id)
            .order_by(Question.updated_at.desc(), Question.id.desc())
        )
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
        query = (
            db.query(Question)
            .options(joinedload(Question.persona))
            .filter(Question.target_id == target_id)
            .order_by(Question.updated_at.desc(), Question.id.desc())
        )
        if status:
            query = query.filter(Question.status == status)
        return query.offset(skip).limit(limit).all()

    @staticmethod
    def count_by_target(
        db: Session,
        target_id: int,
        status: Optional[StatusEnum] = None,
    ) -> int:
        """Count questions for a target, optionally filtered by status."""
        query = db.query(func.count(Question.id)).filter(Question.target_id == target_id)
        if status:
            query = query.filter(Question.status == status)
        return query.scalar() or 0

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

    @staticmethod
    def get_approved_questions_without_answers(
        db: Session,
        target_id: int,
        snapshot_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[Question]:
        """
        Get approved questions that don't have answers for a specific snapshot.

        Args:
            db: Database session
            target_id: Target ID to filter questions
            snapshot_id: Snapshot ID to check for answers
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return

        Returns:
            List of approved questions without answers for the given snapshot
        """
        answer_exists = exists().where(
            and_(
                Answer.question_id == Question.id,
                Answer.snapshot_id == snapshot_id,
            )
        )

        return (
            db.query(Question)
            .options(joinedload(Question.persona))
            .filter(
                Question.target_id == target_id,
                Question.status == StatusEnum.approved,
                not_(answer_exists)
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def count_approved_questions_without_answers(
        db: Session,
        target_id: int,
        snapshot_id: int,
    ) -> int:
        """Count approved questions that do not yet have answers for a snapshot."""
        answer_exists = exists().where(
            and_(
                Answer.question_id == Question.id,
                Answer.snapshot_id == snapshot_id,
            )
        )

        return (
            db.query(func.count(Question.id))
            .filter(
                Question.target_id == target_id,
                Question.status == StatusEnum.approved,
                not_(answer_exists),
            )
            .scalar()
        ) or 0

    @staticmethod
    def get_approved_questions_without_scores(
        db: Session,
        target_id: int,
        snapshot_id: int,
        judge_id: int,
        rubric_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Question]:
        """Get approved questions that have answers but no scores for a snapshot/judge pair.

        When rubric_id is provided, checks a rubric-scoped AnswerScore row; otherwise checks any AnswerScore for the judge.
        """
        q = (
            db.query(Question)
            .options(joinedload(Question.persona))
            .join(Answer, and_(
                Answer.question_id == Question.id,
                Answer.snapshot_id == snapshot_id
            ))
        )
        join_conditions = [
            AnswerScore.answer_id == Answer.id,
            AnswerScore.judge_id == judge_id,
        ]
        if rubric_id is not None:
            join_conditions.append(AnswerScore.rubric_id == rubric_id)
        q = q.outerjoin(AnswerScore, and_(*join_conditions)).filter(
            Question.target_id == target_id,
            Question.status == StatusEnum.approved,
            AnswerScore.id.is_(None),
        )
        return q.offset(skip).limit(limit).all()

    @staticmethod
    def count_approved_questions_without_scores(
        db: Session,
        target_id: int,
        snapshot_id: int,
        judge_id: int,
        rubric_id: Optional[int] = None,
    ) -> int:
        """Count approved questions that have answers but no score for a snapshot/judge pair.

        When rubric_id is provided, counts missing rubric-scoped AnswerScore rows; otherwise any AnswerScore for the judge.
        """
        q = (
            db.query(func.count(Question.id))
            .select_from(Question)
            .join(Answer, and_(
                Answer.question_id == Question.id,
                Answer.snapshot_id == snapshot_id
            ))
        )
        join_conditions = [
            AnswerScore.answer_id == Answer.id,
            AnswerScore.judge_id == judge_id,
        ]
        if rubric_id is not None:
            join_conditions.append(AnswerScore.rubric_id == rubric_id)
        q = q.outerjoin(AnswerScore, and_(*join_conditions)).filter(
            Question.target_id == target_id,
            Question.status == StatusEnum.approved,
            AnswerScore.id.is_(None),
        )
        return q.scalar() or 0

    @staticmethod
    def has_approved_question_without_score(
        db: Session,
        question_id: int,
        target_id: int,
        snapshot_id: int,
        judge_id: int,
        rubric_id: Optional[int] = None,
    ) -> bool:
        """Return True if the specific approved question still lacks a score for this judge.

        When rubric_id is provided, checks a rubric-scoped AnswerScore row; otherwise checks any AnswerScore for the judge.
        """
        q = (
            db.query(Question.id)
            .join(Answer, and_(
                Answer.question_id == Question.id,
                Answer.snapshot_id == snapshot_id
            ))
        )
        join_conditions = [
            AnswerScore.answer_id == Answer.id,
            AnswerScore.judge_id == judge_id,
        ]
        if rubric_id is not None:
            join_conditions.append(AnswerScore.rubric_id == rubric_id)
        q = q.outerjoin(AnswerScore, and_(*join_conditions)).filter(
            Question.id == question_id,
            Question.target_id == target_id,
            Question.status == StatusEnum.approved,
            AnswerScore.id.is_(None),
        )
        return q.first() is not None
