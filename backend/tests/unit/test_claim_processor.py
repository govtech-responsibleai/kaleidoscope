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
            "model": "gemini/gemini-2.5-flash-lite",
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
    async def test_process_success(
        self, mock_llm_class, test_db, sample_qa_job, sample_answer
    ):
        """Test full process pipeline: extract -> check -> update costs."""
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
                    "model": "gemini/gemini-2.5-flash-lite",
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

        # Verify LLM was called only 2 times (1 claim is < 20 chars and skipped)
        # "AI poses privacy risks." = 23 chars (checked)
        # "Bias is a concern." = 19 chars (skipped - too short)
        # "Transparency is important." = 28 chars (checked)
        assert mock_llm_instance.generate_structured_async.call_count == 2

        # Verify job costs updated (2 calls * 0.0002 = 0.0004)
        test_db.refresh(sample_qa_job)
        assert sample_qa_job.prompt_tokens == 200  # 2 calls * 100
        assert sample_qa_job.completion_tokens == 100  # 2 calls * 50
        assert sample_qa_job.total_cost == pytest.approx(0.0004, rel=1e-6)

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

    def test_postprocess_claims_comprehensive(self, test_db, sample_qa_job):
        """Test all postprocessing rules and validate no character loss."""
        processor = ClaimProcessor(test_db, sample_qa_job.id)

        # Test data covering: line breaks, brackets, nesting
        # This simulates what NLTK might produce from a complex answer
        input_claims = [
            "First claim is long.\n(Second claim) text ",  # Space at end
            "[Third is (nested) long enough]"
        ]

        # Save original for validation
        original_joined = "".join(input_claims)

        # Run postprocessing
        result = processor._postprocess_claims(input_claims)

        # CRITICAL: Verify no character loss
        assert "".join(result) == original_joined, "Postprocessed claims must preserve all characters"

        # Expected behavior:
        # 1. Split by \n: ["First claim is long.\n", "(Second claim) text ", "[Third...]"]
        # 2. Shift brackets:
        #    - "(Second claim)" shifts to previous: ["First claim is long.\n(Second claim)", " text ", "[Third...]"]
        #    - "[Third is (nested) long enough]" shifts to previous: [..., " text [Third...]", ""]
        # Final result should have 3 claims (including empty string from bracket shift)
        assert len(result) == 3

        # Verify the claims are correct
        assert result[0] == "First claim is long.\n(Second claim)"
        assert result[1] == " text [Third is (nested) long enough]"
        assert result[2] == ""  # Empty after bracket shift


@pytest.mark.unit
class TestClaimProcessorErrors:
    """Tests for error handling in ClaimProcessor."""

    @pytest.mark.asyncio
    @patch('src.scoring.services.claim_processor.LLMClient')
    async def test_checkworthy_llm_error_defaults_to_checkworthy_true(
        self, mock_llm_class, test_db, sample_qa_job, sample_answer
    ):
        """Test that checkworthy LLM errors default claims to checkworthy=True."""
        # Update answer to have longer sentences that will be checked
        sample_answer.answer_content = "This is a very long claim about AI privacy risks that needs checking. This is another long claim about bias concerns in machine learning."
        test_db.commit()

        # Mock LLM to raise error
        mock_llm_instance = MagicMock()
        mock_llm_instance.generate_structured_async = AsyncMock(
            side_effect=Exception("Checkworthy LLM API error")
        )
        mock_llm_class.return_value = mock_llm_instance

        # Process
        processor = ClaimProcessor(test_db, sample_qa_job.id)
        await processor.process()

        # Verify claims were created and defaulted to checkworthy=True
        from src.common.database.repositories.answer_claim_repo import AnswerClaimRepository
        claims = AnswerClaimRepository.get_by_answer(test_db, sample_answer.id)

        assert len(claims) == 2
        # All should be checkworthy=True (default on error)
        assert all(claim.checkworthy is True for claim in claims)

        # Job should still be running (claim processor hands off to judge scoring)
        test_db.refresh(sample_qa_job)
        assert sample_qa_job.status == JobStatusEnum.running

    @pytest.mark.asyncio
    async def test_missing_answer_sets_job_failed_with_error_message(self, test_db, sample_qa_job):
        """Test that missing answer sets job failed with error_message."""
        # Set answer_id to non-existent answer
        sample_qa_job.answer_id = 99999
        test_db.commit()

        # Process
        processor = ClaimProcessor(test_db, sample_qa_job.id)
        await processor.process()

        # Verify job marked as failed
        test_db.refresh(sample_qa_job)
        assert sample_qa_job.status == JobStatusEnum.failed
        assert sample_qa_job.error_message is not None
        assert "not found" in sample_qa_job.error_message.lower()
