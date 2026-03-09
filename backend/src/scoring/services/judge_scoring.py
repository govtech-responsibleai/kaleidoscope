"""
Service for scoring answers using LLM judges.
"""

import logging
import asyncio
from typing import List
from sqlalchemy.orm import Session

from src.common.database.models import JobStatusEnum, JudgeTypeEnum
from src.common.database.repositories.answer_repo import AnswerRepository
from src.common.database.repositories.answer_claim_repo import AnswerClaimRepository
from src.common.database.repositories.answer_score_repo import AnswerScoreRepository
from src.common.database.repositories.answer_claim_score_repo import AnswerClaimScoreRepository
from src.common.database.repositories.judge_repo import JudgeRepository
from src.common.database.repositories.qa_job_repo import QAJobRepository
from src.common.database.repositories.kb_document_repo import KBDocumentRepository
from src.common.llm import LLMClient, CostTracker
from src.common.prompts import render_template
from src.common.models import ClaimJudgmentResult, ResponseJudgmentResult

logger = logging.getLogger(__name__)


class AnswerJudge:
    """Service for scoring answers using LLM judges."""

    def __init__(self, db: Session, job_id: int):
        """
        Initialize answer judge.

        Args:
            db: Database session
            job_id: QAJob ID for this scoring run
        """
        self.db = db
        self.job_id = job_id
        self.cost_tracker = CostTracker(job_id=job_id)

        # Load job
        self.job = QAJobRepository.get_by_id(db, job_id)
        if not self.job:
            raise ValueError(f"QAJob {job_id} not found")

        # Load judge
        self.judge = JudgeRepository.get_by_id(db, self.job.judge_id)
        if not self.judge:
            raise ValueError(f"Judge {self.job.judge_id} not found")

        # Load answer
        self.answer = AnswerRepository.get_by_id(db, self.job.answer_id)
        if not self.answer:
            raise ValueError(f"Answer {self.job.answer_id} not found")

        # Initialize LLM client with judge's model
        self.llm_client = LLMClient(model=self.judge.model_name)

    async def score(self) -> None:
        """
        Score answer based on judge type (claim-based or response-level).

        This is the main entry point that:
        1. Checks if job is still running
        2. Updates job stage to "scoring_answers"
        3. Routes to appropriate scoring function based on judge type
        4. Updates job status to "completed"

        Raises:
            Exception: If scoring fails
        """
        try:
            # Check if job is still running
            if self.job.status != JobStatusEnum.running:
                logger.info(f"QAJob {self.job_id} is not running (status={self.job.status.value}). Skipping scoring.")
                return

            # Route to appropriate scoring function
            if self.judge.judge_type == JudgeTypeEnum.claim_based:
                logger.info(f"QAJob {self.job_id}: Using claim-based scoring")
                answer_score = await self._score_claim_based()
            elif self.judge.judge_type == JudgeTypeEnum.response_level:
                logger.info(f"QAJob {self.job_id}: Using response-level scoring")
                answer_score = await self._score_response_level()
            else:
                raise ValueError(f"Unknown judge type: {self.judge.judge_type}")

            # Update job costs
            self._update_job_status()

            logger.info(f"QAJob {self.job_id}: Scoring complete with overall_label={answer_score.overall_label}")

        except Exception as e:
            logger.error(f"Answer scoring failed for job {self.job_id}: {e}", exc_info=True)

            # Update job with failure status and error message
            QAJobRepository.update_status(
                self.db,
                self.job_id,
                JobStatusEnum.failed,
                self.job.stage,
                error_message=str(e)
            )

    async def _score_claim_based(self):
        """
        Score an answer using claim-based judging.

        This function:
        1. Gets all checkworthy claims for the answer
        2. Asynchronously scores each claim using LLM
        3. Creates AnswerClaimScore records
        4. Aggregates claim scores to overall answer label
        5. Creates AnswerScore record

        Returns:
            Created AnswerScore object
        """
        # Get context for scoring - prefer RAG citations, fallback to KB documents
        target_id = self.answer.question.target_id

        if self.answer.rag_citations:
            # Priority 1: Use RAG citations from answer
            rag_chunks = [
                f"=== Source Document: {chunk['source']} (Chunk {chunk['id']}) ===\n{chunk['chunk']}"
                for i, chunk in enumerate(self.answer.rag_citations)
            ]
            kb_text = "\n\n".join(rag_chunks)
        else:
            # Priority 2: Fallback to uploaded KB documents
            kb_documents = KBDocumentRepository.get_by_target(self.db, target_id)
            if kb_documents:
                kb_text = "\n\n".join([doc.processed_text for doc in kb_documents])
            else:
                # Priority 3: Empty fallback
                kb_text = "[document is empty]"

        # Get checkworthy claims
        all_claims = AnswerClaimRepository.get_by_answer(self.db, self.answer.id)
        checkworthy_claims = [claim for claim in all_claims if claim.checkworthy]

        if not checkworthy_claims:
            logger.warning(f"No checkworthy claims found for answer {self.answer.id}. Creating default AnswerScore.")
            # No checkworthy claims - mark as accurate by default
            answer_score_data = {
                "answer_id": self.answer.id,
                "judge_id": self.judge.id,
                "overall_label": True,
                "explanation": "No checkworthy claims to evaluate"
            }
            answer_score = AnswerScoreRepository.create(self.db, answer_score_data)
            return answer_score

        # Score each claim asynchronously
        tasks = []
        for claim in checkworthy_claims:
            # Render prompt for this claim
            prompt = render_template(
                "claim_level_judge.md",
                question_text=self.answer.question.text,
                answer_text=self.answer.answer_content,
                claim_text=claim.claim_text,
                kb_documents=kb_text,
                **self.judge.params
            )

            task = self._score_single_claim(claim, prompt)
            tasks.append((claim, task))

        # Execute all tasks concurrently
        results = await asyncio.gather(*[task for _, task in tasks])

        # Aggregate claim scores
        overall_label, overall_explanation = self._aggregate_claim_scores(results)

        # Create AnswerScore first (needed for foreign key)
        answer_score_data = {
            "answer_id": self.answer.id,
            "judge_id": self.judge.id,
            "overall_label": overall_label,
            "explanation": overall_explanation
        }
        answer_score = AnswerScoreRepository.create(self.db, answer_score_data)

        # Create AnswerClaimScore records
        for (claim, _), result in zip(tasks, results):
            claim_score_data = {
                "claim_id": claim.id,
                "answer_score_id": answer_score.id,
                "label": result.label,
                "explanation": result.reasoning
            }
            AnswerClaimScoreRepository.create(self.db, claim_score_data)

        logger.info(f"Scored {len(checkworthy_claims)} claims for answer {self.answer.id}. Overall: {overall_label}")
        return answer_score

    async def _score_single_claim(self, claim, prompt: str) -> ClaimJudgmentResult:
        """
        Score a single claim using LLM judge.

        Args:
            claim: AnswerClaim to score
            prompt: Rendered prompt for the judge

        Returns:
            ClaimJudgmentResult with accuracy judgment
        """
        try:
            result, metadata = await self.llm_client.generate_structured_async(
                prompt=prompt,
                response_model=ClaimJudgmentResult,
                temperature=0.7
            )

            # Track costs
            self.cost_tracker.add_call(metadata)

            logger.debug(f"Claim {claim.id} scored: accurate={result.label}")
            return result

        except Exception as e:
            logger.error(f"Failed to score claim {claim.id}: {e}", exc_info=True)
            return ClaimJudgmentResult(
                label=False,
                reasoning=f"Error during scoring: {e}"
            )

    def _aggregate_claim_scores(self, results: List[ClaimJudgmentResult]) -> tuple[bool, str]:
        """
        Aggregate claim-level scores to overall answer label.
        All claims must be accurate for overall_label to be accurate.

        Args:
            results: List of ClaimJudgmentResult objects

        Returns:
            Tuple of (overall_label, explanation)
        """
        if not results:
            return True, "No claims to evaluate"

        accurate_count = sum(1 for r in results if r.label)
        total_count = len(results)
        accuracy_ratio = accurate_count / total_count

        overall_label = accurate_count == total_count

        explanation = (
            f"Aggregated from {total_count} claims: "
            f"{accurate_count} accurate, {total_count - accurate_count} inaccurate. "
            f"Accuracy ratio: {accuracy_ratio:.2f}"
        )

        return overall_label, explanation

    async def _score_response_level(self):
        """
        Score an answer using response-level holistic judging.

        This function:
        1. Scores the entire response with a single LLM call
        2. Creates AnswerScore record directly (no claim breakdown)

        Returns:
            Created AnswerScore object
        """
        # Get context for scoring - prefer RAG citations, fallback to KB documents
        target_id = self.answer.question.target_id

        if self.answer.rag_citations:
            # Priority 1: Use RAG citations from answer
            rag_chunks = [
                f"=== RAG Chunk {i+1} (ID: {chunk['id']}) ===\n{chunk['chunk']}"
                for i, chunk in enumerate(self.answer.rag_citations)
            ]
            kb_text = "\n\n".join(rag_chunks)
        else:
            # Priority 2: Fallback to uploaded KB documents
            kb_documents = KBDocumentRepository.get_by_target(self.db, target_id)
            if kb_documents:
                kb_text = "\n\n".join([doc.processed_text for doc in kb_documents])
            else:
                # Priority 3: Empty fallback
                kb_text = "[document is empty]"

        # Render prompt
        prompt = render_template(
            "response_level_judge.md",
            answer_text=self.answer.answer_content,
            question_text=self.answer.question.text,
            kb_documents=kb_text,
            **self.judge.params
        )

        # Call LLM
        try:
            result, metadata = await self.llm_client.generate_structured_async(
                prompt=prompt,
                response_model=ResponseJudgmentResult,
                temperature=0.7
            )

            # Track costs
            self.cost_tracker.add_call(metadata)

            # Create AnswerScore
            answer_score_data = {
                "answer_id": self.answer.id,
                "judge_id": self.judge.id,
                "overall_label": result.label,
                "explanation": result.reasoning
            }
            answer_score = AnswerScoreRepository.create(self.db, answer_score_data)

            logger.info(f"Scored answer {self.answer.id} holistically. Accurate: {result.label}")
            return answer_score

        except Exception as e:
            logger.error(f"Failed to score answer {self.answer.id}: {e}", exc_info=True)
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


async def score_answer(db: Session, job_id: int) -> None:
    """Async convenience wrapper for running the judge."""
    judge = AnswerJudge(db, job_id)
    await judge.score()
