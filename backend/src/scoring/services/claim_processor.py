"""
Service for extracting and checking claims from answers.
"""

import logging
import asyncio
from dataclasses import dataclass
from typing import Callable, List
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
from src.common.llm.provider_service import require_default_generation_model, resolve_model_runtime_config
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
SENTENCE_TOKENIZER_ERROR = (
    "Claim extraction requires the NLTK sentence tokenizer data ('punkt'). "
    "Restart the container with the sentence tokenizer package installed."
)


@dataclass
class ClaimSnapshot:
    """Plain snapshot of an extracted claim, safe to hold across LLM calls.

    Detached from any ORM session so scoring never pins a pooled connection
    while awaiting the (slow) checkworthy LLM calls.
    """

    id: int
    claim_index: int
    claim_text: str
    answer_id: int
    checkworthy: bool = True


class ClaimProcessor:
    """Service for extracting and checking claims using LLM."""

    def __init__(self, session_factory: Callable[[], Session], job_id: int):
        """
        Initialize claim processor.

        Args:
            session_factory: Callable returning a new DB session (e.g. ``SessionLocal``).
                A short-lived session snapshots the data needed; no session is held
                across the checkworthy LLM calls, so the connection pool is not pinned.
            job_id: QAJob ID for this processing run
        """
        self.session_factory = session_factory
        self.job_id = job_id
        self.cost_tracker = CostTracker(job_id=job_id)

        db = session_factory()
        try:
            job = QAJobRepository.get_by_id(db, job_id)
            if not job:
                raise ValueError(f"QAJob {job_id} not found")
            self.job_status = job.status
            self.job_stage = job.stage
            self.answer_id = job.answer_id

            answer = AnswerRepository.get_by_id(db, job.answer_id)
            if not answer:
                raise ValueError(f"Answer {job.answer_id} not found")
            self.answer_content = answer.answer_content
            self._system_prompt = answer.system_prompt or "[No system prompt available]"
            target_owner_id = answer.question.target.user_id
            if target_owner_id is None:
                raise ValueError("Answer target owner could not be resolved for claim processing.")

            # Lazily initialize LLM client so tests can override after instantiation
            self._llm_model_name = require_default_generation_model(db, int(target_owner_id))
            self._provider_kwargs = resolve_model_runtime_config(
                db,
                int(target_owner_id),
                self._llm_model_name,
            ).litellm_kwargs
        finally:
            db.close()
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
            if self.job_status != JobStatusEnum.running:
                logger.info(f"QAJob {self.job_id} is not running (status={self.job_status.value}). Skipping claim processing.")
                return

            answer_id = self.answer_id

            # Extract claims (synchronous)
            self._extract_claims(answer_id)

            # Check claims (asynchronous)
            await self._check_claims(answer_id)

            # Update job costs
            self._update_job_status()

            logger.info(f"QAJob {self.job_id}: Completed claim processing for answer {answer_id}")

        except Exception as e:
            logger.error(f"Claim processing failed for job {self.job_id}: {e}", exc_info=True)

            # Mark job as failed with error message
            db = self.session_factory()
            try:
                QAJobRepository.update_status(
                    db,
                    self.job_id,
                    JobStatusEnum.failed,
                    self.job_stage,
                    error_message=str(e)
                )
            finally:
                db.close()
            if raise_on_error:
                raise

    def _extract_claims(self, answer_id: int) -> List[ClaimSnapshot]:
        """
        Extract claims from an answer using sentence tokenization.

        Args:
            answer_id: Answer ID to extract claims from

        Returns:
            List of ClaimSnapshot objects (detached plain data, not ORM objects)
        """
        if nltk is None:
            raise RuntimeError(SENTENCE_TOKENIZER_ERROR)

        try:
            sentences = nltk.sent_tokenize(self.answer_content)
        except LookupError as exc:
            raise RuntimeError(SENTENCE_TOKENIZER_ERROR) from exc

        # Apply transforms pipeline (pure Python, no DB needed)
        sentences = self._apply_transforms(sentences)

        # Create AnswerClaim records in a short session, snapshotting ids+text.
        current_time = datetime.utcnow()
        snapshots: List[ClaimSnapshot] = []
        db = self.session_factory()
        try:
            for idx, sentence in enumerate(sentences):
                claim = AnswerClaimRepository.create(db, {
                    "answer_id": answer_id,
                    "claim_index": idx,
                    "claim_text": sentence.strip(),
                    "checkworthy": True,  # Default to True, will be updated by check_claims
                    "created_at": current_time,
                    "checked_at": current_time  # Initially same as created_at
                })
                snapshots.append(ClaimSnapshot(
                    id=claim.id,
                    claim_index=idx,
                    claim_text=sentence.strip(),
                    answer_id=answer_id,
                ))
        finally:
            db.close()

        logger.info(f"Extracted {len(snapshots)} claims from answer {answer_id}")
        return snapshots

    async def _check_claims(self, answer_id: int) -> None:
        """
        Check all claims for an answer asynchronously using LLM.

        Args:
            answer_id: Answer ID to check claims for
        """
        # Snapshot all claims for the answer as plain data, then release the session.
        db = self.session_factory()
        try:
            claims = [
                ClaimSnapshot(id=c.id, claim_index=idx, claim_text=c.claim_text,
                              answer_id=answer_id, checkworthy=c.checkworthy)
                for idx, c in enumerate(AnswerClaimRepository.get_by_answer(db, answer_id))
            ]
        finally:
            db.close()

        if not claims:
            logger.warning(f"No claims found for answer {answer_id}")
            return

        # Run checkworthy checks asynchronously for all claims. Each task opens its
        # own short session for its single write — no session held across the LLM call.
        tasks = [
            self._check_single_claim(claim, idx, claims)
            for idx, claim in enumerate(claims)
        ]

        settings = get_settings()
        await gather_with_concurrency(settings.batch_max_concurrent_claims, *tasks)

        logger.info(f"Checked {len(claims)} claims for answer {answer_id}.")

    async def _check_single_claim(
        self, claim: ClaimSnapshot, idx: int, all_claims: List[ClaimSnapshot]
    ) -> None:
        """
        Check if a single claim is checkworthy using filters, then LLM.

        Runs each ClaimFilter in order. If any filter returns False, the claim
        is marked not checkworthy without calling the LLM.

        Args:
            claim: ClaimSnapshot to check
            idx: Index of this claim in the full claims list
            all_claims: All claim snapshots for the answer (used to build context)
        """
        # Run filters pipeline
        for f in self.filters:
            result = f.check(claim.claim_text)
            if result is False:
                self._persist_checkworthy(claim.id, checkworthy=False)
                logger.debug(f"Claim {claim.id} filtered by {f.name}: not checkworthy")
                return

        # Build surrounding context so the LLM can see where the claim sits
        # in the response (e.g. to identify headers, labels, or structural text).
        claim_context = self._build_claim_context(idx, all_claims)

        # No filter matched — call LLM (no DB session open while awaiting)
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
                temperature=0.0,
                metadata={
                    "generation_name": "checkworthy",
                    "tags": ["checkworthy"],
                }
            )

            # Track costs
            self.cost_tracker.add_call(metadata)

            # Update claim via repository
            self._persist_checkworthy(claim.id, checkworthy=result.checkworthy)

            logger.debug(f"Claim {claim.id} checkworthy={result.checkworthy}: {result.reasoning}")

        except Exception as e:
            logger.error(f"Failed to check claim {claim.id}: {e}", exc_info=True)
            # Mark as checkworthy=True by default via repository
            self._persist_checkworthy(claim.id, checkworthy=True)
            logger.warning(f"Claim {claim.id} marked as checkworthy=True due to error (will be judged)")

    def _persist_checkworthy(self, claim_id: int, *, checkworthy: bool) -> None:
        """Persist a single claim's checkworthy verdict in its own short session."""
        db = self.session_factory()
        try:
            AnswerClaimRepository.update_checkworthy(
                db, claim_id, checkworthy=checkworthy, checked_at=datetime.utcnow()
            )
        finally:
            db.close()

    @staticmethod
    def _build_claim_context(
        idx: int, all_claims: List[ClaimSnapshot], window: int = 2
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
        db = self.session_factory()
        try:
            QAJobRepository.update_status(
                db,
                self.job_id,
                status=self.job_status,  # Keep current status
                stage=self.job_stage,    # Keep current stage
                prompt_tokens=summary["prompt_tokens"],
                completion_tokens=summary["completion_tokens"],
                total_cost=summary["total_cost"]
            )
        finally:
            db.close()

        logger.info(f"Updated QAJob {self.job_id} costs: ${summary['total_cost']:.4f}")

    def _get_llm_client(self):
        """Create or return the cached LLM client."""
        if self.llm_client is None:
            self.llm_client = LLMClient(
                model=self._llm_model_name,
                provider_kwargs=self._provider_kwargs,
            )
        return self.llm_client


async def extract_and_check_claims(
    session_factory: Callable[[], Session],
    job_id: int,
    raise_on_error: bool = False,
) -> None:
    """Async convenience wrapper used by the QA job pipeline."""
    try:
        processor = ClaimProcessor(session_factory, job_id)
    except Exception as e:
        logger.error(f"ClaimProcessor init failed for job {job_id}: {e}", exc_info=True)
        db = session_factory()
        try:
            QAJobRepository.update_status(
                db, job_id, JobStatusEnum.failed, error_message=str(e)
            )
        finally:
            db.close()
        if raise_on_error:
            raise
        return
    await processor.process(raise_on_error=raise_on_error)
