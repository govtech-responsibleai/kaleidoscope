"""
Integration tests for metrics API endpoints.
"""

import pytest

from src.common.database.repositories.target_rubric_repo import TargetRubricRepository

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("with_provider_bypass")]


def _accuracy_rubric(test_db, target_id: int):
    return TargetRubricRepository.get_by_target(
        test_db, target_id, group="fixed", name="Accuracy"
    )[0]

class TestMetricsAPI:
    """Integration tests for metrics API."""

    def test_results_route_returns_empty_results_when_snapshot_has_no_answers(
        self,
        test_client,
        sample_snapshot,
    ):
        """Results route should return an empty QA-grouped payload when no answers exist."""
        response = test_client.get(f"/api/v1/snapshots/{sample_snapshot.id}/results")

        assert response.status_code == 200
        assert response.json() == {"snapshot_id": sample_snapshot.id, "results": []}

    def test_scoring_pending_counts_are_returned_for_a_requested_rubric(
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
        """The scoring page should be able to load one rubric section's pending counts."""
        from src.common.database.models import Judge, Question, QuestionTypeEnum, QuestionScopeEnum, StatusEnum
        from src.rubric.services.system_rubrics import ensure_system_rubrics

        unanswered_question = Question(
            job_id=sample_job.id,
            persona_id=sample_personas[0].id,
            target_id=sample_target.id,
            text="What governance controls should be added?",
            type=QuestionTypeEnum.typical,
            scope=QuestionScopeEnum.in_kb,
            status=StatusEnum.approved,
        )
        ensure_system_rubrics(test_db, sample_target.id)
        accuracy_rubric = _accuracy_rubric(test_db, sample_target.id)
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

        response = test_client.get(
            f"/api/v1/snapshots/{sample_snapshot.id}/rubrics/{sample_rubric.id}/scoring-pending-counts"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["unanswered_question_count"] == 1
        assert data["rubric_id"] == sample_rubric.id
        assert data["pending_counts"][str(rubric_judge.id)] == 1
        assert str(accuracy_judge.id) not in data["pending_counts"]

    def test_scoring_status_returns_snapshot_scoped_gating_data(
        self,
        test_client,
        test_db,
        sample_target,
        sample_job,
        sample_personas,
        sample_snapshot,
        sample_annotations,
    ):
        """The scoring-status route should return only snapshot-wide gating state."""
        from src.common.database.models import Question, QuestionTypeEnum, QuestionScopeEnum, StatusEnum

        unanswered_question = Question(
            job_id=sample_job.id,
            persona_id=sample_personas[0].id,
            target_id=sample_target.id,
            text="What still needs an answer?",
            type=QuestionTypeEnum.typical,
            scope=QuestionScopeEnum.in_kb,
            status=StatusEnum.approved,
        )
        test_db.add(unanswered_question)
        test_db.commit()

        response = test_client.get(f"/api/v1/snapshots/{sample_snapshot.id}/scoring-status")

        assert response.status_code == 200
        data = response.json()
        assert data["snapshot_id"] == sample_snapshot.id
        assert data["is_complete"] is True
        assert data["unanswered_question_count"] == 1
        assert len(data["selected_ids"]) == len(sample_annotations)
        assert len(data["selected_and_annotated_ids"]) == len(sample_annotations)

    def test_scoring_rubrics_return_inline_judges_without_rows(
        self,
        test_client,
        test_db,
        sample_target,
        sample_snapshot,
        sample_rubric,
    ):
        """The scoring-rubrics route should return rubric metadata and inline judges only."""
        from src.common.database.models import Judge
        from src.rubric.services.system_rubrics import ensure_system_rubrics

        ensure_system_rubrics(test_db, sample_target.id)
        accuracy_rubric = _accuracy_rubric(test_db, sample_target.id)
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

        response = test_client.get(f"/api/v1/snapshots/{sample_snapshot.id}/scoring-rubrics")

        assert response.status_code == 200
        data = response.json()
        assert data["snapshot_id"] == sample_snapshot.id
        returned_rubrics = {rubric["id"]: rubric for rubric in data["rubrics"]}
        assert accuracy_rubric.id in returned_rubrics
        assert sample_rubric.id in returned_rubrics
        assert returned_rubrics[sample_rubric.id]["judges"][0]["name"] == "Tone Judge"
        assert "rows" not in returned_rubrics[sample_rubric.id]

    def test_scoring_results_return_filtered_rows_and_export_parity(
        self,
        test_client,
        test_db,
        sample_target,
        sample_snapshot,
        sample_annotations,
        sample_rubric,
    ):
        """The scoring-results and export routes should share the same filtered rubric dataset."""
        from src.common.database.models import AnswerScore, Judge, Annotation

        judge_one = Judge(
            target_id=sample_target.id,
            rubric_id=sample_rubric.id,
            name="Tone Judge 1",
            model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
            prompt_template="Tone prompt",
            params={"temperature": 0.0},
            is_baseline=False,
            is_editable=True,
        )
        judge_two = Judge(
            target_id=sample_target.id,
            rubric_id=sample_rubric.id,
            name="Tone Judge 2",
            model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
            prompt_template="Tone prompt",
            params={"temperature": 0.0},
            is_baseline=False,
            is_editable=True,
        )
        test_db.add(judge_one)
        test_db.add(judge_two)
        test_db.commit()
        test_db.refresh(judge_one)
        test_db.refresh(judge_two)

        for annotation in sample_annotations:
            option_value = "Professional" if annotation.label else "Casual"
            test_db.add(Annotation(
                answer_id=annotation.answer_id,
                rubric_id=sample_rubric.id,
                option_value=option_value,
            ))
            test_db.add(AnswerScore(
                answer_id=annotation.answer_id,
                rubric_id=sample_rubric.id,
                judge_id=judge_one.id,
                overall_label=option_value,
                explanation="Tone score 1",
            ))
            second_label = option_value
            if annotation.answer_id == sample_annotations[0].answer_id:
                second_label = "Casual"
            test_db.add(AnswerScore(
                answer_id=annotation.answer_id,
                rubric_id=sample_rubric.id,
                judge_id=judge_two.id,
                overall_label=second_label,
                explanation="Tone score 2",
            ))
        test_db.commit()

        scoring_response = test_client.get(
            f"/api/v1/snapshots/{sample_snapshot.id}/rubrics/{sample_rubric.id}/scoring-results",
            params={
                "disagreements_only": True,
                "judge_ids": [judge_one.id, judge_two.id],
                "page": 0,
                "page_size": 10,
            },
        )

        assert scoring_response.status_code == 200
        scoring_data = scoring_response.json()
        assert scoring_data["total_count"] == 1
        assert len(scoring_data["rows"]) == 1
        row = scoring_data["rows"][0]
        assert row["persona_id"] == sample_annotations[0].answer.question.persona_id
        assert row["persona_title"] == sample_annotations[0].answer.question.persona.title
        assert {judge["judge_id"] for judge in scoring_data["aligned_judges"]} == {judge_one.id, judge_two.id}
        assert len(scoring_data["persona_options"]) == 1

        export_response = test_client.get(
            f"/api/v1/targets/snapshots/{sample_snapshot.id}/export",
            params={
                "rubric_id": sample_rubric.id,
                "format": "json",
                "disagreements_only": True,
                "judge_ids": [judge_one.id, judge_two.id],
            },
        )

        assert export_response.status_code == 200
        export_data = export_response.json()
        assert len(export_data) == 1
        assert export_data[0]["answer_id"] == row["answer_id"]
        assert export_data[0]["persona_id"] == row["persona_id"]

    def test_snapshot_metrics_return_rubric_oriented_series_for_fixed_and_custom_rubrics(
        self,
        test_client,
        test_db,
        sample_target,
        sample_snapshot,
        sample_annotations,
        sample_answer_scores,
        sample_rubric,
    ):
        """The unified snapshot-metrics route should return one entry per rubric identity."""
        from src.common.database.models import AnswerScore, Judge, Annotation

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

        negative_answer_id = sample_annotations[1].answer_id
        for annotation in sample_annotations:
            test_db.add(AnswerScore(
                answer_id=annotation.answer_id,
                rubric_id=sample_rubric.id,
                judge_id=rubric_judge.id,
                overall_label="Casual" if annotation.answer_id == negative_answer_id else "Professional",
                explanation="Tone score",
            ))
            test_db.add(Annotation(
                answer_id=annotation.answer_id,
                rubric_id=sample_rubric.id,
                option_value="Casual" if annotation.answer_id == negative_answer_id else "Professional",
            ))
        test_db.commit()

        response = test_client.get(f"/api/v1/targets/{sample_target.id}/snapshot-metrics")

        assert response.status_code == 200
        data = response.json()
        returned_rubric_ids = {entry["rubric_id"] for entry in data["rubrics"]}
        assert sample_rubric.id in returned_rubric_ids
        accuracy_entry = next(entry for entry in data["rubrics"] if entry["rubric_name"] == "Accuracy")
        rubric_entry = next(entry for entry in data["rubrics"] if entry["rubric_id"] == sample_rubric.id)
        assert accuracy_entry["snapshots"][0]["snapshot_id"] == sample_snapshot.id
        assert rubric_entry["snapshots"][0]["aggregated_score"] == 0.9

    def test_rubric_scoped_judge_accuracy_and_missing_score_lookup_use_rubric_identity(
        self,
        test_client,
        test_db,
        sample_target,
        sample_snapshot,
        sample_annotations,
        sample_rubric,
    ):
        """Judge accuracy and missing-score queries should be scoped by the requested rubric_id."""
        from src.common.database.models import AnswerScore, Judge, Question, QuestionScopeEnum, QuestionTypeEnum, StatusEnum

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

        for annotation in sample_annotations[:8]:
            test_db.add(AnswerScore(
                answer_id=annotation.answer_id,
                rubric_id=sample_rubric.id,
                judge_id=rubric_judge.id,
                overall_label="Professional",
                explanation="Tone score",
            ))

        unanswered_question = Question(
            job_id=sample_annotations[0].answer.question.job_id,
            persona_id=sample_annotations[0].answer.question.persona_id,
            target_id=sample_target.id,
            text="Which responses still need rubric scoring?",
            type=QuestionTypeEnum.typical,
            scope=QuestionScopeEnum.in_kb,
            status=StatusEnum.approved,
        )
        test_db.add(unanswered_question)
        test_db.commit()

        accuracy_response = test_client.get(
            f"/api/v1/snapshots/{sample_snapshot.id}/judges/{rubric_judge.id}/rubrics/{sample_rubric.id}/accuracy"
        )
        assert accuracy_response.status_code == 200
        assert accuracy_response.json()["accuracy"] == 1.0
        assert accuracy_response.json()["total_answers"] == 8

        missing_scores_response = test_client.get(
            f"/api/v1/snapshots/{sample_snapshot.id}/questions/approved/without-scores",
            params={"judge_id": rubric_judge.id, "rubric_id": sample_rubric.id},
        )
        assert missing_scores_response.status_code == 200
        missing_question_ids = {question["id"] for question in missing_scores_response.json()}
        assert unanswered_question.id not in missing_question_ids
        expected_missing_ids = {annotation.answer.question_id for annotation in sample_annotations[8:]}
        assert expected_missing_ids <= missing_question_ids

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

    def test_qa_job_detail_keeps_existing_verdicts_visible_after_full_rubric_reconciliation(
        self,
        test_client,
        test_db,
        sample_target,
        sample_qa_job,
        sample_answer,
        sample_rubric,
        sample_rubric_second,
    ):
        from src.common.database.models import AnswerScore, Judge

        empathy_judge = Judge(
            target_id=sample_target.id,
            rubric_id=sample_rubric.id,
            name="Empathy Judge",
            model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
            prompt_template="Empathy prompt",
            params={"temperature": 0.0},
            is_baseline=False,
            is_editable=True,
        )
        custom_judge = Judge(
            target_id=sample_target.id,
            rubric_id=sample_rubric_second.id,
            name="Custom Judge",
            model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
            prompt_template="Custom prompt",
            params={"temperature": 0.0},
            is_baseline=False,
            is_editable=True,
        )
        test_db.add(empathy_judge)
        test_db.add(custom_judge)
        test_db.commit()
        test_db.refresh(empathy_judge)
        test_db.refresh(custom_judge)

        test_db.add_all([
            AnswerScore(
                answer_id=sample_answer.id,
                rubric_id=sample_qa_job.judge.rubric_id,
                judge_id=sample_qa_job.judge_id,
                overall_label="Accurate",
                explanation="Accuracy verdict",
            ),
            AnswerScore(
                answer_id=sample_answer.id,
                rubric_id=sample_rubric.id,
                judge_id=empathy_judge.id,
                overall_label=sample_rubric.best_option,
                explanation="Empathy verdict",
            ),
            AnswerScore(
                answer_id=sample_answer.id,
                rubric_id=sample_rubric_second.id,
                judge_id=custom_judge.id,
                overall_label=sample_rubric_second.best_option,
                explanation="Custom verdict",
            ),
        ])
        sample_qa_job.rubric_specs = [
            {"rubric_id": sample_qa_job.judge.rubric_id, "judge_id": sample_qa_job.judge_id},
            {"rubric_id": sample_rubric.id, "judge_id": empathy_judge.id},
            {"rubric_id": sample_rubric_second.id, "judge_id": custom_judge.id},
        ]
        test_db.commit()

        response = test_client.get(f"/api/v1/qa-jobs/{sample_qa_job.id}")

        assert response.status_code == 200
        data = response.json()
        rubric_statuses = {status["rubric_id"]: status for status in data["rubric_statuses"]}

        assert set(rubric_statuses) == {
            sample_qa_job.judge.rubric_id,
            sample_rubric.id,
            sample_rubric_second.id,
        }
        assert rubric_statuses[sample_qa_job.judge.rubric_id]["state"] == "success"
        assert rubric_statuses[sample_rubric.id]["state"] == "success"
        assert rubric_statuses[sample_rubric_second.id]["state"] == "success"

    def test_qa_job_detail_drops_removed_rubric_from_reconciled_statuses(
        self,
        test_client,
        test_db,
        sample_target,
        sample_qa_job,
        sample_answer,
        sample_rubric,
    ):
        from src.common.database.models import AnswerScore, Judge

        removed_judge = Judge(
            target_id=sample_target.id,
            rubric_id=sample_rubric.id,
            name="Removed Rubric Judge",
            model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
            prompt_template="Removed prompt",
            params={"temperature": 0.0},
            is_baseline=False,
            is_editable=True,
        )
        test_db.add(removed_judge)
        test_db.commit()
        test_db.refresh(removed_judge)

        test_db.add_all([
            AnswerScore(
                answer_id=sample_answer.id,
                rubric_id=sample_qa_job.judge.rubric_id,
                judge_id=sample_qa_job.judge_id,
                overall_label="Accurate",
                explanation="Accuracy verdict",
            ),
            AnswerScore(
                answer_id=sample_answer.id,
                rubric_id=sample_rubric.id,
                judge_id=removed_judge.id,
                overall_label=sample_rubric.best_option,
                explanation="Historical removed verdict",
            ),
        ])
        sample_qa_job.rubric_specs = [
            {"rubric_id": sample_qa_job.judge.rubric_id, "judge_id": sample_qa_job.judge_id},
        ]
        test_db.commit()

        response = test_client.get(f"/api/v1/qa-jobs/{sample_qa_job.id}")

        assert response.status_code == 200
        data = response.json()
        rubric_ids = [status["rubric_id"] for status in data["rubric_statuses"]]

        assert rubric_ids == [sample_qa_job.judge.rubric_id]
        assert sample_rubric.id not in rubric_ids

    def test_qa_job_detail_uses_target_baselines_so_all_current_rubrics_render(
        self,
        test_client,
        test_db,
        sample_target,
        sample_qa_job,
        sample_answer,
        sample_rubric,
        sample_rubric_second,
    ):
        from src.common.database.models import AnswerScore, Judge

        tone_baseline = Judge(
            target_id=sample_target.id,
            rubric_id=sample_rubric.id,
            name="Tone Baseline",
            model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
            prompt_template="Tone prompt",
            params={"temperature": 0.0},
            is_baseline=True,
            is_editable=False,
        )
        relevance_baseline = Judge(
            target_id=sample_target.id,
            rubric_id=sample_rubric_second.id,
            name="Relevance Baseline",
            model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
            prompt_template="Relevance prompt",
            params={"temperature": 0.0},
            is_baseline=True,
            is_editable=False,
        )
        test_db.add_all([tone_baseline, relevance_baseline])
        test_db.commit()
        test_db.refresh(tone_baseline)
        test_db.refresh(relevance_baseline)

        test_db.add_all([
            AnswerScore(
                answer_id=sample_answer.id,
                rubric_id=sample_qa_job.judge.rubric_id,
                judge_id=sample_qa_job.judge_id,
                overall_label="Accurate",
                explanation="Accuracy verdict",
            ),
            AnswerScore(
                answer_id=sample_answer.id,
                rubric_id=sample_rubric.id,
                judge_id=tone_baseline.id,
                overall_label=sample_rubric.best_option,
                explanation="Tone verdict",
            ),
            AnswerScore(
                answer_id=sample_answer.id,
                rubric_id=sample_rubric_second.id,
                judge_id=relevance_baseline.id,
                overall_label=sample_rubric_second.best_option,
                explanation="Relevance verdict",
            ),
        ])
        sample_qa_job.rubric_specs = [
            {"rubric_id": sample_qa_job.judge.rubric_id, "judge_id": sample_qa_job.judge_id},
        ]
        test_db.commit()

        response = test_client.get(f"/api/v1/qa-jobs/{sample_qa_job.id}")

        assert response.status_code == 200
        data = response.json()
        rubric_statuses = {status["rubric_id"]: status for status in data["rubric_statuses"]}

        assert set(rubric_statuses) == {
            sample_qa_job.judge.rubric_id,
            sample_rubric.id,
            sample_rubric_second.id,
        }
        assert rubric_statuses[sample_rubric.id]["judge_id"] == tone_baseline.id
        assert rubric_statuses[sample_rubric_second.id]["judge_id"] == relevance_baseline.id
        assert rubric_statuses[sample_rubric_second.id]["state"] == "success"

    def test_qa_job_detail_prefers_target_baseline_judge_over_ad_hoc_job_judge(
        self,
        test_client,
        test_db,
        sample_target,
        sample_qa_job,
        sample_answer,
        sample_rubric,
    ):
        from src.common.database.models import AnswerScore, Judge

        baseline_judge = Judge(
            target_id=sample_target.id,
            rubric_id=sample_rubric.id,
            name="Tone Baseline",
            model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
            prompt_template="Baseline prompt",
            params={"temperature": 0.0},
            is_baseline=True,
            is_editable=False,
        )
        ad_hoc_judge = Judge(
            target_id=sample_target.id,
            rubric_id=sample_rubric.id,
            name="Tone Ad Hoc",
            model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
            prompt_template="Ad hoc prompt",
            params={"temperature": 0.0},
            is_baseline=False,
            is_editable=True,
        )
        test_db.add_all([baseline_judge, ad_hoc_judge])
        test_db.commit()
        test_db.refresh(baseline_judge)
        test_db.refresh(ad_hoc_judge)

        test_db.add_all([
            AnswerScore(
                answer_id=sample_answer.id,
                rubric_id=sample_qa_job.judge.rubric_id,
                judge_id=sample_qa_job.judge_id,
                overall_label="Accurate",
                explanation="Accuracy verdict",
            ),
            AnswerScore(
                answer_id=sample_answer.id,
                rubric_id=sample_rubric.id,
                judge_id=baseline_judge.id,
                overall_label=sample_rubric.best_option,
                explanation="Baseline tone verdict",
            ),
            AnswerScore(
                answer_id=sample_answer.id,
                rubric_id=sample_rubric.id,
                judge_id=ad_hoc_judge.id,
                overall_label="Casual",
                explanation="Ad hoc tone verdict",
            ),
        ])
        sample_qa_job.rubric_specs = [
            {"rubric_id": sample_qa_job.judge.rubric_id, "judge_id": sample_qa_job.judge_id},
            {"rubric_id": sample_rubric.id, "judge_id": ad_hoc_judge.id},
        ]
        test_db.commit()

        response = test_client.get(f"/api/v1/qa-jobs/{sample_qa_job.id}")

        assert response.status_code == 200
        data = response.json()
        metric = next(status for status in data["rubric_statuses"] if status["rubric_id"] == sample_rubric.id)

        assert metric["judge_id"] == baseline_judge.id
        assert metric["judge_name"] == "Tone Baseline"
        assert metric["score"]["value"] == sample_rubric.best_option
