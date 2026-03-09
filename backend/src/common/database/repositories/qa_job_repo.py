"""
Repository for QAJob database operations.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.common.database.models import QAJob, JobStatusEnum, QAJobStageEnum


class QAJobRepository:
    """Repository for QAJob CRUD operations."""

    @staticmethod
    def create(db: Session, qa_job_data: dict) -> QAJob:
        """Create a new QA job."""
        qa_job = QAJob(**qa_job_data)
        db.add(qa_job)
        db.commit()
        db.refresh(qa_job)
        return qa_job

    @staticmethod
    def create_many(db: Session, qa_jobs_data: List[dict]) -> List[QAJob]:
        """Create multiple QA jobs."""
        qa_jobs = [QAJob(**data) for data in qa_jobs_data]
        db.add_all(qa_jobs)
        db.flush()
        db.commit()
        return qa_jobs

    @staticmethod
    def get_by_id(db: Session, qa_job_id: int) -> Optional[QAJob]:
        """Get QA job by ID."""
        return db.query(QAJob).filter(QAJob.id == qa_job_id).first()

    @staticmethod
    def get_by_snapshot(
        db: Session,
        snapshot_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[QAJob]:
        """Get all QA jobs for a snapshot with pagination."""
        return (
            db.query(QAJob)
            .filter(QAJob.snapshot_id == snapshot_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_by_snapshot_and_judge(
        db: Session,
        snapshot_id: int,
        judge_id: int
    ) -> List[QAJob]:
        """Get all QA jobs for a specific snapshot and judge combination."""
        return (
            db.query(QAJob)
            .filter(
                QAJob.snapshot_id == snapshot_id,
                QAJob.judge_id == judge_id
            )
            .all()
        )

    @staticmethod
    def get_by_snapshot_question_judge(
        db: Session,
        snapshot_id: int,
        question_id: int,
        judge_id: int
    ) -> Optional[QAJob]:
        """Get QA job for a specific snapshot, question, and judge combination."""
        return (
            db.query(QAJob)
            .filter(
                QAJob.snapshot_id == snapshot_id,
                QAJob.question_id == question_id,
                QAJob.judge_id == judge_id
            )
            .order_by(QAJob.updated_at.desc())
            .first()
        )

    @staticmethod
    def update_status(
        db: Session,
        qa_job_id: int,
        status: JobStatusEnum,
        stage: Optional[QAJobStageEnum] = None,
        answer_id: Optional[int] = None,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        total_cost: Optional[float] = None,
        error_message: Optional[str] = None
    ) -> Optional[QAJob]:
        """
        Update QA job status and optionally stage, answer_id, costs, and error_message.

        Args:
            db: Database session
            qa_job_id: QA job ID
            status: New status
            stage: Optional new stage
            answer_id: Optional answer ID to set
            prompt_tokens: Optional prompt tokens to add (accumulated)
            completion_tokens: Optional completion tokens to add (accumulated)
            total_cost: Optional total cost to add (accumulated)
            error_message: Optional error message when job fails

        Returns:
            Updated QAJob object or None if not found
        """
        qa_job = db.query(QAJob).filter(QAJob.id == qa_job_id).first()
        if not qa_job:
            return None

        qa_job.status = status
        if stage is not None:
            qa_job.stage = stage
        if answer_id is not None:
            qa_job.answer_id = answer_id
        if prompt_tokens is not None:
            qa_job.prompt_tokens += prompt_tokens
        if completion_tokens is not None:
            qa_job.completion_tokens += completion_tokens
        if total_cost is not None:
            qa_job.total_cost += total_cost
        if error_message is not None:
            qa_job.error_message = error_message

        db.commit()
        db.refresh(qa_job)
        return qa_job

    @staticmethod
    def get_running_jobs(db: Session, snapshot_id: int) -> List[QAJob]:
        """Get all running QA jobs for a snapshot."""
        return (
            db.query(QAJob)
            .filter(
                QAJob.snapshot_id == snapshot_id,
                QAJob.status == JobStatusEnum.running
            )
            .all()
        )

    @staticmethod
    def get_paused_jobs(db: Session, snapshot_id: int) -> List[QAJob]:
        """Get all paused QA jobs for a snapshot."""
        return (
            db.query(QAJob)
            .filter(
                QAJob.snapshot_id == snapshot_id,
                QAJob.status == JobStatusEnum.paused
            )
            .all()
        )

    @staticmethod
    def count_by_snapshot_and_status(
        db: Session,
        snapshot_id: int,
        status: JobStatusEnum
    ) -> int:
        """Count QA jobs by snapshot and status."""
        return (
            db.query(func.count(QAJob.id))
            .filter(
                QAJob.snapshot_id == snapshot_id,
                QAJob.status == status
            )
            .scalar()
        ) or 0

    @staticmethod
    def get_by_answer(db: Session, answer_id: int) -> Optional[QAJob]:
        """Get QA job for a specific answer."""
        return db.query(QAJob).filter(QAJob.answer_id == answer_id).first()

    @staticmethod
    def delete(db: Session, qa_job_id: int) -> bool:
        """Delete a QA job."""
        qa_job = db.query(QAJob).filter(QAJob.id == qa_job_id).first()
        if not qa_job:
            return False

        db.delete(qa_job)
        db.commit()
        return True
