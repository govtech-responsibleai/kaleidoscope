"""
Service for scoring answers using LLM judges.
"""

import logging
from typing import List
from sqlalchemy.orm import Session

from src.common.concurrency import gather_with_concurrency
from src.common.config import get_settings

from src.common.database.models import JobStatusEnum
from src.common.database.repositories.answer_repo import AnswerRepository
from src.common.database.repositories.answer_claim_repo import AnswerClaimRepository
from src.common.database.repositories.answer_score_repo import AnswerScoreRepository
from src.common.database.repositories.answer_claim_score_repo import AnswerClaimScoreRepository
from src.common.database.repositories.judge_repo import JudgeRepository
from src.common.database.repositories.qa_job_repo import QAJobRepository
from src.common.database.repositories.kb_document_repo import KBDocumentRepository
from src.common.database.repositories.target_rubric_repo import TargetRubricRepository
from src.common.llm import LLMClient, CostTracker
from src.common.llm.provider_service import resolve_model_runtime_config_for_target
from src.common.prompts import render_template
from src.common.prompts.template_loader import get_loader
from src.common.models import ClaimJudgmentResult, RubricJudgmentResult
from src.rubric.services.prompt_files import resolve_rubric_prompt_text
from src.rubric.services.system_rubrics import negative_option_for_rubric

logger = logging.getLogger(__name__)


class AnswerJudge:
    """Service for scoring answers using LLM judges."""

    def __init__(
        self,
        db: Session,
        job_id: int,
        override_judge_id: int | None = None,
        override_rubric_id: int | None = None,
        skip_job_update: bool = False,
    ):
        """
        Initialize answer judge.

        Args:
            db: Database session
            job_id: QAJob ID for this scoring run
            override_judge_id: If set, use this judge instead of job.judge_id
            override_rubric_id: If set, use this rubric for rubric scoring
            skip_job_update: If True, don't write costs to QAJob (caller aggregates)
        """
        self.db = db
        self.job_id = job_id
        self.skip_job_update = skip_job_update
        self.cost_tracker = CostTracker(job_id=job_id)

        # Load job
        self.job = QAJobRepository.get_by_id(db, job_id)
        if not self.job:
            raise ValueError(f"QAJob {job_id} not found")

        # Load judge (override or from job)
        judge_id = override_judge_id or self.job.judge_id
        self.judge = JudgeRepository.get_by_id(db, judge_id)
        if not self.judge:
            raise ValueError(f"Judge {judge_id} not found")

        # Load answer
        self.answer = AnswerRepository.get_by_id(db, self.job.answer_id)
        if not self.answer:
            raise ValueError(f"Answer {self.job.answer_id} not found")

        # Load rubric: explicit override first, then fall back to judge's rubric_id
        self.rubric = None
        rubric_id = override_rubric_id or self.judge.rubric_id
        if rubric_id:
            self.rubric = TargetRubricRepository.get_by_id(db, rubric_id)
            if not self.rubric:
                raise ValueError(f"Rubric {rubric_id} not found")

        runtime_config = resolve_model_runtime_config_for_target(
            db,
            self.answer.question.target_id,
            self.judge.model_name,
        )
        self.llm_client = LLMClient(
            model=self.judge.model_name,
            provider_kwargs=runtime_config.litellm_kwargs,
        )

    async def score(self, raise_on_error: bool = False) -> None:
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

            # Route based on rubric.scoring_mode
            if self.rubric is None:
                raise ValueError(f"Judge {self.judge.id} must be bound to a rubric before scoring")

            if self.rubric.scoring_mode == "claim_based":
                logger.info(f"QAJob {self.job_id}: Using claim-based scoring (rubric {self.rubric.id})")
                answer_score = await self._score_claim_level()
            else:
                logger.info(f"QAJob {self.job_id}: Using response-level scoring (rubric {self.rubric.id})")
                answer_score = await self._score_response_level()

            # Update job costs
            if not self.skip_job_update:
                self._update_job_status()

            logger.info(f"QAJob {self.job_id}: Scoring complete with overall_label={answer_score.overall_label}")

        except Exception as e:
            logger.error(f"Answer scoring failed for job {self.job_id}: {e}", exc_info=True)

            # Only update job status when this scorer owns the job lifecycle.
            # When skip_job_update=True the caller (e.g. _score_single_rubric)
            # manages job status, so writing "failed" here would corrupt a job
            # that may still complete successfully via other parallel scorers.
            if not self.skip_job_update:
                QAJobRepository.update_status(
                    self.db,
                    self.job_id,
                    JobStatusEnum.failed,
                    self.job.stage,
                    error_message=str(e)
                )
            if raise_on_error:
                raise

    def _apply_language_directives(self, prompt: str) -> str:
        """
        Append language instructions to a rendered judge prompt.

        Reads ``language``, ``language_aware`` and ``language_output`` from the
        judge's params. When a language is set and at least one toggle is on, a
        short ``## Language Instructions`` block is appended. Applied post-render
        so it works uniformly for fixed, preset, and LLM-generated custom prompts
        without touching any judge template or the rubric augmenter.

        Args:
            prompt: The fully rendered judge prompt

        Returns:
            The prompt, with a language instructions block appended when configured
        """
        params = self.judge.params or {}
        language = params.get("language")
        if not language or not str(language).strip():
            return prompt
        language = str(language).strip()

        aware = bool(params.get("language_aware"))
        output = bool(params.get("language_output"))
        if not aware and not output:
            return prompt

        directives = ["", "## Language Instructions"]
        if aware:
            directives.append(
                f"- The question and answer are written in {language}. Evaluate them "
                f"fairly on their merits; do not penalise the response for not being in English."
            )
        if output:
            directives.append(
                f"- Write your reasoning and explanation in {language}. Keep any verdict "
                f"or option label exactly as specified above — do not translate the labels."
            )
        return prompt + "\n".join(directives) + "\n"

    def _resolved_rubric_id(self) -> int | None:
        if self.rubric is None:
            raise ValueError("Rubric is required for scoring")
        return self.rubric.id

    def _negative_option(self) -> str:
        if self.rubric is None:
            raise ValueError("Rubric is required for scoring")
        return negative_option_for_rubric(self.rubric)

    async def _score_claim_level(self):
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
            include_chunk_ids = len(self.answer.rag_citations) > 1
            rag_chunks = [
                (
                    f"=== Source Document: {chunk['source']}"
                    + (f" (Chunk {chunk['id']})" if include_chunk_ids and chunk.get("id") else "")
                    + f" ===\n{chunk['chunk']}"
                )
                for chunk in self.answer.rag_citations
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
                "rubric_id": self._resolved_rubric_id(),
                "judge_id": self.judge.id,
                "overall_label": self.rubric.best_option,
                "explanation": "No checkworthy claims to evaluate"
            }
            answer_score = AnswerScoreRepository.replace_for_answer_judge_rubric(self.db, answer_score_data)
            return answer_score

        rubric_prompt = resolve_rubric_prompt_text(self.rubric)
        if not rubric_prompt:
            raise ValueError(f"Claim-based rubric {self.rubric.id} is missing judge prompt content")

        # Score each claim asynchronously
        tasks = []
        for claim in checkworthy_claims:
            # Render prompt for this claim
            prompt = get_loader().render_from_string(
                rubric_prompt,
                question_text=self.answer.question.text,
                answer_text=self.answer.answer_content,
                claim_text=claim.claim_text,
                kb_documents=kb_text,
                **self.judge.params
            )
            prompt = self._apply_language_directives(prompt)

            task = self._score_single_claim(claim, prompt)
            tasks.append((claim, task))

        # Execute tasks with bounded concurrency to avoid rate limiting
        settings = get_settings()
        results = await gather_with_concurrency(
            settings.batch_max_concurrent_claims,
            *[task for _, task in tasks]
        )

        # Aggregate claim scores
        overall_label, overall_explanation = self._aggregate_claim_scores(results)

        answer_score_data = {
            "answer_id": self.answer.id,
            "rubric_id": self._resolved_rubric_id(),
            "judge_id": self.judge.id,
            "overall_label": overall_label,
            "explanation": overall_explanation,
        }

        claim_scores_data = [
            {
                "claim_id": claim.id,
                "answer_score_id": None,
                "label": result.label,
                "explanation": result.reasoning,
            }
            for (claim, _), result in zip(tasks, results)
        ]

        try:
            answer_score = AnswerScoreRepository.replace_for_answer_judge_rubric_no_commit(
                self.db,
                answer_score_data,
            )
            for claim_score_data in claim_scores_data:
                claim_score_data["answer_score_id"] = answer_score.id
            AnswerClaimScoreRepository.create_many_no_commit(self.db, claim_scores_data)
            self.db.commit()
            self.db.refresh(answer_score)
        except Exception:
            self.db.rollback()
            raise

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
                temperature=0.0,
                metadata={
                    "generation_name": "llm-judge",
                    "tags": ["llm-judge", "claim-level"],
                    "trace_metadata": {
                        "judge_name": self.judge.name,
                        "judge_level": "claim-level",
                    },
                }
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

    def _aggregate_claim_scores(self, results: List[ClaimJudgmentResult]) -> tuple[str, str]:
        """
        Aggregate claim-level scores to overall answer label.
        All claims must be accurate for overall_label to be accurate.

        Args:
            results: List of ClaimJudgmentResult objects

        Returns:
            Tuple of (overall_label, explanation)
        """
        if not results:
            return self.rubric.best_option, "No claims to evaluate"

        accurate_count = sum(1 for r in results if r.label)
        total_count = len(results)
        accuracy_ratio = accurate_count / total_count

        overall_label = self.rubric.best_option if accurate_count == total_count else self._negative_option()

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
        prompt_template = resolve_rubric_prompt_text(self.rubric)
        if prompt_template:
            loader = get_loader()
            prompt = loader.render_from_string(
                prompt_template,
                Question=self.answer.question.text,
                Answer=self.answer.answer_content,
                question_text=self.answer.question.text,
                answer_text=self.answer.answer_content,
                rubric_name=self.rubric.name,
                rubric_criteria=self.rubric.criteria,
                rubric_options=self.rubric.options,
            )
        else:
            prompt = render_template(
                "default_rubric_judge.md",
                question_text=self.answer.question.text,
                answer_text=self.answer.answer_content,
                rubric_name=self.rubric.name,
                rubric_criteria=self.rubric.criteria,
                rubric_options=self.rubric.options,
            )

        prompt = self._apply_language_directives(prompt)

        # Call LLM
        try:
            result, metadata = await self.llm_client.generate_structured_async(
                prompt=prompt,
                response_model=RubricJudgmentResult,
                temperature=0.0,
                metadata={
                    "generation_name": "llm-judge",
                    "tags": ["llm-judge", "rubric"],
                    "trace_metadata": {
                        "judge_name": self.judge.name,
                        "judge_level": "rubric",
                    },
                }
            )

            # Track costs
            self.cost_tracker.add_call(metadata)

            # Create AnswerScore
            answer_score_data = {
                "answer_id": self.answer.id,
                "rubric_id": self._resolved_rubric_id(),
                "judge_id": self.judge.id,
                "overall_label": result.chosen_option,
                "explanation": result.explanation,
            }
            answer_score = AnswerScoreRepository.replace_for_answer_judge_rubric(self.db, answer_score_data)

            logger.info(f"Scored answer {self.answer.id} holistically. Verdict: {answer_score.overall_label}")
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


async def score_answer(
    db: Session,
    job_id: int,
    override_judge_id: int | None = None,
    override_rubric_id: int | None = None,
    skip_job_update: bool = False,
) -> None:
    """Async convenience wrapper for running the judge."""
    judge = AnswerJudge(
        db, job_id,
        override_judge_id=override_judge_id,
        override_rubric_id=override_rubric_id,
        skip_job_update=skip_job_update,
    )
    await judge.score()
