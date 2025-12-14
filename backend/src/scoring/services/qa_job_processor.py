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
from src.query_generation.services.answer_generator import generate_answer_for_job
from src.scoring.services.claim_processor import extract_and_check_claims
from src.scoring.services.judge_scoring import score_answer
from src.common.models.qa_job import QAJobFailureMessage

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

    async def run(self, job_id: int, is_scoring: bool = False) -> QAJob:
        """
        Process an existing QA job through its pipeline stages.

        This function assumes the job record already exists in the database (created via
        get_or_create_qajobs_batch). It retrieves the job and processes it based on its
        current stage.

        Args:
            job_id: QAJob ID to process (required)
            is_scoring: If True, override stage to scoring_answers

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

        # Update job stage if is_scoring flag is set
        if is_scoring:
            stage = QAJobStageEnum.scoring_answers
            logger.info(f"Updating job {job_id} stage to {stage.value} (is_scoring=True)")
            job = QAJobRepository.update_status(self.db, job.id, job.status, stage)

        # Trigger pipeline based on current stage
        await self._trigger_pipeline_stage(job)

        return job

    async def _trigger_pipeline_stage(self, job: QAJob) -> None:
        """
        Trigger the appropriate pipeline stage based on job's current stage.

        This runs: 
        1) generate_answer_for_job(...)
        2) extract_and_check_claims(...)
        3) score_answer(...)

        Args:
            job: QAJob to process
        """
        current_stage = job.stage

        if current_stage == QAJobStageEnum.starting:
            # Start from beginning - generate answer
            logger.info(f"QAJob {job.id}: Starting pipeline from 'starting' stage")
            await generate_answer_for_job(self.db, job.id, self.question_id, self.snapshot_id)

        elif current_stage == QAJobStageEnum.generating_answers:
            # Check if answer exists
            answer = AnswerRepository.get_by_question_and_snapshot(
                self.db, self.question_id, self.snapshot_id
            )

            # Check if answer exists AND is not a failure message
            if answer and answer.answer_content and answer.answer_content != QAJobFailureMessage("generating_answers"):
                # Valid answer exists, move to claim processing
                logger.info(f"QAJob {job.id}: Answer exists, moving to claim processing")
                await extract_and_check_claims(self.db, job.id)
            else:
                # Answer missing or failed, retry generation
                logger.info(f"QAJob {job.id}: Answer missing, generating answer")
                await generate_answer_for_job(self.db, job.id, self.question_id, self.snapshot_id)

        elif current_stage == QAJobStageEnum.processing_answers:
            # Check if claims exist AND are fully checked
            claims = AnswerClaimRepository.get_by_answer(self.db, job.answer_id)

            if claims:
                # Check if all claims have been checked (created_at != checked_at)
                # Note: checked_at acts as a natural failure indicator. When generate_structured_async
                # fails in _check_single_claim, checked_at is never updated and remains == created_at.
                # This allows us to detect unchecked claims and retry without needing a failure message.
                all_checked = all(claim.created_at != claim.checked_at for claim in claims)

                if all_checked:
                    logger.info(f"QAJob {job.id}: All {len(claims)} claims checked, moving to scoring")
                    await score_answer(self.db, job.id)
                else:
                    unchecked_count = sum(
                        1 for claim in claims if claim.created_at == claim.checked_at
                    )
                    logger.info(
                        f"QAJob {job.id}: {unchecked_count} claims not checked, "
                        f"running claim processing"
                    )
                    await extract_and_check_claims(self.db, job.id)
            else:
                logger.info(f"QAJob {job.id}: No claims found, running claim processing")
                await extract_and_check_claims(self.db, job.id)

        elif current_stage == QAJobStageEnum.scoring_answers:
            # Check if score exists
            score = AnswerScoreRepository.get_by_answer_and_judge(
                self.db, job.answer_id, self.judge_id
            )

            # Check if score exists AND is not a failure message
            if score and score.explanation != QAJobFailureMessage("scoring_answers"):
                # Valid score exists, mark as completed
                logger.info(f"QAJob {job.id}: Score already exists, marking as completed")
                QAJobRepository.update_status(
                    self.db, job.id, JobStatusEnum.completed, QAJobStageEnum.completed
                )
            else:
                # Score missing or failed, retry scoring
                logger.info(f"QAJob {job.id}: Score missing, running scoring")
                await score_answer(self.db, job.id)

        else:
            raise ValueError(f"Unknown stage: {current_stage}")


async def run_qajob(
    db: Session,
    snapshot_id: int,
    question_id: int,
    judge_id: int,
    job_id: int,
    is_scoring: bool = False
) -> QAJob:
    """
    Process an existing QA job through its pipeline stages (convenience function).

    This function assumes the job record already exists in the database.

    Args:
        db: Database session
        snapshot_id: Snapshot ID
        question_id: Question ID
        judge_id: Judge ID for scoring
        job_id: QAJob ID to process (required)
        is_scoring: If True, override stage to scoring_answers

    Returns:
        QAJob object after processing
    """
    processor = QAJobProcessor(db, snapshot_id, question_id, judge_id)
    return await processor.run(job_id, is_scoring)


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

    Returns:
        List of QAJob objects (created or retrieved from DB)
    """
    jobs = []

    if job_ids is None:
        # Create new jobs or get existing ones per question
        for qn_id in question_ids:
            existing_job = QAJobRepository.get_by_snapshot_question_judge(
                db, snapshot_id, qn_id, judge_id
            )

            if existing_job:
                # Job exists - update status if needed
                if existing_job.status == JobStatusEnum.paused:
                    # Resume paused job
                    QAJobRepository.update_status(
                        db, existing_job.id, JobStatusEnum.running, existing_job.stage
                    )
                    logger.info(f"Resuming paused job {existing_job.id}")
                jobs.append(existing_job)
            else:
                # Create new job
                job_data = {
                    "snapshot_id": snapshot_id,
                    "question_id": qn_id,
                    "judge_id": judge_id,
                    "type": QAJobTypeEnum.claim_scoring_full,
                    "status": JobStatusEnum.running,
                    "stage": QAJobStageEnum.starting
                }

                # Check if answers/claims already exist for the current question + snapshot
                answer = AnswerRepository.get_by_question_and_snapshot(
                    db, qn_id, snapshot_id
                )
                if answer:
                    job_data["answer_id"] = answer.id

                job = QAJobRepository.create(db, job_data)
                logger.info(f"Created new QAJob {job.id} for question {qn_id}")
                jobs.append(job)
    else:
        # Resume specific jobs by ID
        for job_id in job_ids:
            job = QAJobRepository.get_by_id(db, job_id)
            if job:
                # Validate job status before resuming
                if job.status == JobStatusEnum.paused:
                    QAJobRepository.update_status(
                        db, job_id, JobStatusEnum.running, job.stage
                    )
                    logger.info(f"Resuming paused job {job_id}")
                elif job.status == JobStatusEnum.failed:
                    # Allow retrying failed jobs
                    QAJobRepository.update_status(
                        db, job_id, JobStatusEnum.running, job.stage
                    )
                    logger.info(f"Retrying failed job {job_id}")
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
    is_scoring: bool = False,
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
        is_scoring: Boolean flag to indicate if this is a scoring job

    Returns:
        List of QAJob objects after processing
    """
    # Ensure job records exist for all questions (this should be idempotent)
    qajobs = get_or_create_qajobs_batch(db, snapshot_id, judge_id, question_ids, job_ids)

    # Build mapping of question_id -> job_id
    qn2qajob = {job.question_id: job.id for job in qajobs if job}

    # Process all jobs concurrently
    jobs = await asyncio.gather(*(
        run_qajob(db, snapshot_id, qn_id, judge_id, qn2qajob.get(qn_id), is_scoring)
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
