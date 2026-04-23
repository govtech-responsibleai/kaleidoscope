"""
Service for orchestrating QA job pipeline (answer generation -> claim processing -> scoring).

Architecture: ONE QAJob per question. The single job orchestrates:
  Phase 1: Generate answer (call target API)
  Phase 2: Process claims (extract + checkworthiness)
  Phase 3: Score ALL rubrics in parallel (accuracy + custom rubrics)
"""

import asyncio
import logging
from typing import List, Optional
from sqlalchemy.orm import Session

from src.common.concurrency import gather_with_concurrency
from src.common.config import get_settings
from src.common.database.connection import SessionLocal
from src.common.database.models import QAJob, QAJobStageEnum, JobStatusEnum, QAJobTypeEnum
from src.common.database.repositories.qa_job_repo import QAJobRepository
from src.common.database.repositories.answer_repo import AnswerRepository
from src.common.database.repositories.answer_claim_repo import AnswerClaimRepository
from src.common.database.repositories.answer_claim_score_repo import AnswerClaimScoreRepository
from src.common.database.repositories.answer_score_repo import AnswerScoreRepository
from src.common.database.repositories.judge_repo import JudgeRepository
from src.common.database.repositories.target_rubric_repo import TargetRubricRepository
from src.query_generation.services.answer_generator import generate_answer_for_job
from src.scoring.services.claim_processor import extract_and_check_claims
from src.scoring.services.judge_scoring import AnswerJudge

logger = logging.getLogger(__name__)


def _claims_ready(claims) -> bool:
    return bool(claims) and all(claim.created_at != claim.checked_at for claim in claims)


def _is_rubric_score_complete(
    db: Session,
    answer_id: int,
    judge_id: int,
    rubric_id: int,
    claims=None,
    rubric=None,
) -> bool:
    """Return whether a rubric result is complete for the current answer state."""
    score = AnswerScoreRepository.get_by_answer_judge_rubric(db, answer_id, judge_id, rubric_id)
    if score is None:
        return False

    resolved_rubric = rubric or TargetRubricRepository.get_by_id(db, rubric_id)
    if resolved_rubric is None or resolved_rubric.scoring_mode != "claim_based":
        return True

    current_claims = claims if claims is not None else AnswerClaimRepository.get_by_answer(db, answer_id)
    if not _claims_ready(current_claims):
        return False

    checkworthy_count = sum(1 for claim in current_claims if claim.checkworthy)
    claim_scores = AnswerClaimScoreRepository.get_by_answer_score(db, score.id)
    return len(claim_scores) == checkworthy_count


def _job_needs_scoring(
    db: Session,
    job: QAJob,
    rubric_specs: Optional[List[dict]] = None,
) -> bool:
    if not job.answer_id:
        return True

    for spec in (rubric_specs or job.rubric_specs or []):
        if not _is_rubric_score_complete(
            db,
            job.answer_id,
            spec["judge_id"],
            spec["rubric_id"],
        ):
            return True

    return False


def _normalize_rubric_specs(
    rubric_specs: Optional[List[dict]],
) -> Optional[List[dict]]:
    """Deduplicate rubric specs by rubric_id while preserving the latest explicit selection."""
    normalized: dict[int, dict] = {}
    for spec in rubric_specs or []:
        normalized[spec["rubric_id"]] = {
            "rubric_id": spec["rubric_id"],
            "judge_id": spec["judge_id"],
        }
    return list(normalized.values()) or None


def _primary_judge_id(rubric_specs: Optional[List[dict]]) -> Optional[int]:
    if not rubric_specs:
        return None
    return rubric_specs[0]["judge_id"]


def _verify_expected_scores(
    db: Session,
    job_id: int,
    rubric_specs: Optional[List[dict]] = None,
) -> None:
    job = QAJobRepository.get_by_id(db, job_id)
    if not job:
        raise RuntimeError(f"QAJob {job_id} not found")
    if not job.answer_id:
        raise RuntimeError(f"QAJob {job_id} has no answer to score")

    expected_specs = rubric_specs or job.rubric_specs or []
    missing_specs: list[str] = []
    for spec in expected_specs:
        score = AnswerScoreRepository.get_by_answer_judge_rubric(
            db,
            job.answer_id,
            spec["judge_id"],
            spec["rubric_id"],
        )
        if score is None or not _is_rubric_score_complete(
            db,
            job.answer_id,
            spec["judge_id"],
            spec["rubric_id"],
        ):
            missing_specs.append(
                f"rubric {spec['rubric_id']} / judge {spec['judge_id']}"
            )

    if missing_specs:
        raise RuntimeError(
            "Missing persisted scores for scheduled rubric specs: "
            + ", ".join(missing_specs)
        )


# ---------------------------------------------------------------------------
# Single-job processor (used by the old /start endpoint and by the phased runner)
# ---------------------------------------------------------------------------

class QAJobProcessor:
    """Service for orchestrating QA job pipelines."""

    def __init__(self, db: Session, snapshot_id: int, question_id: int, judge_id: int):
        self.db = db
        self.snapshot_id = snapshot_id
        self.question_id = question_id
        self.judge_id = judge_id

    def _uses_claim_processing(self) -> bool:
        judge = JudgeRepository.get_by_id(self.db, self.judge_id)
        if judge is None or not judge.rubric_id:
            return False
        rubric = TargetRubricRepository.get_by_id(self.db, judge.rubric_id)
        return rubric is not None and rubric.scoring_mode == "claim_based"

    async def run(self, job_id: int) -> QAJob:
        logger.info(f"Processing QAJob {job_id}")

        job = QAJobRepository.get_by_id(self.db, job_id)
        if not job:
            raise ValueError(f"QAJob with id {job_id} not found")

        if job.status == JobStatusEnum.completed:
            logger.info(f"Job {job_id} is already completed, skipping")
            return job

        if job.status != JobStatusEnum.running:
            QAJobRepository.update_status(self.db, job_id, JobStatusEnum.running, job.stage)

        await self._run_pipeline(job)
        return job

    async def _run_pipeline(self, job: QAJob) -> None:
        stages = [
            (QAJobStageEnum.generating_answers, self._run_answer_generation),
            (QAJobStageEnum.processing_answers, self._run_claim_processing),
            (QAJobStageEnum.scoring_answers, self._run_scoring),
        ]
        if not self._uses_claim_processing():
            stages = [stage for stage in stages if stage[0] != QAJobStageEnum.processing_answers]

        start_idx = self._get_start_index(job)

        if start_idx >= len(stages):
            QAJobRepository.update_status(
                self.db, job.id, JobStatusEnum.completed, QAJobStageEnum.completed
            )
            return

        for stage_enum, stage_fn in stages[start_idx:]:
            job = QAJobRepository.get_by_id(self.db, job.id)
            if job.status == JobStatusEnum.paused:
                logger.info(f"Job {job.id} paused before {stage_enum.value}")
                return

            QAJobRepository.update_status(self.db, job.id, JobStatusEnum.running, stage_enum)
            try:
                await stage_fn(job)
            except Exception as e:
                logger.error(f"QAJob {job.id} failed during {stage_enum.value}: {e}")
                QAJobRepository.update_status(
                    self.db, job.id, JobStatusEnum.failed, stage_enum
                )
                return

            job = QAJobRepository.get_by_id(self.db, job.id)
            if job.status != JobStatusEnum.running:
                return

        QAJobRepository.update_status(
            self.db, job.id, JobStatusEnum.completed, QAJobStageEnum.completed
        )

    def _get_start_index(self, job: QAJob) -> int:
        answer = AnswerRepository.get_by_question_and_snapshot(
            self.db, self.question_id, self.snapshot_id
        )
        if not answer or not answer.answer_content:
            return 0

        if self._uses_claim_processing():
            claims = AnswerClaimRepository.get_by_answer(self.db, answer.id)
            if not claims:
                return 1

            all_checked = all(claim.created_at != claim.checked_at for claim in claims)
            if not all_checked:
                return 1

        judge = JudgeRepository.get_by_id(self.db, self.judge_id)
        rubric_id = judge.rubric_id if judge else None
        score_complete = (
            rubric_id is not None
            and _is_rubric_score_complete(
                self.db,
                answer.id,
                self.judge_id,
                rubric_id,
                claims=claims if self._uses_claim_processing() else None,
            )
        )
        if not score_complete:
            return 2 if self._uses_claim_processing() else 1

        return 3 if self._uses_claim_processing() else 2

    async def _run_answer_generation(self, job: QAJob) -> None:
        await generate_answer_for_job(self.db, job.id, self.question_id, self.snapshot_id)

    async def _run_claim_processing(self, job: QAJob) -> None:
        await extract_and_check_claims(self.db, job.id)

    async def _run_scoring(self, job: QAJob) -> None:
        judge = AnswerJudge(self.db, job.id, override_judge_id=self.judge_id)
        await judge.score()


async def run_qajob(
    db: Session,
    snapshot_id: int,
    question_id: int,
    judge_id: int,
    job_id: int,
) -> QAJob:
    processor = QAJobProcessor(db, snapshot_id, question_id, judge_id)
    return await processor.run(job_id)


async def pause_qajob(db: Session, job_id: int) -> QAJob:
    job = QAJobRepository.get_by_id(db, job_id)
    if not job:
        raise ValueError(f"QAJob with id {job_id} not found")

    if job.status != JobStatusEnum.running:
        raise ValueError(
            f"Cannot pause job {job_id}. Job must be running "
            f"(current status: {job.status.value})"
        )

    QAJobRepository.update_status(db, job_id, JobStatusEnum.paused, job.stage)
    logger.info(f"Paused QAJob {job_id} at stage {job.stage.value}")
    return job


# ---------------------------------------------------------------------------
# Batch helpers (old endpoint compatibility)
# ---------------------------------------------------------------------------

def get_or_create_qajobs_batch(
    db: Session,
    snapshot_id: int,
    judge_id: int,
    question_ids: List[int],
    job_ids: Optional[List[int]] = None,
) -> List[QAJob]:
    """Get or create ONE QA job per question."""
    jobs = []

    if job_ids is None:
        judge = JudgeRepository.get_by_id(db, judge_id)
        judge_rubric_id = judge.rubric_id if judge else None
        for qn_id in question_ids:
            existing_job = QAJobRepository.get_by_snapshot_and_question(
                db, snapshot_id, qn_id
            )

            if existing_job:
                needs_scoring = (
                    not existing_job.answer_id
                    or not _is_rubric_score_complete(
                        db,
                        existing_job.answer_id,
                        judge_id,
                        judge_rubric_id,
                    )
                )
                if existing_job.status == JobStatusEnum.completed and needs_scoring:
                    next_stage = QAJobStageEnum.scoring_answers if existing_job.answer_id else QAJobStageEnum.starting
                    QAJobRepository.update_status(
                        db,
                        existing_job.id,
                        JobStatusEnum.running,
                        next_stage,
                        error_message="",
                    )
                    db.refresh(existing_job)
                logger.info(f"Retrieved existing job {existing_job.id} with status={existing_job.status.value}")
                jobs.append(existing_job)
            else:
                answer = AnswerRepository.get_by_question_and_snapshot(db, qn_id, snapshot_id)
                job_data = {
                    "snapshot_id": snapshot_id,
                    "question_id": qn_id,
                    "judge_id": judge_id,
                    "type": QAJobTypeEnum.claim_scoring_full,
                    "status": JobStatusEnum.running,
                    "stage": QAJobStageEnum.starting,
                }
                if answer:
                    job_data["answer_id"] = answer.id

                job = QAJobRepository.create(db, job_data)
                logger.info(f"Created new QAJob {job.id} for question {qn_id}")
                jobs.append(job)
    else:
        for job_id in job_ids:
            job = QAJobRepository.get_by_id(db, job_id)
            if job:
                jobs.append(job)
            else:
                logger.warning(f"Job {job_id} not found, skipping")

    return jobs


async def _run_qajob_isolated(
    snapshot_id: int,
    question_id: int,
    judge_id: int,
    job_id: int,
) -> Optional[QAJob]:
    """Run a single QA job in its own DB session."""
    db = SessionLocal()
    try:
        return await run_qajob(db, snapshot_id, question_id, judge_id, job_id)
    finally:
        db.close()


async def run_qajobs_batch(
    db: Session,
    snapshot_id: int,
    judge_id: int,
    question_ids: List[int],
    job_ids: Optional[List[int]] = None,
) -> List[QAJob]:
    """Run QA jobs batch for multiple questions (legacy endpoint)."""
    qajobs = get_or_create_qajobs_batch(db, snapshot_id, judge_id, question_ids, job_ids)

    qn2qajob = {job.question_id: job.id for job in qajobs if job}

    settings = get_settings()
    jobs = await gather_with_concurrency(
        settings.batch_max_concurrent_jobs,
        *(
            _run_qajob_isolated(snapshot_id, qn_id, judge_id, qn2qajob[qn_id])
            for qn_id in question_ids
            if qn2qajob.get(qn_id) is not None
        )
    )

    logger.info(f"Processed {len(jobs)} QA jobs for snapshot {snapshot_id}, judge {judge_id}")
    return jobs


# ---------------------------------------------------------------------------
# Unified pipeline: ONE QAJob per question with parallel scoring
# ---------------------------------------------------------------------------

def create_all_jobs(
    db: Session,
    snapshot_id: int,
    question_ids: List[int],
    rubric_specs: Optional[List[dict]] = None,
    job_ids: Optional[List[int]] = None,
) -> List[QAJob]:
    """
    Create ONE QA job per question with rubric_specs embedded.

    When explicit rubric_specs are provided, they are treated as the full
    rubric plan for the affected jobs. Existing jobs are reconciled to that
    normalized set, and missing-score detection decides whether they need to
    resume scoring.

    Returns:
        List of QAJob records (one per question)
    """
    normalized_specs = _normalize_rubric_specs(rubric_specs)
    primary_judge_id = _primary_judge_id(normalized_specs)

    if job_ids:
        jobs = []
        for job_id in job_ids:
            job = QAJobRepository.get_by_id(db, job_id)
            if job:
                if primary_judge_id is not None and job.judge_id != primary_judge_id:
                    job.judge_id = primary_judge_id
                    db.commit()
                    db.refresh(job)
                if normalized_specs is not None and job.rubric_specs != normalized_specs:
                    job.rubric_specs = normalized_specs
                    db.commit()
                    db.refresh(job)
                next_stage = QAJobStageEnum.scoring_answers if job.answer_id else QAJobStageEnum.starting
                if job.status in (JobStatusEnum.paused, JobStatusEnum.failed):
                    QAJobRepository.update_status(
                        db, job_id, JobStatusEnum.running, next_stage, error_message=""
                    )
                    db.refresh(job)
                jobs.append(job)
            else:
                logger.warning(f"Job {job_id} not found, skipping")
        return jobs

    jobs = []
    for qn_id in question_ids:
        existing_job = QAJobRepository.get_by_snapshot_and_question(
            db, snapshot_id, qn_id
        )

        if existing_job:
            if primary_judge_id is not None and existing_job.judge_id != primary_judge_id:
                existing_job.judge_id = primary_judge_id
                db.commit()
                db.refresh(existing_job)
            if normalized_specs is not None and existing_job.rubric_specs != normalized_specs:
                existing_job.rubric_specs = normalized_specs
                db.commit()
                db.refresh(existing_job)
            if existing_job.status in (JobStatusEnum.paused, JobStatusEnum.failed) or (
                existing_job.status == JobStatusEnum.completed
                and _job_needs_scoring(db, existing_job, normalized_specs)
            ):
                next_stage = QAJobStageEnum.scoring_answers if existing_job.answer_id else QAJobStageEnum.starting
                QAJobRepository.update_status(
                    db,
                    existing_job.id,
                    JobStatusEnum.running,
                    next_stage,
                    error_message="",
                )
                db.refresh(existing_job)
            logger.info(f"Retrieved existing job {existing_job.id}")
            jobs.append(existing_job)
        else:
            answer = AnswerRepository.get_by_question_and_snapshot(db, qn_id, snapshot_id)
            job_data = {
                "snapshot_id": snapshot_id,
                "question_id": qn_id,
                "judge_id": primary_judge_id,
                "type": QAJobTypeEnum.claim_scoring_full,
                "status": JobStatusEnum.running,
                "stage": QAJobStageEnum.starting,
                "rubric_specs": normalized_specs,
            }
            if answer:
                job_data["answer_id"] = answer.id

            job = QAJobRepository.create(db, job_data)
            logger.info(f"Created QAJob {job.id} for question {qn_id}")
            jobs.append(job)

    return jobs


async def _generate_answer(
    snapshot_id: int,
    question_id: int,
    job_id: int,
) -> None:
    """Generate an answer for one question in its own DB session."""
    db = SessionLocal()
    try:
        await generate_answer_for_job(db, job_id, question_id, snapshot_id)
    finally:
        db.close()


async def _score_response_level(
    job_id: int,
    judge_id: int,
    rubric_id: int,
) -> dict:
    """
    Run a single rubric scoring in its own DB session.

    Returns cost summary dict from AnswerJudge.
    """
    db = SessionLocal()
    try:
        job = QAJobRepository.get_by_id(db, job_id)
        if job and job.answer_id:
            if _is_rubric_score_complete(db, job.answer_id, judge_id, rubric_id):
                logger.info(f"QAJob {job_id}: rubric {rubric_id} score already exists, skipping")
                return {"prompt_tokens": 0, "completion_tokens": 0, "total_cost": 0.0}

        judge = AnswerJudge(
            db, job_id,
            override_judge_id=judge_id,
            override_rubric_id=rubric_id,
            skip_job_update=True,
        )
        await judge.score(raise_on_error=True)

        job = QAJobRepository.get_by_id(db, job_id)
        if job and job.status == JobStatusEnum.failed:
            raise RuntimeError(job.error_message or f"Rubric scoring failed for rubric {rubric_id}")

        if not job or not job.answer_id:
            raise RuntimeError(f"QAJob {job_id} has no answer after rubric scoring")

        persisted = AnswerScoreRepository.get_by_answer_judge_rubric(
            db, job.answer_id, judge_id, rubric_id
        )
        if persisted is None:
            raise RuntimeError(f"Rubric {rubric_id} score was not persisted")
        return judge.cost_tracker.get_summary()
    finally:
        db.close()


async def _score_rubric_spec(
    job_id: int,
    judge_id: int,
    rubric_id: int,
) -> dict:
    """Run one scheduled rubric spec, including claim extraction when required."""
    db = SessionLocal()
    try:
        job = QAJobRepository.get_by_id(db, job_id)
        if not job:
            raise RuntimeError(f"QAJob {job_id} not found")
        if not job.answer_id:
            raise RuntimeError(f"QAJob {job_id} has no answer after generation")

        if _is_rubric_score_complete(db, job.answer_id, judge_id, rubric_id):
            logger.info(f"QAJob {job_id}: rubric {rubric_id} score already exists, skipping")
            return {"prompt_tokens": 0, "completion_tokens": 0, "total_cost": 0.0}

        rubric = TargetRubricRepository.get_by_id(db, rubric_id)
        if rubric is None:
            raise RuntimeError(f"Rubric {rubric_id} not found")

        existing_claims = AnswerClaimRepository.get_by_answer(db, job.answer_id)
        if rubric.scoring_mode == "claim_based":
            if _claims_ready(existing_claims):
                logger.info(f"QAJob {job_id}: checked claims already exist, skipping extraction")
            else:
                if existing_claims:
                    AnswerClaimRepository.delete_by_answer(db, job.answer_id)
                await extract_and_check_claims(db, job_id, raise_on_error=True)

                refreshed = QAJobRepository.get_by_id(db, job_id)
                if refreshed and refreshed.status == JobStatusEnum.failed:
                    raise RuntimeError(refreshed.error_message or f"Claim processing failed for rubric {rubric_id}")

        judge = AnswerJudge(
            db,
            job_id,
            override_judge_id=judge_id,
            override_rubric_id=rubric_id,
            skip_job_update=True,
        )
        await judge.score(raise_on_error=True)

        refreshed = QAJobRepository.get_by_id(db, job_id)
        if refreshed and refreshed.status == JobStatusEnum.failed:
            raise RuntimeError(refreshed.error_message or f"Rubric scoring failed for rubric {rubric_id}")

        if not _is_rubric_score_complete(
            db,
            job.answer_id,
            judge_id,
            rubric_id,
            rubric=rubric,
        ):
            raise RuntimeError(f"Rubric {rubric_id} score was not persisted completely")

        return judge.cost_tracker.get_summary()
    finally:
        db.close()

async def _run_job_phased(
    job_id: int,
    snapshot_id: int,
    question_id: int,
    rubric_specs: Optional[List[dict]],
) -> None:
    """
    Run the full pipeline for a single QAJob in phases.

    Phase 1: Generate answer
    Phase 2: Process claims (in accuracy scoring coroutine)
    Phase 3: Score ALL rubrics in parallel (accuracy + custom)
    """
    settings = get_settings()

    def _update_stage(stage: QAJobStageEnum) -> Optional[QAJob]:
        db = SessionLocal()
        try:
            fresh = QAJobRepository.get_by_id(db, job_id)
            if not fresh or fresh.status != JobStatusEnum.running:
                return fresh
            QAJobRepository.update_status(db, job_id, JobStatusEnum.running, stage)
            return fresh
        finally:
            db.close()

    def _check_paused() -> bool:
        db = SessionLocal()
        try:
            fresh = QAJobRepository.get_by_id(db, job_id)
            return fresh is not None and fresh.status == JobStatusEnum.paused
        finally:
            db.close()

    try:
        # --- Phase 1: Generate answer (skip if answer already exists) ---
        db_phase1 = SessionLocal()
        try:
            answer = AnswerRepository.get_by_question_and_snapshot(db_phase1, question_id, snapshot_id)
            if answer and answer.answer_content:
                logger.info(f"QAJob {job_id}: answer already exists (answer_id={answer.id}), skipping generation")
                job = QAJobRepository.get_by_id(db_phase1, job_id)
                if job and not job.answer_id:
                    QAJobRepository.update_status(
                        db_phase1, job_id, JobStatusEnum.running,
                        QAJobStageEnum.generating_answers, answer_id=answer.id
                    )
        finally:
            db_phase1.close()

        if not answer or not answer.answer_content:
            fresh = _update_stage(QAJobStageEnum.generating_answers)
            if not fresh or fresh.status != JobStatusEnum.running:
                return

            await _generate_answer(snapshot_id, question_id, job_id)

            db_link = SessionLocal()
            try:
                answer = AnswerRepository.get_by_question_and_snapshot(db_link, question_id, snapshot_id)
                if answer:
                    QAJobRepository.update_status(
                        db_link, job_id, JobStatusEnum.running,
                        QAJobStageEnum.generating_answers, answer_id=answer.id
                    )
            finally:
                db_link.close()

        if _check_paused():
            return

        # --- Phase 2+3: Scoring (claims + all rubrics in parallel) ---
        fresh = _update_stage(QAJobStageEnum.scoring_answers)
        if not fresh or fresh.status != JobStatusEnum.running:
            return

        score_coros = []
        for spec in (rubric_specs or []):
            score_coros.append(
                _score_rubric_spec(job_id, spec["judge_id"], spec["rubric_id"])
            )

        cost_summaries = await gather_with_concurrency(
            settings.batch_max_concurrent_scorers_per_job, *score_coros
        )

        if _check_paused():
            return

        db_verify = SessionLocal()
        try:
            finished = QAJobRepository.get_by_id(db_verify, job_id)
            if finished and finished.status == JobStatusEnum.failed:
                raise RuntimeError(finished.error_message or f"QAJob {job_id} failed during scoring")
            _verify_expected_scores(db_verify, job_id, rubric_specs)
        finally:
            db_verify.close()

        total_prompt = sum(s.get("prompt_tokens", 0) for s in cost_summaries)
        total_completion = sum(s.get("completion_tokens", 0) for s in cost_summaries)
        total_cost = sum(s.get("total_cost", 0.0) for s in cost_summaries)

        db_final = SessionLocal()
        try:
            QAJobRepository.update_status(
                db_final, job_id, JobStatusEnum.completed, QAJobStageEnum.completed,
                prompt_tokens=total_prompt,
                completion_tokens=total_completion,
                total_cost=total_cost,
            )
        finally:
            db_final.close()

        logger.info(f"QAJob {job_id} completed. Cost: ${total_cost:.4f}")

    except Exception as e:
        logger.error(f"QAJob {job_id} failed: {e}", exc_info=True)
        db_err = SessionLocal()
        try:
            current = QAJobRepository.get_by_id(db_err, job_id)
            if current and current.status == JobStatusEnum.paused:
                return
            QAJobRepository.update_status(
                db_err, job_id, JobStatusEnum.failed,
                error_message=str(e),
            )
        except Exception:
            pass
        finally:
            db_err.close()


async def run_qajobs_phased(
    snapshot_id: int,
    question_ids: List[int],
    all_jobs: List[QAJob],
    rubric_specs: Optional[List[dict]] = None,
) -> None:
    """
    Run the unified QA pipeline: one QAJob per question, each with parallel scoring.

    Args:
        snapshot_id: Snapshot ID
        judge_id: Accuracy judge ID
        all_jobs: Pre-created job records from create_all_jobs()
        rubric_specs: Optional list of {"rubric_id": int, "judge_id": int} dicts
    """
    settings = get_settings()
    concurrency = settings.batch_max_concurrent_jobs

    coros = []
    for job in all_jobs:
        if job.status in (JobStatusEnum.completed, JobStatusEnum.failed):
            continue
        coros.append(
            _run_job_phased(
                job.id, snapshot_id, job.question_id,
                job.rubric_specs or rubric_specs,
            )
        )

    if coros:
        await gather_with_concurrency(concurrency, *coros)

    logger.info(f"Phased pipeline complete for {len(all_jobs)} jobs")


async def pause_qajobs_batch(
    db: Session,
    job_ids: List[int],
) -> List[QAJob]:
    """
    Pause QA jobs batch. Only pauses running jobs; others are silently skipped.
    """
    running_ids = []
    for job_id in job_ids:
        job = QAJobRepository.get_by_id(db, job_id)
        if job and job.status == JobStatusEnum.running:
            running_ids.append(job_id)

    if not running_ids:
        logger.info("No running jobs to pause.")
        return []

    jobs = await asyncio.gather(*(pause_qajob(db, job_id) for job_id in running_ids))

    logger.info(f"Paused {len(jobs)} QA jobs.")
    return jobs
