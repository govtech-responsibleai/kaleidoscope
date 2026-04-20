"""
API routes for QA Job management and execution.
"""

import asyncio
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
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
    RubricAnswerScoreResponse,
    UnifiedQAJobStart,
)
from src.scoring.services.qa_job_processor import (
    get_or_create_qajobs_batch,
    run_qajobs_batch,
    pause_qajobs_batch,
    create_all_jobs,
    run_qajobs_phased,
)

router = APIRouter()


@router.post("/snapshots/{snapshot_id}/qa-jobs/start", response_model=List[QAJobResponse])
async def start_qa_jobs(
    snapshot_id: int,
    request: QAJobStart,
    db: Session = Depends(get_db)
):
    """
    Start QA jobs in batch for multiple questions (legacy endpoint).
    """
    logging.info(f"Starting QA jobs for snapshot {snapshot_id}")

    snapshot = SnapshotRepository.get_by_id(db, snapshot_id)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {snapshot_id} not found"
        )

    if request.snapshot_id != snapshot_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Snapshot ID in request ({request.snapshot_id}) does not match path parameter ({snapshot_id})"
        )

    judge = JudgeRepository.get_by_id(db, request.judge_id)
    if not judge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Judge {request.judge_id} not found"
        )

    try:
        jobs = get_or_create_qajobs_batch(
            db=db,
            snapshot_id=snapshot_id,
            judge_id=request.judge_id,
            question_ids=request.question_ids,
            job_ids=request.job_ids
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create QA job records: {str(e)}"
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
                    job_ids=request.job_ids)
                )
            finally:
                db.close()
        await run_in_threadpool(sync_work)

    asyncio.create_task(runner())

    return jobs


@router.post("/snapshots/{snapshot_id}/qa-jobs/start-all", response_model=List[QAJobResponse])
async def start_all_qa_jobs(
    snapshot_id: int,
    request: UnifiedQAJobStart,
    db: Session = Depends(get_db)
):
    """
    Start all QA jobs (accuracy + rubric) in one call.

    Creates ONE job per question with rubric_specs embedded. Processes in background:
    Phase 1 generates answers, Phase 2+3 scores all rubrics in parallel.
    """
    snapshot = SnapshotRepository.get_by_id(db, snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Snapshot {snapshot_id} not found")

    if request.snapshot_id != snapshot_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Snapshot ID mismatch between path and body")

    judge = JudgeRepository.get_by_id(db, request.judge_id)
    if not judge:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Judge {request.judge_id} not found")

    # Validate each rubric spec
    rubric_specs_dicts = []
    for spec in (request.rubric_specs or []):
        rubric = TargetRubricRepository.get_by_id(db, spec.rubric_id)
        if not rubric:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rubric {spec.rubric_id} not found")
        rubric_options = rubric.options if rubric.options else []
        if len(rubric_options) < 2:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Rubric {spec.rubric_id} must have at least 2 options")
        if not rubric.best_option:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Rubric {spec.rubric_id} must have a best_option")
        option_names = [o.option if hasattr(o, "option") else o["option"] for o in rubric_options]
        if rubric.best_option not in option_names:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Rubric {spec.rubric_id} best_option does not match any option")

        rjudge = JudgeRepository.get_by_id(db, spec.judge_id)
        if not rjudge:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Judge {spec.judge_id} not found")

        rubric_specs_dicts.append({"rubric_id": spec.rubric_id, "judge_id": spec.judge_id})

    try:
        jobs = create_all_jobs(
            db=db,
            snapshot_id=snapshot_id,
            judge_id=request.judge_id,
            question_ids=request.question_ids,
            rubric_specs=rubric_specs_dicts or None,
            job_ids=request.job_ids,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create jobs: {str(e)}")

    async def runner():
        def sync_work():
            asyncio.run(run_qajobs_phased(
                snapshot_id=snapshot_id,
                judge_id=request.judge_id,
                question_ids=request.question_ids,
                all_jobs=jobs,
                rubric_specs=rubric_specs_dicts or None,
            ))
        await run_in_threadpool(sync_work)

    asyncio.create_task(runner())

    return jobs


@router.post("/qa-jobs/pause", response_model=List[QAJobResponse])
async def pause_qa_jobs(
    request: QAJobPauseRequest,
    db: Session = Depends(get_db)
):
    """Pause a list of running QA jobs."""
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
    """List all QA jobs for a snapshot."""
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
    """List all QA jobs for a specific snapshot and judge combination."""
    snapshot = SnapshotRepository.get_by_id(db, snapshot_id)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {snapshot_id} not found"
        )

    judge = JudgeRepository.get_by_id(db, judge_id)
    if not judge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Judge {judge_id} not found"
        )

    jobs = QAJobRepository.get_by_snapshot_and_judge(db, snapshot_id, judge_id)
    return jobs


@router.get("/answers/{answer_id}/rubric-scores", response_model=List[RubricAnswerScoreResponse])
def get_rubric_scores_for_answer(
    answer_id: int,
    rubric_id: int,
    db: Session = Depends(get_db)
):
    """Get all rubric judge scores for a specific answer and rubric."""
    scores = RubricAnswerScoreRepository.get_by_answer_and_rubric(db, answer_id, rubric_id)
    return scores


@router.get("/qa-jobs/{job_id}", response_model=QAJobDetailResponse)
def get_qa_job(
    job_id: int,
    db: Session = Depends(get_db)
):
    """Get QA job details with cost tracking."""
    job = QAJobRepository.get_by_id(db, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"QA job {job_id} not found"
        )
    return job
