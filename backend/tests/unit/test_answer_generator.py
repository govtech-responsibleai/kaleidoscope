"""
Unit tests for AnswerGenerator service.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock

from src.query_generation.services.answer_generator import AnswerGenerator
from src.common.database.models import JobStatusEnum, QAJobStageEnum


@pytest.mark.unit
class TestAnswerGenerator:
    """Unit tests for AnswerGenerator class."""

    @patch('src.query_generation.services.answer_generator.httpx.Client')
    def test_generate_creates_answer(self, mock_httpx_client, test_db, sample_question, sample_snapshot, sample_target):
        """Test that generating for a question creates exactly one answer."""
        # Setup target with AIBots endpoint
        sample_target.endpoint_type = "aibots"
        sample_target.api_endpoint = "https://api.test.com"
        sample_target.endpoint_config = {"api_key": "test_key"}
        test_db.commit()

        # Mock httpx responses
        mock_client_instance = MagicMock()
        mock_httpx_client.return_value.__enter__.return_value = mock_client_instance

        # Mock chat creation
        mock_client_instance.post.return_value.json.return_value = {"id": "chat123"}
        mock_client_instance.post.return_value.raise_for_status = Mock()

        # Setup for message send (second post call)
        message_response = {
            "id": "msg456",
            "response": {"content": "AI has privacy risks and bias concerns."},
            "systemPrompt": {"content": "You are a helpful assistant"},
            "model": "gpt-4",
            "rag": {"chunks": []},
        }

        def side_effect(*args, **kwargs):
            # First call is chat creation, second is message
            if 'chats' in args[0] and 'messages' not in args[0]:
                mock_response = Mock()
                mock_response.json.return_value = {"id": "chat123"}
                mock_response.raise_for_status = Mock()
                return mock_response
            else:
                mock_response = Mock()
                mock_response.json.return_value = message_response
                mock_response.raise_for_status = Mock()
                return mock_response

        mock_client_instance.post.side_effect = side_effect

        # Generate answer
        generator = AnswerGenerator(test_db)
        answer = generator.generate(sample_question.id, sample_snapshot.id)

        # Verify answer created
        assert answer is not None
        assert answer.question_id == sample_question.id
        assert answer.snapshot_id == sample_snapshot.id
        assert answer.chat_id is not None
        assert answer.message_id is not None
        assert len(answer.answer_content) > 0

    @patch('src.query_generation.services.answer_generator.httpx.Client')
    def test_generate_different_snapshots_creates_different_answers(
        self, mock_httpx_client, test_db, sample_question, sample_snapshot, sample_target
    ):
        """Test that generating for different snapshots creates answers with different IDs."""
        # Setup target
        sample_target.endpoint_type = "aibots"
        sample_target.api_endpoint = "https://api.test.com"
        sample_target.endpoint_config = {"api_key": "test_key"}
        test_db.commit()

        # Create second snapshot
        from src.common.database.models import Snapshot
        snapshot2 = Snapshot(
            target_id=sample_target.id,
            name="v2.0",
            description="Second snapshot"
        )
        test_db.add(snapshot2)
        test_db.commit()
        test_db.refresh(snapshot2)

        # Mock httpx responses
        mock_client_instance = MagicMock()
        mock_httpx_client.return_value.__enter__.return_value = mock_client_instance

        message_response = {
            "id": "msg_test",
            "response": {"content": "Test answer content"},
            "systemPrompt": {"content": "System"},
            "model": "gpt-4",
            "rag": {"chunks": []},
        }

        def side_effect(*args, **kwargs):
            if 'chats' in args[0] and 'messages' not in args[0]:
                mock_response = Mock()
                mock_response.json.return_value = {"id": "chat_test"}
                mock_response.raise_for_status = Mock()
                return mock_response
            else:
                mock_response = Mock()
                mock_response.json.return_value = message_response
                mock_response.raise_for_status = Mock()
                return mock_response

        mock_client_instance.post.side_effect = side_effect

        # Generate for first snapshot
        generator = AnswerGenerator(test_db)
        answer1 = generator.generate(sample_question.id, sample_snapshot.id)

        # Reset mock
        mock_client_instance.post.side_effect = side_effect

        # Generate for second snapshot
        answer2 = generator.generate(sample_question.id, snapshot2.id)

        # Verify different answers created
        assert answer1.id != answer2.id
        assert answer1.snapshot_id == sample_snapshot.id
        assert answer2.snapshot_id == snapshot2.id
        assert answer1.question_id == answer2.question_id

    @pytest.mark.asyncio
    @patch('src.query_generation.services.answer_generator.httpx.Client')
    @patch('src.scoring.services.claim_processor.extract_and_check_claims', new_callable=AsyncMock)
    async def test_generate_for_job_success(
        self, mock_extract_claims, mock_httpx_client, test_db, sample_qa_job, sample_question, sample_target
    ):
        """Test answer generation for QA job updates job status and calls next stage."""
        # Setup target
        sample_target.endpoint_type = "aibots"
        sample_target.api_endpoint = "https://api.test.com"
        sample_target.endpoint_config = {"api_key": "test_key"}
        test_db.commit()

        # Mock httpx
        mock_client_instance = MagicMock()
        mock_httpx_client.return_value.__enter__.return_value = mock_client_instance

        message_response = {
            "id": "msg_job",
            "response": {"content": "Job answer content"},
            "systemPrompt": {"content": "System"},
            "model": "gpt-4",
            "rag": {"chunks": []},
        }

        def side_effect(*args, **kwargs):
            if 'chats' in args[0] and 'messages' not in args[0]:
                mock_response = Mock()
                mock_response.json.return_value = {"id": "chat_job"}
                mock_response.raise_for_status = Mock()
                return mock_response
            else:
                mock_response = Mock()
                mock_response.json.return_value = message_response
                mock_response.raise_for_status = Mock()
                return mock_response

        mock_client_instance.post.side_effect = side_effect

        # Generate for job
        generator = AnswerGenerator(test_db, sample_qa_job.id)
        await generator.generate_for_job(sample_question.id, sample_qa_job.snapshot_id)

        # Verify job stage updated
        test_db.refresh(sample_qa_job)
        assert sample_qa_job.stage == QAJobStageEnum.generating_answers

        # Verify next stage called
        mock_extract_claims.assert_awaited_once_with(test_db, sample_qa_job.id)

    @pytest.mark.asyncio
    @patch('src.query_generation.services.answer_generator.httpx.Client')
    @patch('src.scoring.services.claim_processor.extract_and_check_claims', new_callable=AsyncMock)
    async def test_generate_for_job_skips_if_answer_exists(
        self, mock_extract_claims, mock_httpx_client, test_db, sample_qa_job, sample_question, sample_answer
    ):
        """Test that generate_for_job skips generation if answer already exists."""
        # Generate for job (answer already exists from fixture)
        generator = AnswerGenerator(test_db, sample_qa_job.id)
        await generator.generate_for_job(sample_question.id, sample_qa_job.snapshot_id)

        # Verify httpx was NOT called (no new API request)
        mock_httpx_client.assert_not_called()

        # Verify next stage was still called
        mock_extract_claims.assert_awaited_once_with(test_db, sample_qa_job.id)
