"""
Unit tests for QAJobProcessor service.
"""

import pytest
from unittest.mock import Mock, patch

from src.scoring.services.qa_job_processor import QAJobProcessor, run_qajob, pause_qajob
from src.common.database.models import JobStatusEnum, QAJobStageEnum, QAJobTypeEnum


@pytest.mark.unit
class TestQAJobProcessor:
    """Unit tests for QAJobProcessor class."""

    @patch('src.scoring.services.qa_job_processor.generate_answer_for_job')
    def test_run_creates_new_job(
        self, mock_generate_answer, test_db, sample_snapshot, sample_question, sample_judge_claim_based
    ):
        """Test that run with job_id=None creates a new job and starts pipeline."""
        # Run
        processor = QAJobProcessor(
            test_db, sample_snapshot.id, sample_question.id, sample_judge_claim_based.id
        )
        job = processor.run(job_id=None)

        # Verify job created
        assert job is not None
        assert job.status == JobStatusEnum.running
        assert job.stage == QAJobStageEnum.starting
        assert job.snapshot_id == sample_snapshot.id
        assert job.question_id == sample_question.id
        assert job.judge_id == sample_judge_claim_based.id

        # Verify pipeline started (generate_answer_for_job called)
        mock_generate_answer.assert_called_once()

    def test_run_job_not_found_raises_error(self, test_db, sample_snapshot, sample_question, sample_judge_claim_based):
        """Test that run with non-existent job_id raises ValueError."""
        processor = QAJobProcessor(
            test_db, sample_snapshot.id, sample_question.id, sample_judge_claim_based.id
        )

        with pytest.raises(ValueError, match="QAJob with id 999 not found"):
            processor.run(job_id=999)

    def test_run_job_not_paused_running_raises_error(
        self, test_db, sample_qa_job, sample_snapshot, sample_question
    ):
        """Test that resuming a running job raises specific error."""
        # Job is already running
        sample_qa_job.status = JobStatusEnum.running
        test_db.commit()

        processor = QAJobProcessor(
            test_db, sample_snapshot.id, sample_question.id, sample_qa_job.judge_id
        )

        with pytest.raises(ValueError, match="Job .* is already running"):
            processor.run(job_id=sample_qa_job.id)

    def test_run_job_not_paused_failed_raises_error(
        self, test_db, sample_qa_job, sample_snapshot, sample_question
    ):
        """Test that resuming a failed job raises specific error with retry suggestion."""
        # Set job to failed
        sample_qa_job.status = JobStatusEnum.failed
        test_db.commit()

        processor = QAJobProcessor(
            test_db, sample_snapshot.id, sample_question.id, sample_qa_job.judge_id
        )

        with pytest.raises(ValueError, match="Job .* is failed. Create a new run to retry"):
            processor.run(job_id=sample_qa_job.id)

    def test_run_job_not_paused_completed_raises_error(
        self, test_db, sample_qa_job, sample_snapshot, sample_question
    ):
        """Test that resuming a completed job raises specific error with rerun suggestion."""
        # Set job to completed
        sample_qa_job.status = JobStatusEnum.completed
        test_db.commit()

        processor = QAJobProcessor(
            test_db, sample_snapshot.id, sample_question.id, sample_qa_job.judge_id
        )

        with pytest.raises(ValueError, match="Job .* is completed.*Create a new run to rerun"):
            processor.run(job_id=sample_qa_job.id)

    @patch('src.scoring.services.qa_job_processor.score_answer')
    def test_run_with_stage_override_calls_right_function(
        self, mock_score_answer, test_db, sample_qa_job, sample_snapshot, sample_question, sample_answer, sample_claims
    ):
        """Test that providing stage=scoring_answers directly calls score_answer()."""
        # Set job to paused so we can resume it
        sample_qa_job.status = JobStatusEnum.paused
        sample_qa_job.stage = QAJobStageEnum.processing_answers
        test_db.commit()

        # Run with stage override
        processor = QAJobProcessor(
            test_db, sample_snapshot.id, sample_question.id, sample_qa_job.judge_id
        )
        processor.run(job_id=sample_qa_job.id, stage=QAJobStageEnum.scoring_answers)

        # Verify score_answer was called
        mock_score_answer.assert_called_once_with(test_db, sample_qa_job.id)

    def test_pause_updates_status(self, test_db, sample_qa_job):
        """Test that pause_qajob updates status to paused."""
        # Job starts as running
        assert sample_qa_job.status == JobStatusEnum.running

        # Pause
        paused_job = pause_qajob(test_db, sample_qa_job.id)

        # Verify status changed
        assert paused_job.status == JobStatusEnum.paused
        assert paused_job.stage == sample_qa_job.stage  # Stage unchanged

    @patch('src.scoring.services.qa_job_processor.extract_and_check_claims')
    def test_resume_continues_from_stage(
        self, mock_extract_claims, test_db, sample_qa_job, sample_snapshot, sample_question, sample_answer
    ):
        """Test that resuming a paused job continues from where it left off."""
        # Pause job at processing_answers stage
        sample_qa_job.status = JobStatusEnum.paused
        sample_qa_job.stage = QAJobStageEnum.processing_answers
        test_db.commit()

        # Resume
        processor = QAJobProcessor(
            test_db, sample_snapshot.id, sample_question.id, sample_qa_job.judge_id
        )
        processor.run(job_id=sample_qa_job.id)

        # Verify it continued from processing_answers stage
        mock_extract_claims.assert_called_once_with(test_db, sample_qa_job.id)

        # Verify status is now running
        test_db.refresh(sample_qa_job)
        assert sample_qa_job.status == JobStatusEnum.running

    @patch('src.scoring.services.qa_job_processor.generate_answer_for_job')
    @patch('src.scoring.services.qa_job_processor.extract_and_check_claims')
    @patch('src.scoring.services.qa_job_processor.score_answer')
    def test_full_pipeline_integration(
        self, mock_score_answer, mock_extract_claims, mock_generate_answer,
        test_db, sample_snapshot, sample_question, sample_judge_claim_based
    ):
        """Test full pipeline goes through all stages: starting -> generating -> processing -> scoring -> completed."""

        # Create a new job
        processor = QAJobProcessor(
            test_db, sample_snapshot.id, sample_question.id, sample_judge_claim_based.id
        )
        job = processor.run(job_id=None)

        # Verify started at 'starting' stage and called generate_answer_for_job
        assert job.stage == QAJobStageEnum.starting
        mock_generate_answer.assert_called_once()

        # Reset mocks
        mock_generate_answer.reset_mock()
        mock_extract_claims.reset_mock()
        mock_score_answer.reset_mock()

        # Simulate progression through stages
        # Stage 1: generating_answers
        job.stage = QAJobStageEnum.generating_answers
        test_db.commit()

        # Use the answer that was already created during job creation (from placeholder in run())
        from src.common.database.repositories.answer_repo import AnswerRepository
        answer = AnswerRepository.get_by_question_and_snapshot(
            test_db, sample_question.id, sample_snapshot.id
        )
        # Update it with content
        answer.answer_content = "Test answer"
        answer.chat_id = "chat_test"
        answer.message_id = "msg_test"
        test_db.commit()

        processor._trigger_pipeline_stage(job)
        mock_extract_claims.assert_called_once()

        # Stage 2: processing_answers
        mock_extract_claims.reset_mock()
        job.stage = QAJobStageEnum.processing_answers
        test_db.commit()

        # Create claims to simulate completion of claim processing
        from src.common.database.models import AnswerClaim
        from datetime import datetime
        claims = [
            AnswerClaim(
                answer_id=answer.id,
                claim_index=0,
                text="Test claim 1",
                checkworthy=True,
                created_at=datetime(2024, 1, 1),
                checked_at=datetime(2024, 1, 2)  # Different to show it was checked
            ),
            AnswerClaim(
                answer_id=answer.id,
                claim_index=1,
                text="Test claim 2",
                checkworthy=True,
                created_at=datetime(2024, 1, 1),
                checked_at=datetime(2024, 1, 2)
            )
        ]
        test_db.add_all(claims)
        test_db.commit()

        # Update job with answer_id
        job.answer_id = answer.id
        test_db.commit()

        processor._trigger_pipeline_stage(job)
        mock_score_answer.assert_called_once()

        # Stage 3: scoring_answers
        mock_score_answer.reset_mock()
        job.stage = QAJobStageEnum.scoring_answers
        test_db.commit()

        # Create score to simulate completion of scoring
        from src.common.database.models import AnswerScore
        score = AnswerScore(
            answer_id=answer.id,
            judge_id=sample_judge_claim_based.id,
            overall_label=True,
            explanation="Test explanation"
        )
        test_db.add(score)
        test_db.commit()

        processor._trigger_pipeline_stage(job)

        # Verify job marked as completed
        test_db.refresh(job)
        assert job.status == JobStatusEnum.completed
