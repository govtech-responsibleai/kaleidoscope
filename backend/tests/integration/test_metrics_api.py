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
            model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
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
            model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
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

    def test_scoring_contracts_return_backend_owned_accuracy_and_rubric_metrics(
        self,
        test_client,
        test_db,
        sample_target,
        sample_snapshot,
        sample_annotations,
        sample_answer_scores,
        sample_rubric,
    ):
        """The scoring page should be able to fetch one backend-owned contract for all metric sections."""
        from src.common.database.models import Judge, JudgeTypeEnum

        accuracy_judge = Judge(
            target_id=sample_target.id,
            category="accuracy",
            name="Judge 1 (Recommended)",
            model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
            prompt_template="Accuracy prompt",
            params={"temperature": 0.0},
            judge_type=JudgeTypeEnum.claim_based,
            is_baseline=True,
            is_editable=False,
        )
        rubric_judge = Judge(
            target_id=sample_target.id,
            category=sample_rubric.category,
            rubric_id=sample_rubric.id,
            name="Tone Judge",
            model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
            prompt_template="Tone prompt",
            params={"temperature": 0.0},
            judge_type=JudgeTypeEnum.response_level,
            is_baseline=False,
            is_editable=True,
        )
        test_db.add(accuracy_judge)
        test_db.add(rubric_judge)
        test_db.commit()

        response = test_client.get(f"/api/v1/snapshots/{sample_snapshot.id}/scoring-contracts")

        assert response.status_code == 200
        data = response.json()
        assert data["snapshot_id"] == sample_snapshot.id
        accuracy_metric = next(metric for metric in data["metrics"] if metric["metric_type"] == "accuracy")
        rubric_metric = next(metric for metric in data["metrics"] if metric["metric_type"] == "rubric" and metric["rubric_id"] == sample_rubric.id)

        assert accuracy_metric["metric_key"] == "accuracy"
        assert isinstance(accuracy_metric["judge_summaries"], list)
        assert len(accuracy_metric["rows"]) == len(sample_annotations)

        assert rubric_metric["metric_key"] == f"rubric:{sample_rubric.id}"
        assert rubric_metric["target_label"] == sample_rubric.best_option
        assert len(rubric_metric["rows"]) == len(sample_annotations)

    def test_scoring_contracts_return_null_summaries_for_judges_that_have_not_run(
        self,
        test_client,
        test_db,
        sample_target,
        sample_snapshot,
        sample_annotations,
        sample_rubric,
    ):
        """Created judges without metric results should return unavailable summaries."""
        from src.common.database.models import Judge, JudgeTypeEnum

        accuracy_judge = Judge(
            target_id=sample_target.id,
            category="accuracy",
            name="Custom Accuracy Judge",
            model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
            prompt_template="Accuracy prompt",
            params={"temperature": 0.0},
            judge_type=JudgeTypeEnum.claim_based,
            is_baseline=False,
            is_editable=True,
        )
        rubric_judge = Judge(
            target_id=sample_target.id,
            category=sample_rubric.category,
            rubric_id=sample_rubric.id,
            name="Custom Rubric Judge",
            model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
            prompt_template="Rubric prompt",
            params={"temperature": 0.0},
            judge_type=JudgeTypeEnum.response_level,
            is_baseline=False,
            is_editable=True,
        )
        test_db.add(accuracy_judge)
        test_db.add(rubric_judge)
        test_db.commit()

        response = test_client.get(f"/api/v1/snapshots/{sample_snapshot.id}/scoring-contracts")

        assert response.status_code == 200
        data = response.json()
        accuracy_metric = next(metric for metric in data["metrics"] if metric["metric_type"] == "accuracy")
        rubric_metric = next(metric for metric in data["metrics"] if metric["metric_type"] == "rubric" and metric["rubric_id"] == sample_rubric.id)

        accuracy_summary = next(summary for summary in accuracy_metric["judge_summaries"] if summary["judge_id"] == accuracy_judge.id)
        rubric_summary = next(summary for summary in rubric_metric["judge_summaries"] if summary["judge_id"] == rubric_judge.id)

        assert accuracy_summary["accuracy"] is None
        assert accuracy_summary["reliability"] is None
        assert rubric_summary["accuracy"] is None
        assert rubric_summary["reliability"] is None
