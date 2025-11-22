"""
Service for generating answers using AIBots API.
"""

import logging
import httpx
from typing import Dict, Any

from sqlalchemy.orm import Session

from src.common.config import get_settings
from src.common.database.models import Question, Answer
from src.common.database.repositories.answer_repo import AnswerRepository
from src.common.database.repositories.question_repo import QuestionRepository

logger = logging.getLogger(__name__)
settings = get_settings()


class AnswerGenerator:
    """Generates answers for questions using AIBots API."""

    def __init__(self, db: Session):
        self.db = db

    def generate(self, question_id: int) -> Answer:
        """
        Generate an answer for a question using AIBots API.

        1. Create a chat session
        2. Send the question as a message
        3. Store and return the answer
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

        # Create chat session
        chat_id = self._create_chat(question, api_key, base_url)

        # Send message and get response
        api_response = self._send_message(chat_id, question.text, api_key, base_url)

        # Extract and store answer
        answer = self._save_answer(question, chat_id, api_response)

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

        print(f"Creating chat at: {url}")
        print(f"Payload: {payload}")

        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        print(f"Create chat response: {data}")
        return data["id"]

    def _send_message(self, chat_id: str, content: str, api_key: str, base_url: str) -> Dict[str, Any]:
        """Send a message to the chat and get the response."""
        url = f"{base_url}/chats/{chat_id}/messages?streaming=false&cloak=false"

        headers = {
            "X-ATLAS-Key": api_key,
        }

        # Using multipart/form-data as per API spec
        data = {"content": content}

        print(f"Sending message to: {url}")
        print(f"Message payload: {data}")

        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, data=data, headers=headers)
            print(f"Message response status: {response.status_code}")
            print(f"Message response body: {response.text}")
            response.raise_for_status()

        return response.json()

    def _save_answer(
        self,
        question: Question,
        chat_id: str,
        api_response: Dict[str, Any]
    ) -> Answer:
        """Extract important fields and save answer to database."""

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
        chunks = rag_obj.get("chunks", [])
        rag_citations = [{"id": chunk.get("id"), "chunk": chunk.get("chunk")} for chunk in chunks if chunk.get("chunk")]

        # Extract model
        model = api_response.get("model")

        answer_data = {
            "question_id": question.id,
            "target_id": question.target_id,
            "chat_id": chat_id,
            "message_id": api_response.get("id"),
            "answer_content": answer_content,
            "system_prompt": system_prompt,
            "model": model,
            "guardrails": guardrails,
            "rag_citations": rag_citations,
            "raw_response": api_response
        }

        answer = AnswerRepository.create(self.db, answer_data)
        logger.info(f"Saved answer {answer.id} for question {question.id}")

        return answer


def generate_answer_for_question(db: Session, question_id: int) -> Answer:
    """Convenience function to generate answer for a question."""
    generator = AnswerGenerator(db)
    return generator.generate(question_id)
