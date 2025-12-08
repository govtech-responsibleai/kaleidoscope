"""
Service for extracting and checking claims from answers.
"""

import logging
import asyncio
from typing import List
from datetime import datetime
from sqlalchemy.orm import Session
import nltk

from src.common.database.models import AnswerClaim, JobStatusEnum, QAJobStageEnum
from src.common.database.repositories.answer_repo import AnswerRepository
from src.common.database.repositories.answer_claim_repo import AnswerClaimRepository
from src.common.database.repositories.qa_job_repo import QAJobRepository
from src.common.llm import LLMClient, CostTracker
from src.common.prompts import render_template
from src.common.models import CheckworthyResult

logger = logging.getLogger(__name__)

# Ensure NLTK punkt tokenizer is available
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
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

        # Initialize LLM client
        self.llm_client = LLMClient(model="gemini/gemini-2.0-flash-lite")

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
            score_answer(self.db, self.job_id)

        except Exception as e:
            logger.error(f"Claim processing failed for job {self.job_id}: {e}", exc_info=True)
            raise

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
        sentences = nltk.sent_tokenize(answer.answer_content)

        # Create AnswerClaim records
        claims = []
        current_time = datetime.utcnow()

        for idx, sentence in enumerate(sentences):
            claim_data = {
                "answer_id": answer_id,
                "claim_index": idx,
                "text": sentence.strip(),
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
            claim_text=claim.text
        )

        # Call LLM
        try:
            result, metadata = await self.llm_client.generate_structured_async(
                prompt=prompt,
                response_model=CheckworthyResult,
                temperature=0.7
            )

            # Track costs
            self.cost_tracker.add_call(metadata)

            # Update claim
            claim.checkworthy = result.is_checkworthy
            claim.checked_at = datetime.utcnow()
            self.db.commit()

            logger.debug(f"Claim {claim.id} checkworthy={result.is_checkworthy}: {result.reasoning}")

        except Exception as e:
            logger.error(f"Failed to check claim {claim.id}: {e}", exc_info=True)
            # On error, keep checkworthy=True to be safe
            claim.checked_at = datetime.utcnow()
            self.db.commit()

    def _update_job_status(self) -> None:
        """Update job costs in database."""
        summary = self.cost_tracker.get_summary()

        # Update job with accumulated costs
        self.job.prompt_tokens += summary["prompt_tokens"]
        self.job.completion_tokens += summary["completion_tokens"]
        self.job.total_cost += summary["total_cost"]
        self.db.commit()

        logger.info(f"Updated QAJob {self.job_id} costs: ${summary['total_cost']:.4f}")


def extract_and_check_claims(db: Session, job_id: int) -> None:
    """
    Extract and check claims for a QA job (convenience function).

    Args:
        db: Database session
        job_id: QAJob ID to process
    """
    processor = ClaimProcessor(db, job_id)
    asyncio.run(processor.process())
