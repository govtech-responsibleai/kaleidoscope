"""
Repository for Job database operations.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.common.database.models import Job, Persona, Question, JobTypeEnum, JobStatusEnum


class JobRepository:
    """Repository for Job CRUD operations."""

    @staticmethod
    def create(db: Session, job_data: dict) -> Job:
        """Create a new job."""
        job = Job(**job_data)
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def get_by_id(db: Session, job_id: int) -> Optional[Job]:
        """Get job by ID."""
        return db.query(Job).filter(Job.id == job_id).first()

    @staticmethod
    def get_all(
        db: Session,
        target_id: Optional[int] = None,
        job_type: Optional[JobTypeEnum] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Job]:
        """Get all jobs, optionally filtered by target_id and/or type."""
        query = db.query(Job)
        if target_id is not None:
            query = query.filter(Job.target_id == target_id)
        if job_type:
            query = query.filter(Job.type == job_type)
        return query.order_by(Job.created_at.desc()).offset(skip).limit(limit).all()

    @staticmethod
    def get_by_target(
        db: Session,
        target_id: int,
        job_type: Optional[JobTypeEnum] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Job]:
        """Get jobs for a target, optionally filtered by type."""
        query = db.query(Job).filter(Job.target_id == target_id)
        if job_type:
            query = query.filter(Job.type == job_type)
        return query.order_by(Job.created_at.desc()).offset(skip).limit(limit).all()

    @staticmethod
    def update_status(
        db: Session,
        job_id: int,
        status: JobStatusEnum,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        total_cost: Optional[float] = None
    ) -> Optional[Job]:
        """Update job status and optionally token counts and cost."""
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return None

        job.status = status
        if prompt_tokens is not None:
            job.prompt_tokens = prompt_tokens
        if completion_tokens is not None:
            job.completion_tokens = completion_tokens
        if total_cost is not None:
            job.total_cost = total_cost

        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def get_stats(db: Session, job_id: int) -> dict:
        """Get statistics for a job."""
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return {}

        if job.type == JobTypeEnum.persona_generation:
            # Get persona counts by status
            persona_counts = (
                db.query(Persona.status, func.count(Persona.id))
                .filter(Persona.job_id == job_id)
                .group_by(Persona.status)
                .all()
            )
            by_status = {status.value: count for status, count in persona_counts}
            total_generated = sum(by_status.values())
        else:  # question_generation
            # Get question counts by status
            question_counts = (
                db.query(Question.status, func.count(Question.id))
                .filter(Question.job_id == job_id)
                .group_by(Question.status)
                .all()
            )
            by_status = {status.value: count for status, count in question_counts}
            total_generated = sum(by_status.values())

        return {
            "total_generated": total_generated,
            "by_status": by_status,
            "prompt_tokens": job.prompt_tokens,
            "completion_tokens": job.completion_tokens,
            "total_cost": float(job.total_cost)
        }
