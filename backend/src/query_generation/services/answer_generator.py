"""
Service for generating answers from target application endpoints.

Uses the connector abstraction to support AIBots, generic HTTP, and
any future endpoint types.
"""

import asyncio
import logging

import httpx
from sqlalchemy.orm import Session

from src.common.config import get_settings
from src.common.connectors import ConnectorResponse, get_connector
from src.common.database.models import Answer, JobStatusEnum
from src.common.database.repositories import (
    AnswerRepository,
    QAJobRepository,
    QuestionRepository,
)
from src.common.llm import CostTracker

logger = logging.getLogger(__name__)
settings = get_settings()


class AnswerGenerationError(Exception):
    """Base exception for answer generation errors."""
    pass


class APIConnectionError(AnswerGenerationError):
    """Raised when unable to connect to the API endpoint."""
    pass


class APIResponseError(AnswerGenerationError):
    """Raised when API returns an error response or empty content."""
    pass


class AnswerGenerator:
    """Generates answers for questions by calling the target's endpoint."""

    def __init__(self, db: Session, job_id: int = None):
        """
        Args:
            db: Database session
            job_id: Optional QAJob ID for job tracking
        """
        self.db = db
        self.job_id = job_id
        self.job = None
        self.cost_tracker = None

        if job_id is not None:
            self.job = QAJobRepository.get_by_id(db, job_id)
            if not self.job:
                raise ValueError(f"QAJob {job_id} not found")
            self.cost_tracker = CostTracker(job_id=job_id)

    # ---- Synchronous entry point ----

    def generate(self, question_id: int, snapshot_id: int = None) -> Answer:
        """Generate an answer for a question (sync wrapper over async)."""
        return asyncio.get_event_loop().run_until_complete(
            self.generate_async(question_id, snapshot_id)
        )

    # ---- Async entry points ----

    async def generate_for_job(self, question_id: int, snapshot_id: int) -> None:
        """Generate answer as part of a QA job pipeline."""
        if self.job_id is None or self.job is None:
            raise ValueError("generate_for_job requires job_id to be set in __init__")

        try:
            if self.job.status != JobStatusEnum.running:
                logger.info(f"QAJob {self.job_id} is not running (status={self.job.status.value}). Skipping.")
                return

            existing_answer = AnswerRepository.get_by_question_and_snapshot(
                self.db, question_id, snapshot_id
            )

            if existing_answer:
                answer = existing_answer
                logger.info(f"Answer already exists for question {question_id}, snapshot {snapshot_id}. Skipping.")
            else:
                answer = await self.generate_async(question_id, snapshot_id)
                logger.info(f"Generated answer {answer.id} for question {question_id}, snapshot {snapshot_id}")

            self._update_job(answer_id=answer.id)

        except Exception as e:
            logger.error(f"Answer generation failed for job {self.job_id}: {e}", exc_info=True)
            QAJobRepository.update_status(
                self.db,
                self.job_id,
                JobStatusEnum.failed,
                self.job.stage,
                error_message=str(e),
            )

    async def generate_async(self, question_id: int, snapshot_id: int = None) -> Answer:
        """Generate an answer for a question using the target's connector."""
        question = QuestionRepository.get_by_id(self.db, question_id)
        if not question:
            raise ValueError(f"Question with id {question_id} not found")

        target = question.target
        connector = get_connector(target)  # Raises ValueError for bad config

        max_retries = settings.llm_num_retries

        for attempt in range(max_retries + 1):
            try:
                response = await connector.send_message(question.text)
                return self._save_answer(question, response, snapshot_id)

            except httpx.HTTPStatusError as e:
                if e.response.status_code in (429, 503) and attempt < max_retries:
                    wait = 2 ** attempt
                    logger.warning(
                        f"Target API returned {e.response.status_code}, retrying in {wait}s "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait)
                    continue
                raise APIResponseError(
                    f"API returned error {e.response.status_code}: {e.response.text}"
                )
            except httpx.TimeoutException as e:
                if attempt < max_retries:
                    wait = 2 ** attempt
                    logger.warning(
                        f"Target API timed out, retrying in {wait}s "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait)
                    continue
                raise APIConnectionError(f"Connection to API timed out: {e}")
            except httpx.ConnectError as e:
                raise APIConnectionError(f"Failed to connect to API at {target.api_endpoint}: {e}")
            except AnswerGenerationError:
                raise
            except Exception as e:
                raise APIResponseError(f"Unexpected error from API: {e}")

        raise APIResponseError(f"API rate limit exceeded after {max_retries} retries")

    # ---- Internal helpers ----

    def _save_answer(
        self,
        question,
        response: ConnectorResponse,
        snapshot_id: int = None,
    ) -> Answer:
        """Persist a ConnectorResponse as an Answer record."""
        meta = response.metadata or {}

        answer_data = {
            "question_id": question.id,
            "chat_id": meta.get("chat_id"),
            "message_id": meta.get("message_id"),
            "answer_content": response.content,
            "system_prompt": meta.get("system_prompt"),
            "model": response.model,
            "guardrails": meta.get("guardrails"),
            "rag_citations": meta.get("rag_citations"),
            "raw_response": response.raw_response,
            "is_selected_for_annotation": False,
        }

        if snapshot_id is not None:
            answer_data["snapshot_id"] = snapshot_id

        answer = AnswerRepository.create(self.db, answer_data)
        logger.info(f"Saved answer {answer.id} for question {question.id}")
        return answer

    def _update_job(self, answer_id: int = None) -> None:
        """Update job with answer_id and costs."""
        if self.cost_tracker is None:
            return

        summary = self.cost_tracker.get_summary()
        QAJobRepository.update_status(
            self.db,
            self.job_id,
            status=self.job.status,
            stage=self.job.stage,
            answer_id=answer_id,
            prompt_tokens=summary["prompt_tokens"],
            completion_tokens=summary["completion_tokens"],
            total_cost=summary["total_cost"],
        )
        logger.info(f"Updated QAJob {self.job_id} costs: ${summary['total_cost']:.4f}")


def generate_answer_for_question(db: Session, question_id: int) -> Answer:
    """Convenience function to generate answer for a question."""
    generator = AnswerGenerator(db)
    return generator.generate(question_id)


async def generate_answer_for_job(
    db: Session, job_id: int, question_id: int, snapshot_id: int
) -> None:
    """Async convenience wrapper for QA job pipeline."""
    generator = AnswerGenerator(db, job_id)
    await generator.generate_for_job(question_id, snapshot_id)
