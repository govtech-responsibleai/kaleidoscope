"""
Integration tests for metrics API endpoints.
"""

import pytest


@pytest.mark.integration
class TestMetricsAPI:
    """Integration tests for metrics API."""

    def test_scoring_pending_counts_are_returned_in_one_response(
        self,
        test_client,
        test_db,
        sample_target,
        sample_job,
        sample_personas,
        sample_snapshot,
        sample_question,
        sample_answer,
        sample_rubric,
    ):
        """The scoring page should be able to load pending counts without per-judge fan-out."""
        from src.common.database.models import Judge, Question, JudgeTypeEnum, QuestionTypeEnum, QuestionScopeEnum, StatusEnum

        unanswered_question = Question(
            job_id=sample_job.id,
            persona_id=sample_personas[0].id,
            target_id=sample_target.id,
            text="What governance controls should be added?",
            type=QuestionTypeEnum.typical,
            scope=QuestionScopeEnum.in_kb,
            status=StatusEnum.approved,
        )
        accuracy_judge = Judge(
            target_id=sample_target.id,
            category="accuracy",
            name="Judge 1 (Recommended)",
            model_name="gemini/gemini-2.5-flash-lite",
            prompt_template="Accuracy prompt",
            params={"temperature": 0.0},
            judge_type=JudgeTypeEnum.claim_based,
            is_baseline=True,
            is_editable=False,
        )
        rubric_judge = Judge(
            target_id=sample_target.id,
            category=sample_rubric.category,
            name="Tone Judge",
            model_name="gemini/gemini-2.5-flash-lite",
            prompt_template="Tone prompt",
            params={"temperature": 0.0},
            judge_type=JudgeTypeEnum.response_level,
            is_baseline=False,
            is_editable=True,
        )

        test_db.add(unanswered_question)
        test_db.add(accuracy_judge)
        test_db.add(rubric_judge)
        test_db.commit()
        test_db.refresh(unanswered_question)
        test_db.refresh(accuracy_judge)
        test_db.refresh(rubric_judge)

        response = test_client.get(f"/api/v1/snapshots/{sample_snapshot.id}/scoring-pending-counts")

        assert response.status_code == 200
        data = response.json()
        assert data["unanswered_question_count"] == 1
        assert data["accuracy_pending_counts"][str(accuracy_judge.id)] == 1
        assert data["rubric_pending_counts"][f"{rubric_judge.id}:{sample_rubric.id}"] == 1

