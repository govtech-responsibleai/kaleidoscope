"""
Unit tests for QAJobProcessor service.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

from src.scoring.services.qa_job_processor import (
    QAJobProcessor, run_qajob, run_qajobs_batch,
    pause_qajob, pause_qajobs_batch, get_or_create_qajobs_batch, create_all_jobs,
    _is_rubric_score_complete,
)
from src.common.database.models import (
    JobStatusEnum, QAJobStageEnum, QAJobTypeEnum,
    Answer, AnswerClaim, AnswerClaimScore, AnswerScore, Judge,
    Question, QuestionTypeEnum, QuestionScopeEnum, StatusEnum,
)
from src.common.database.repositories.qa_job_repo import QAJobRepository
from src.common.database.repositories.answer_repo import AnswerRepository
from src.common.database.repositories.answer_score_repo import AnswerScoreRepository


@pytest.mark.unit
class TestQAJobProcessor:
    """Unit tests for QAJobProcessor class."""

    @pytest.mark.asyncio
    @patch('src.scoring.services.qa_job_processor.generate_answer_for_job', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.extract_and_check_claims', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.AnswerJudge')
    async def test_run_processes_existing_job(
        self, MockAnswerJudge, mock_extract_claims, mock_generate_answer,
        test_db, sample_snapshot, sample_question, sample_judge_claim_based
    ):
        """Test that run processes an existing job through the full pipeline."""
        mock_judge_instance = MockAnswerJudge.return_value
        mock_judge_instance.score = AsyncMock()

        job = QAJobRepository.create(
            test_db,
            {
                "snapshot_id": sample_snapshot.id,
                "question_id": sample_question.id,
                "judge_id": sample_judge_claim_based.id,
                "type": QAJobTypeEnum.claim_scoring_full,
                "status": JobStatusEnum.running,
                "stage": QAJobStageEnum.starting,
            }
        )

        processor = QAJobProcessor(
            test_db, sample_snapshot.id, sample_question.id, sample_judge_claim_based.id
        )
        processed_job = await processor.run(job_id=job.id)

        assert processed_job is not None
        assert processed_job.id == job.id
        assert processed_job.snapshot_id == sample_snapshot.id
        assert processed_job.question_id == sample_question.id
        assert processed_job.judge_id == sample_judge_claim_based.id

        mock_generate_answer.assert_awaited_once()

    @pytest.mark.asyncio
    @patch('src.scoring.services.qa_job_processor.generate_answer_for_job', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.extract_and_check_claims', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.AnswerJudge')
    async def test_response_level_judge_skips_claim_processing(
        self,
        MockAnswerJudge,
        mock_extract_claims,
        mock_generate_answer,
        test_db,
        sample_snapshot,
        sample_question,
        sample_answer,
        sample_judge_response_level,
    ):
        """Response-level judges should score directly from the answer."""
        mock_judge_instance = MockAnswerJudge.return_value
        mock_judge_instance.score = AsyncMock()

        job = QAJobRepository.create(
            test_db,
            {
                "snapshot_id": sample_snapshot.id,
                "question_id": sample_question.id,
                "judge_id": sample_judge_response_level.id,
                "answer_id": sample_answer.id,
                "type": QAJobTypeEnum.response_scoring_full,
                "status": JobStatusEnum.running,
                "stage": QAJobStageEnum.starting,
            }
        )

        processor = QAJobProcessor(
            test_db, sample_snapshot.id, sample_question.id, sample_judge_response_level.id
        )
        await processor.run(job_id=job.id)

        mock_generate_answer.assert_not_awaited()
        mock_extract_claims.assert_not_awaited()
        MockAnswerJudge.assert_called_once_with(
            test_db,
            job.id,
            override_judge_id=sample_judge_response_level.id,
        )
        mock_judge_instance.score.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_job_not_found_raises_error(self, test_db, sample_snapshot, sample_question, sample_judge_claim_based):
        """Test that run with non-existent job_id raises ValueError."""
        processor = QAJobProcessor(
            test_db, sample_snapshot.id, sample_question.id, sample_judge_claim_based.id
        )

        with pytest.raises(ValueError, match="QAJob with id 999 not found"):
            await processor.run(job_id=999)

    @pytest.mark.asyncio
    @patch('src.scoring.services.qa_job_processor.AnswerJudge')
    async def test_run_scoring_only_when_claims_checked(
        self, MockAnswerJudge, test_db, sample_qa_job, sample_snapshot, sample_question, sample_answer
    ):
        """Test that pipeline skips to scoring when answer and fully-checked claims exist but score doesn't."""
        from datetime import datetime, timedelta
        from src.common.database.models import AnswerClaim

        mock_judge_instance = MockAnswerJudge.return_value
        mock_judge_instance.score = AsyncMock()

        # Create claims with different created_at and checked_at (marking them as checked)
        now = datetime.utcnow()
        claims = [
            AnswerClaim(
                answer_id=sample_answer.id,
                claim_index=0,
                claim_text="AI poses privacy risks.",
                checkworthy=True,
                created_at=now,
                checked_at=now + timedelta(seconds=1)
            ),
            AnswerClaim(
                answer_id=sample_answer.id,
                claim_index=1,
                claim_text="Bias is a concern.",
                checkworthy=True,
                created_at=now,
                checked_at=now + timedelta(seconds=1)
            ),
        ]
        test_db.add_all(claims)
        test_db.commit()

        # Set job to paused so we can resume it
        sample_qa_job.status = JobStatusEnum.paused
        sample_qa_job.stage = QAJobStageEnum.processing_answers
        test_db.commit()

        # Run — _get_start_index should detect answer+checked claims exist and skip to scoring
        processor = QAJobProcessor(
            test_db, sample_snapshot.id, sample_question.id, sample_qa_job.judge_id
        )
        await processor.run(job_id=sample_qa_job.id)

        # Verify AnswerJudge was instantiated and score() called
        MockAnswerJudge.assert_called_once_with(
            test_db,
            sample_qa_job.id,
            override_judge_id=sample_qa_job.judge_id,
        )
        mock_judge_instance.score.assert_awaited_once()


    @pytest.mark.asyncio
    @patch('src.scoring.services.qa_job_processor.generate_answer_for_job', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.extract_and_check_claims', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.AnswerJudge')
    async def test_full_pipeline_runs_all_stages(
        self, MockAnswerJudge, mock_extract_claims, mock_generate_answer,
        test_db, sample_snapshot, sample_question, sample_judge_claim_based
    ):
        """Test full pipeline calls all three stages sequentially when no prior data exists."""
        mock_judge_instance = MockAnswerJudge.return_value
        mock_judge_instance.score = AsyncMock()

        job = QAJobRepository.create(
            test_db,
            {
                "snapshot_id": sample_snapshot.id,
                "question_id": sample_question.id,
                "judge_id": sample_judge_claim_based.id,
                "type": QAJobTypeEnum.claim_scoring_full,
                "status": JobStatusEnum.running,
                "stage": QAJobStageEnum.starting,
            }
        )

        processor = QAJobProcessor(
            test_db, sample_snapshot.id, sample_question.id, sample_judge_claim_based.id
        )
        await processor.run(job_id=job.id)

        # All three stages should be called since no prior data exists
        mock_generate_answer.assert_awaited_once()
        mock_extract_claims.assert_awaited_once()
        mock_judge_instance.score.assert_awaited_once()

        # Verify job marked as completed
        test_db.refresh(job)
        assert job.status == JobStatusEnum.completed
        assert job.stage == QAJobStageEnum.completed

    def test_create_all_jobs_keeps_existing_job_rubric_specs_when_running_extra_judges(
        self,
        test_db,
        sample_snapshot,
        sample_qa_job,
        sample_rubric,
        sample_rubric_second,
    ):
        """Existing jobs keep their stored rubric specs when extra judges are run later."""
        sample_qa_job.snapshot_id = sample_snapshot.id
        sample_qa_job.rubric_specs = [
            {"rubric_id": sample_qa_job.judge.rubric_id, "judge_id": sample_qa_job.judge_id},
            {"rubric_id": sample_rubric.id, "judge_id": 101},
        ]
        test_db.commit()

        jobs = create_all_jobs(
            db=test_db,
            snapshot_id=sample_snapshot.id,
            question_ids=[sample_qa_job.question_id],
            rubric_specs=[
                {"rubric_id": sample_qa_job.judge.rubric_id, "judge_id": sample_qa_job.judge_id},
                {"rubric_id": sample_rubric.id, "judge_id": 101},
                {"rubric_id": sample_rubric_second.id, "judge_id": 202},
            ],
        )

        assert len(jobs) == 1
        test_db.refresh(sample_qa_job)
        assert sample_qa_job.rubric_specs == [
            {"rubric_id": sample_qa_job.judge.rubric_id, "judge_id": sample_qa_job.judge_id},
            {"rubric_id": sample_rubric.id, "judge_id": 101},
        ]

    def test_create_all_jobs_marks_completed_job_running_only_when_full_set_has_missing_score(
        self,
        test_db,
        sample_snapshot,
        sample_answer,
        sample_qa_job,
        sample_claims,
        sample_rubric,
        sample_rubric_second,
    ):
        """Completed jobs should resume only when the reconciled full rubric set still has gaps."""
        for claim in sample_claims:
            claim.checked_at = claim.created_at + timedelta(seconds=1)

        existing_empathy_judge = Judge(
            target_id=sample_snapshot.target_id,
            rubric_id=sample_rubric.id,
            name="Empathy Judge",
            model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
            prompt_template="Empathy prompt",
            params={},
            is_baseline=False,
            is_editable=True,
        )
        test_db.add(existing_empathy_judge)
        test_db.commit()
        test_db.refresh(existing_empathy_judge)

        accuracy_score = AnswerScore(
            answer_id=sample_answer.id,
            rubric_id=sample_qa_job.judge.rubric_id,
            judge_id=sample_qa_job.judge_id,
            overall_label="Accurate",
            explanation="Accuracy already scored",
        )
        empathy_score = AnswerScore(
            answer_id=sample_answer.id,
            rubric_id=sample_rubric.id,
            judge_id=existing_empathy_judge.id,
            overall_label=sample_rubric.best_option,
            explanation="Empathy already scored",
        )
        test_db.add_all([accuracy_score, empathy_score])
        test_db.commit()
        test_db.refresh(accuracy_score)

        test_db.add_all(
            [
                AnswerClaimScore(
                    claim_id=claim.id,
                    answer_score_id=accuracy_score.id,
                    label=True,
                    explanation="Accuracy already scored",
                )
                for claim in sample_claims
            ]
        )
        sample_qa_job.status = JobStatusEnum.completed
        sample_qa_job.stage = QAJobStageEnum.completed
        sample_qa_job.rubric_specs = [
            {"rubric_id": sample_qa_job.judge.rubric_id, "judge_id": sample_qa_job.judge_id},
            {"rubric_id": sample_rubric.id, "judge_id": existing_empathy_judge.id},
        ]
        test_db.commit()

        unchanged_jobs = create_all_jobs(
            db=test_db,
            snapshot_id=sample_snapshot.id,
            question_ids=[sample_qa_job.question_id],
            rubric_specs=[
                {"rubric_id": sample_qa_job.judge.rubric_id, "judge_id": sample_qa_job.judge_id},
                {"rubric_id": sample_rubric.id, "judge_id": existing_empathy_judge.id},
            ],
        )

        assert len(unchanged_jobs) == 1
        test_db.refresh(sample_qa_job)
        assert sample_qa_job.status == JobStatusEnum.completed

        resumed_jobs = create_all_jobs(
            db=test_db,
            snapshot_id=sample_snapshot.id,
            question_ids=[sample_qa_job.question_id],
            rubric_specs=[
                {"rubric_id": sample_qa_job.judge.rubric_id, "judge_id": sample_qa_job.judge_id},
                {"rubric_id": sample_rubric.id, "judge_id": existing_empathy_judge.id},
                {"rubric_id": sample_rubric_second.id, "judge_id": 202},
            ],
        )

        assert len(resumed_jobs) == 1
        test_db.refresh(sample_qa_job)
        assert sample_qa_job.status == JobStatusEnum.running
        assert sample_qa_job.stage == QAJobStageEnum.scoring_answers
        assert sample_qa_job.rubric_specs == [
            {"rubric_id": sample_qa_job.judge.rubric_id, "judge_id": sample_qa_job.judge_id},
            {"rubric_id": sample_rubric.id, "judge_id": existing_empathy_judge.id},
        ]

    @pytest.mark.asyncio
    @patch("src.scoring.services.qa_job_processor._run_job_phased")
    @patch("src.scoring.services.qa_job_processor.gather_with_concurrency", new_callable=AsyncMock)
    async def test_run_qajobs_phased_prefers_explicit_specs_over_job_specs(
        self,
        mock_gather_with_concurrency,
        mock_run_job_phased,
        test_db,
        sample_snapshot,
        sample_qa_job,
    ):
        """Ad hoc reruns should score the requested judges without mutating stored job specs."""
        from src.scoring.services.qa_job_processor import run_qajobs_phased

        sample_qa_job.snapshot_id = sample_snapshot.id
        sample_qa_job.status = JobStatusEnum.running
        sample_qa_job.rubric_specs = [
            {"rubric_id": sample_qa_job.judge.rubric_id, "judge_id": sample_qa_job.judge_id},
        ]
        test_db.commit()

        explicit_specs = [
            {"rubric_id": sample_qa_job.judge.rubric_id, "judge_id": 999},
        ]
        mock_gather_with_concurrency.return_value = []

        await run_qajobs_phased(
            snapshot_id=sample_snapshot.id,
            question_ids=[sample_qa_job.question_id],
            all_jobs=[sample_qa_job],
            rubric_specs=explicit_specs,
        )

        mock_run_job_phased.assert_called_once_with(
            sample_qa_job.id,
            sample_snapshot.id,
            sample_qa_job.question_id,
            explicit_specs,
        )

    def test_uses_claim_processing_true_for_accuracy_judge(
        self, test_db, sample_snapshot, sample_question, sample_judge_claim_based
    ):
        """_uses_claim_processing returns True when judge is bound to a claim-based rubric."""
        processor = QAJobProcessor(
            test_db, sample_snapshot.id, sample_question.id, sample_judge_claim_based.id
        )
        assert processor._uses_claim_processing() is True

    def test_uses_claim_processing_false_for_response_level_judge(
        self, test_db, sample_snapshot, sample_question, sample_judge_response_level
    ):
        """_uses_claim_processing returns False when judge has no rubric_id."""
        processor = QAJobProcessor(
            test_db, sample_snapshot.id, sample_question.id, sample_judge_response_level.id
        )
        assert processor._uses_claim_processing() is False

    @pytest.mark.asyncio
    @patch("src.scoring.services.qa_job_processor._score_rubric_spec", new_callable=AsyncMock)
    @patch("src.scoring.services.qa_job_processor._generate_answer", new_callable=AsyncMock)
    @patch("src.scoring.services.qa_job_processor.SessionLocal")
    async def test_run_job_phased_schedules_claim_based_rubric_specs_directly(
        self, MockSessionLocal, mock_generate_answer, mock_score_rubric_spec, test_db, sample_snapshot, sample_question, sample_answer, sample_qa_job
    ):
        """Claim-based jobs should schedule rubric specs directly through _score_rubric_spec."""
        from src.scoring.services.qa_job_processor import _run_job_phased

        sample_qa_job.rubric_specs = [{"rubric_id": sample_qa_job.judge.rubric_id, "judge_id": sample_qa_job.judge_id}]
        sample_qa_job.snapshot_id = sample_snapshot.id
        sample_qa_job.question_id = sample_question.id
        sample_qa_job.answer_id = sample_answer.id
        sample_qa_job.status = JobStatusEnum.running
        sample_qa_job.stage = QAJobStageEnum.starting
        test_db.commit()
        mock_session = Mock(wraps=test_db)
        mock_session.close = Mock()
        MockSessionLocal.return_value = mock_session

        mock_generate_answer.return_value = None
        mock_score_rubric_spec.return_value = {
            "prompt_tokens": 0, "completion_tokens": 0, "total_cost": 0.0
        }

        await _run_job_phased(
            sample_qa_job.id,
            sample_snapshot.id,
            sample_question.id,
            sample_qa_job.rubric_specs,
        )

        mock_score_rubric_spec.assert_awaited_once_with(
            sample_qa_job.id,
            sample_qa_job.judge_id,
            sample_qa_job.judge.rubric_id,
        )

    @pytest.mark.asyncio
    @patch("src.scoring.services.qa_job_processor._score_rubric_spec", new_callable=AsyncMock)
    @patch("src.scoring.services.qa_job_processor._generate_answer", new_callable=AsyncMock)
    @patch("src.scoring.services.qa_job_processor.SessionLocal")
    async def test_run_job_phased_fails_when_scheduled_score_is_not_persisted(
        self,
        MockSessionLocal,
        mock_generate_answer,
        mock_score_rubric_spec,
        test_db,
        sample_snapshot,
        sample_question,
        sample_answer,
        sample_qa_job,
    ):
        """Unified jobs stay failed, not completed, when a scheduled score never lands in storage."""
        from src.scoring.services.qa_job_processor import _run_job_phased

        sample_qa_job.snapshot_id = sample_snapshot.id
        sample_qa_job.question_id = sample_question.id
        sample_qa_job.answer_id = sample_answer.id
        sample_qa_job.status = JobStatusEnum.running
        sample_qa_job.stage = QAJobStageEnum.starting
        sample_qa_job.rubric_specs = [{"rubric_id": sample_qa_job.judge.rubric_id, "judge_id": sample_qa_job.judge_id}]
        test_db.commit()

        mock_session = Mock(wraps=test_db)
        mock_session.close = Mock()
        MockSessionLocal.return_value = mock_session
        mock_score_rubric_spec.return_value = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_cost": 0.0,
        }

        await _run_job_phased(
            sample_qa_job.id,
            sample_snapshot.id,
            sample_question.id,
            sample_qa_job.rubric_specs,
        )

        failed_job = QAJobRepository.get_by_id(test_db, sample_qa_job.id)
        assert failed_job is not None
        assert failed_job.status == JobStatusEnum.failed
        assert "Missing persisted scores for scheduled rubric specs" in (failed_job.error_message or "")

    @pytest.mark.asyncio
    @patch("src.scoring.services.qa_job_processor.SessionLocal")
    async def test_score_rubric_spec_skips_existing_score(
        self,
        MockSessionLocal,
        test_db,
        sample_answer,
        sample_qa_job,
        sample_claims,
    ):
        """Full-set retries should not rescore rubric specs that already persisted a score."""
        from src.scoring.services.qa_job_processor import _score_rubric_spec

        mock_session = Mock(wraps=test_db)
        mock_session.close = Mock()
        MockSessionLocal.return_value = mock_session

        test_db.add(
            score := AnswerScore(
                answer_id=sample_answer.id,
                rubric_id=sample_qa_job.judge.rubric_id,
                judge_id=sample_qa_job.judge_id,
                overall_label="Accurate",
                explanation="Already persisted",
            )
        )
        for claim in sample_claims:
            claim.checked_at = claim.created_at + timedelta(seconds=1)
        test_db.flush()
        test_db.add_all(
            [
                AnswerClaimScore(
                    claim_id=claim.id,
                    answer_score_id=score.id,
                    label=True,
                    explanation="Persisted claim score",
                )
                for claim in sample_claims
            ]
        )
        sample_qa_job.answer_id = sample_answer.id
        sample_qa_job.status = JobStatusEnum.running
        test_db.commit()

        result = await _score_rubric_spec(
            sample_qa_job.id,
            sample_qa_job.judge_id,
            sample_qa_job.judge.rubric_id,
        )

        assert result == {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_cost": 0.0,
        }

    def test_is_rubric_score_complete_requires_full_claim_score_count(
        self,
        test_db,
        sample_answer,
        sample_qa_job,
        sample_claims,
    ):
        """Claim-based completeness requires one persisted claim score per current checkworthy claim."""
        for claim in sample_claims:
            claim.checked_at = claim.created_at + timedelta(seconds=1)
        test_db.commit()

        score = AnswerScoreRepository.create(
            test_db,
            {
                "answer_id": sample_answer.id,
                "rubric_id": sample_qa_job.judge.rubric_id,
                "judge_id": sample_qa_job.judge_id,
                "overall_label": "Accurate",
                "explanation": "Incomplete claim score set",
            },
        )
        test_db.add(
            AnswerClaimScore(
                claim_id=sample_claims[0].id,
                answer_score_id=score.id,
                label=True,
                explanation="Only one claim scored",
            )
        )
        test_db.commit()

        assert _is_rubric_score_complete(
            test_db,
            sample_answer.id,
            sample_qa_job.judge_id,
            sample_qa_job.judge.rubric_id,
        ) is False

    def test_create_all_jobs_resumes_completed_job_when_claim_scores_incomplete(
        self,
        test_db,
        sample_snapshot,
        sample_answer,
        sample_qa_job,
        sample_claims,
    ):
        """Completed jobs should reopen when a claim-based score row exists without the full claim score set."""
        for claim in sample_claims:
            claim.checked_at = claim.created_at + timedelta(seconds=1)
        test_db.commit()

        score = AnswerScoreRepository.create(
            test_db,
            {
                "answer_id": sample_answer.id,
                "rubric_id": sample_qa_job.judge.rubric_id,
                "judge_id": sample_qa_job.judge_id,
                "overall_label": "Accurate",
                "explanation": "Missing some claim scores",
            },
        )
        test_db.add(
            AnswerClaimScore(
                claim_id=sample_claims[0].id,
                answer_score_id=score.id,
                label=True,
                explanation="Only one claim scored",
            )
        )
        sample_qa_job.status = JobStatusEnum.completed
        sample_qa_job.stage = QAJobStageEnum.completed
        sample_qa_job.rubric_specs = [
            {"rubric_id": sample_qa_job.judge.rubric_id, "judge_id": sample_qa_job.judge_id},
        ]
        test_db.commit()

        jobs = create_all_jobs(
            db=test_db,
            snapshot_id=sample_snapshot.id,
            question_ids=[sample_qa_job.question_id],
            rubric_specs=sample_qa_job.rubric_specs,
        )

        assert len(jobs) == 1
        test_db.refresh(sample_qa_job)
        assert sample_qa_job.status == JobStatusEnum.running
        assert sample_qa_job.stage == QAJobStageEnum.scoring_answers

    @pytest.mark.asyncio
    @patch("src.scoring.services.qa_job_processor.extract_and_check_claims", new_callable=AsyncMock)
    @patch("src.scoring.services.qa_job_processor.AnswerJudge")
    @patch("src.scoring.services.qa_job_processor.SessionLocal")
    async def test_score_rubric_spec_rescores_incomplete_claim_score_set(
        self,
        MockSessionLocal,
        MockAnswerJudge,
        mock_extract_claims,
        test_db,
        sample_answer,
        sample_qa_job,
        sample_claims,
    ):
        """Claim-based skip logic should rerun when the existing score row is missing claim scores."""
        from src.scoring.services.qa_job_processor import _score_rubric_spec

        for claim in sample_claims:
            claim.checked_at = claim.created_at + timedelta(seconds=1)

        score = AnswerScoreRepository.create(
            test_db,
            {
                "answer_id": sample_answer.id,
                "rubric_id": sample_qa_job.judge.rubric_id,
                "judge_id": sample_qa_job.judge_id,
                "overall_label": "Accurate",
                "explanation": "Incomplete claim score set",
            },
        )
        test_db.add(
            AnswerClaimScore(
                claim_id=sample_claims[0].id,
                answer_score_id=score.id,
                label=True,
                explanation="Only one claim scored",
            )
        )
        sample_qa_job.answer_id = sample_answer.id
        sample_qa_job.status = JobStatusEnum.running
        test_db.commit()

        mock_session = Mock(wraps=test_db)
        mock_session.close = Mock()
        MockSessionLocal.return_value = mock_session

        mock_judge_instance = MockAnswerJudge.return_value
        mock_judge_instance.cost_tracker.get_summary.return_value = {
            "prompt_tokens": 11,
            "completion_tokens": 7,
            "total_cost": 0.3,
        }

        async def persist_complete_claim_scores(*args, **kwargs):
            repaired_score = AnswerScoreRepository.replace_for_answer_judge_rubric(
                test_db,
                {
                    "answer_id": sample_answer.id,
                    "rubric_id": sample_qa_job.judge.rubric_id,
                    "judge_id": sample_qa_job.judge_id,
                    "overall_label": "Accurate",
                    "explanation": "Now complete",
                },
            )
            test_db.add_all(
                [
                    AnswerClaimScore(
                        claim_id=claim.id,
                        answer_score_id=repaired_score.id,
                        label=True,
                        explanation="Recovered during rescore",
                    )
                    for claim in sample_claims
                ]
            )
            test_db.commit()

        mock_judge_instance.score = AsyncMock(side_effect=persist_complete_claim_scores)

        result = await _score_rubric_spec(
            sample_qa_job.id,
            sample_qa_job.judge_id,
            sample_qa_job.judge.rubric_id,
        )

        mock_extract_claims.assert_not_awaited()
        MockAnswerJudge.assert_called_once()
        mock_judge_instance.score.assert_awaited_once_with(raise_on_error=True)
        assert result == {
            "prompt_tokens": 11,
            "completion_tokens": 7,
            "total_cost": 0.3,
        }


@pytest.mark.unit
class TestQAJobPipelineResume:
    """Tests verifying pause/resume behavior: pause_qajob stops the pipeline, resume picks up correctly."""

    def _create_running_job(self, test_db, snapshot, question, judge):
        """Helper to create a running QAJob at starting stage."""
        return QAJobRepository.create(
            test_db,
            {
                "snapshot_id": snapshot.id,
                "question_id": question.id,
                "judge_id": judge.id,
                "type": QAJobTypeEnum.claim_scoring_full,
                "status": JobStatusEnum.running,
                "stage": QAJobStageEnum.starting,
            }
        )

    def _create_checked_claims(self, test_db, answer_id, count=2):
        """Helper to create claims with checked_at != created_at."""
        now = datetime.utcnow()
        claims = []
        for i in range(count):
            claim = AnswerClaim(
                answer_id=answer_id,
                claim_index=i,
                claim_text=f"Claim {i}.",
                checkworthy=True,
                created_at=now,
                checked_at=now + timedelta(seconds=1),
            )
            claims.append(claim)
        test_db.add_all(claims)
        test_db.commit()
        return claims

    @pytest.mark.asyncio
    @patch('src.scoring.services.qa_job_processor.generate_answer_for_job', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.extract_and_check_claims', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.AnswerJudge')
    async def test_pause_during_answer_gen_resumes_at_answer_gen(
        self, MockAnswerJudge, mock_claims, mock_answer,
        test_db, sample_snapshot, sample_question, sample_judge_claim_based
    ):
        """Pause during answer gen → pipeline stops → resume runs all 3 stages."""
        mock_judge_instance = MockAnswerJudge.return_value
        mock_judge_instance.score = AsyncMock()

        job = self._create_running_job(
            test_db, sample_snapshot, sample_question, sample_judge_claim_based,
        )

        # Side effect: pause the job during answer generation
        async def pause_during_answer(*args, **kwargs):
            await pause_qajob(test_db, job.id)

        mock_answer.side_effect = pause_during_answer

        # Run 1: pipeline pauses after answer gen
        processor = QAJobProcessor(
            test_db, sample_snapshot.id, sample_question.id, sample_judge_claim_based.id
        )
        await processor.run(job_id=job.id)

        mock_answer.assert_awaited_once()
        mock_claims.assert_not_awaited()
        mock_judge_instance.score.assert_not_awaited()
        test_db.refresh(job)
        assert job.status == JobStatusEnum.paused

        # Resume: no answer in DB (mock didn't create one) → starts from stage 0
        mock_answer.reset_mock()
        mock_answer.side_effect = None
        mock_claims.reset_mock()
        MockAnswerJudge.reset_mock()
        mock_judge_instance.score.reset_mock()

        await processor.run(job_id=job.id)

        mock_answer.assert_awaited_once()
        mock_claims.assert_awaited_once()
        mock_judge_instance.score.assert_awaited_once()

    @pytest.mark.asyncio
    @patch('src.scoring.services.qa_job_processor.generate_answer_for_job', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.extract_and_check_claims', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.AnswerJudge')
    async def test_pause_during_claim_processing_resumes_at_claims(
        self, MockAnswerJudge, mock_claims, mock_answer,
        test_db, sample_snapshot, sample_question, sample_judge_claim_based
    ):
        """Pause during claims → pipeline stops → set up answer in DB → resume skips to claims."""
        mock_judge_instance = MockAnswerJudge.return_value
        mock_judge_instance.score = AsyncMock()

        job = self._create_running_job(
            test_db, sample_snapshot, sample_question, sample_judge_claim_based,
        )

        # Side effect: pause during claim processing
        async def pause_during_claims(*args, **kwargs):
            await pause_qajob(test_db, job.id)

        mock_claims.side_effect = pause_during_claims

        # Run 1: answer gen runs, claims pauses, scoring never called
        processor = QAJobProcessor(
            test_db, sample_snapshot.id, sample_question.id, sample_judge_claim_based.id
        )
        await processor.run(job_id=job.id)

        mock_answer.assert_awaited_once()
        mock_claims.assert_awaited_once()
        mock_judge_instance.score.assert_not_awaited()
        test_db.refresh(job)
        assert job.status == JobStatusEnum.paused

        # Set up DB state: answer exists (simulating what answer gen produced)
        AnswerRepository.create(test_db, {
            "question_id": sample_question.id,
            "snapshot_id": sample_snapshot.id,
            "answer_content": "Test answer content.",
        })

        # Resume: answer exists, no claims → _get_start_index returns 1
        mock_answer.reset_mock()
        mock_claims.reset_mock()
        mock_claims.side_effect = None
        MockAnswerJudge.reset_mock()
        mock_judge_instance.score.reset_mock()

        await processor.run(job_id=job.id)

        mock_answer.assert_not_awaited()
        mock_claims.assert_awaited_once()
        mock_judge_instance.score.assert_awaited_once()

    @pytest.mark.asyncio
    @patch('src.scoring.services.qa_job_processor.generate_answer_for_job', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.extract_and_check_claims', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.AnswerJudge')
    async def test_pause_during_scoring_resumes_at_scoring(
        self, MockAnswerJudge, mock_claims, mock_answer,
        test_db, sample_snapshot, sample_question, sample_judge_claim_based
    ):
        """Pause during scoring → pipeline stops (not overwritten to completed) → resume runs scoring."""
        mock_judge_instance = MockAnswerJudge.return_value
        mock_judge_instance.score = AsyncMock()

        job = self._create_running_job(
            test_db, sample_snapshot, sample_question, sample_judge_claim_based,
        )

        # Side effect: pause during scoring
        async def pause_during_scoring():
            await pause_qajob(test_db, job.id)

        mock_judge_instance.score.side_effect = pause_during_scoring

        # Run 1: all stages called, but scoring pauses
        processor = QAJobProcessor(
            test_db, sample_snapshot.id, sample_question.id, sample_judge_claim_based.id
        )
        await processor.run(job_id=job.id)

        mock_answer.assert_awaited_once()
        mock_claims.assert_awaited_once()
        mock_judge_instance.score.assert_awaited_once()
        test_db.refresh(job)
        assert job.status == JobStatusEnum.paused
        assert job.stage != QAJobStageEnum.completed  # Bug fix: not overwritten

        # Set up DB state: answer + checked claims (simulating completed stages)
        answer = AnswerRepository.create(test_db, {
            "question_id": sample_question.id,
            "snapshot_id": sample_snapshot.id,
            "answer_content": "Test answer content.",
        })
        self._create_checked_claims(test_db, answer.id)

        # Resume: answer + checked claims exist, no score → _get_start_index returns 2
        mock_answer.reset_mock()
        mock_claims.reset_mock()
        MockAnswerJudge.reset_mock()
        mock_judge_instance.score.reset_mock()
        mock_judge_instance.score.side_effect = None

        await processor.run(job_id=job.id)

        mock_answer.assert_not_awaited()
        mock_claims.assert_not_awaited()
        mock_judge_instance.score.assert_awaited_once()

    @pytest.mark.asyncio
    @patch('src.scoring.services.qa_job_processor.generate_answer_for_job', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.extract_and_check_claims', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.AnswerJudge')
    async def test_completed_status_after_full_pipeline(
        self, MockAnswerJudge, mock_claims, mock_answer,
        test_db, sample_snapshot, sample_question, sample_judge_claim_based
    ):
        """Full pipeline from starting → job ends with status=completed, stage=completed."""
        mock_judge_instance = MockAnswerJudge.return_value
        mock_judge_instance.score = AsyncMock()

        job = self._create_running_job(
            test_db, sample_snapshot, sample_question, sample_judge_claim_based,
        )

        processor = QAJobProcessor(
            test_db, sample_snapshot.id, sample_question.id, sample_judge_claim_based.id
        )
        await processor.run(job_id=job.id)

        test_db.refresh(job)
        assert job.status == JobStatusEnum.completed
        assert job.stage == QAJobStageEnum.completed

    @pytest.mark.asyncio
    @patch('src.scoring.services.qa_job_processor.generate_answer_for_job', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.extract_and_check_claims', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.AnswerJudge')
    async def test_new_judge_skips_to_scoring_only(
        self, MockAnswerJudge, mock_claims, mock_answer,
        test_db, sample_snapshot, sample_question, sample_judge_claim_based
    ):
        """Answer + checked claims + score for judge A exist. New judge B → scoring only."""
        mock_judge_instance = MockAnswerJudge.return_value
        mock_judge_instance.score = AsyncMock()

        # Set up complete data for judge A
        answer = AnswerRepository.create(test_db, {
            "question_id": sample_question.id,
            "snapshot_id": sample_snapshot.id,
            "answer_content": "Test answer content.",
        })
        self._create_checked_claims(test_db, answer.id)
        AnswerScoreRepository.create(test_db, {
            "answer_id": answer.id,
            "rubric_id": sample_judge_claim_based.rubric_id,
            "judge_id": sample_judge_claim_based.id,
            "overall_label": "Accurate",
            "explanation": "All claims supported.",
        })

        # Create judge B
        judge_b = Judge(
            name="Judge B",
            model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
            prompt_template="Template B",
            params={},
            rubric_id=sample_judge_claim_based.rubric_id,
            is_baseline=False,
            is_editable=True,
        )
        test_db.add(judge_b)
        test_db.commit()
        test_db.refresh(judge_b)

        # Create job for judge B
        job = self._create_running_job(
            test_db, sample_snapshot, sample_question, judge_b,
        )

        processor = QAJobProcessor(
            test_db, sample_snapshot.id, sample_question.id, judge_b.id
        )
        await processor.run(job_id=job.id)

        mock_answer.assert_not_awaited()
        mock_claims.assert_not_awaited()
        mock_judge_instance.score.assert_awaited_once()

    @pytest.mark.asyncio
    @patch('src.scoring.services.qa_job_processor.generate_answer_for_job', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.extract_and_check_claims', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.AnswerJudge')
    async def test_stage_failure_sets_failed_status(
        self, MockAnswerJudge, mock_claims, mock_answer,
        test_db, sample_snapshot, sample_question, sample_judge_claim_based
    ):
        """Stage sets status=failed internally → pipeline stops, later stages skipped.

        This mirrors production behavior where stage functions (e.g. extract_and_check_claims)
        catch their own exceptions, set status=failed via QAJobRepository, and return normally.
        """
        mock_judge_instance = MockAnswerJudge.return_value
        mock_judge_instance.score = AsyncMock()

        job = self._create_running_job(
            test_db, sample_snapshot, sample_question, sample_judge_claim_based,
        )

        # Simulate real stage behavior: catch error internally, set failed, return normally
        async def fail_internally(*args, **kwargs):
            QAJobRepository.update_status(
                test_db, job.id, JobStatusEnum.failed, QAJobStageEnum.processing_answers
            )

        mock_claims.side_effect = fail_internally

        processor = QAJobProcessor(
            test_db, sample_snapshot.id, sample_question.id, sample_judge_claim_based.id
        )
        await processor.run(job_id=job.id)

        test_db.refresh(job)
        assert job.status == JobStatusEnum.failed
        assert job.stage == QAJobStageEnum.processing_answers

        mock_answer.assert_awaited_once()
        mock_claims.assert_awaited_once()
        mock_judge_instance.score.assert_not_awaited()

    @pytest.mark.asyncio
    @patch('src.scoring.services.qa_job_processor.generate_answer_for_job', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.extract_and_check_claims', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.AnswerJudge')
    async def test_failed_job_can_be_resumed(
        self, MockAnswerJudge, mock_claims, mock_answer,
        test_db, sample_snapshot, sample_question, sample_judge_claim_based
    ):
        """Stage fails internally → job marked failed → resume retries from correct stage."""
        mock_judge_instance = MockAnswerJudge.return_value
        mock_judge_instance.score = AsyncMock()

        job = self._create_running_job(
            test_db, sample_snapshot, sample_question, sample_judge_claim_based,
        )

        # Run 1: claims fails internally (like production)
        async def fail_internally(*args, **kwargs):
            QAJobRepository.update_status(
                test_db, job.id, JobStatusEnum.failed, QAJobStageEnum.processing_answers
            )

        mock_claims.side_effect = fail_internally

        processor = QAJobProcessor(
            test_db, sample_snapshot.id, sample_question.id, sample_judge_claim_based.id
        )
        await processor.run(job_id=job.id)

        test_db.refresh(job)
        assert job.status == JobStatusEnum.failed

        # Set up DB state: answer exists (simulating what answer gen produced)
        AnswerRepository.create(test_db, {
            "question_id": sample_question.id,
            "snapshot_id": sample_snapshot.id,
            "answer_content": "Test answer content.",
        })

        # Resume: answer exists, no claims → _get_start_index returns 1
        mock_answer.reset_mock()
        mock_claims.reset_mock()
        mock_claims.side_effect = None
        MockAnswerJudge.reset_mock()
        mock_judge_instance.score.reset_mock()

        await processor.run(job_id=job.id)

        mock_answer.assert_not_awaited()
        mock_claims.assert_awaited_once()
        mock_judge_instance.score.assert_awaited_once()
        test_db.refresh(job)
        assert job.status == JobStatusEnum.completed

    @pytest.mark.asyncio
    @patch('src.scoring.services.qa_job_processor.generate_answer_for_job', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.extract_and_check_claims', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.AnswerJudge')
    async def test_unhandled_exception_sets_failed_status(
        self, MockAnswerJudge, mock_claims, mock_answer,
        test_db, sample_snapshot, sample_question, sample_judge_claim_based
    ):
        """Stage raises unhandled exception → pipeline catches it, sets failed, stops.

        Safety net for cases where stage functions don't catch their own errors
        (e.g. unexpected crashes, programming errors).
        """
        mock_judge_instance = MockAnswerJudge.return_value
        mock_judge_instance.score = AsyncMock()

        job = self._create_running_job(
            test_db, sample_snapshot, sample_question, sample_judge_claim_based,
        )

        mock_answer.side_effect = RuntimeError("unexpected crash")

        processor = QAJobProcessor(
            test_db, sample_snapshot.id, sample_question.id, sample_judge_claim_based.id
        )
        await processor.run(job_id=job.id)

        test_db.refresh(job)
        assert job.status == JobStatusEnum.failed
        assert job.stage == QAJobStageEnum.generating_answers

        mock_answer.assert_awaited_once()
        mock_claims.assert_not_awaited()
        mock_judge_instance.score.assert_not_awaited()


@pytest.mark.unit
class TestPauseBatchEdgeCases:
    """Tests verifying pause_qajobs_batch handles non-running jobs gracefully."""

    def _create_questions(self, test_db, target, job, persona, count):
        """Helper to create N questions for testing."""
        questions = []
        for i in range(count):
            q = Question(
                job_id=job.id,
                persona_id=persona.id,
                target_id=target.id,
                text=f"Test question {i}?",
                type=QuestionTypeEnum.typical,
                scope=QuestionScopeEnum.in_kb,
                status=StatusEnum.approved,
            )
            test_db.add(q)
            questions.append(q)
        test_db.commit()
        for q in questions:
            test_db.refresh(q)
        return questions

    def _create_job(self, test_db, snapshot, question, judge, status, stage=QAJobStageEnum.starting):
        """Helper to create a QAJob with a specific status."""
        return QAJobRepository.create(
            test_db,
            {
                "snapshot_id": snapshot.id,
                "question_id": question.id,
                "judge_id": judge.id,
                "type": QAJobTypeEnum.claim_scoring_full,
                "status": status,
                "stage": stage,
            }
        )

    @pytest.mark.asyncio
    async def test_pause_batch_skips_completed_jobs(
        self, test_db, sample_snapshot, sample_target, sample_job, sample_personas, sample_judge_claim_based
    ):
        """Batch with 2 running + 1 completed → only running jobs paused, no error."""
        questions = self._create_questions(test_db, sample_target, sample_job, sample_personas[0], 3)
        job1 = self._create_job(test_db, sample_snapshot, questions[0], sample_judge_claim_based, JobStatusEnum.running)
        job2 = self._create_job(test_db, sample_snapshot, questions[1], sample_judge_claim_based, JobStatusEnum.running)
        job3 = self._create_job(test_db, sample_snapshot, questions[2], sample_judge_claim_based, JobStatusEnum.completed, QAJobStageEnum.completed)

        result = await pause_qajobs_batch(test_db, [job1.id, job2.id, job3.id])

        test_db.refresh(job1)
        test_db.refresh(job2)
        test_db.refresh(job3)
        assert job1.status == JobStatusEnum.paused
        assert job2.status == JobStatusEnum.paused
        assert job3.status == JobStatusEnum.completed  # unchanged

    @pytest.mark.asyncio
    async def test_pause_batch_skips_failed_jobs(
        self, test_db, sample_snapshot, sample_target, sample_job, sample_personas, sample_judge_claim_based
    ):
        """Batch with 1 running + 1 failed → running paused, failed unchanged."""
        questions = self._create_questions(test_db, sample_target, sample_job, sample_personas[0], 2)
        job1 = self._create_job(test_db, sample_snapshot, questions[0], sample_judge_claim_based, JobStatusEnum.running)
        job2 = self._create_job(test_db, sample_snapshot, questions[1], sample_judge_claim_based, JobStatusEnum.failed)

        result = await pause_qajobs_batch(test_db, [job1.id, job2.id])

        test_db.refresh(job1)
        test_db.refresh(job2)
        assert job1.status == JobStatusEnum.paused
        assert job2.status == JobStatusEnum.failed  # unchanged

    @pytest.mark.asyncio
    async def test_pause_batch_all_non_running_returns_empty(
        self, test_db, sample_snapshot, sample_target, sample_job, sample_personas, sample_judge_claim_based
    ):
        """Batch of all completed jobs → returns empty list, no error."""
        questions = self._create_questions(test_db, sample_target, sample_job, sample_personas[0], 2)
        job1 = self._create_job(test_db, sample_snapshot, questions[0], sample_judge_claim_based, JobStatusEnum.completed, QAJobStageEnum.completed)
        job2 = self._create_job(test_db, sample_snapshot, questions[1], sample_judge_claim_based, JobStatusEnum.completed, QAJobStageEnum.completed)

        result = await pause_qajobs_batch(test_db, [job1.id, job2.id])

        assert len(result) == 0
        test_db.refresh(job1)
        test_db.refresh(job2)
        assert job1.status == JobStatusEnum.completed
        assert job2.status == JobStatusEnum.completed

    @pytest.mark.asyncio
    async def test_pause_batch_mixed_statuses(
        self, test_db, sample_snapshot, sample_target, sample_job, sample_personas, sample_judge_claim_based
    ):
        """Batch with running + completed + failed + paused → only running gets paused."""
        questions = self._create_questions(test_db, sample_target, sample_job, sample_personas[0], 4)
        running_job = self._create_job(test_db, sample_snapshot, questions[0], sample_judge_claim_based, JobStatusEnum.running)
        completed_job = self._create_job(test_db, sample_snapshot, questions[1], sample_judge_claim_based, JobStatusEnum.completed, QAJobStageEnum.completed)
        failed_job = self._create_job(test_db, sample_snapshot, questions[2], sample_judge_claim_based, JobStatusEnum.failed)
        paused_job = self._create_job(test_db, sample_snapshot, questions[3], sample_judge_claim_based, JobStatusEnum.paused)

        result = await pause_qajobs_batch(
            test_db, [running_job.id, completed_job.id, failed_job.id, paused_job.id]
        )

        test_db.refresh(running_job)
        test_db.refresh(completed_job)
        test_db.refresh(failed_job)
        test_db.refresh(paused_job)
        assert running_job.status == JobStatusEnum.paused
        assert completed_job.status == JobStatusEnum.completed
        assert failed_job.status == JobStatusEnum.failed
        assert paused_job.status == JobStatusEnum.paused


@pytest.mark.unit
class TestGetOrCreateQAJobsBatch:
    """Tests for reopening a shared QAJob for additional judges."""

    def test_reopens_completed_job_when_requested_judge_score_missing(
        self,
        test_db,
        sample_snapshot,
        sample_question,
        sample_answer,
        sample_judge_claim_based,
        sample_judge_response_level,
    ):
        job = QAJobRepository.create(
            test_db,
            {
                "snapshot_id": sample_snapshot.id,
                "question_id": sample_question.id,
                "judge_id": sample_judge_claim_based.id,
                "answer_id": sample_answer.id,
                "type": QAJobTypeEnum.claim_scoring_full,
                "status": JobStatusEnum.completed,
                "stage": QAJobStageEnum.completed,
            }
        )

        jobs = get_or_create_qajobs_batch(
            test_db,
            snapshot_id=sample_snapshot.id,
            judge_id=sample_judge_response_level.id,
            question_ids=[sample_question.id],
        )

        assert len(jobs) == 1
        test_db.refresh(job)
        assert job.status == JobStatusEnum.running
        assert job.stage == QAJobStageEnum.scoring_answers


@pytest.mark.unit
class TestBatchEdgeCases:
    """Tests for edge cases in run_qajobs_batch."""

    @pytest.mark.asyncio
    @patch('src.scoring.services.qa_job_processor.generate_answer_for_job', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.extract_and_check_claims', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.AnswerJudge')
    async def test_batch_creates_missing_jobs_and_processes_all(
        self, MockAnswerJudge, mock_claims, mock_answer,
        test_db, test_db_factory, sample_snapshot, sample_questions, sample_judge_claim_based
    ):
        """question_ids includes a question with no existing job → should not crash.

        get_or_create_qajobs_batch creates jobs for all questions, so the mapping
        should cover every question_id. This test verifies the full batch flow.
        """
        mock_judge_instance = MockAnswerJudge.return_value
        mock_judge_instance.score = AsyncMock()

        q1, q2 = sample_questions[0], sample_questions[1]

        # Pre-create a job only for q1
        QAJobRepository.create(test_db, {
            "snapshot_id": sample_snapshot.id,
            "question_id": q1.id,
            "judge_id": sample_judge_claim_based.id,
            "type": QAJobTypeEnum.claim_scoring_full,
            "status": JobStatusEnum.running,
            "stage": QAJobStageEnum.starting,
        })

        # Patch SessionLocal so per-job isolated sessions use the in-memory
        # test database instead of the production engine.
        with patch(
            'src.scoring.services.qa_job_processor.SessionLocal',
            test_db_factory,
        ):
            result = await run_qajobs_batch(
                test_db, sample_snapshot.id, sample_judge_claim_based.id,
                question_ids=[q1.id, q2.id],
            )

        # Both jobs should complete (get_or_create creates the missing one)
        assert len(result) == 2
        for job in result:
            assert job is not None
