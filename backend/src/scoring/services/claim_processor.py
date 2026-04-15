"""
Service for extracting and checking claims from answers.
"""

import logging
import asyncio
from typing import List
from datetime import datetime
from sqlalchemy.orm import Session

from src.common.concurrency import gather_with_concurrency
from src.common.config import get_settings

try:
    import nltk  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    nltk = None

from src.common.database.models import AnswerClaim, JobStatusEnum
from src.common.database.repositories.answer_repo import AnswerRepository
from src.common.database.repositories.answer_claim_repo import AnswerClaimRepository
from src.common.database.repositories.answer_score_repo import AnswerScoreRepository
from src.common.database.repositories.qa_job_repo import QAJobRepository
from src.common.llm import LLMClient, CostTracker
from src.common.prompts import render_template
from src.common.models import CheckworthyResult
from src.scoring.services.claim_processor_steps import (
    ClaimTransform,
    ClaimFilter,
    ClaimSplitNewlines,
    ClaimMergeCodeBlocks,
    ClaimShiftBracketGroups,
    ClaimShortFilter,
    ClaimCitationFilter,
)

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
        self._llm_model_name = "gemini/gemini-2.5-flash-lite"
        self.llm_client = None

        # --- Pipeline steps (add new steps here) ---
        self.transforms: List[ClaimTransform] = [
            ClaimSplitNewlines(),
            ClaimMergeCodeBlocks(),
            ClaimShiftBracketGroups(),
        ]
        self.filters: List[ClaimFilter] = [
            ClaimShortFilter(),
            ClaimCitationFilter(),
        ]

    async def process(self, raise_on_error: bool = False) -> None:
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

            # Get answer_id from job
            answer_id = self.job.answer_id

            # Extract claims (synchronous)
            claims = self._extract_claims(answer_id)

            # Check claims (asynchronous)
            await self._check_claims(answer_id)

            # Update job costs
            self._update_job_status()

            logger.info(f"QAJob {self.job_id}: Completed claim processing for answer {answer_id}")

        except Exception as e:
            logger.error(f"Claim processing failed for job {self.job_id}: {e}", exc_info=True)

            # Mark job as failed with error message
            QAJobRepository.update_status(
                self.db,
                self.job_id,
                JobStatusEnum.failed,
                self.job.stage,
                error_message=str(e)
            )
            if raise_on_error:
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

        # Cache system prompt for checkworthy checks
        self._system_prompt = answer.system_prompt or "[No system prompt available]"

        # Use NLTK to split into sentences
        if nltk is None:
            raise ImportError("nltk is required for claim extraction. Install nltk to run claim processing.")
        sentences = nltk.sent_tokenize(answer.answer_content)

        # Apply transforms pipeline
        sentences = self._apply_transforms(sentences)

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

        # Run checkworthy checks asynchronously for all claims.
        # Pass full claims list + index so each check can build surrounding context.
        tasks = [
            self._check_single_claim(claim, idx, claims)
            for idx, claim in enumerate(claims)
        ]

        settings = get_settings()
        await gather_with_concurrency(settings.batch_max_concurrent_claims, *tasks)

        checkworthy_count = sum(1 for claim in claims if claim.checkworthy)
        logger.info(f"Checked {len(claims)} claims for answer {answer_id}. {checkworthy_count} are checkworthy.")

    async def _check_single_claim(
        self, claim: AnswerClaim, idx: int, all_claims: List[AnswerClaim]
    ) -> None:
        """
        Check if a single claim is checkworthy using filters, then LLM.

        Runs each ClaimFilter in order. If any filter returns False, the claim
        is marked not checkworthy without calling the LLM.

        Args:
            claim: AnswerClaim to check
            idx: Index of this claim in the full claims list
            all_claims: All claims for the answer (used to build surrounding context)
        """
        # Run filters pipeline
        for f in self.filters:
            result = f.check(claim.claim_text)
            if result is False:
                AnswerClaimRepository.update_checkworthy(
                    self.db, claim.id, checkworthy=False, checked_at=datetime.utcnow()
                )
                logger.debug(f"Claim {claim.id} filtered by {f.name}: not checkworthy")
                return

        # Build surrounding context so the LLM can see where the claim sits
        # in the response (e.g. to identify headers, labels, or structural text).
        claim_context = self._build_claim_context(idx, all_claims)

        # No filter matched — call LLM
        prompt = render_template(
            "checkworthy.md",
            system_prompt=self._system_prompt,
            claim_context=claim_context,
        )

        try:
            client = self._get_llm_client()
            result, metadata = await client.generate_structured_async(
                prompt=prompt,
                response_model=CheckworthyResult,
                temperature=0.0
            )

            # Track costs
            self.cost_tracker.add_call(metadata)

            # Update claim via repository
            AnswerClaimRepository.update_checkworthy(
                self.db, claim.id, checkworthy=result.checkworthy, checked_at=datetime.utcnow()
            )

            logger.debug(f"Claim {claim.id} checkworthy={result.checkworthy}: {result.reasoning}")

        except Exception as e:
            logger.error(f"Failed to check claim {claim.id}: {e}", exc_info=True)
            # Mark as checkworthy=True by default via repository
            AnswerClaimRepository.update_checkworthy(
                self.db, claim.id, checkworthy=True, checked_at=datetime.utcnow()
            )
            logger.warning(f"Claim {claim.id} marked as checkworthy=True due to error (will be judged)")

    @staticmethod
    def _build_claim_context(
        idx: int, all_claims: List[AnswerClaim], window: int = 2
    ) -> str:
        """
        Build a short surrounding-context string for a claim.

        This gives the LLM visibility into where the claim sits in the
        response — helping it identify headers, structural labels, or
        other non-substantive text that shouldn't be treated as claims.

        Args:
            idx: Index of the current claim in all_claims
            all_claims: Full ordered list of claims for the answer
            window: Number of claims before/after to include

        Returns:
            A string with surrounding claims and the current claim
            highlighted with >>> <<< markers.
        """
        before = [c.claim_text for c in all_claims[max(0, idx - window):idx]]
        after = [c.claim_text for c in all_claims[idx + 1:idx + 1 + window]]
        current = f">>> {all_claims[idx].claim_text} <<<"
        parts = before + [current] + after
        return " ... ".join(parts)

    def _apply_transforms(self, claims: List[str]) -> List[str]:
        """
        Apply all ClaimTransform steps in order with validation.

        Args:
            claims: List of claim strings from NLTK sentence tokenizer

        Returns:
            Transformed list of claim strings

        Raises:
            ValueError: If transforms lose or add characters
        """
        original_joined = "".join(claims)

        for transform in self.transforms:
            claims = transform.transform(claims)

        # Validation — ensure no characters were lost or added
        joined = "".join(claims)
        if joined != original_joined:
            logger.error(
                f"Transform validation failed. "
                f"Expected {len(original_joined)} chars, got {len(joined)}. "
                f"Original: {original_joined!r}, Joined: {joined!r}"
            )
            raise ValueError("Transform validation failed: character mismatch")

        return claims

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


async def extract_and_check_claims(
    db: Session,
    job_id: int,
    raise_on_error: bool = False,
) -> None:
    """Async convenience wrapper used by the QA job pipeline."""
    processor = ClaimProcessor(db, job_id)
    await processor.process(raise_on_error=raise_on_error)
