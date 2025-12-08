"""
Service for orchestrating QA job pipeline (answer generation -> claim processing -> scoring).
"""

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

    def run(self, job_id: Optional[int] = None, stage: Optional[QAJobStageEnum] = None) -> QAJob:
        """
        Run or resume a QA job.

        This is the main orchestration function that:
        1. Creates a new job or gets existing job
        2. Optionally updates the stage (with warning if updating existing job)
        3. Routes to the appropriate pipeline stage based on current stage

        Args:
            job_id: Optional QAJob ID to resume (None = create new job)
            stage: Optional stage to set/override

        Returns:
            QAJob object

        Raises:
            ValueError: If job validation fails
        """
        # Step 1: Get or create QAJob
        if job_id is None:
            # CREATE NEW JOB
            # Get or create answer first
            answer = AnswerRepository.get_by_question_and_snapshot(
                self.db, self.question_id, self.snapshot_id
            )
            if not answer:
                # Create placeholder answer (will be generated in pipeline)
                answer_data = {
                    "question_id": self.question_id,
                    "snapshot_id": self.snapshot_id,
                    "answer_content": "",  # Placeholder
                    "is_selected_for_annotation": False
                }
                answer = AnswerRepository.create(self.db, answer_data)

            # Create new QAJob
            job_data = {
                "snapshot_id": self.snapshot_id,
                "question_id": self.question_id,
                "answer_id": answer.id,
                "judge_id": self.judge_id,
                "type": QAJobTypeEnum.claim_scoring_full,  # Default type
                "status": JobStatusEnum.running,
                "stage": QAJobStageEnum.starting
            }
            job = QAJobRepository.create(self.db, job_data)
            logger.info(
                f"Created new QAJob {job.id} for question {self.question_id}, "
                f"snapshot {self.snapshot_id}, judge {self.judge_id}"
            )

        else:
            # RESUME EXISTING JOB
            job = QAJobRepository.get_by_id(self.db, job_id)
            if not job:
                raise ValueError(f"QAJob with id {job_id} not found")

            # Validate job status before resuming
            if job.status != JobStatusEnum.paused:
                if job.status == JobStatusEnum.running:
                    raise ValueError(f"Job {job_id} is already running.")
                elif job.status == JobStatusEnum.failed:
                    raise ValueError(
                        f"Job {job_id} is failed. Create a new run to retry."
                    )
                elif job.status == JobStatusEnum.completed:
                    raise ValueError(
                        f"Job {job_id} is completed. You're good to go. "
                        f"Create a new run to rerun the same job."
                    )
                else:
                    raise ValueError(
                        f"Cannot resume job {job_id}. Current status: {job.status.value}"
                    )

            # Set status to running
            QAJobRepository.update_status(self.db, job_id, JobStatusEnum.running, job.stage)
            logger.info(f"Resumed QAJob {job_id} from paused state")

        # Step 2: Update stage if provided
        if stage is not None:
            if job_id is not None:
                logger.warning(
                    f"Updating stage of existing job {job_id} to {stage.value}. "
                    f"This may break the workflow."
                )

            QAJobRepository.update_status(self.db, job.id, JobStatusEnum.running, stage)
            job.stage = stage
            logger.info(f"QAJob {job.id}: Stage updated to {stage.value}")

        # Step 3: Trigger pipeline based on current stage
        self._trigger_pipeline_stage(job)

        return job

    def _trigger_pipeline_stage(self, job: QAJob) -> None:
        """
        Trigger the appropriate pipeline stage based on job's current stage.

        Args:
            job: QAJob to process
        """
        current_stage = job.stage

        if current_stage == QAJobStageEnum.starting:
            # Start from beginning - generate answer
            logger.info(f"QAJob {job.id}: Starting pipeline from 'starting' stage")
            generate_answer_for_job(self.db, job.id, self.question_id, self.snapshot_id)

        elif current_stage == QAJobStageEnum.generating_answers:
            # Check if answer exists
            answer = AnswerRepository.get_by_question_and_snapshot(
                self.db, self.question_id, self.snapshot_id
            )

            if answer and answer.answer_content:  # Answer exists with content
                logger.info(f"QAJob {job.id}: Answer exists, moving to claim processing")
                extract_and_check_claims(self.db, job.id)
            else:
                logger.info(f"QAJob {job.id}: Answer missing, generating answer")
                generate_answer_for_job(self.db, job.id, self.question_id, self.snapshot_id)

        elif current_stage == QAJobStageEnum.processing_answers:
            # Check if claims exist AND are fully checked
            claims = AnswerClaimRepository.get_by_answer(self.db, job.answer_id)

            if claims:
                # Check if all claims have been checked (created_at != checked_at)
                all_checked = all(claim.created_at != claim.checked_at for claim in claims)

                if all_checked:
                    logger.info(f"QAJob {job.id}: All {len(claims)} claims checked, moving to scoring")
                    score_answer(self.db, job.id)
                else:
                    unchecked_count = sum(
                        1 for claim in claims if claim.created_at == claim.checked_at
                    )
                    logger.info(
                        f"QAJob {job.id}: {unchecked_count} claims not checked, "
                        f"running claim processing"
                    )
                    extract_and_check_claims(self.db, job.id)
            else:
                logger.info(f"QAJob {job.id}: No claims found, running claim processing")
                extract_and_check_claims(self.db, job.id)

        elif current_stage == QAJobStageEnum.scoring_answers:
            # Check if score exists
            score = AnswerScoreRepository.get_by_answer_and_judge(
                self.db, job.answer_id, self.judge_id
            )

            if score:
                logger.info(f"QAJob {job.id}: Score already exists, marking as completed")
                QAJobRepository.update_status(
                    self.db, job.id, JobStatusEnum.completed, current_stage
                )
            else:
                logger.info(f"QAJob {job.id}: No score found, running scoring")
                score_answer(self.db, job.id)

        else:
            raise ValueError(f"Unknown stage: {current_stage}")


def run_qajob(
    db: Session,
    snapshot_id: int,
    question_id: int,
    judge_id: int,
    job_id: int = None,
    stage: QAJobStageEnum = None
) -> QAJob:
    """
    Run or resume a QA job (convenience function).

    Args:
        db: Database session
        snapshot_id: Snapshot ID
        question_id: Question ID
        judge_id: Judge ID for scoring
        job_id: Optional QAJob ID to resume (None = create new job)
        stage: Optional stage to set/override

    Returns:
        QAJob object
    """
    processor = QAJobProcessor(db, snapshot_id, question_id, judge_id)
    return processor.run(job_id, stage)


def pause_qajob(db: Session, job_id: int) -> QAJob:
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


def run_qajobs_batch(
    db: Session,
    snapshot_id: int,
    judge_id: int,
    question_ids: List[int],
    stage: QAJobStageEnum = None,
    background_tasks: BackgroundTasks = None
) -> List[QAJob]:
    """
    Run QA jobs in batch for multiple questions.

    This spawns background tasks for parallel execution across N questions.

    Args:
        db: Database session
        snapshot_id: Snapshot ID
        judge_id: Judge ID for scoring
        question_ids: List of question IDs to process
        stage: Optional starting stage (default: starting)
        background_tasks: FastAPI BackgroundTasks for async execution

    Returns:
        List of created QAJob objects
    """
    jobs = []

    for question_id in question_ids:
        # Create job (synchronously)
        processor = QAJobProcessor(db, snapshot_id, question_id, judge_id)
        job = processor.run(job_id=None, stage=stage)
        jobs.append(job)

        # If background tasks provided, spawn async processing
        if background_tasks:
            background_tasks.add_task(
                _run_job_async,
                job_id=job.id,
                snapshot_id=snapshot_id,
                question_id=question_id,
                judge_id=judge_id
            )

    logger.info(f"Created {len(jobs)} QA jobs for snapshot {snapshot_id}, judge {judge_id}")
    return jobs


def _run_job_async(
    job_id: int,
    snapshot_id: int,
    question_id: int,
    judge_id: int
) -> None:
    """
    Background task to run a QA job asynchronously.

    This is intended to be run as a FastAPI background task.

    Args:
        job_id: QAJob ID
        snapshot_id: Snapshot ID
        question_id: Question ID
        judge_id: Judge ID
    """
    from src.common.database.connection import SessionLocal

    db = SessionLocal()
    try:
        # Just call the convenience function with the new session
        run_qajob(db, snapshot_id, question_id, judge_id, job_id=job_id, stage=None)
    except Exception as e:
        logger.error(f"QAJob {job_id} failed: {e}", exc_info=True)
        # Mark job as failed
        QAJobRepository.update_status(db, job_id, JobStatusEnum.failed, None)
    finally:
        db.close()
