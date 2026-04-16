"""
Unit tests for AnswerGenerator service.
"""

import pytest
import httpx
from unittest.mock import Mock, patch, AsyncMock

from src.query_generation.services.answer_generator import AnswerGenerator, APIResponseError, APIConnectionError
from src.common.connectors.base import ConnectorResponse, TargetHttpError
from src.common.database.models import JobStatusEnum


def _make_connector_response(**overrides):
    """Helper to build a ConnectorResponse for tests."""
    defaults = {
        "content": "AI has privacy risks and bias concerns.",
        "raw_response": {
            "id": "msg_456",
            "response": {"content": "AI has privacy risks and bias concerns."},
            "model": "gpt-4",
        },
        "model": "gpt-4",
        "tokens": None,
        "metadata": {
            "chat_id": "chat_123",
            "message_id": "msg_456",
            "system_prompt": "You are a helpful assistant",
            "guardrails": None,
            "rag_citations": [],
        },
    }
    defaults.update(overrides)
    return ConnectorResponse(**defaults)


@pytest.mark.unit
class TestAnswerGenerator:
    """Unit tests for AnswerGenerator class."""

    @patch('src.query_generation.services.answer_generator.get_connector')
    def test_generate_creates_answer(self, mock_get_connector, test_db, sample_question, sample_snapshot, sample_target):
        """Test that generating for a question creates exactly one answer."""
        sample_target.endpoint_type = "http"
        sample_target.api_endpoint = "https://api.test.com"
        sample_target.endpoint_config = {"response_content_path": "output"}
        test_db.commit()

        mock_connector = AsyncMock()
        mock_connector.send_message.return_value = _make_connector_response()
        mock_get_connector.return_value = mock_connector

        generator = AnswerGenerator(test_db)
        answer = generator.generate(sample_question.id, sample_snapshot.id)

        assert answer is not None
        assert answer.question_id == sample_question.id
        assert answer.snapshot_id == sample_snapshot.id
        assert answer.chat_id == "chat_123"
        assert answer.message_id == "msg_456"
        assert len(answer.answer_content) > 0
        mock_connector.send_message.assert_called_once_with(sample_question.text)

    @patch('src.query_generation.services.answer_generator.get_connector')
    def test_generate_different_snapshots_creates_different_answers(
        self, mock_get_connector, test_db, sample_question, sample_snapshot, sample_target
    ):
        """Test that generating for different snapshots creates answers with different IDs."""
        sample_target.endpoint_type = "http"
        sample_target.api_endpoint = "https://api.test.com"
        sample_target.endpoint_config = {"response_content_path": "output"}
        test_db.commit()

        from src.common.database.models import Snapshot
        snapshot2 = Snapshot(target_id=sample_target.id, name="v2.0", description="Second snapshot")
        test_db.add(snapshot2)
        test_db.commit()
        test_db.refresh(snapshot2)

        mock_connector = AsyncMock()
        mock_connector.send_message.return_value = _make_connector_response()
        mock_get_connector.return_value = mock_connector

        generator = AnswerGenerator(test_db)
        answer1 = generator.generate(sample_question.id, sample_snapshot.id)
        answer2 = generator.generate(sample_question.id, snapshot2.id)

        assert answer1.id != answer2.id
        assert answer1.snapshot_id == sample_snapshot.id
        assert answer2.snapshot_id == snapshot2.id

    @pytest.mark.asyncio
    @patch('src.query_generation.services.answer_generator.get_connector')
    async def test_generate_for_job_success(
        self, mock_get_connector, test_db, sample_qa_job, sample_question, sample_target
    ):
        """Test answer generation for QA job."""
        sample_target.endpoint_type = "http"
        sample_target.api_endpoint = "https://api.test.com"
        sample_target.endpoint_config = {"response_content_path": "output"}
        test_db.commit()

        mock_connector = AsyncMock()
        mock_connector.send_message.return_value = _make_connector_response()
        mock_get_connector.return_value = mock_connector

        generator = AnswerGenerator(test_db, sample_qa_job.id)
        await generator.generate_for_job(sample_question.id, sample_qa_job.snapshot_id)

        test_db.refresh(sample_qa_job)
        assert sample_qa_job.answer_id is not None

    @pytest.mark.asyncio
    async def test_generate_for_job_skips_if_answer_exists(
        self, test_db, sample_qa_job, sample_question, sample_answer
    ):
        """Test that generate_for_job skips generation if answer already exists."""
        with patch('src.query_generation.services.answer_generator.get_connector') as mock_gc:
            generator = AnswerGenerator(test_db, sample_qa_job.id)
            await generator.generate_for_job(sample_question.id, sample_qa_job.snapshot_id)
            mock_gc.assert_not_called()


@pytest.mark.unit
class TestAnswerGeneratorErrors:
    """Tests for API error handling during answer generation."""

    @pytest.mark.asyncio
    @patch('src.query_generation.services.answer_generator.get_connector')
    async def test_api_connection_error_sets_job_failed(
        self, mock_get_connector, test_db, sample_qa_job_no_answer
    ):
        """Test that connection errors mark job as failed."""
        job_data = sample_qa_job_no_answer
        qa_job = job_data["job"]
        question = job_data["question"]
        target = job_data["target"]

        target.endpoint_type = "http"
        target.api_endpoint = "https://api.invalid.com"
        target.endpoint_config = {"response_content_path": "output"}
        test_db.commit()

        mock_connector = AsyncMock()
        mock_connector.send_message.side_effect = httpx.ConnectError("Connection refused")
        mock_get_connector.return_value = mock_connector

        generator = AnswerGenerator(test_db, qa_job.id)
        await generator.generate_for_job(question.id, qa_job.snapshot_id)

        test_db.refresh(qa_job)
        assert qa_job.status == JobStatusEnum.failed
        assert "Failed to connect to API" in qa_job.error_message

    @pytest.mark.asyncio
    @patch('src.query_generation.services.answer_generator.get_connector')
    async def test_api_timeout_error_sets_job_failed(
        self, mock_get_connector, test_db, sample_qa_job_no_answer
    ):
        """Test that timeout errors mark job as failed after retries."""
        job_data = sample_qa_job_no_answer
        qa_job = job_data["job"]
        question = job_data["question"]
        target = job_data["target"]

        target.endpoint_type = "http"
        target.api_endpoint = "https://api.slow.com"
        target.endpoint_config = {"response_content_path": "output"}
        test_db.commit()

        mock_connector = AsyncMock()
        mock_connector.send_message.side_effect = httpx.TimeoutException("Request timed out")
        mock_get_connector.return_value = mock_connector

        generator = AnswerGenerator(test_db, qa_job.id)
        with patch('src.query_generation.services.answer_generator.asyncio.sleep', new_callable=AsyncMock):
            await generator.generate_for_job(question.id, qa_job.snapshot_id)

        test_db.refresh(qa_job)
        assert qa_job.status == JobStatusEnum.failed
        assert "timed out" in qa_job.error_message.lower()

    @pytest.mark.asyncio
    @patch('src.query_generation.services.answer_generator.get_connector')
    async def test_api_http_401_error_sets_job_failed(
        self, mock_get_connector, test_db, sample_qa_job_no_answer
    ):
        """Test that HTTP 401 errors mark job as failed."""
        job_data = sample_qa_job_no_answer
        qa_job = job_data["job"]
        question = job_data["question"]
        target = job_data["target"]

        target.endpoint_type = "http"
        target.api_endpoint = "https://api.error.com"
        target.endpoint_config = {"response_content_path": "output"}
        test_db.commit()

        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_connector = AsyncMock()
        mock_connector.send_message.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized", request=Mock(), response=mock_response
        )
        mock_get_connector.return_value = mock_connector

        generator = AnswerGenerator(test_db, qa_job.id)
        await generator.generate_for_job(question.id, qa_job.snapshot_id)

        test_db.refresh(qa_job)
        assert qa_job.status == JobStatusEnum.failed
        assert "401" in qa_job.error_message

    @pytest.mark.asyncio
    @patch('src.query_generation.services.answer_generator.get_connector')
    async def test_api_http_500_error_sets_job_failed(
        self, mock_get_connector, test_db, sample_qa_job_no_answer
    ):
        """Test that HTTP 500 server errors are captured correctly."""
        job_data = sample_qa_job_no_answer
        qa_job = job_data["job"]
        question = job_data["question"]
        target = job_data["target"]

        target.endpoint_type = "http"
        target.api_endpoint = "https://api.broken.com"
        target.endpoint_config = {"response_content_path": "output"}
        test_db.commit()

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_connector = AsyncMock()
        mock_connector.send_message.side_effect = httpx.HTTPStatusError(
            "500 Internal Server Error", request=Mock(), response=mock_response
        )
        mock_get_connector.return_value = mock_connector

        generator = AnswerGenerator(test_db, qa_job.id)
        await generator.generate_for_job(question.id, qa_job.snapshot_id)

        test_db.refresh(qa_job)
        assert qa_job.status == JobStatusEnum.failed
        assert "500" in qa_job.error_message

    @pytest.mark.asyncio
    @patch('src.query_generation.services.answer_generator.get_connector')
    async def test_target_http_401_error_sets_job_failed(
        self, mock_get_connector, test_db, sample_qa_job_no_answer
    ):
        """Normalized connector HTTP 401 errors still fail the job clearly."""
        job_data = sample_qa_job_no_answer
        qa_job = job_data["job"]
        question = job_data["question"]
        target = job_data["target"]

        target.endpoint_type = "http"
        target.api_endpoint = "https://api.error.com"
        target.endpoint_config = {"response_content_path": "output"}
        test_db.commit()

        mock_connector = AsyncMock()
        mock_connector.send_message.side_effect = TargetHttpError(
            status_code=401,
            body="Unauthorized",
            headers={"content-type": "text/plain"},
        )
        mock_get_connector.return_value = mock_connector

        generator = AnswerGenerator(test_db, qa_job.id)
        await generator.generate_for_job(question.id, qa_job.snapshot_id)

        test_db.refresh(qa_job)
        assert qa_job.status == JobStatusEnum.failed
        assert "401" in qa_job.error_message


@pytest.mark.unit
class TestAnswerGeneratorRetry:
    """Tests for retry behavior in generate_async."""

    def _make_http_error(self, status_code, text="Error"):
        mock_response = Mock()
        mock_response.status_code = status_code
        mock_response.text = text
        return httpx.HTTPStatusError(
            f"{status_code} Error", request=Mock(), response=mock_response
        )

    def _make_target_http_error(self, status_code, text="Error"):
        return TargetHttpError(
            status_code=status_code,
            body=text,
            headers={"content-type": "text/plain"},
        )

    @pytest.mark.asyncio
    @patch('src.query_generation.services.answer_generator.asyncio.sleep', new_callable=AsyncMock)
    @patch('src.query_generation.services.answer_generator.get_connector')
    async def test_retry_on_429_succeeds(
        self, mock_get_connector, mock_sleep, test_db, sample_qa_job_no_answer
    ):
        """429 on first attempt, success on second."""
        job_data = sample_qa_job_no_answer
        qa_job = job_data["job"]
        question = job_data["question"]
        target = job_data["target"]

        target.endpoint_type = "http"
        target.api_endpoint = "https://api.test.com"
        target.endpoint_config = {"response_content_path": "output"}
        test_db.commit()

        mock_connector = AsyncMock()
        mock_connector.send_message.side_effect = [
            self._make_http_error(429, "Rate limited"),
            _make_connector_response(),
        ]
        mock_get_connector.return_value = mock_connector

        generator = AnswerGenerator(test_db, qa_job.id)
        await generator.generate_for_job(question.id, qa_job.snapshot_id)

        test_db.refresh(qa_job)
        assert qa_job.status != JobStatusEnum.failed
        assert qa_job.answer_id is not None
        mock_sleep.assert_awaited_once_with(1)

    @pytest.mark.asyncio
    @patch('src.query_generation.services.answer_generator.asyncio.sleep', new_callable=AsyncMock)
    @patch('src.query_generation.services.answer_generator.get_connector')
    async def test_retry_on_503_succeeds(
        self, mock_get_connector, mock_sleep, test_db, sample_qa_job_no_answer
    ):
        """503 on first attempt, success on second."""
        job_data = sample_qa_job_no_answer
        qa_job = job_data["job"]
        question = job_data["question"]
        target = job_data["target"]

        target.endpoint_type = "http"
        target.api_endpoint = "https://api.test.com"
        target.endpoint_config = {"response_content_path": "output"}
        test_db.commit()

        mock_connector = AsyncMock()
        mock_connector.send_message.side_effect = [
            self._make_http_error(503, "Service Unavailable"),
            _make_connector_response(),
        ]
        mock_get_connector.return_value = mock_connector

        generator = AnswerGenerator(test_db, qa_job.id)
        await generator.generate_for_job(question.id, qa_job.snapshot_id)

        test_db.refresh(qa_job)
        assert qa_job.status != JobStatusEnum.failed
        assert qa_job.answer_id is not None
        mock_sleep.assert_awaited_once_with(1)

    @pytest.mark.asyncio
    @patch('src.query_generation.services.answer_generator.asyncio.sleep', new_callable=AsyncMock)
    @patch('src.query_generation.services.answer_generator.get_connector')
    async def test_retry_on_target_http_429_succeeds(
        self, mock_get_connector, mock_sleep, test_db, sample_qa_job_no_answer
    ):
        """Normalized TargetHttpError 429 retries and then succeeds."""
        job_data = sample_qa_job_no_answer
        qa_job = job_data["job"]
        question = job_data["question"]
        target = job_data["target"]

        target.endpoint_type = "http"
        target.api_endpoint = "https://api.test.com"
        target.endpoint_config = {"response_content_path": "output"}
        test_db.commit()

        mock_connector = AsyncMock()
        mock_connector.send_message.side_effect = [
            self._make_target_http_error(429, "Rate limited"),
            _make_connector_response(),
        ]
        mock_get_connector.return_value = mock_connector

        generator = AnswerGenerator(test_db, qa_job.id)
        await generator.generate_for_job(question.id, qa_job.snapshot_id)

        test_db.refresh(qa_job)
        assert qa_job.status != JobStatusEnum.failed
        assert qa_job.answer_id is not None
        mock_sleep.assert_awaited_once_with(1)

    @pytest.mark.asyncio
    @patch('src.query_generation.services.answer_generator.asyncio.sleep', new_callable=AsyncMock)
    @patch('src.query_generation.services.answer_generator.get_connector')
    async def test_retry_on_target_http_503_succeeds(
        self, mock_get_connector, mock_sleep, test_db, sample_qa_job_no_answer
    ):
        """Normalized TargetHttpError 503 retries and then succeeds."""
        job_data = sample_qa_job_no_answer
        qa_job = job_data["job"]
        question = job_data["question"]
        target = job_data["target"]

        target.endpoint_type = "http"
        target.api_endpoint = "https://api.test.com"
        target.endpoint_config = {"response_content_path": "output"}
        test_db.commit()

        mock_connector = AsyncMock()
        mock_connector.send_message.side_effect = [
            self._make_target_http_error(503, "Service unavailable"),
            _make_connector_response(),
        ]
        mock_get_connector.return_value = mock_connector

        generator = AnswerGenerator(test_db, qa_job.id)
        await generator.generate_for_job(question.id, qa_job.snapshot_id)

        test_db.refresh(qa_job)
        assert qa_job.status != JobStatusEnum.failed
        assert qa_job.answer_id is not None
        mock_sleep.assert_awaited_once_with(1)

    @pytest.mark.asyncio
    @patch('src.query_generation.services.answer_generator.asyncio.sleep', new_callable=AsyncMock)
    @patch('src.query_generation.services.answer_generator.get_connector')
    async def test_retry_on_timeout_succeeds(
        self, mock_get_connector, mock_sleep, test_db, sample_qa_job_no_answer
    ):
        """Timeout on first attempt, success on second."""
        job_data = sample_qa_job_no_answer
        qa_job = job_data["job"]
        question = job_data["question"]
        target = job_data["target"]

        target.endpoint_type = "http"
        target.api_endpoint = "https://api.test.com"
        target.endpoint_config = {"response_content_path": "output"}
        test_db.commit()

        mock_connector = AsyncMock()
        mock_connector.send_message.side_effect = [
            httpx.ReadTimeout("Read timed out"),
            _make_connector_response(),
        ]
        mock_get_connector.return_value = mock_connector

        generator = AnswerGenerator(test_db, qa_job.id)
        await generator.generate_for_job(question.id, qa_job.snapshot_id)

        test_db.refresh(qa_job)
        assert qa_job.status != JobStatusEnum.failed
        assert qa_job.answer_id is not None

    @pytest.mark.asyncio
    @patch('src.query_generation.services.answer_generator.asyncio.sleep', new_callable=AsyncMock)
    @patch('src.query_generation.services.answer_generator.get_connector')
    async def test_retry_exhaustion_fails(
        self, mock_get_connector, mock_sleep, test_db, sample_qa_job_no_answer
    ):
        """429 on every attempt exhausts retries and fails."""
        job_data = sample_qa_job_no_answer
        qa_job = job_data["job"]
        question = job_data["question"]
        target = job_data["target"]

        target.endpoint_type = "http"
        target.api_endpoint = "https://api.test.com"
        target.endpoint_config = {"response_content_path": "output"}
        test_db.commit()

        mock_connector = AsyncMock()
        mock_connector.send_message.side_effect = self._make_http_error(429, "Rate limited")
        mock_get_connector.return_value = mock_connector

        generator = AnswerGenerator(test_db, qa_job.id)
        await generator.generate_for_job(question.id, qa_job.snapshot_id)

        test_db.refresh(qa_job)
        assert qa_job.status == JobStatusEnum.failed
        assert qa_job.error_message is not None

    @pytest.mark.asyncio
    @patch('src.query_generation.services.answer_generator.asyncio.sleep', new_callable=AsyncMock)
    @patch('src.query_generation.services.answer_generator.get_connector')
    async def test_target_http_retry_exhaustion_fails(
        self, mock_get_connector, mock_sleep, test_db, sample_qa_job_no_answer
    ):
        """Repeated normalized TargetHttpError 429 exhausts retries and fails."""
        job_data = sample_qa_job_no_answer
        qa_job = job_data["job"]
        question = job_data["question"]
        target = job_data["target"]

        target.endpoint_type = "http"
        target.api_endpoint = "https://api.test.com"
        target.endpoint_config = {"response_content_path": "output"}
        test_db.commit()

        mock_connector = AsyncMock()
        mock_connector.send_message.side_effect = self._make_target_http_error(429, "Rate limited")
        mock_get_connector.return_value = mock_connector

        generator = AnswerGenerator(test_db, qa_job.id)
        await generator.generate_for_job(question.id, qa_job.snapshot_id)

        test_db.refresh(qa_job)
        assert qa_job.status == JobStatusEnum.failed
        assert qa_job.error_message is not None
