"""
Service for orchestrating QA job pipeline (answer generation -> claim processing -> scoring).
"""

import asyncio
import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import BackgroundTasks

from src.common.database.models import QAJob, QAJobStageEnum, JobStatusEnum, QAJobTypeEnum
from src.common.database.repositories.qa_job_repo import QAJobRepository
from src.common.database.repositories.answer_repo import AnswerRepository
from src.common.database.repositories.answer_claim_repo import AnswerClaimRepository
from src.common.database.repositories.answer_score_repo import AnswerScoreRepository
from src.common.database.repositories.rubric_answer_score_repo import RubricAnswerScoreRepository
from src.query_generation.services.answer_generator import generate_answer_for_job
from src.scoring.services.claim_processor import extract_and_check_claims
from src.scoring.services.judge_scoring import score_answer

logger = logging.getLogger(__name__)


class QAJobProcessor:
    """Service for orchestrating QA job pipelines."""

    def __init__(self, db: Session, snapshot_id: int, question_id: int, judge_id: int):
        """
        Initialize QA job processor.

        Args:
            db: Database session
            snapshot_id: Snapshot ID
            question_id: Question ID
            judge_id: Judge ID for scoring
        """
        self.db = db
        self.snapshot_id = snapshot_id
        self.question_id = question_id
        self.judge_id = judge_id

    async def run(self, job_id: int) -> QAJob:
        """
        Process an existing QA job through its pipeline stages.

        Args:
            job_id: QAJob ID to process (required)

        Returns:
            QAJob object after processing

        Raises:
            ValueError: If job not found or validation fails
        """
        logger.info(f"Processing QAJob {job_id}")

        # Retrieve existing job from database
        job = QAJobRepository.get_by_id(self.db, job_id)
        if not job:
            raise ValueError(f"QAJob with id {job_id} not found")

        # Validate job is in a processable state
        if job.status == JobStatusEnum.completed:
            logger.info(f"Job {job_id} is already completed, skipping")
            return job

        # Ensure job is in running state
        if job.status != JobStatusEnum.running:
            QAJobRepository.update_status(self.db, job_id, JobStatusEnum.running, job.stage)
            logger.info(f"Updated job {job_id} status to running")

        # Run the pipeline
        await self._run_pipeline(job)

        return job

    async def _run_pipeline(self, job: QAJob) -> None:
        """
        Run pipeline stages sequentially with pause checks between stages.

        Args:
            job: QAJob to process
        """
        stages = [
            (QAJobStageEnum.generating_answers, self._run_answer_generation),
            (QAJobStageEnum.processing_answers, self._run_claim_processing),
            (QAJobStageEnum.scoring_answers, self._run_scoring),
        ]

        # Rubric jobs skip claim processing (pipeline: answer → score only)
        if job.rubric_id is not None:
            stages = [(e, fn) for e, fn in stages if e != QAJobStageEnum.processing_answers]

        start_idx = self._get_start_index(job)

        if start_idx >= len(stages):
            # All stages already done
            logger.info(f"QAJob {job.id}: All stages already complete")
            QAJobRepository.update_status(
                self.db, job.id, JobStatusEnum.completed, QAJobStageEnum.completed
            )
            return

        for stage_enum, stage_fn in stages[start_idx:]:
            # Re-read job status from DB to check for pause
            job = QAJobRepository.get_by_id(self.db, job.id)
            if job.status == JobStatusEnum.paused:
                logger.info(f"Job {job.id} paused before {stage_enum.value}")
                return

            QAJobRepository.update_status(self.db, job.id, JobStatusEnum.running, stage_enum)
            try:
                await stage_fn(job)
            except Exception as e:
                # Catch unhandled exceptions (stage functions should handle errors
                # internally, but this is a safety net for unexpected failures)
                logger.error(f"QAJob {job.id} failed during {stage_enum.value}: {e}")
                QAJobRepository.update_status(
                    self.db, job.id, JobStatusEnum.failed, stage_enum
                )
                return

            # Re-check status after stage completes
            # Stage functions may set status to failed (internal error handling) or
            # an external caller may have set status to paused
            job = QAJobRepository.get_by_id(self.db, job.id)
            if job.status != JobStatusEnum.running:
                logger.info(
                    f"Job {job.id} stopped during {stage_enum.value} "
                    f"(status: {job.status.value})"
                )
                return

        QAJobRepository.update_status(
            self.db, job.id, JobStatusEnum.completed, QAJobStageEnum.completed
        )

    def _get_start_index(self, job: QAJob) -> int:
        """
        Determine which pipeline stage to start from based on existing data.

        For rubric jobs (job.rubric_id set), the pipeline is:
            [0] answer generation → [1] scoring (claims skipped)
        For accuracy jobs, the pipeline is:
            [0] answer generation → [1] claim processing → [2] scoring

        Returns:
            Index into the (possibly filtered) stages list, or len(stages) when all done.
        """
        # Check if answer exists
        answer = AnswerRepository.get_by_question_and_snapshot(
            self.db, self.question_id, self.snapshot_id
        )
        if not answer or not answer.answer_content:
            return 0  # answer generation

        if job.rubric_id is not None:
            # Rubric pipeline (claim stage removed): scoring is at index 1
            score = RubricAnswerScoreRepository.get_by_answer_rubric_judge(
                self.db, answer.id, job.rubric_id, self.judge_id
            )
            if not score:
                return 1  # scoring (index 1 in filtered stages)
            return 2  # all done

        # Accuracy pipeline: check claims then score
        claims = AnswerClaimRepository.get_by_answer(self.db, answer.id)
        if not claims:
            return 1  # claim processing

        all_checked = all(claim.created_at != claim.checked_at for claim in claims)
        if not all_checked:
            return 1  # retry unchecked claims

        # Check if score exists for this judge
        score = AnswerScoreRepository.get_by_answer_and_judge(
            self.db, answer.id, self.judge_id
        )
        if not score:
            return 2  # scoring

        return 3  # all done

    async def _run_answer_generation(self, job: QAJob) -> None:
        """Run the answer generation stage."""
        await generate_answer_for_job(self.db, job.id, self.question_id, self.snapshot_id)

    async def _run_claim_processing(self, job: QAJob) -> None:
        """Run the claim processing stage."""
        await extract_and_check_claims(self.db, job.id)

    async def _run_scoring(self, job: QAJob) -> None:
        """Run the scoring stage."""
        await score_answer(self.db, job.id)


async def run_qajob(
    db: Session,
    snapshot_id: int,
    question_id: int,
    judge_id: int,
    job_id: int,
) -> QAJob:
    """
    Process an existing QA job through its pipeline stages (convenience function).

    Args:
        db: Database session
        snapshot_id: Snapshot ID
        question_id: Question ID
        judge_id: Judge ID for scoring
        job_id: QAJob ID to process (required)

    Returns:
        QAJob object after processing
    """
    processor = QAJobProcessor(db, snapshot_id, question_id, judge_id)
    return await processor.run(job_id)


async def pause_qajob(db: Session, job_id: int) -> QAJob:
    """
    Pause a running QA job.

    Args:
        db: Database session
        job_id: QAJob ID to pause

    Returns:
        Updated QAJob object

    Raises:
        ValueError: If job not found or not in running state
    """
    job = QAJobRepository.get_by_id(db, job_id)
    if not job:
        raise ValueError(f"QAJob with id {job_id} not found")

    if job.status != JobStatusEnum.running:
        raise ValueError(
            f"Cannot pause job {job_id}. Job must be running "
            f"(current status: {job.status.value})"
        )

    # Pause the job (keep current stage)
    QAJobRepository.update_status(db, job_id, JobStatusEnum.paused, job.stage)
    logger.info(f"Paused QAJob {job_id} at stage {job.stage.value}")

    return job

def get_or_create_qajobs_batch(
    db: Session,
    snapshot_id: int,
    judge_id: int,
    question_ids: List[int],
    job_ids: Optional[List[int]] = None,
    rubric_id: Optional[int] = None,
) -> List[QAJob]:
    """
    Get or create QA job records for a batch of questions.

    This function ensures that job records exist in the database before processing begins.
    It does NOT run the pipeline - it only manages job records.

    Args:
        db: Database session
        snapshot_id: Snapshot ID
        judge_id: Judge ID for scoring
        question_ids: List of question IDs to process
        job_ids: Optional list of job IDs to resume (if provided, retrieves these jobs)
        rubric_id: Optional rubric ID for rubric scoring jobs

    Returns:
        List of QAJob objects (created or retrieved from DB)
    """
    jobs = []

    if job_ids is None:
        # Create new jobs or get existing ones per question
        for qn_id in question_ids:
            if rubric_id is not None:
                existing_job = QAJobRepository.get_by_snapshot_question_judge_rubric(
                    db, snapshot_id, qn_id, judge_id, rubric_id
                )
            else:
                existing_job = QAJobRepository.get_by_snapshot_question_judge(
                    db, snapshot_id, qn_id, judge_id
                )

            if existing_job:
                # Job exists - retrieve as-is (status will be managed by .run())
                logger.info(f"Retrieved existing job {existing_job.id} with status={existing_job.status.value}")
                jobs.append(existing_job)
            else:
                # Create new job
                job_data = {
                    "snapshot_id": snapshot_id,
                    "question_id": qn_id,
                    "judge_id": judge_id,
                    "type": QAJobTypeEnum.claim_scoring_full,
                    "status": JobStatusEnum.running,
                    "stage": QAJobStageEnum.starting,
                }

                if rubric_id is not None:
                    job_data["rubric_id"] = rubric_id

                # Check if answers already exist for the current question + snapshot
                answer = AnswerRepository.get_by_question_and_snapshot(
                    db, qn_id, snapshot_id
                )
                if answer:
                    job_data["answer_id"] = answer.id

                job = QAJobRepository.create(db, job_data)
                logger.info(f"Created new QAJob {job.id} for question {qn_id}")
                jobs.append(job)
    else:
        # Retrieve specific jobs by ID (status will be managed by .run())
        for job_id in job_ids:
            job = QAJobRepository.get_by_id(db, job_id)
            if job:
                logger.info(f"Retrieved job {job_id} with status={job.status.value}, stage={job.stage.value}")
                jobs.append(job)
            else:
                logger.warning(f"Job {job_id} not found, skipping")

    return jobs

async def run_qajobs_batch(
    db: Session,
    snapshot_id: int,
    judge_id: int,
    question_ids: List[int],
    job_ids: Optional[List[int]] = None,
    rubric_id: Optional[int] = None,
) -> List[QAJob]:
    """
    Run QA jobs batch for multiple questions.

    This function processes existing job records through their pipeline stages.
    Job records must already exist in the database (created by get_or_create_qajobs_batch).

    Args:
        db: Database session
        snapshot_id: Snapshot ID
        judge_id: Judge ID for scoring
        question_ids: List of question IDs to process
        job_ids: Optional list of job IDs to resume (None = check for existing or create new)
        rubric_id: Optional rubric ID for rubric scoring jobs

    Returns:
        List of QAJob objects after processing
    """
    # Ensure job records exist for all questions (this should be idempotent)
    qajobs = get_or_create_qajobs_batch(db, snapshot_id, judge_id, question_ids, job_ids, rubric_id)

    # Build mapping of question_id -> job_id
    qn2qajob = {job.question_id: job.id for job in qajobs if job}

    # Process all jobs concurrently
    jobs = await asyncio.gather(*(
        run_qajob(db, snapshot_id, qn_id, judge_id, qn2qajob.get(qn_id))
        for qn_id in question_ids
    ))

    logger.info(f"Processed {len(jobs)} QA jobs for snapshot {snapshot_id}, judge {judge_id}")
    return jobs


async def pause_qajobs_batch(
    db: Session,
    job_ids: List[int],
) -> List[QAJob]:
    """
    Pause QA jobs batch for multiple questions.

    Args:
        db: Database session
        job_ids: List of job IDs to process

    Returns:
        List of paused QAJob objects
    """

    jobs = await asyncio.gather(*(pause_qajob(db, job_id) for job_id in job_ids))

    logger.info(f"Paused {len(jobs)} QA jobs.")
    return jobs
