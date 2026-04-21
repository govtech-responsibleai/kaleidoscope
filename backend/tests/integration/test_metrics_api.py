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
        from src.common.database.models import Judge, Question, QuestionTypeEnum, QuestionScopeEnum, StatusEnum
        from src.common.services.system_rubrics import ensure_fixed_accuracy_rubric

        unanswered_question = Question(
            job_id=sample_job.id,
            persona_id=sample_personas[0].id,
            target_id=sample_target.id,
            text="What governance controls should be added?",
            type=QuestionTypeEnum.typical,
            scope=QuestionScopeEnum.in_kb,
            status=StatusEnum.approved,
        )
        accuracy_rubric = ensure_fixed_accuracy_rubric(test_db, sample_target.id)
        accuracy_judge = Judge(
            target_id=sample_target.id,
            rubric_id=accuracy_rubric.id,
            name="Judge 1 (Recommended)",
            model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
            prompt_template="Accuracy prompt",
            params={"temperature": 0.0},
            is_baseline=True,
            is_editable=False,
        )
        rubric_judge = Judge(
            target_id=sample_target.id,
            rubric_id=sample_rubric.id,
            name="Tone Judge",
            model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
            prompt_template="Tone prompt",
            params={"temperature": 0.0},
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
        from src.common.database.models import Judge
        from src.common.services.system_rubrics import ensure_fixed_accuracy_rubric

        accuracy_rubric = ensure_fixed_accuracy_rubric(test_db, sample_target.id)
        accuracy_judge = Judge(
            target_id=sample_target.id,
            rubric_id=accuracy_rubric.id,
            name="Judge 1 (Recommended)",
            model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
            prompt_template="Accuracy prompt",
            params={"temperature": 0.0},
            is_baseline=True,
            is_editable=False,
        )
        rubric_judge = Judge(
            target_id=sample_target.id,
            rubric_id=sample_rubric.id,
            name="Tone Judge",
            model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
            prompt_template="Tone prompt",
            params={"temperature": 0.0},
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
        accuracy_metric = next(metric for metric in data["metrics"] if metric["group"] == "fixed")
        rubric_metric = next(metric for metric in data["metrics"] if metric["group"] != "fixed" and metric["rubric_id"] == sample_rubric.id)

        assert accuracy_metric["rubric_name"] == "Accuracy"
        assert isinstance(accuracy_metric["judge_summaries"], list)
        assert len(accuracy_metric["rows"]) == len(sample_annotations)

        assert rubric_metric["rubric_name"] == sample_rubric.name
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
        from src.common.database.models import Judge
        from src.common.services.system_rubrics import ensure_fixed_accuracy_rubric

        accuracy_rubric = ensure_fixed_accuracy_rubric(test_db, sample_target.id)
        accuracy_judge = Judge(
            target_id=sample_target.id,
            rubric_id=accuracy_rubric.id,
            name="Custom Accuracy Judge",
            model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
            prompt_template="Accuracy prompt",
            params={"temperature": 0.0},
            is_baseline=False,
            is_editable=True,
        )
        rubric_judge = Judge(
            target_id=sample_target.id,
            rubric_id=sample_rubric.id,
            name="Custom Rubric Judge",
            model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
            prompt_template="Rubric prompt",
            params={"temperature": 0.0},
            is_baseline=False,
            is_editable=True,
        )
        test_db.add(accuracy_judge)
        test_db.add(rubric_judge)
        test_db.commit()

        response = test_client.get(f"/api/v1/snapshots/{sample_snapshot.id}/scoring-contracts")

        assert response.status_code == 200
        data = response.json()
        accuracy_metric = next(metric for metric in data["metrics"] if metric["group"] == "fixed")
        rubric_metric = next(metric for metric in data["metrics"] if metric["group"] != "fixed" and metric["rubric_id"] == sample_rubric.id)

        accuracy_summary = next(summary for summary in accuracy_metric["judge_summaries"] if summary["judge_id"] == accuracy_judge.id)
        rubric_summary = next(summary for summary in rubric_metric["judge_summaries"] if summary["judge_id"] == rubric_judge.id)

        assert accuracy_summary["accuracy"] is None
        assert accuracy_summary["reliability"] is None
        assert rubric_summary["accuracy"] is None
        assert rubric_summary["reliability"] is None

    def test_scoring_contracts_reflect_accuracy_and_rubric_manual_overrides(
        self,
        test_client,
        test_db,
        sample_target,
        sample_snapshot,
        sample_annotations,
        sample_answer_scores,
        sample_rubric,
    ):
        """Saved manual label overrides should persist in rows and update metric aggregates."""
        from src.common.database.models import AnswerScore, Judge, RubricAnnotation
        from src.common.services.system_rubrics import ensure_fixed_accuracy_rubric

        rubric_judge = Judge(
            target_id=sample_target.id,
            rubric_id=sample_rubric.id,
            name="Tone Judge",
            model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
            prompt_template="Tone prompt",
            params={"temperature": 0.0},
            is_baseline=False,
            is_editable=True,
        )
        test_db.add(rubric_judge)
        test_db.commit()
        test_db.refresh(rubric_judge)

        overridden_answer_id = sample_annotations[0].answer_id
        negative_control_answer_id = sample_annotations[1].answer_id
        for annotation in sample_annotations:
            test_db.add(AnswerScore(
                answer_id=annotation.answer_id,
                rubric_id=sample_rubric.id,
                judge_id=rubric_judge.id,
                overall_label="Casual" if annotation.answer_id in {overridden_answer_id, negative_control_answer_id} else "Professional",
                explanation="Tone score",
            ))
            test_db.add(RubricAnnotation(
                answer_id=annotation.answer_id,
                rubric_id=sample_rubric.id,
                option_value="Casual" if annotation.answer_id == negative_control_answer_id else "Professional",
            ))
        test_db.commit()

        accuracy_rubric = ensure_fixed_accuracy_rubric(test_db, sample_target.id)

        accuracy_override_response = test_client.put(
            f"/api/v1/answers/{sample_annotations[8].answer_id}/label-overrides/{accuracy_rubric.id}",
            json={"edited_value": "accurate"}
        )
        assert accuracy_override_response.status_code == 200
        assert accuracy_override_response.json()["edited_value"] == "Accurate"

        rubric_override_response = test_client.put(
            f"/api/v1/answers/{overridden_answer_id}/label-overrides/{sample_rubric.id}",
            json={"edited_value": "Professional"}
        )
        assert rubric_override_response.status_code == 200

        response = test_client.get(f"/api/v1/snapshots/{sample_snapshot.id}/scoring-contracts")
        assert response.status_code == 200
        data = response.json()

        accuracy_metric = next(metric for metric in data["metrics"] if metric["group"] == "fixed")
        rubric_metric = next(metric for metric in data["metrics"] if metric["group"] != "fixed" and metric["rubric_id"] == sample_rubric.id)

        accuracy_row = next(row for row in accuracy_metric["rows"] if row["answer_id"] == sample_annotations[8].answer_id)
        rubric_row = next(row for row in rubric_metric["rows"] if row["answer_id"] == overridden_answer_id)

        assert accuracy_row["aggregated_result"]["method"] == "override"
        assert accuracy_row["aggregated_result"]["value"] == "Accurate"
        assert accuracy_row["aggregated_result"]["baseline_value"] == "Inaccurate"
        assert accuracy_row["aggregated_result"]["is_edited"] is True
        assert accuracy_metric["accurate_count"] == 9
        assert accuracy_metric["inaccurate_count"] == 1

        assert rubric_row["aggregated_result"]["method"] == "override"
        assert rubric_row["aggregated_result"]["value"] == "Professional"
        assert rubric_row["aggregated_result"]["baseline_value"] == "Casual"
        assert rubric_row["aggregated_result"]["is_edited"] is True
        assert rubric_row["human_option"] == "Professional"
        assert rubric_metric["accurate_count"] == 9
        assert rubric_metric["inaccurate_count"] == 1
        assert rubric_metric["edited_count"] == 1
        assert rubric_metric["aggregated_accuracy"] == 0.9

    def test_scoring_contracts_do_not_treat_rubric_annotations_as_scoring_overrides(
        self,
        test_client,
        test_db,
        sample_target,
        sample_snapshot,
        sample_annotations,
        sample_rubric,
    ):
        """Rubric annotations stay as judge-evaluation ground truth and do not replace the scoring aggregate."""
        from src.common.database.models import AnswerScore, Judge, RubricAnnotation

        rubric_judge = Judge(
            target_id=sample_target.id,
            rubric_id=sample_rubric.id,
            name="Tone Judge",
            model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
            prompt_template="Tone prompt",
            params={"temperature": 0.0},
            is_baseline=False,
            is_editable=True,
        )
        test_db.add(rubric_judge)
        test_db.commit()
        test_db.refresh(rubric_judge)

        overridden_answer_id = sample_annotations[0].answer_id
        negative_control_answer_id = sample_annotations[1].answer_id
        for annotation in sample_annotations:
            test_db.add(AnswerScore(
                answer_id=annotation.answer_id,
                rubric_id=sample_rubric.id,
                judge_id=rubric_judge.id,
                overall_label="Casual" if annotation.answer_id in {overridden_answer_id, negative_control_answer_id} else "Professional",
                explanation="Tone score",
            ))
            test_db.add(RubricAnnotation(
                answer_id=annotation.answer_id,
                rubric_id=sample_rubric.id,
                option_value="Casual" if annotation.answer_id == negative_control_answer_id else "Professional",
            ))
        test_db.commit()

        response = test_client.get(f"/api/v1/snapshots/{sample_snapshot.id}/scoring-contracts")
        assert response.status_code == 200
        data = response.json()

        rubric_metric = next(metric for metric in data["metrics"] if metric["group"] != "fixed" and metric["rubric_id"] == sample_rubric.id)
        rubric_row = next(row for row in rubric_metric["rows"] if row["answer_id"] == overridden_answer_id)

        assert rubric_row["aggregated_result"]["method"] == "majority"
        assert rubric_row["aggregated_result"]["value"] == "Casual"
        assert rubric_row["aggregated_result"]["baseline_value"] == "Casual"
        assert rubric_row["aggregated_result"]["is_edited"] is False
        assert rubric_row["human_option"] == "Professional"
        assert rubric_metric["accurate_count"] == 8
        assert rubric_metric["inaccurate_count"] == 2
        assert rubric_metric["edited_count"] == 0
        assert rubric_metric["aggregated_accuracy"] == 0.8

    def test_qa_job_metric_status_returns_no_judge_configured_for_rubric(
        self,
        test_client,
        test_db,
        sample_qa_job,
        sample_answer,
        sample_rubric,
    ):
        sample_qa_job.rubric_specs = [{"rubric_id": sample_rubric.id, "judge_id": 999999}]
        test_db.commit()

        response = test_client.get(
            f"/api/v1/qa-jobs/{sample_qa_job.id}",
        )

        assert response.status_code == 200
        data = response.json()
        metric = next(status for status in data["rubric_statuses"] if status["rubric_id"] == sample_rubric.id)
        assert metric["state"] == "no_judge_configured"
        assert metric["judge_id"] is None
        assert metric["score"] is None

    def test_qa_job_metric_status_returns_pending_for_configured_rubric_judge_without_score(
        self,
        test_client,
        test_db,
        sample_target,
        sample_qa_job,
        sample_answer,
        sample_rubric,
    ):
        from src.common.database.models import Judge

        judge = Judge(
            target_id=sample_target.id,
            rubric_id=sample_rubric.id,
            name="Tone Judge",
            model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
            prompt_template="Tone prompt",
            params={"temperature": 0.0},
            is_baseline=False,
            is_editable=True,
        )
        test_db.add(judge)
        test_db.commit()
        sample_qa_job.rubric_specs = [{"rubric_id": sample_rubric.id, "judge_id": judge.id}]
        test_db.commit()

        response = test_client.get(
            f"/api/v1/qa-jobs/{sample_qa_job.id}",
        )

        assert response.status_code == 200
        data = response.json()
        metric = next(status for status in data["rubric_statuses"] if status["rubric_id"] == sample_rubric.id)
        assert metric["state"] == "pending_evaluation"
        assert metric["judge_id"] == judge.id
        assert metric["score"] is None

    def test_qa_job_metric_status_returns_job_failed_when_question_not_pending(
        self,
        test_client,
        test_db,
        sample_target,
        sample_qa_job,
        sample_answer,
        sample_rubric,
    ):
        from src.common.database.models import Judge, StatusEnum

        judge = Judge(
            target_id=sample_target.id,
            rubric_id=sample_rubric.id,
            name="Tone Judge",
            model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
            prompt_template="Tone prompt",
            params={"temperature": 0.0},
            is_baseline=False,
            is_editable=True,
        )
        sample_answer.question.status = StatusEnum.pending
        test_db.add(judge)
        test_db.commit()
        sample_qa_job.rubric_specs = [{"rubric_id": sample_rubric.id, "judge_id": judge.id}]
        test_db.commit()

        response = test_client.get(
            f"/api/v1/qa-jobs/{sample_qa_job.id}",
        )

        assert response.status_code == 200
        data = response.json()
        metric = next(status for status in data["rubric_statuses"] if status["rubric_id"] == sample_rubric.id)
        assert metric["state"] == "job_failed"
        assert metric["judge_id"] == judge.id
        assert metric["score"] is None
        assert 'did not produce a score' in metric["message"]

    def test_qa_job_metric_status_uses_rubric_spec_judge_and_score(
        self,
        test_client,
        test_db,
        sample_target,
        sample_qa_job,
        sample_answer,
        sample_rubric_second,
    ):
        from src.common.database.models import AnswerScore, Judge, TargetRubric

        other_rubric = TargetRubric(
            target_id=sample_target.id,
            name="Helpfulness",
            criteria="Evaluate helpfulness",
            options=[
                {"option": "Helpful", "description": "Helpful"},
                {"option": "Not Helpful", "description": "Not helpful"},
            ],
            best_option="Helpful",
            position=5,
        )
        test_db.add(other_rubric)
        test_db.commit()
        test_db.refresh(other_rubric)

        correct_judge = Judge(
            target_id=sample_target.id,
            rubric_id=sample_rubric_second.id,
            name="Scoped Judge A",
            model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
            prompt_template="Rubric A prompt",
            params={"temperature": 0.0},
            is_baseline=False,
            is_editable=True,
        )
        other_judge = Judge(
            target_id=sample_target.id,
            rubric_id=other_rubric.id,
            name="Scoped Judge B",
            model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
            prompt_template="Rubric B prompt",
            params={"temperature": 0.0},
            is_baseline=False,
            is_editable=True,
        )
        test_db.add(correct_judge)
        test_db.add(other_judge)
        test_db.commit()
        test_db.refresh(correct_judge)

        test_db.add(AnswerScore(
            answer_id=sample_answer.id,
            rubric_id=sample_rubric_second.id,
            judge_id=correct_judge.id,
            overall_label=sample_rubric_second.best_option,
            explanation="Scoped score",
        ))
        test_db.commit()
        sample_qa_job.rubric_specs = [{"rubric_id": sample_rubric_second.id, "judge_id": correct_judge.id}]
        test_db.commit()

        response = test_client.get(
            f"/api/v1/qa-jobs/{sample_qa_job.id}",
        )

        assert response.status_code == 200
        data = response.json()
        metric = next(status for status in data["rubric_statuses"] if status["rubric_id"] == sample_rubric_second.id)
        assert metric["state"] == "success"
        assert metric["judge_id"] == correct_judge.id
        assert metric["judge_name"] == "Scoped Judge A"
        assert metric["score"]["judge_id"] == correct_judge.id
        assert metric["score"]["value"] == sample_rubric_second.best_option
