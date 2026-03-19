"""
API routes for QA Job management and execution.
"""

import asyncio
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from src.common.database.connection import get_db, SessionLocal
from src.common.database.repositories import (
    QAJobRepository, SnapshotRepository, JudgeRepository, TargetRubricRepository
)
from src.common.database.repositories.rubric_answer_score_repo import RubricAnswerScoreRepository
from src.common.models import (
    QAJobStart,
    QAJobPauseRequest,
    QAJobResponse,
    QAJobDetailResponse,
    RubricQAJobStart,
    RubricAnswerScoreResponse,
)
from src.scoring.services.qa_job_processor import (
    get_or_create_qajobs_batch,
    run_qajobs_batch,
    pause_qajobs_batch
)

router = APIRouter()


@router.post("/snapshots/{snapshot_id}/qa-jobs/start", response_model=List[QAJobResponse])
async def start_qa_jobs(
    snapshot_id: int,
    request: QAJobStart,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Start QA jobs in batch for multiple questions.

    This endpoint creates QA job records and returns them immediately, then processes
    them in the background.

    Each job will be processed through:
    1. Generate answer from target chatbot
    2. Extract and check claims
    3. Score the answer using the specified judge

    Args:
        snapshot_id: Snapshot ID
        request: Request with judge_id, question_ids, and optional job_ids
        background_tasks: FastAPI background tasks for async execution
        db: Database session

    Returns:
        List of created/retrieved QA jobs (in RUNNING/STARTING state)

    Raises:
        HTTPException: If snapshot or judge not found, or validation fails
    """
    logging.info(f"Starting QA jobs for snapshot {snapshot_id}")

    # Verify snapshot exists
    snapshot = SnapshotRepository.get_by_id(db, snapshot_id)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {snapshot_id} not found"
        )

    # Verify snapshot_id in request matches path parameter
    if request.snapshot_id != snapshot_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Snapshot ID in request ({request.snapshot_id}) does not match path parameter ({snapshot_id})"
        )

    # Verify judge exists
    judge = JudgeRepository.get_by_id(db, request.judge_id)
    if not judge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Judge {request.judge_id} not found"
        )

    # Create or retrieve job records immediately (synchronous)
    try:
        jobs = get_or_create_qajobs_batch(
            db=db,
            snapshot_id=snapshot_id,
            judge_id=request.judge_id,
            question_ids=request.question_ids,
            job_ids=request.job_ids
        )
        logging.info(f"Created/retrieved {len(jobs)} job records")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create QA job records: {str(e)}"
        )

    # Use run_in_threadpool to run in a separate thread so no blocking occurs
    async def runner():
        def sync_work():
            db = SessionLocal()
            try:
                asyncio.run(run_qajobs_batch(
                    db=db,
                    snapshot_id=snapshot_id,
                    judge_id=request.judge_id,
                    question_ids=request.question_ids,
                    job_ids=request.job_ids)
                )
            finally:
                db.close()
        await run_in_threadpool(sync_work)

    asyncio.create_task(runner())

    logging.info(f"Scheduled background processing for {len(jobs)} jobs")

    # Return immediately with job records
    return jobs   


@router.post("/qa-jobs/pause", response_model=List[QAJobResponse])
async def pause_qa_jobs(
    request: QAJobPauseRequest,
    db: Session = Depends(get_db)
):
    """
    Pause a list of running QA jobs.

    Args:
        request: Request with job_ids to pause
        db: Database session

    Returns:
        Updated list of QA jobs

    Raises:
        HTTPException: If job not found or not in running state
    """

    # Pause batch QA jobs
    try:
        jobs = await pause_qajobs_batch(
            db=db,
            job_ids=request.job_ids,
        )
        return jobs
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to pause QA jobs: {str(e)}"
        )   

@router.get("/snapshots/{snapshot_id}/qa-jobs", response_model=List[QAJobResponse])
def list_qa_jobs(
    snapshot_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    List all QA jobs for a snapshot.

    Args:
        snapshot_id: Snapshot ID
        skip: Pagination offset
        limit: Pagination limit
        db: Database session

    Returns:
        List of QA jobs

    Raises:
        HTTPException: If snapshot not found
    """
    # Verify snapshot exists
    snapshot = SnapshotRepository.get_by_id(db, snapshot_id)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {snapshot_id} not found"
        )

    jobs = QAJobRepository.get_by_snapshot(db, snapshot_id, skip, limit)
    return jobs


@router.get("/snapshots/{snapshot_id}/judges/{judge_id}/qa-jobs", response_model=List[QAJobResponse])
def list_qa_jobs_by_judge(
    snapshot_id: int,
    judge_id: int,
    db: Session = Depends(get_db)
):
    """
    List all QA jobs for a specific snapshot and judge combination.

    Args:
        snapshot_id: Snapshot ID
        judge_id: Judge ID
        db: Database session

    Returns:
        List of QA jobs for the judge

    Raises:
        HTTPException: If snapshot or judge not found
    """
    # Verify snapshot exists
    snapshot = SnapshotRepository.get_by_id(db, snapshot_id)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {snapshot_id} not found"
        )

    # Verify judge exists
    judge = JudgeRepository.get_by_id(db, judge_id)
    if not judge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Judge {judge_id} not found"
        )

    jobs = QAJobRepository.get_by_snapshot_and_judge(db, snapshot_id, judge_id)
    return jobs


@router.post("/snapshots/{snapshot_id}/rubric-qa-jobs/start", response_model=List[QAJobResponse])
async def start_rubric_qa_jobs(
    snapshot_id: int,
    request: RubricQAJobStart,
    db: Session = Depends(get_db)
):
    """
    Start rubric QA jobs for a batch of questions.

    Creates QAJob records with rubric_id set and processes them in the background.
    The pipeline skips claim extraction (answer → rubric score directly).
    """
    snapshot = SnapshotRepository.get_by_id(db, snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Snapshot {snapshot_id} not found")

    judge = JudgeRepository.get_by_id(db, request.judge_id)
    if not judge:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Judge {request.judge_id} not found")

    rubric = TargetRubricRepository.get_by_id(db, request.rubric_id)
    if not rubric:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rubric {request.rubric_id} not found")

    # Validate rubric completeness before starting scoring
    rubric_options = rubric.options if rubric.options else []
    if len(rubric_options) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rubric must have at least 2 options to run scoring")
    if not rubric.best_option:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rubric must have a best_option selected to run scoring")
    option_names = [o.option if hasattr(o, "option") else o["option"] for o in rubric_options]
    if rubric.best_option not in option_names:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rubric best_option does not match any option")

    try:
        jobs = get_or_create_qajobs_batch(
            db=db,
            snapshot_id=snapshot_id,
            judge_id=request.judge_id,
            question_ids=request.question_ids,
            rubric_id=request.rubric_id,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create rubric QA job records: {str(e)}"
        )

    async def runner():
        def sync_work():
            db = SessionLocal()
            try:
                asyncio.run(run_qajobs_batch(
                    db=db,
                    snapshot_id=snapshot_id,
                    judge_id=request.judge_id,
                    question_ids=request.question_ids,
                    rubric_id=request.rubric_id,
                ))
            finally:
                db.close()
        await run_in_threadpool(sync_work)

    asyncio.create_task(runner())

    return jobs


@router.get("/answers/{answer_id}/rubric-scores", response_model=List[RubricAnswerScoreResponse])
def get_rubric_scores_for_answer(
    answer_id: int,
    rubric_id: int,
    db: Session = Depends(get_db)
):
    """
    Get all rubric judge scores for a specific answer and rubric.
    """
    scores = RubricAnswerScoreRepository.get_by_answer_and_rubric(db, answer_id, rubric_id)
    return scores


@router.get("/qa-jobs/{job_id}", response_model=QAJobDetailResponse)
def get_qa_job(
    job_id: int,
    db: Session = Depends(get_db)
):
    """
    Get QA job details with cost tracking.

    Args:
        job_id: QA job ID
        db: Database session

    Returns:
        QA job details including token counts and costs

    Raises:
        HTTPException: If job not found
    """
    job = QAJobRepository.get_by_id(db, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"QA job {job_id} not found"
        )
    return job
