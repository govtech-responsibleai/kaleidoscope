"""
API routes for Job management and generation endpoints.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.common.database.connection import get_db
from src.common.config import get_settings
from src.common.database.repositories import (
    JobRepository,
    TargetRepository,
    PersonaRepository,
    QuestionRepository
)
from src.common.models import (
    JobCreate,
    JobResponse,
    PersonaResponse,
    QuestionResponse
)
from src.common.database.models import JobTypeEnum
from src.query_generation.services import generate_personas_for_job, generate_questions_for_job

router = APIRouter()
logger = logging.getLogger(__name__)


def run_question_generation_background(job_id: int, persona_ids: Optional[List[int]] = None):
    """
    Background task for running question generation asynchronously.

    Args:
        job_id: Job ID for the generation task
        persona_ids: Optional list of persona IDs to generate for
    """
    # Create a new database session for the background task
    from src.common.database.connection import SessionLocal
    db = SessionLocal()

    try:
        generate_questions_for_job(db, job_id, persona_ids=persona_ids)
        logger.info(f"Background task completed question generation for job {job_id}")
    except Exception as e:
        logger.error(f"Background question generation failed for job {job_id}: {e}", exc_info=True)
        # Error handling is done inside generate_questions_for_job (updates job status to failed)
    finally:
        db.close()


@router.post(
    "/jobs/personas",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED
)
def create_persona_generation_job(
    job_request: JobCreate,
    db: Session = Depends(get_db)
):
    """
    Create a persona generation job for a target.

    Creates a new generation job and runs persona generation synchronously.

    Args:
        job_request: Generation job configuration (includes target_id)
        db: Database session

    Returns:
        Completed job with generated personas

    Raises:
        HTTPException: If target not found or generation fails
    """
    # Verify target exists
    target = TargetRepository.get_by_id(db, job_request.target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target {job_request.target_id} not found"
        )

    # Create job
    settings = get_settings()
    job_data = {
        "target_id": job_request.target_id,
        "type": JobTypeEnum.persona_generation,
        "count_requested": job_request.count_requested,
        "model_used": job_request.model_used or settings.default_llm_model,
        "status": "running"
    }
    job = JobRepository.create(db, job_data)

    # Store job_id before generation (in case of DB rollback)
    job_id = job.id

    # Run persona generation synchronously
    try:
        generate_personas_for_job(db, job_id)
        logger.info(f"Completed persona generation for job {job_id}")
    except Exception as e:
        logger.error(f"Persona generation failed for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Persona generation failed: {str(e)}"
        )

    # Refresh job to get updated status
    db.refresh(job)
    return job


@router.post(
    "/jobs/questions",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED
)
def create_question_generation_job_for_target(
    job_request: JobCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Create a question generation job for personas in a target.

    Runs generation asynchronously in the background. Returns immediately with status="running".
    Use GET /jobs/{id} to check completion status.

    If persona_ids is provided in the body, generates questions for those specific personas.
    If persona_ids is not provided, generates questions for all approved personas.

    Args:
        job_request: Generation job configuration (includes target_id, can include persona_ids)
        background_tasks: FastAPI background tasks
        db: Database session

    Returns:
        Created job with status="running"

    Raises:
        HTTPException: If target not found, no personas available, or invalid persona_ids
    """
    # Verify target exists
    target = TargetRepository.get_by_id(db, job_request.target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target {job_request.target_id} not found"
        )

    # Validate persona IDs if provided
    if job_request.persona_ids:
        for persona_id in job_request.persona_ids:
            persona = PersonaRepository.get_by_id(db, persona_id)
            if not persona:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Persona {persona_id} not found"
                )
            if persona.target_id != job_request.target_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Persona {persona_id} does not belong to target {job_request.target_id}"
                )
    else:
        # Check if there are approved personas when no specific IDs provided
        approved_personas = PersonaRepository.get_approved_by_target(db, job_request.target_id)
        if not approved_personas:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Target {job_request.target_id} has no approved personas"
            )

    # Create job
    settings = get_settings()
    job_data = {
        "target_id": job_request.target_id,
        "type": JobTypeEnum.question_generation,
        "persona_id": None,  # Multiple personas
        "count_requested": job_request.count_requested,
        "model_used": job_request.model_used or settings.default_llm_model,
        "status": "running"
    }
    job = JobRepository.create(db, job_data)

    # Run question generation asynchronously in background
    background_tasks.add_task(
        run_question_generation_background,
        job.id,
        job_request.persona_ids
    )

    logger.info(f"Created question generation job {job.id}, running in background")

    # Return immediately with status="running"
    return job


@router.get("/jobs", response_model=List[JobResponse])
def list_jobs(
    target_id: Optional[int] = None,
    job_type: Optional[JobTypeEnum] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    List all jobs, optionally filtered by target_id and/or job_type.

    Args:
        target_id: Optional target ID to filter by
        job_type: Optional filter by job type
        skip: Pagination offset
        limit: Pagination limit
        db: Database session

    Returns:
        List of jobs
    """
    # Verify target exists if target_id is provided
    if target_id is not None:
        target = TargetRepository.get_by_id(db, target_id)
        if not target:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Target {target_id} not found"
            )

    jobs = JobRepository.get_all(db, target_id, job_type, skip, limit)
    return jobs


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(
    job_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific job by ID.

    Args:
        job_id: Job ID
        db: Database session

    Returns:
        Job details
    """
    job = JobRepository.get_by_id(db, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )
    return job


@router.get("/jobs/{job_id}/personas", response_model=List[PersonaResponse])
def get_personas_from_job(
    job_id: int,
    db: Session = Depends(get_db)
):
    """
    Get all personas generated by a specific job.

    Args:
        job_id: Job ID
        db: Database session

    Returns:
        List of personas from this job
    """
    job = JobRepository.get_by_id(db, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )

    if job.type != JobTypeEnum.persona_generation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job {job_id} is not a persona generation job"
        )

    personas = PersonaRepository.get_by_job(db, job_id)
    return personas


@router.get("/jobs/{job_id}/questions", response_model=List[QuestionResponse])
def get_questions_from_job(
    job_id: int,
    db: Session = Depends(get_db)
):
    """
    Get all questions generated by a specific job.

    Args:
        job_id: Job ID
        db: Database session

    Returns:
        List of questions from this job
    """
    job = JobRepository.get_by_id(db, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )

    if job.type != JobTypeEnum.question_generation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job {job_id} is not a question generation job"
        )

    questions = QuestionRepository.get_by_job(db, job_id)
    return questions
