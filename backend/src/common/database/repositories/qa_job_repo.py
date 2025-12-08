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
        db.commit()
        for qa_job in qa_jobs:
            db.refresh(qa_job)
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
    def update_status(
        db: Session,
        qa_job_id: int,
        status: JobStatusEnum,
        stage: Optional[QAJobStageEnum] = None
    ) -> Optional[QAJob]:
        """Update QA job status and optionally stage."""
        qa_job = db.query(QAJob).filter(QAJob.id == qa_job_id).first()
        if not qa_job:
            return None

        qa_job.status = status
        if stage is not None:
            qa_job.stage = stage

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
