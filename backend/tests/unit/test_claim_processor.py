"""
Unit tests for ClaimProcessor service.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime

from src.scoring.services.claim_processor import ClaimProcessor
from src.common.database.models import JobStatusEnum, QAJobStageEnum
from src.common.models import CheckworthyResult


@pytest.mark.unit
class TestClaimProcessor:
    """Unit tests for ClaimProcessor class."""

    def test_extract_claims_creates_n_claims(self, test_db, sample_qa_job, sample_answer):
        """Test that extracting claims from answer creates N claims for N sentences."""
        processor = ClaimProcessor(test_db, sample_qa_job.id)

        # Extract claims (answer has 3 sentences)
        claims = processor._extract_claims(sample_answer.id)

        # Verify 3 claims created
        assert len(claims) == 3
        assert claims[0].claim_text == "AI poses privacy risks."
        assert claims[1].claim_text == "Bias is a concern."
        assert claims[2].claim_text == "Transparency is important."
        assert all(claim.checkworthy is True for claim in claims)
        assert all(claim.answer_id == sample_answer.id for claim in claims)

    @pytest.mark.asyncio
    @patch('src.scoring.services.claim_processor.LLMClient')
    async def test_check_claims_updates_all_checked_at(
        self, mock_llm_class, test_db, sample_qa_job, sample_answer
    ):
        """Test that checking claims updates checked_at for all claims."""
        # Create claims first
        processor = ClaimProcessor(test_db, sample_qa_job.id)
        claims = processor._extract_claims(sample_answer.id)

        # Set created_at to a specific past time
        past_time = datetime(2024, 1, 1, 12, 0, 0)
        for claim in claims:
            claim.created_at = past_time
            claim.checked_at = past_time
        test_db.commit()

        # Mock LLM client
        mock_llm_instance = MagicMock()
        mock_checkworthy_result = CheckworthyResult(
            checkworthy=True,
            reasoning="This is a factual claim that can be verified."
        )
        mock_metadata = {
            "prompt_tokens": 50,
            "completion_tokens": 20,
            "total_tokens": 70,
            "model": "gemini/gemini-2.0-flash-lite",
            "cost": 0.0001
        }
        mock_llm_instance.generate_structured_async = AsyncMock(
            return_value=(mock_checkworthy_result, mock_metadata)
        )
        mock_llm_class.return_value = mock_llm_instance

        # Check claims
        await processor._check_claims(sample_answer.id)

        # Verify all claims have updated checked_at
        test_db.refresh(claims[0])
        test_db.refresh(claims[1])
        test_db.refresh(claims[2])

        for claim in claims:
            assert claim.checked_at > past_time
            assert claim.checked_at != claim.created_at

    @pytest.mark.asyncio
    @patch('src.scoring.services.claim_processor.LLMClient')
    @patch('src.scoring.services.judge_scoring.score_answer', new_callable=AsyncMock)
    async def test_process_success(
        self, mock_score_answer, mock_llm_class, test_db, sample_qa_job, sample_answer
    ):
        """Test full process pipeline: extract -> check -> update costs -> call next stage."""
        # Mock LLM - will be called 3 times (once per claim)
        mock_llm_instance = MagicMock()

        async def async_return(*args, **kwargs):
            return (
                CheckworthyResult(
                    checkworthy=True,
                    reasoning="Checkworthy claim"
                ),
                {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                    "model": "gemini/gemini-2.0-flash-lite",
                    "cost": 0.0002
                }
            )

        mock_llm_instance.generate_structured_async = AsyncMock(side_effect=async_return)
        mock_llm_class.return_value = mock_llm_instance

        # Process
        processor = ClaimProcessor(test_db, sample_qa_job.id)
        await processor.process()

        # Verify claims created
        from src.common.database.repositories.answer_claim_repo import AnswerClaimRepository
        claims = AnswerClaimRepository.get_by_answer(test_db, sample_answer.id)
        assert len(claims) == 3

        # Verify LLM was called 3 times (once per claim)
        assert mock_llm_instance.generate_structured_async.call_count == 3

        # Verify job costs updated (3 calls * 0.0002 = 0.0006)
        test_db.refresh(sample_qa_job)
        assert sample_qa_job.prompt_tokens == 300  # 3 calls * 100
        assert sample_qa_job.completion_tokens == 150  # 3 calls * 50
        assert sample_qa_job.total_cost == pytest.approx(0.0006, rel=1e-6)

        # Verify next stage called
        mock_score_answer.assert_awaited_once_with(test_db, sample_qa_job.id)

    @pytest.mark.asyncio
    async def test_process_skips_if_not_running(self, test_db, sample_qa_job, sample_answer):
        """Test that process exits early if job is not running."""
        # Set job to paused
        sample_qa_job.status = JobStatusEnum.paused
        test_db.commit()

        # Process
        processor = ClaimProcessor(test_db, sample_qa_job.id)
        await processor.process()

        # Verify no claims created
        from src.common.database.repositories.answer_claim_repo import AnswerClaimRepository
        claims = AnswerClaimRepository.get_by_answer(test_db, sample_answer.id)
        assert len(claims) == 0
