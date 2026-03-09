"""
Service for generating answers using AIBots API.
"""

import asyncio
import logging
import httpx
from typing import Dict, Any

from sqlalchemy.orm import Session

from src.common.config import get_settings
from src.common.database.models import Question, Answer, QAJob, JobStatusEnum
from src.common.database.repositories import (
    AnswerRepository,
    QuestionRepository,
    QAJobRepository,
    KBDocumentRepository
)
from src.common.llm import CostTracker

logger = logging.getLogger(__name__)
settings = get_settings()


class AnswerGenerationError(Exception):
    """Base exception for answer generation errors."""
    pass


class APIConnectionError(AnswerGenerationError):
    """Raised when unable to connect to the API endpoint (DNS failure, network unreachable, etc.)."""
    pass


class APIResponseError(AnswerGenerationError):
    """Raised when API returns an error response (4xx, 5xx) or empty content."""
    pass


class AnswerGenerator:
    """Generates answers for questions using AIBots API."""

    def __init__(self, db: Session, job_id: int = None):
        """
        Initialize answer generator.

        Args:
            db: Database session
            job_id: Optional QAJob ID for job tracking
        """
        self.db = db
        self.job_id = job_id
        self.job = None
        self.cost_tracker = None

        # Load job if provided
        if job_id is not None:
            self.job = QAJobRepository.get_by_id(db, job_id)
            if not self.job:
                raise ValueError(f"QAJob {job_id} not found")
            self.cost_tracker = CostTracker(job_id=job_id)

    #######################
    # Synchronous methods #
    #######################
    def generate(self, question_id: int, snapshot_id: int = None) -> Answer:
        """
        Generate an answer for a question using AIBots API.

        1. Create a chat session
        2. Send the question as a message
        3. Store and return the answer

        Args:
            question_id: ID of the question to generate answer for
            snapshot_id: Optional snapshot ID to associate with the answer

        Returns:
            Created Answer object
        """
        # Get the question
        question = QuestionRepository.get_by_id(self.db, question_id)
        if not question:
            raise ValueError(f"Question with id {question_id} not found")

        # Get endpoint config from target
        target = question.target
        if not target.endpoint_type or target.endpoint_type != "aibots":
            raise ValueError(f"Target {target.id} endpoint type '{target.endpoint_type}' not supported. Only 'aibots' is supported.")

        if not target.api_endpoint:
            raise ValueError(f"Target {target.id} missing api_endpoint")

        config = target.endpoint_config or {}
        api_key = config.get("api_key")

        if not api_key:
            raise ValueError(f"Target {target.id} missing api_key in endpoint_config")

        base_url = target.api_endpoint.rstrip("/")

        try:
            # Create chat session
            chat_id = self._create_chat(question, api_key, base_url)

            # Send message and get response
            api_response = self._send_message(chat_id, question.text, api_key, base_url)

            # Extract and store answer
            answer = self._save_answer(question, chat_id, api_response, snapshot_id)

        except httpx.ConnectError as e:
            raise APIConnectionError(f"Failed to connect to API at {base_url}: {e}")
        except httpx.TimeoutException as e:
            raise APIConnectionError(f"Connection to API timed out: {e}")
        except httpx.HTTPStatusError as e:
            raise APIResponseError(f"API returned error {e.response.status_code}: {e.response.text}")
        except Exception as e:
            raise APIResponseError(f"Unexpected error from API: {e}")

        return answer

    def _create_chat(self, question: Question, api_key: str, base_url: str) -> str:
        """Create a new chat session with AIBots API."""
        url = f"{base_url}/chats"

        payload = {
            "name": f"Kaleidoscope - Q{question.id}",
            "agents": []
        }

        headers = {
            "X-ATLAS-Key": api_key,
            "Content-Type": "application/json"
        }

        logger.info(f"Creating chat at: {url}")
        logger.debug(f"Payload: {payload}")

        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        logger.debug(f"Create chat response: {data}")
        return data["id"]

    def _send_message(self, chat_id: str, content: str, api_key: str, base_url: str) -> Dict[str, Any]:
        """Send a message to the chat and get the response."""
        url = f"{base_url}/chats/{chat_id}/messages?streaming=false&cloak=false"

        headers = {
            "X-ATLAS-Key": api_key,
        }

        # Using multipart/form-data as per API spec
        data = {"content": content}

        logger.debug(f"Sending message to: {url}")
        logger.debug(f"Message payload: {data}")

        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, data=data, headers=headers)
            logger.debug(f"Message response status: {response.status_code}")
            logger.debug(f"Message response body: {response.text}")
            response.raise_for_status()

        return response.json()

    def _save_answer(
        self,
        question: Question,
        chat_id: str,
        api_response: Dict[str, Any],
        snapshot_id: int = None
    ) -> Answer:
        """
        Extract important fields and save answer to database.

        Args:
            question: Question object
            chat_id: AIBots chat ID
            api_response: Raw API response
            snapshot_id: Optional snapshot ID to associate with answer

        Returns:
            Created Answer object
        """
        # Extract response content
        response_obj = api_response.get("response", {})
        answer_content = response_obj.get("content", "")

        # Extract system prompt
        system_prompt_obj = api_response.get("systemPrompt", {})
        system_prompt = system_prompt_obj.get("content")

        # Extract guardrails from response
        guardrails = response_obj.get("guardrails")

        # Extract RAG chunks
        rag_obj = api_response.get("rag", {})
        rag_citations = rag_obj.get("chunks", [])
        # rag_citations = [{"id": chunk.get("id"), "chunk": chunk.get("chunk")} for chunk in chunks if chunk.get("chunk")]

        # Extract model
        model = api_response.get("model")

        answer_data = {
            "question_id": question.id,
            "chat_id": chat_id,
            "message_id": api_response.get("id"),
            "answer_content": answer_content,
            "system_prompt": system_prompt,
            "model": model,
            "guardrails": guardrails,
            "rag_citations": rag_citations,
            "raw_response": api_response,
            "is_selected_for_annotation": False
        }

        # Add snapshot_id if provided
        if snapshot_id is not None:
            answer_data["snapshot_id"] = snapshot_id

        answer = AnswerRepository.create(self.db, answer_data)
        logger.info(f"Saved answer {answer.id} for question {question.id}")

        return answer

    ########################
    # Asynchronous methods #
    ########################
    async def generate_for_job(self, question_id: int, snapshot_id: int) -> None:
        """
        Generate answer for a QA job with status tracking.

        This is part of the QA job pipeline and:
        1. Checks if the job is still running (exits if paused/completed)
        2. Updates the job stage to "generating_answers"
        3. Checks if answer already exists, otherwise generates it
        4. Updates job costs
        5. Calls the next pipeline stage (claim processing)

        Args:
            question_id: Question ID to generate answer for
            snapshot_id: Snapshot ID for the answer

        Raises:
            ValueError: If called without job_id in __init__
        """
        if self.job_id is None or self.job is None:
            raise ValueError("generate_for_job requires job_id to be set in __init__")

        try:
            # Check if job is still running
            if self.job.status != JobStatusEnum.running:
                logger.info(f"QAJob {self.job_id} is not running (status={self.job.status.value}). Skipping answer generation.")
                return

            # Check if answer already exists
            existing_answer = AnswerRepository.get_by_question_and_snapshot(self.db, question_id, snapshot_id)

            if existing_answer:
                # Valid answer exists, reuse it
                answer = existing_answer
                logger.info(f"Answer already exists for question {question_id}, snapshot {snapshot_id}. Skipping generation.")
            else:
                # Generate new answer
                answer = await self.generate_async(question_id, snapshot_id)
                logger.info(f"Generated answer {answer.id} for question {question_id}, snapshot {snapshot_id}")

            # Update job with answer_id and costs
            self._update_job(answer_id=answer.id)

        except Exception as e:
            logger.error(f"Answer generation failed for job {self.job_id}: {e}", exc_info=True)

            # Mark job as failed with error message
            QAJobRepository.update_status(
                self.db,
                self.job_id,
                JobStatusEnum.failed,
                self.job.stage,
                error_message=str(e)
            )

    
    async def generate_async(self, question_id: int, snapshot_id: int = None) -> Answer:
        """
        Async variant of generate() for use in asyncio pipelines.

        Args:
            question_id: ID of the question to generate answer for
            snapshot_id: Optional snapshot ID to associate with the answer

        Returns:
            Created Answer object
        """
        question = QuestionRepository.get_by_id(self.db, question_id)
        if not question:
            raise ValueError(f"Question with id {question_id} not found")

        target = question.target
        if not target.endpoint_type or target.endpoint_type != "aibots":
            raise ValueError(f"Target {target.id} endpoint type '{target.endpoint_type}' not supported. Only 'aibots' is supported.")

        if not target.api_endpoint:
            raise ValueError(f"Target {target.id} missing api_endpoint")

        config = target.endpoint_config or {}
        api_key = config.get("api_key")

        if not api_key:
            raise ValueError(f"Target {target.id} missing api_key in endpoint_config")

        base_url = target.api_endpoint.rstrip("/")

        try:
            # Create chat session
            chat_id = await self._create_chat_async(question, api_key, base_url)

            # Send message and get response
            api_response = await self._send_message_async(chat_id, question.text, api_key, base_url)

            # Extract and store answer
            answer = await self._save_answer_async(question, chat_id, api_response, snapshot_id)

        except httpx.ConnectError as e:
            raise APIConnectionError(f"Failed to connect to API at {base_url}: {e}")
        except httpx.TimeoutException as e:
            raise APIConnectionError(f"Connection to API timed out: {e}")
        except httpx.HTTPStatusError as e:
            raise APIResponseError(f"API returned error {e.response.status_code}: {e.response.text}")
        except Exception as e:
            raise APIResponseError(f"Unexpected error from API: {e}")

        return answer
    

    async def _create_chat_async(self, question: Question, api_key: str, base_url: str) -> str:
        """Async helper mirroring _create_chat to avoid blocking."""
        url = f"{base_url}/chats"

        payload = {
            "name": f"Kaleidoscope - Q{question.id}",
            "agents": []
        }

        headers = {
            "X-ATLAS-Key": api_key,
            "Content-Type": "application/json"
        }

        logger.debug(f"[async] Creating chat at: {url}")
        logger.debug(f"[async] Payload: {payload}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        logger.debug(f"[async] Create chat response: {data}")
        return data["id"]

    async def _send_message_async(self, chat_id: str, content: str, api_key: str, base_url: str) -> Dict[str, Any]:
        """Async helper mirroring _send_message."""
        url = f"{base_url}/chats/{chat_id}/messages?streaming=false&cloak=false"

        headers = {
            "X-ATLAS-Key": api_key,
        }

        data = {"content": content}

        logger.debug(f"[async] Sending message to: {url}")
        logger.debug(f"[async] Message payload: {data}")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, data=data, headers=headers)
            logger.debug(f"[async] Message response status: {response.status_code}")
            logger.debug(f"[async] Message response body: {response.text}")
            response.raise_for_status()

        return response.json()

    async def _save_answer_async(
        self,
        question: Question,
        chat_id: str,
        api_response: Dict[str, Any],
        snapshot_id: int = None
    ) -> Answer:
        """Async wrapper for _save_answer to maintain API symmetry."""
        return self._save_answer(question, chat_id, api_response, snapshot_id)

    def _update_job(self, answer_id: int = None) -> None:
        """
        Update job with answer_id and costs in database.

        Args:
            answer_id: Optional answer ID to set
        """
        if self.cost_tracker is None:
            return

        summary = self.cost_tracker.get_summary()

        # Update job using repository (keeps current status/stage, adds costs, sets answer_id)
        QAJobRepository.update_status(
            self.db,
            self.job_id,
            status=self.job.status,  # Keep current status
            stage=self.job.stage,    # Keep current stage
            answer_id=answer_id,
            prompt_tokens=summary["prompt_tokens"],
            completion_tokens=summary["completion_tokens"],
            total_cost=summary["total_cost"]
        )

        logger.info(f"Updated QAJob {self.job_id} costs: ${summary['total_cost']:.4f}")


def generate_answer_for_question(db: Session, question_id: int) -> Answer:
    """Convenience function to generate answer for a question."""
    generator = AnswerGenerator(db)
    return generator.generate(question_id)

async def generate_answer_for_job(db: Session, job_id: int, question_id: int, snapshot_id: int) -> None:
    """Async convenience wrapper for QA job pipeline."""
    generator = AnswerGenerator(db, job_id)
    await generator.generate_for_job(question_id, snapshot_id)
