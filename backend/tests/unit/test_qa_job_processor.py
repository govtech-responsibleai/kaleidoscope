"""
Unit tests for QAJobProcessor service.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

from src.scoring.services.qa_job_processor import QAJobProcessor, run_qajob, pause_qajob
from src.common.database.models import (
    JobStatusEnum, QAJobStageEnum, QAJobTypeEnum,
    Answer, AnswerClaim, AnswerScore, Judge, JudgeTypeEnum,
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
    @patch('src.scoring.services.qa_job_processor.score_answer', new_callable=AsyncMock)
    async def test_run_processes_existing_job(
        self, mock_score_answer, mock_extract_claims, mock_generate_answer,
        test_db, sample_snapshot, sample_question, sample_judge_claim_based
    ):
        """Test that run processes an existing job through the full pipeline."""
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
    async def test_run_job_not_found_raises_error(self, test_db, sample_snapshot, sample_question, sample_judge_claim_based):
        """Test that run with non-existent job_id raises ValueError."""
        processor = QAJobProcessor(
            test_db, sample_snapshot.id, sample_question.id, sample_judge_claim_based.id
        )

        with pytest.raises(ValueError, match="QAJob with id 999 not found"):
            await processor.run(job_id=999)

    @pytest.mark.asyncio
    @patch('src.scoring.services.qa_job_processor.score_answer', new_callable=AsyncMock)
    async def test_run_scoring_only_when_claims_checked(
        self, mock_score_answer, test_db, sample_qa_job, sample_snapshot, sample_question, sample_answer
    ):
        """Test that pipeline skips to scoring when answer and fully-checked claims exist but score doesn't."""
        from datetime import datetime, timedelta
        from src.common.database.models import AnswerClaim

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

        # Verify score_answer was called
        mock_score_answer.assert_awaited_once_with(test_db, sample_qa_job.id)


    @pytest.mark.asyncio
    @patch('src.scoring.services.qa_job_processor.generate_answer_for_job', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.extract_and_check_claims', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.score_answer', new_callable=AsyncMock)
    async def test_full_pipeline_runs_all_stages(
        self, mock_score_answer, mock_extract_claims, mock_generate_answer,
        test_db, sample_snapshot, sample_question, sample_judge_claim_based
    ):
        """Test full pipeline calls all three stages sequentially when no prior data exists."""

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
        mock_score_answer.assert_awaited_once()

        # Verify job marked as completed
        test_db.refresh(job)
        assert job.status == JobStatusEnum.completed
        assert job.stage == QAJobStageEnum.completed


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
    @patch('src.scoring.services.qa_job_processor.score_answer', new_callable=AsyncMock)
    async def test_pause_during_answer_gen_resumes_at_answer_gen(
        self, mock_score, mock_claims, mock_answer,
        test_db, sample_snapshot, sample_question, sample_judge_claim_based
    ):
        """Pause during answer gen → pipeline stops → resume runs all 3 stages."""
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
        mock_score.assert_not_awaited()
        test_db.refresh(job)
        assert job.status == JobStatusEnum.paused

        # Resume: no answer in DB (mock didn't create one) → starts from stage 0
        mock_answer.reset_mock()
        mock_answer.side_effect = None
        mock_claims.reset_mock()
        mock_score.reset_mock()

        await processor.run(job_id=job.id)

        mock_answer.assert_awaited_once()
        mock_claims.assert_awaited_once()
        mock_score.assert_awaited_once()

    @pytest.mark.asyncio
    @patch('src.scoring.services.qa_job_processor.generate_answer_for_job', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.extract_and_check_claims', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.score_answer', new_callable=AsyncMock)
    async def test_pause_during_claim_processing_resumes_at_claims(
        self, mock_score, mock_claims, mock_answer,
        test_db, sample_snapshot, sample_question, sample_judge_claim_based
    ):
        """Pause during claims → pipeline stops → set up answer in DB → resume skips to claims."""
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
        mock_score.assert_not_awaited()
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
        mock_score.reset_mock()

        await processor.run(job_id=job.id)

        mock_answer.assert_not_awaited()
        mock_claims.assert_awaited_once()
        mock_score.assert_awaited_once()

    @pytest.mark.asyncio
    @patch('src.scoring.services.qa_job_processor.generate_answer_for_job', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.extract_and_check_claims', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.score_answer', new_callable=AsyncMock)
    async def test_pause_during_scoring_resumes_at_scoring(
        self, mock_score, mock_claims, mock_answer,
        test_db, sample_snapshot, sample_question, sample_judge_claim_based
    ):
        """Pause during scoring → pipeline stops (not overwritten to completed) → resume runs scoring."""
        job = self._create_running_job(
            test_db, sample_snapshot, sample_question, sample_judge_claim_based,
        )

        # Side effect: pause during scoring
        async def pause_during_scoring(*args, **kwargs):
            await pause_qajob(test_db, job.id)

        mock_score.side_effect = pause_during_scoring

        # Run 1: all stages called, but scoring pauses
        processor = QAJobProcessor(
            test_db, sample_snapshot.id, sample_question.id, sample_judge_claim_based.id
        )
        await processor.run(job_id=job.id)

        mock_answer.assert_awaited_once()
        mock_claims.assert_awaited_once()
        mock_score.assert_awaited_once()
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
        mock_score.reset_mock()
        mock_score.side_effect = None

        await processor.run(job_id=job.id)

        mock_answer.assert_not_awaited()
        mock_claims.assert_not_awaited()
        mock_score.assert_awaited_once()

    @pytest.mark.asyncio
    @patch('src.scoring.services.qa_job_processor.generate_answer_for_job', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.extract_and_check_claims', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.score_answer', new_callable=AsyncMock)
    async def test_completed_status_after_full_pipeline(
        self, mock_score, mock_claims, mock_answer,
        test_db, sample_snapshot, sample_question, sample_judge_claim_based
    ):
        """Full pipeline from starting → job ends with status=completed, stage=completed."""
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
    @patch('src.scoring.services.qa_job_processor.score_answer', new_callable=AsyncMock)
    async def test_new_judge_skips_to_scoring_only(
        self, mock_score, mock_claims, mock_answer,
        test_db, sample_snapshot, sample_question, sample_judge_claim_based
    ):
        """Answer + checked claims + score for judge A exist. New judge B → scoring only."""
        # Set up complete data for judge A
        answer = AnswerRepository.create(test_db, {
            "question_id": sample_question.id,
            "snapshot_id": sample_snapshot.id,
            "answer_content": "Test answer content.",
        })
        self._create_checked_claims(test_db, answer.id)
        AnswerScoreRepository.create(test_db, {
            "answer_id": answer.id,
            "judge_id": sample_judge_claim_based.id,
            "overall_label": True,
            "explanation": "All claims supported.",
        })

        # Create judge B
        judge_b = Judge(
            name="Judge B",
            model_name="gemini/gemini-2.5-flash-lite",
            prompt_template="Template B",
            params={},
            judge_type=JudgeTypeEnum.claim_based,
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
        mock_score.assert_awaited_once()

    @pytest.mark.asyncio
    @patch('src.scoring.services.qa_job_processor.generate_answer_for_job', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.extract_and_check_claims', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.score_answer', new_callable=AsyncMock)
    async def test_stage_failure_sets_failed_status(
        self, mock_score, mock_claims, mock_answer,
        test_db, sample_snapshot, sample_question, sample_judge_claim_based
    ):
        """Stage sets status=failed internally → pipeline stops, later stages skipped.

        This mirrors production behavior where stage functions (e.g. extract_and_check_claims)
        catch their own exceptions, set status=failed via QAJobRepository, and return normally.
        """
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
        mock_score.assert_not_awaited()

    @pytest.mark.asyncio
    @patch('src.scoring.services.qa_job_processor.generate_answer_for_job', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.extract_and_check_claims', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.score_answer', new_callable=AsyncMock)
    async def test_failed_job_can_be_resumed(
        self, mock_score, mock_claims, mock_answer,
        test_db, sample_snapshot, sample_question, sample_judge_claim_based
    ):
        """Stage fails internally → job marked failed → resume retries from correct stage."""
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
        mock_score.reset_mock()

        await processor.run(job_id=job.id)

        mock_answer.assert_not_awaited()
        mock_claims.assert_awaited_once()
        mock_score.assert_awaited_once()
        test_db.refresh(job)
        assert job.status == JobStatusEnum.completed

    @pytest.mark.asyncio
    @patch('src.scoring.services.qa_job_processor.generate_answer_for_job', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.extract_and_check_claims', new_callable=AsyncMock)
    @patch('src.scoring.services.qa_job_processor.score_answer', new_callable=AsyncMock)
    async def test_unhandled_exception_sets_failed_status(
        self, mock_score, mock_claims, mock_answer,
        test_db, sample_snapshot, sample_question, sample_judge_claim_based
    ):
        """Stage raises unhandled exception → pipeline catches it, sets failed, stops.

        Safety net for cases where stage functions don't catch their own errors
        (e.g. unexpected crashes, programming errors).
        """
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
        mock_score.assert_not_awaited()
