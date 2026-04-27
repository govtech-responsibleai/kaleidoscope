"""API routes for QA Job management and execution."""

import asyncio
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from src.common.database.connection import get_db
from src.common.database.models import JobStatusEnum
from src.common.database.repositories import (
    QAJobRepository, SnapshotRepository, JudgeRepository, TargetRubricRepository, QuestionRepository
)
from src.common.database.repositories.answer_score_repo import AnswerScoreRepository
from src.common.models import (
    QAJobPauseRequest,
    QAJobResponse,
    QAJobDetailResponse,
    QARubricScore,
    QARubricStatus,
    RubricVerdictState,
    UnifiedQAJobStart,
)
from src.common.models.answer_score import AnswerScoreResponse
from src.rubric.services.rubric_specs import (
    RubricSpecResolutionError,
    resolve_target_rubric_specs,
    validate_target_rubric_spec,
)
from src.scoring.services.qa_job_processor import (
    pause_qajobs_batch,
    create_all_jobs,
    run_qajobs_phased,
)

router = APIRouter()


def _build_verdict_status(
    db: Session,
    job,
    snapshot,
    judge,
    *,
    rubric_id: int,
    rubric_name: str,
    group: str,
    score_lookup,
    score_to_value,
    score_to_explanation,
    no_judge_msg: str = "No judge configured for this metric.",
) -> QARubricStatus:
    """Shared state machine for all rubric verdict resolution."""
    if not judge:
        return QARubricStatus(
            rubric_id=rubric_id,
            rubric_name=rubric_name,
            group=group,
            state=RubricVerdictState.no_judge_configured,
            message=no_judge_msg,
        )

    if not job.answer_id:
        return QARubricStatus(
            rubric_id=rubric_id,
            rubric_name=rubric_name,
            group=group,
            state=RubricVerdictState.awaiting_answer,
            message=f'Judge "{judge.name}" is still waiting for an answer to evaluate.',
            judge_id=judge.id,
            judge_name=judge.name,
        )

    score = score_lookup(job.answer_id, judge.id)
    if score:
        return QARubricStatus(
            rubric_id=rubric_id,
            rubric_name=rubric_name,
            group=group,
            state=RubricVerdictState.success,
            message=f'Judge "{judge.name}" produced a verdict.',
            judge_id=judge.id,
            judge_name=judge.name,
            score=QARubricScore(
                judge_id=judge.id,
                value=score_to_value(score),
                explanation=score_to_explanation(score),
                created_at=score.created_at,
            ),
        )

    if job.status == JobStatusEnum.failed:
        return QARubricStatus(
            rubric_id=rubric_id,
            rubric_name=rubric_name,
            group=group,
            state=RubricVerdictState.job_failed,
            message=job.error_message or "QA job failed before producing a verdict.",
            judge_id=judge.id,
            judge_name=judge.name,
        )

    is_pending = QuestionRepository.has_approved_question_without_score(
        db,
        question_id=job.question_id,
        target_id=snapshot.target_id if snapshot else 0,
        snapshot_id=job.snapshot_id,
        judge_id=judge.id,
        rubric_id=rubric_id,
    )
    state = RubricVerdictState.pending_evaluation if is_pending else RubricVerdictState.job_failed
    message = (
        f'Judge "{judge.name}" has not produced a score for this answer yet.'
        if is_pending
        else (job.error_message or f'QA job did not produce a score for judge "{judge.name}".')
    )
    return QARubricStatus(
        rubric_id=rubric_id,
        rubric_name=rubric_name,
        group=group,
        state=state,
        message=message,
        judge_id=judge.id,
        judge_name=judge.name,
    )


def _build_rubric_metric_status(
    db: Session,
    job,
    rubric_id: int,
    judge_id: Optional[int],
) -> QARubricStatus:
    snapshot = SnapshotRepository.get_by_id(db, job.snapshot_id)
    rubric = TargetRubricRepository.get_by_id(db, rubric_id)
    rubric_name = rubric.name if rubric else f"Rubric {rubric_id}"
    judge = JudgeRepository.get_by_id(db, judge_id) if judge_id else None
    if not rubric:
        judge = None
    return _build_verdict_status(
        db, job, snapshot, judge,
        rubric_id=rubric_id,
        rubric_name=rubric_name,
        group=rubric.group if rubric else "custom",
        score_lookup=lambda aid, jid: AnswerScoreRepository.get_by_answer_judge_rubric(
            db, answer_id=aid, rubric_id=rubric_id, judge_id=jid
        ),
        score_to_value=lambda s: s.overall_label,
        score_to_explanation=lambda s: s.explanation,
        no_judge_msg="No rubric judge configured for this rubric.",
    )


def _resolve_annotation_rubric_specs(db: Session, snapshot, job) -> list[dict[str, int]]:
    """Resolve the rubric/judge set shown on the annotation page.

    Prefer the target's current baseline rubric specs so annotation continues to
    show the canonical judge verdicts even after ad hoc judge runs. If the
    target cannot resolve to a full baseline set, fall back to the job's stored
    rubric specs.
    """
    if snapshot is None:
        return list(job.rubric_specs or [])

    try:
        return resolve_target_rubric_specs(db, snapshot.target_id)
    except RubricSpecResolutionError:
        return list(job.rubric_specs or [])


@router.post("/snapshots/{snapshot_id}/qa-jobs/start", response_model=List[QAJobResponse])
async def start_qa_jobs(
    snapshot_id: int,
    request: UnifiedQAJobStart,
    db: Session = Depends(get_db)
):
    """
    Start all QA jobs for rubrics defined in rubric_specs or resolved from target configuration.

    Creates ONE job per question with rubric_specs embedded. Processes in background:
    Phase 1 generates answers, Phase 2+3 scores all rubrics in parallel.
    """
    snapshot = SnapshotRepository.get_by_id(db, snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Snapshot {snapshot_id} not found")

    if request.snapshot_id != snapshot_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Snapshot ID mismatch between path and body")

    try:
        if request.rubric_specs is None:
            rubric_specs_dicts = resolve_target_rubric_specs(db, snapshot.target_id)
        else:
            rubric_specs_dicts = []
            for spec in request.rubric_specs:
                validated = validate_target_rubric_spec(
                    db,
                    snapshot.target_id,
                    spec.rubric_id,
                    spec.judge_id,
                )
                if validated is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Judge {spec.judge_id} is not valid for rubric {spec.rubric_id} on target {snapshot.target_id}",
                    )

                rubric = TargetRubricRepository.get_by_id(db, spec.rubric_id)
                if not rubric:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Rubric {spec.rubric_id} not found",
                    )
                rubric_options = rubric.options if rubric.options else []
                if len(rubric_options) < 2:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Rubric {spec.rubric_id} must have at least 2 options")
                if not rubric.best_option:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Rubric {spec.rubric_id} must have a best_option")
                option_names = [o.option if hasattr(o, "option") else o["option"] for o in rubric_options]
                if rubric.best_option not in option_names:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Rubric {spec.rubric_id} best_option does not match any option")

                rubric_specs_dicts.append(validated)
    except RubricSpecResolutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Each target rubric must have exactly one baseline judge.",
                "errors": exc.errors,
            },
        ) from exc

    try:
        jobs = create_all_jobs(
            db=db,
            snapshot_id=snapshot_id,
            question_ids=request.question_ids,
            rubric_specs=rubric_specs_dicts,
            job_ids=request.job_ids,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create jobs: {str(e)}")

    async def runner():
        def sync_work():
            asyncio.run(run_qajobs_phased(
                snapshot_id=snapshot_id,
                question_ids=request.question_ids,
                all_jobs=jobs,
                rubric_specs=rubric_specs_dicts,
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


@router.get("/answers/{answer_id}/rubric-scores", response_model=List[AnswerScoreResponse])
def get_rubric_scores_for_answer(
    answer_id: int,
    rubric_id: int,
    db: Session = Depends(get_db)
):
    """Get all rubric judge scores for a specific answer and rubric."""
    scores = AnswerScoreRepository.get_by_answer_and_rubric(db, answer_id, rubric_id)
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

    snapshot = SnapshotRepository.get_by_id(db, job.snapshot_id)
    rubric_statuses = []
    for spec in _resolve_annotation_rubric_specs(db, snapshot, job):
        rubric_statuses.append(
            _build_rubric_metric_status(
                db,
                job,
                rubric_id=spec.get("rubric_id"),
                judge_id=spec.get("judge_id"),
            )
        )

    job_response = QAJobResponse.model_validate(job, from_attributes=True)
    return QAJobDetailResponse(
        **job_response.model_dump(),
        rubric_statuses=rubric_statuses,
    )
