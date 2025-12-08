"""
Unit tests for AnswerJudge service.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.scoring.services.judge_scoring import AnswerJudge
from src.common.database.models import JobStatusEnum
from src.common.models import ClaimJudgmentResult, ResponseJudgmentResult


@pytest.mark.unit
class TestAnswerJudge:
    """Unit tests for AnswerJudge class."""

    @patch('src.scoring.services.judge_scoring.LLMClient')
    def test_score_claim_based_creates_n_scores(
        self, mock_llm_class, test_db, sample_qa_job, sample_answer, sample_claims, sample_kb_documents
    ):
        """Test claim-based scoring creates N AnswerClaimScore records for N claims."""
        # Update job to use claim-based judge
        from src.common.database.models import JudgeTypeEnum
        judge = sample_qa_job.judge
        judge.judge_type = JudgeTypeEnum.claim_based
        test_db.commit()

        # Mock LLM
        mock_llm_instance = MagicMock()

        async def async_return(*args, **kwargs):
            return (
                ClaimJudgmentResult(
                    is_accurate=True,
                    explanation="This claim is supported by the knowledge base."
                ),
                {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                    "model": "gemini/gemini-2.0-flash-lite",
                    "cost": 0.0002
                }
            )

        mock_llm_instance.generate_structured_async.side_effect = async_return
        mock_llm_class.return_value = mock_llm_instance

        # Score
        import asyncio
        scorer = AnswerJudge(test_db, sample_qa_job.id)
        asyncio.run(scorer.score())

        # Verify AnswerScore created
        from src.common.database.repositories.answer_score_repo import AnswerScoreRepository
        answer_score = AnswerScoreRepository.get_by_answer_and_judge(
            test_db, sample_answer.id, sample_qa_job.judge_id
        )
        assert answer_score is not None

        # Verify AnswerClaimScore records created (3 claims)
        from src.common.database.repositories.answer_claim_score_repo import AnswerClaimScoreRepository
        claim_scores = AnswerClaimScoreRepository.get_by_answer_score(test_db, answer_score.id)
        assert len(claim_scores) == 3
        assert all(score.label is True for score in claim_scores)

    @patch('src.scoring.services.judge_scoring.LLMClient')
    def test_score_claim_based_aggregation(
        self, mock_llm_class, test_db, sample_qa_job, sample_answer, sample_claims, sample_kb_documents
    ):
        """Test claim-based aggregation uses majority vote (3 accurate, 2 inaccurate -> overall True)."""
        # Update job to use claim-based judge
        from src.common.database.models import JudgeTypeEnum
        judge = sample_qa_job.judge
        judge.judge_type = JudgeTypeEnum.claim_based
        test_db.commit()

        # Add 2 more claims to get 5 total
        from src.common.database.models import AnswerClaim
        from datetime import datetime
        extra_claims = [
            AnswerClaim(
                answer_id=sample_answer.id,
                claim_index=3,
                text="Extra claim 1.",
                checkworthy=True,
                created_at=datetime.utcnow(),
                checked_at=datetime.utcnow()
            ),
            AnswerClaim(
                answer_id=sample_answer.id,
                claim_index=4,
                text="Extra claim 2.",
                checkworthy=True,
                created_at=datetime.utcnow(),
                checked_at=datetime.utcnow()
            )
        ]
        test_db.add_all(extra_claims)
        test_db.commit()

        # Mock LLM to return different results: accurate, accurate, accurate, inaccurate, inaccurate
        mock_llm_instance = MagicMock()

        call_count = [0]

        async def mock_generate(*args, **kwargs):
            call_count[0] += 1
            # First 3 calls return accurate, last 2 return inaccurate
            is_accurate = call_count[0] <= 3
            result = ClaimJudgmentResult(
                is_accurate=is_accurate,
                explanation=f"Claim {call_count[0]} explanation"
            )
            metadata = {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
                "model": "gemini/gemini-2.0-flash-lite",
                "cost": 0.0002
            }
            return result, metadata

        mock_llm_instance.generate_structured_async.side_effect = mock_generate
        mock_llm_class.return_value = mock_llm_instance

        # Score
        import asyncio
        scorer = AnswerJudge(test_db, sample_qa_job.id)
        asyncio.run(scorer.score())

        # Verify overall label is True (3/5 accurate > 50%)
        from src.common.database.repositories.answer_score_repo import AnswerScoreRepository
        answer_score = AnswerScoreRepository.get_by_answer_and_judge(
            test_db, sample_answer.id, sample_qa_job.judge_id
        )
        assert answer_score.overall_label is True
        assert "Accuracy ratio: 0.60" in answer_score.explanation

    @patch('src.scoring.services.judge_scoring.LLMClient')
    def test_score_response_level_single_score(
        self, mock_llm_class, test_db, sample_qa_job, sample_answer, sample_kb_documents
    ):
        """Test response-level scoring creates 1 AnswerScore, no claim scores."""
        # Update job to use response-level judge
        from src.common.database.models import JudgeTypeEnum
        judge = sample_qa_job.judge
        judge.judge_type = JudgeTypeEnum.response_level
        test_db.commit()

        # Mock LLM
        mock_llm_instance = MagicMock()

        async def async_return(*args, **kwargs):
            return (
                ResponseJudgmentResult(
                    is_accurate=True,
                    explanation="The response is overall accurate and well-supported."
                ),
                {
                    "prompt_tokens": 150,
                    "completion_tokens": 75,
                    "total_tokens": 225,
                    "model": "gemini/gemini-2.0-flash-lite",
                    "cost": 0.0003
                }
            )

        mock_llm_instance.generate_structured_async.side_effect = async_return
        mock_llm_class.return_value = mock_llm_instance

        # Score
        import asyncio
        scorer = AnswerJudge(test_db, sample_qa_job.id)
        asyncio.run(scorer.score())

        # Verify AnswerScore created
        from src.common.database.repositories.answer_score_repo import AnswerScoreRepository
        answer_score = AnswerScoreRepository.get_by_answer_and_judge(
            test_db, sample_answer.id, sample_qa_job.judge_id
        )
        assert answer_score is not None
        assert answer_score.overall_label is True

        # Verify NO AnswerClaimScore records created
        from src.common.database.repositories.answer_claim_score_repo import AnswerClaimScoreRepository
        claim_scores = AnswerClaimScoreRepository.get_by_answer_score(test_db, answer_score.id)
        assert len(claim_scores) == 0

    @patch('src.scoring.services.judge_scoring.LLMClient')
    def test_score_response_level_accuracy(
        self, mock_llm_class, test_db, sample_qa_job, sample_answer, sample_kb_documents
    ):
        """Test response-level judgment label propagates to AnswerScore."""
        # Update job to use response-level judge
        from src.common.database.models import JudgeTypeEnum
        judge = sample_qa_job.judge
        judge.judge_type = JudgeTypeEnum.response_level
        test_db.commit()

        # Mock LLM to return inaccurate
        mock_llm_instance = MagicMock()

        async def async_return(*args, **kwargs):
            return (
                ResponseJudgmentResult(
                    is_accurate=False,
                    explanation="The response contains inaccuracies."
                ),
                {
                    "prompt_tokens": 150,
                    "completion_tokens": 75,
                    "total_tokens": 225,
                    "model": "gemini/gemini-2.0-flash-lite",
                    "cost": 0.0003
                }
            )

        mock_llm_instance.generate_structured_async.side_effect = async_return
        mock_llm_class.return_value = mock_llm_instance

        # Score
        import asyncio
        scorer = AnswerJudge(test_db, sample_qa_job.id)
        asyncio.run(scorer.score())

        # Verify label is False
        from src.common.database.repositories.answer_score_repo import AnswerScoreRepository
        answer_score = AnswerScoreRepository.get_by_answer_and_judge(
            test_db, sample_answer.id, sample_qa_job.judge_id
        )
        assert answer_score.overall_label is False
        assert "inaccuracies" in answer_score.explanation

    @patch('src.scoring.services.judge_scoring.LLMClient')
    def test_score_updates_job_costs(
        self, mock_llm_class, test_db, sample_qa_job, sample_answer, sample_claims, sample_kb_documents
    ):
        """Test that scoring updates QAJob costs."""
        # Update job to use claim-based judge
        from src.common.database.models import JudgeTypeEnum
        judge = sample_qa_job.judge
        judge.judge_type = JudgeTypeEnum.claim_based
        test_db.commit()

        # Mock LLM
        mock_llm_instance = MagicMock()

        async def async_return(*args, **kwargs):
            return (
                ClaimJudgmentResult(
                    is_accurate=True,
                    explanation="Accurate"
                ),
                {
                    "prompt_tokens": 200,
                    "completion_tokens": 100,
                    "total_tokens": 300,
                    "model": "gemini/gemini-2.0-flash-lite",
                    "cost": 0.0005
                }
            )

        mock_llm_instance.generate_structured_async.side_effect = async_return
        mock_llm_class.return_value = mock_llm_instance

        # Initial costs
        initial_tokens = sample_qa_job.prompt_tokens
        initial_cost = sample_qa_job.total_cost

        # Score
        import asyncio
        scorer = AnswerJudge(test_db, sample_qa_job.id)
        asyncio.run(scorer.score())

        # Verify costs updated (3 claims scored)
        test_db.refresh(sample_qa_job)
        assert sample_qa_job.prompt_tokens > initial_tokens
        assert sample_qa_job.total_cost > initial_cost

    @patch('src.scoring.services.judge_scoring.LLMClient')
    def test_score_handles_llm_failure(
        self, mock_llm_class, test_db, sample_qa_job, sample_answer, sample_claims, sample_kb_documents
    ):
        """Test that LLM errors result in default inaccurate scores."""
        # Update job to use claim-based judge
        from src.common.database.models import JudgeTypeEnum
        judge = sample_qa_job.judge
        judge.judge_type = JudgeTypeEnum.claim_based
        test_db.commit()

        # Mock LLM to raise error
        mock_llm_instance = MagicMock()
        mock_llm_instance.generate_structured_async.side_effect = Exception("LLM API error")
        mock_llm_class.return_value = mock_llm_instance

        # Score - should not raise, but create default scores
        import asyncio
        scorer = AnswerJudge(test_db, sample_qa_job.id)
        asyncio.run(scorer.score())

        # Verify AnswerScore created with error handling
        from src.common.database.repositories.answer_score_repo import AnswerScoreRepository
        answer_score = AnswerScoreRepository.get_by_answer_and_judge(
            test_db, sample_answer.id, sample_qa_job.judge_id
        )
        assert answer_score is not None

        # Verify claim scores have error messages
        from src.common.database.repositories.answer_claim_score_repo import AnswerClaimScoreRepository
        claim_scores = AnswerClaimScoreRepository.get_by_answer_score(test_db, answer_score.id)
        assert len(claim_scores) == 3
        assert all(score.label is False for score in claim_scores)
        assert all("Error during scoring" in score.explanation for score in claim_scores)
