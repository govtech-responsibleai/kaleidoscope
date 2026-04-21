"""
Unit tests for AnswerJudge service.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock

from src.scoring.services.judge_scoring import AnswerJudge
from src.common.database.models import JobStatusEnum
from src.common.models import ClaimJudgmentResult, ResponseJudgmentResult


@pytest.mark.unit
class TestAnswerJudge:
    """Unit tests for AnswerJudge class."""

    @pytest.mark.asyncio
    @patch('src.scoring.services.judge_scoring.LLMClient')
    async def test_score_claim_based_creates_n_scores(
        self, mock_llm_class, test_db, sample_qa_job, sample_answer, sample_claims, sample_kb_documents
    ):
        """Test claim-based scoring creates N AnswerClaimScore records for N claims."""
        # sample_qa_job fixture creates judge bound to claim_based accuracy rubric
        mock_llm_instance = MagicMock()

        async def async_return(*args, **kwargs):
            return (
                ClaimJudgmentResult(
                    label=True,
                    reasoning="This claim is supported by the knowledge base."
                ),
                {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                    "model": "litellm_proxy/gemini-3.1-flash-lite-preview-global",
                    "cost": 0.0002
                }
            )

        mock_llm_instance.generate_structured_async = AsyncMock(side_effect=async_return)
        mock_llm_class.return_value = mock_llm_instance

        scorer = AnswerJudge(test_db, sample_qa_job.id)
        await scorer.score()

        from src.common.database.repositories.answer_score_repo import AnswerScoreRepository
        answer_score = AnswerScoreRepository.get_by_answer_and_judge(
            test_db, sample_answer.id, sample_qa_job.judge_id
        )
        assert answer_score is not None

        from src.common.database.repositories.answer_claim_score_repo import AnswerClaimScoreRepository
        claim_scores = AnswerClaimScoreRepository.get_by_answer_score(test_db, answer_score.id)
        assert len(claim_scores) == 3
        assert all(score.label is True for score in claim_scores)

    @pytest.mark.asyncio
    @patch('src.scoring.services.judge_scoring.LLMClient')
    async def test_score_claim_based_aggregation(
        self, mock_llm_class, test_db, sample_qa_job, sample_answer, sample_claims, sample_kb_documents
    ):
        """Test claim-based aggregation uses majority vote (3 accurate, 2 inaccurate -> overall True)."""
        from src.common.database.models import AnswerClaim
        from datetime import datetime
        extra_claims = [
            AnswerClaim(
                answer_id=sample_answer.id,
                claim_index=3,
                claim_text="Extra claim 1.",
                checkworthy=True,
                created_at=datetime.utcnow(),
                checked_at=datetime.utcnow()
            ),
            AnswerClaim(
                answer_id=sample_answer.id,
                claim_index=4,
                claim_text="Extra claim 2.",
                checkworthy=True,
                created_at=datetime.utcnow(),
                checked_at=datetime.utcnow()
            )
        ]
        test_db.add_all(extra_claims)
        test_db.commit()

        mock_llm_instance = MagicMock()
        call_count = [0]

        async def mock_generate(*args, **kwargs):
            call_count[0] += 1
            is_accurate = call_count[0] <= 3
            result = ClaimJudgmentResult(
                label=is_accurate,
                reasoning=f"Claim {call_count[0]} explanation"
            )
            metadata = {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
                "model": "litellm_proxy/gemini-3.1-flash-lite-preview-global",
                "cost": 0.0002
            }
            return result, metadata

        mock_llm_instance.generate_structured_async = AsyncMock(side_effect=mock_generate)
        mock_llm_class.return_value = mock_llm_instance

        scorer = AnswerJudge(test_db, sample_qa_job.id)
        await scorer.score()

        from src.common.database.repositories.answer_score_repo import AnswerScoreRepository
        answer_score = AnswerScoreRepository.get_by_answer_and_judge(
            test_db, sample_answer.id, sample_qa_job.judge_id
        )
        assert answer_score.overall_label == "Inaccurate"
        assert "Accuracy ratio: 0.60" in answer_score.explanation

    @pytest.mark.asyncio
    @patch('src.scoring.services.judge_scoring.LLMClient')
    async def test_score_response_level_single_score(
        self, mock_llm_class, test_db, sample_qa_job, sample_answer, sample_kb_documents
    ):
        """Test response-level scoring creates 1 AnswerScore, no claim scores."""
        # Detach judge from rubric to use generic response-level path
        judge = sample_qa_job.judge
        judge.rubric_id = None
        test_db.commit()

        mock_llm_instance = MagicMock()

        async def async_return(*args, **kwargs):
            return (
                ResponseJudgmentResult(
                    label=True,
                    reasoning="The response is overall accurate and well-supported."
                ),
                {
                    "prompt_tokens": 150,
                    "completion_tokens": 75,
                    "total_tokens": 225,
                    "model": "litellm_proxy/gemini-3.1-flash-lite-preview-global",
                    "cost": 0.0003
                }
            )

        mock_llm_instance.generate_structured_async = AsyncMock(side_effect=async_return)
        mock_llm_class.return_value = mock_llm_instance

        scorer = AnswerJudge(test_db, sample_qa_job.id)
        await scorer.score()

        from src.common.database.repositories.answer_score_repo import AnswerScoreRepository
        answer_score = AnswerScoreRepository.get_by_answer_and_judge(
            test_db, sample_answer.id, sample_qa_job.judge_id
        )
        assert answer_score is not None
        assert answer_score.overall_label == "Accurate"

        from src.common.database.repositories.answer_claim_score_repo import AnswerClaimScoreRepository
        claim_scores = AnswerClaimScoreRepository.get_by_answer_score(test_db, answer_score.id)
        assert len(claim_scores) == 0

    @pytest.mark.asyncio
    @patch('src.scoring.services.judge_scoring.LLMClient')
    async def test_score_response_level_accuracy(
        self, mock_llm_class, test_db, sample_qa_job, sample_answer, sample_kb_documents
    ):
        """Test response-level judgment label propagates to AnswerScore."""
        judge = sample_qa_job.judge
        judge.rubric_id = None
        test_db.commit()

        mock_llm_instance = MagicMock()

        async def async_return(*args, **kwargs):
            return (
                ResponseJudgmentResult(
                    label=False,
                    reasoning="The response contains inaccuracies."
                ),
                {
                    "prompt_tokens": 150,
                    "completion_tokens": 75,
                    "total_tokens": 225,
                    "model": "litellm_proxy/gemini-3.1-flash-lite-preview-global",
                    "cost": 0.0003
                }
            )

        mock_llm_instance.generate_structured_async = AsyncMock(side_effect=async_return)
        mock_llm_class.return_value = mock_llm_instance

        scorer = AnswerJudge(test_db, sample_qa_job.id)
        await scorer.score()

        from src.common.database.repositories.answer_score_repo import AnswerScoreRepository
        answer_score = AnswerScoreRepository.get_by_answer_and_judge(
            test_db, sample_answer.id, sample_qa_job.judge_id
        )
        assert answer_score.overall_label == "Inaccurate"
        assert "inaccuracies" in answer_score.explanation

    @pytest.mark.asyncio
    @patch('src.scoring.services.judge_scoring.LLMClient')
    async def test_score_updates_job_costs(
        self, mock_llm_class, test_db, sample_qa_job, sample_answer, sample_claims, sample_kb_documents
    ):
        """Test that scoring updates QAJob costs."""
        mock_llm_instance = MagicMock()

        async def async_return(*args, **kwargs):
            return (
                ClaimJudgmentResult(
                    label=True,
                    reasoning="Accurate"
                ),
                {
                    "prompt_tokens": 200,
                    "completion_tokens": 100,
                    "total_tokens": 300,
                    "model": "litellm_proxy/gemini-3.1-flash-lite-preview-global",
                    "cost": 0.0005
                }
            )

        mock_llm_instance.generate_structured_async = AsyncMock(side_effect=async_return)
        mock_llm_class.return_value = mock_llm_instance

        initial_tokens = sample_qa_job.prompt_tokens
        initial_cost = sample_qa_job.total_cost

        scorer = AnswerJudge(test_db, sample_qa_job.id)
        await scorer.score()

        test_db.refresh(sample_qa_job)
        assert sample_qa_job.prompt_tokens > initial_tokens
        assert sample_qa_job.total_cost > initial_cost

    @pytest.mark.asyncio
    @patch('src.scoring.services.judge_scoring.LLMClient')
    async def test_score_handles_llm_failure(
        self, mock_llm_class, test_db, sample_qa_job, sample_answer, sample_claims, sample_kb_documents
    ):
        """Test that LLM errors result in default inaccurate scores."""
        mock_llm_instance = MagicMock()
        mock_llm_instance.generate_structured_async = AsyncMock(side_effect=Exception("LLM API error"))
        mock_llm_class.return_value = mock_llm_instance

        scorer = AnswerJudge(test_db, sample_qa_job.id)
        await scorer.score()

        from src.common.database.repositories.answer_score_repo import AnswerScoreRepository
        answer_score = AnswerScoreRepository.get_by_answer_and_judge(
            test_db, sample_answer.id, sample_qa_job.judge_id
        )
        assert answer_score is not None

        from src.common.database.repositories.answer_claim_score_repo import AnswerClaimScoreRepository
        claim_scores = AnswerClaimScoreRepository.get_by_answer_score(test_db, answer_score.id)
        assert len(claim_scores) == 3
        assert all(score.label is False for score in claim_scores)
        assert all("Error during scoring" in score.explanation for score in claim_scores)


@pytest.mark.unit
class TestContextPriority:
    """Tests for RAG citations vs KB documents context priority."""

    @pytest.mark.asyncio
    @patch('src.scoring.services.judge_scoring.render_template')
    @patch('src.scoring.services.judge_scoring.LLMClient')
    async def test_claim_based_uses_rag_over_kb(
        self, mock_llm_class, mock_render_template, test_db, sample_qa_job, sample_answer, sample_claims, sample_kb_documents
    ):
        """RAG citations take priority over KB documents for claim-based scoring."""
        sample_answer.rag_citations = [
            {"source": "rag.pdf", "id": "c1", "chunk": "RAG chunk content here."}
        ]
        test_db.commit()

        mock_llm_instance = MagicMock()
        mock_llm_instance.generate_structured_async = AsyncMock(return_value=(
            ClaimJudgmentResult(label=True, reasoning="OK"),
            {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150, "model": "test", "cost": 0.0001}
        ))
        mock_llm_class.return_value = mock_llm_instance
        mock_render_template.return_value = "mocked prompt"

        scorer = AnswerJudge(test_db, sample_qa_job.id)
        await scorer.score()

        kb_text = mock_render_template.call_args_list[0].kwargs.get('kb_documents')
        assert "RAG chunk content" in kb_text
        assert "Privacy is a major concern" not in kb_text

    @pytest.mark.asyncio
    @patch('src.scoring.services.judge_scoring.render_template')
    @patch('src.scoring.services.judge_scoring.LLMClient')
    async def test_claim_based_falls_back_to_kb(
        self, mock_llm_class, mock_render_template, test_db, sample_qa_job, sample_answer, sample_claims, sample_kb_documents
    ):
        """KB documents used when no RAG citations for claim-based scoring."""
        sample_answer.rag_citations = None
        test_db.commit()

        mock_llm_instance = MagicMock()
        mock_llm_instance.generate_structured_async = AsyncMock(return_value=(
            ClaimJudgmentResult(label=True, reasoning="OK"),
            {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150, "model": "test", "cost": 0.0001}
        ))
        mock_llm_class.return_value = mock_llm_instance
        mock_render_template.return_value = "mocked prompt"

        scorer = AnswerJudge(test_db, sample_qa_job.id)
        await scorer.score()

        kb_text = mock_render_template.call_args_list[0].kwargs.get('kb_documents')
        assert "Privacy is a major concern" in kb_text

    @pytest.mark.asyncio
    @patch('src.scoring.services.judge_scoring.render_template')
    @patch('src.scoring.services.judge_scoring.LLMClient')
    async def test_claim_based_empty_when_no_context(
        self, mock_llm_class, mock_render_template, test_db, sample_qa_job, sample_answer, sample_claims
    ):
        """Empty fallback when no RAG citations and no KB documents."""
        sample_answer.rag_citations = None
        test_db.commit()

        mock_llm_instance = MagicMock()
        mock_llm_instance.generate_structured_async = AsyncMock(return_value=(
            ClaimJudgmentResult(label=True, reasoning="OK"),
            {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150, "model": "test", "cost": 0.0001}
        ))
        mock_llm_class.return_value = mock_llm_instance
        mock_render_template.return_value = "mocked prompt"

        scorer = AnswerJudge(test_db, sample_qa_job.id)
        await scorer.score()

        kb_text = mock_render_template.call_args_list[0].kwargs.get('kb_documents')
        assert kb_text == "[document is empty]"


@pytest.mark.unit
class TestAnswerJudgeErrors:
    """Tests for error handling during LLM scoring."""

    @pytest.mark.asyncio
    @patch('src.scoring.services.judge_scoring.LLMClient')
    async def test_claim_level_llm_error_captures_error_in_explanation(
        self, mock_llm_class, test_db, sample_qa_job, sample_answer, sample_claims, sample_kb_documents
    ):
        """Test that claim-level LLM errors are captured in claim score explanations."""
        mock_llm_instance = MagicMock()
        mock_llm_instance.generate_structured_async = AsyncMock(
            side_effect=Exception("LLM API rate limit exceeded")
        )
        mock_llm_class.return_value = mock_llm_instance

        scorer = AnswerJudge(test_db, sample_qa_job.id)
        await scorer.score()

        test_db.refresh(sample_qa_job)
        assert sample_qa_job.status == JobStatusEnum.running

        from src.common.database.repositories.answer_score_repo import AnswerScoreRepository
        from src.common.database.repositories.answer_claim_score_repo import AnswerClaimScoreRepository

        answer_score = AnswerScoreRepository.get_by_answer_and_judge(
            test_db, sample_answer.id, sample_qa_job.judge_id
        )
        claim_scores = AnswerClaimScoreRepository.get_by_answer_score(test_db, answer_score.id)

        assert len(claim_scores) == 3
        assert all("LLM API rate limit exceeded" in score.explanation for score in claim_scores)

    @pytest.mark.asyncio
    @patch('src.scoring.services.judge_scoring.LLMClient')
    async def test_response_level_llm_error_sets_job_failed(
        self, mock_llm_class, test_db, sample_qa_job, sample_answer, sample_kb_documents
    ):
        """Test that response-level LLM errors mark job as failed with error_message."""
        judge = sample_qa_job.judge
        judge.rubric_id = None
        test_db.commit()

        mock_llm_instance = MagicMock()
        mock_llm_instance.generate_structured_async = AsyncMock(
            side_effect=Exception("LLM service unavailable")
        )
        mock_llm_class.return_value = mock_llm_instance

        scorer = AnswerJudge(test_db, sample_qa_job.id)
        await scorer.score()

        test_db.refresh(sample_qa_job)
        assert sample_qa_job.status == JobStatusEnum.failed
        assert sample_qa_job.error_message is not None
        assert "LLM service unavailable" in sample_qa_job.error_message
