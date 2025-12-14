"""
Service for extracting and checking claims from answers.
"""

import logging
import asyncio
from typing import List
from datetime import datetime
from sqlalchemy.orm import Session

try:
    import nltk  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    nltk = None

from src.common.database.models import AnswerClaim, JobStatusEnum, QAJobStageEnum
from src.common.database.repositories.answer_repo import AnswerRepository
from src.common.database.repositories.answer_claim_repo import AnswerClaimRepository
from src.common.database.repositories.answer_score_repo import AnswerScoreRepository
from src.common.database.repositories.qa_job_repo import QAJobRepository
from src.common.llm import LLMClient, CostTracker
from src.common.prompts import render_template
from src.common.models import CheckworthyResult
from src.common.models.qa_job import QAJobFailureMessage

logger = logging.getLogger(__name__)

# Ensure NLTK punkt tokenizer is available when the package exists.
if nltk is not None:  # pragma: no branch
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:  # pragma: no cover - download path
        nltk.download('punkt')


class ClaimProcessor:
    """Service for extracting and checking claims using LLM."""

    def __init__(self, db: Session, job_id: int):
        """
        Initialize claim processor.

        Args:
            db: Database session
            job_id: QAJob ID for this processing run
        """
        self.db = db
        self.job_id = job_id
        self.cost_tracker = CostTracker(job_id=job_id)

        # Load job
        self.job = QAJobRepository.get_by_id(db, job_id)
        if not self.job:
            raise ValueError(f"QAJob {job_id} not found")

        # Lazily initialize LLM client so tests can override after instantiation
        self._llm_model_name = "gemini/gemini-2.0-flash-lite"
        self.llm_client = None

    async def process(self) -> None:
        """
        Extract and check claims for the job's answer.

        This is the main entry point that:
        1. Checks if job is still running
        2. Updates job stage to "processing_answers"
        3. Extracts claims using NLTK
        4. Checks claims for checkworthiness using async LLM calls
        5. Calls next pipeline stage (judge scoring)

        Raises:
            Exception: If processing fails
        """
        try:
            # Check if job is still running
            if self.job.status != JobStatusEnum.running:
                logger.info(f"QAJob {self.job_id} is not running (status={self.job.status.value}). Skipping claim processing.")
                return

            # Update job stage
            QAJobRepository.update_status(self.db, self.job_id, JobStatusEnum.running, QAJobStageEnum.processing_answers)
            logger.info(f"QAJob {self.job_id}: Stage updated to 'processing_answers'")

            # Get answer_id from job
            answer_id = self.job.answer_id

            # Extract claims (synchronous)
            claims = self._extract_claims(answer_id)

            # Check claims (asynchronous)
            await self._check_claims(answer_id)

            # Update job costs
            self._update_job_status()

            logger.info(f"QAJob {self.job_id}: Completed claim processing for answer {answer_id}")

            # Call next stage in pipeline
            from src.scoring.services.judge_scoring import score_answer
            await score_answer(self.db, self.job_id)

        except Exception as e:
            logger.error(f"Claim processing failed for job {self.job_id}: {e}", exc_info=True)

            # Mark job as failed but DON'T create a failure message record
            # The natural indicator is claim.checked_at: if generate_structured_async fails,
            # claim.checked_at is never updated and remains == created_at, which signals
            # an unchecked claim. The retry logic in _trigger_pipeline_stage will detect this.
            QAJobRepository.update_status(self.db, self.job_id, JobStatusEnum.failed, self.job.stage)

    def _extract_claims(self, answer_id: int) -> List[AnswerClaim]:
        """
        Extract claims from an answer using NLTK sentence tokenizer.

        Args:
            answer_id: Answer ID to extract claims from

        Returns:
            List of created AnswerClaim objects
        """
        # Get the answer
        answer = AnswerRepository.get_by_id(self.db, answer_id)
        if not answer:
            raise ValueError(f"Answer with id {answer_id} not found")

        # Use NLTK to split into sentences
        if nltk is None:
            raise ImportError("nltk is required for claim extraction. Install nltk to run claim processing.")
        sentences = nltk.sent_tokenize(answer.answer_content)

        # Create AnswerClaim records
        claims = []
        current_time = datetime.utcnow()

        for idx, sentence in enumerate(sentences):
            claim_data = {
                "answer_id": answer_id,
                "claim_index": idx,
                "claim_text": sentence.strip(),
                "checkworthy": True,  # Default to True, will be updated by check_claims
                "created_at": current_time,
                "checked_at": current_time  # Initially same as created_at
            }
            claim = AnswerClaimRepository.create(self.db, claim_data)
            claims.append(claim)

        logger.info(f"Extracted {len(claims)} claims from answer {answer_id}")
        return claims

    async def _check_claims(self, answer_id: int) -> None:
        """
        Check all claims for an answer asynchronously using LLM.

        Args:
            answer_id: Answer ID to check claims for
        """
        # Get all claims for the answer
        claims = AnswerClaimRepository.get_by_answer(self.db, answer_id)

        if not claims:
            logger.warning(f"No claims found for answer {answer_id}")
            return

        # Run checkworthy checks asynchronously for all claims
        tasks = [
            self._check_single_claim(claim)
            for claim in claims
        ]

        await asyncio.gather(*tasks)

        checkworthy_count = sum(1 for claim in claims if claim.checkworthy)
        logger.info(f"Checked {len(claims)} claims for answer {answer_id}. {checkworthy_count} are checkworthy.")

    async def _check_single_claim(self, claim: AnswerClaim) -> None:
        """
        Check if a single claim is checkworthy using LLM.

        Args:
            claim: AnswerClaim to check
        """
        # Render prompt
        prompt = render_template(
            "checkworthy.md",
            claim_text=claim.claim_text
        )

        # Call LLM
        try:
            client = self._get_llm_client()
            result, metadata = await client.generate_structured_async(
                prompt=prompt,
                response_model=CheckworthyResult,
                temperature=0.7
            )

            logger.info(f"Prompt checked: {prompt}")

            # Track costs
            self.cost_tracker.add_call(metadata)

            # Update claim
            claim.checkworthy = result.checkworthy
            claim.checked_at = datetime.utcnow()
            self.db.commit()

            logger.debug(f"Claim {claim.id} checkworthy={result.checkworthy}: {result.reasoning}")

        except Exception as e:
            logger.error(f"Failed to check claim {claim.id}: {e}", exc_info=True)
            raise

    def _update_job_status(self) -> None:
        """Update job costs in database."""
        summary = self.cost_tracker.get_summary()

        # Update job using repository (keeps current status/stage, adds costs)
        QAJobRepository.update_status(
            self.db,
            self.job_id,
            status=self.job.status,  # Keep current status
            stage=self.job.stage,    # Keep current stage
            prompt_tokens=summary["prompt_tokens"],
            completion_tokens=summary["completion_tokens"],
            total_cost=summary["total_cost"]
        )

        logger.info(f"Updated QAJob {self.job_id} costs: ${summary['total_cost']:.4f}")

    def _get_llm_client(self):
        """Create or return the cached LLM client."""
        if self.llm_client is None:
            self.llm_client = LLMClient(model=self._llm_model_name)
        return self.llm_client


async def extract_and_check_claims(db: Session, job_id: int) -> None:
    """Async convenience wrapper used by the QA job pipeline."""
    processor = ClaimProcessor(db, job_id)
    await processor.process()
