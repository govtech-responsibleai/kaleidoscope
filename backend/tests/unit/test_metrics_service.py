"""
Unit tests for MetricsService.
"""

import pytest
from unittest.mock import patch
from src.common.database.repositories.target_rubric_repo import TargetRubricRepository
from src.common.database.models import (
    Answer,
    AnswerLabelOverride,
    AnswerScore,
    Judge,
    Annotation,
    Question,
    QuestionScopeEnum,
    QuestionTypeEnum,
    StatusEnum,
)

from src.scoring.services.metrics_service import MetricsService
from src.common.models.metrics import (
    AggregatedResult,
    ConfusionMatrixResponse,
    JudgeAccuracyResponse,
    JudgeAlignmentResponse,
    SnapshotMetric,
)


@pytest.mark.unit
class TestMetricsService:
    """Unit tests for MetricsService class."""

    @staticmethod
    def _accuracy_rubric_id(test_db, target_id: int) -> int:
        return TargetRubricRepository.get_by_target(
            test_db, target_id, group="preset", name="Accuracy"
        )[0].id

    def test_calculate_judge_alignment(
        self, test_db, sample_annotations, sample_answer_scores, sample_snapshot, sample_judge_claim_based
    ):
        """Test judge alignment calculation returns correct F1, precision, recall, accuracy."""
        service = MetricsService(test_db)
        metrics = service.calculate_judge_alignment(
            sample_snapshot.id,
            sample_judge_claim_based.id,
            sample_judge_claim_based.rubric_id,
        )

        # Verify metrics structure
        assert isinstance(metrics, JudgeAlignmentResponse)

        # Verify sample count matches
        assert metrics.sample_count == 10

        # Verify all metrics are between 0 and 1
        assert 0 <= metrics.f1 <= 1
        assert 0 <= metrics.precision <= 1
        assert 0 <= metrics.recall <= 1
        assert 0 <= metrics.accuracy <= 1

    def test_alignment_ignores_label_overrides(
        self, test_db, sample_annotations, sample_answer_scores, sample_snapshot, sample_judge_claim_based
    ):
        """Overrides edit the reported verdict; they must never change the calibration ground truth."""
        service = MetricsService(test_db)
        rubric_id = sample_judge_claim_based.rubric_id
        before = service.calculate_judge_alignment(sample_snapshot.id, sample_judge_claim_based.id, rubric_id)

        # Flip every human label via overrides; alignment must not move.
        for annotation in sample_annotations:
            test_db.add(AnswerLabelOverride(
                answer_id=annotation.answer_id, rubric_id=rubric_id,
                edited_value="Inaccurate" if annotation.label else "Accurate",
            ))
        test_db.commit()

        after = service.calculate_judge_alignment(sample_snapshot.id, sample_judge_claim_based.id, rubric_id)
        assert after.f1 == before.f1
        assert after.accuracy == before.accuracy

    def test_calculate_accuracy(
        self, test_db, sample_answer_scores, sample_snapshot, sample_judge_claim_based
    ):
        """Test accuracy calculation: 8 accurate out of 10 = 0.8."""
        service = MetricsService(test_db)
        metrics = service.calculate_accuracy(
            sample_snapshot.id,
            sample_judge_claim_based.id,
            sample_judge_claim_based.rubric_id,
        )

        assert isinstance(metrics, JudgeAccuracyResponse)
        assert metrics.accuracy == 0.8
        assert metrics.total_answers == 10
        assert metrics.accurate_count == 8

    def test_alignment_raises_if_no_annotations(self, test_db, sample_snapshot, sample_judge_claim_based):
        """Test that calculate_judge_alignment raises ValueError when no annotations found."""
        service = MetricsService(test_db)

        with pytest.raises(ValueError, match="No annotations found"):
            service.calculate_judge_alignment(
                sample_snapshot.id,
                sample_judge_claim_based.id,
                sample_judge_claim_based.rubric_id,
            )

    def test_accuracy_raises_if_no_scores(self, test_db, sample_snapshot, sample_judge_claim_based):
        """Test that calculate_accuracy raises ValueError when no scores found."""
        service = MetricsService(test_db)

        with pytest.raises(ValueError, match="No scores found"):
            service.calculate_accuracy(
                sample_snapshot.id,
                sample_judge_claim_based.id,
                sample_judge_claim_based.rubric_id,
            )

    def test_get_aggregated_results(
        self, test_db, sample_annotations, sample_answer_scores, sample_snapshot
    ):
        """Test get_aggregated_results returns (list of AggregatedResult, reliability_map) tuple."""
        service = MetricsService(test_db)
        rubric_id = self._accuracy_rubric_id(test_db, sample_snapshot.target_id)
        results, reliability_map = service.get_aggregated_results(sample_snapshot.id, rubric_id)

        # Verify we get results for all answers
        assert len(results) == 10

        # Verify return types
        assert isinstance(reliability_map, dict)

        # Verify structure of each result
        for result in results:
            assert isinstance(result, AggregatedResult)
            assert result.question_id is not None
            assert result.answer_id is not None
            assert result.answer_content is not None
            assert result.aggregated_score is not None

            agg = result.aggregated_score
            assert agg.method in ["majority", "majority_tied", "no_aligned_judge", "override"]
            assert isinstance(agg.metadata, list)


    def test_get_aggregated_results_raises_if_no_answers(self, test_db, sample_snapshot):
        """Test that get_aggregated_results raises ValueError when no answers found."""
        from src.rubric.services.system_rubrics import ensure_system_rubrics

        ensure_system_rubrics(test_db, sample_snapshot.target_id)
        service = MetricsService(test_db)
        rubric_id = self._accuracy_rubric_id(test_db, sample_snapshot.target_id)

        with pytest.raises(ValueError, match="No answers found"):
            service.get_aggregated_results(sample_snapshot.id, rubric_id)

    def test_calculate_snapshot_summary(
        self, test_db, sample_annotations, sample_answer_scores, sample_snapshot
    ):
        """Test calculate_snapshot_summary returns correct summary metrics with aligned_judges."""
        service = MetricsService(test_db)
        rubric_id = self._accuracy_rubric_id(test_db, sample_snapshot.target_id)
        summary = service.calculate_snapshot_summary(sample_snapshot.id, rubric_id)

        # Verify structure
        assert isinstance(summary, SnapshotMetric)

        # Verify aligned_judges is a list (B3)
        assert isinstance(summary.aligned_judges, list)
        for judge in summary.aligned_judges:
            assert judge.judge_id is not None
            assert judge.name
            assert judge.f1 is not None

        # Verify aggregated_score is between 0 and 1
        assert 0 <= summary.aggregated_score <= 1

        # Verify counts are non-negative
        assert summary.total_answers >= 0
        assert summary.accurate_count >= 0
        assert summary.inaccurate_count >= 0
        assert summary.pending_count >= 0
        assert summary.edited_count >= 0

        # Verify counts add up
        assert (
            summary.accurate_count + summary.inaccurate_count + summary.pending_count
            == summary.total_answers
        )

        # Verify judge_alignment_range
        jar = summary.judge_alignment_range
        if jar is not None:
            assert jar["min"] <= jar["max"]
            assert jar["min"] <= 1.0
            assert jar["max"] >= 0.0

    def test_calculate_confusion_matrix(
        self, test_db, sample_target, sample_annotations, sample_answer_scores, sample_snapshot, sample_judge_claim_based
    ):
        """Test calculate_confusion_matrix returns breakdown by question type/scope."""
        service = MetricsService(test_db)
        result = service.calculate_confusion_matrix(
            sample_target.id,
            sample_judge_claim_based.rubric_id,
            sample_snapshot.id,
        )

        # Verify structure
        assert isinstance(result, ConfusionMatrixResponse)

        # Verify matrix has all combinations
        matrix = result.matrix
        assert "typical_in_kb" in matrix
        assert "typical_out_kb" in matrix
        assert "edge_in_kb" in matrix
        assert "edge_out_kb" in matrix

        # Verify all counts are non-negative
        for key, value in matrix.items():
            assert value >= 0

        assert result.total_inaccurate >= 0

    def test_rubric_metrics_use_existing_rubric_without_request_time_ensure(
        self,
        test_db,
        sample_annotations,
        sample_answer_scores,
        sample_snapshot,
        sample_judge_claim_based,
    ):
        """Metrics service should read the existing preset rubric instead of calling the invariant repair helper."""
        service = MetricsService(test_db)

        with patch(
            "src.rubric.services.system_rubrics.ensure_system_rubrics",
            side_effect=AssertionError("request-time ensure should not run"),
        ):
            rubric_id = self._accuracy_rubric_id(test_db, sample_snapshot.target_id)
            contract = service._build_base_scoring_contract(sample_snapshot.id, rubric_id)
            accuracy = service.calculate_accuracy(sample_snapshot.id, sample_judge_claim_based.id, rubric_id)
            results, _ = service.get_aggregated_results(sample_snapshot.id, rubric_id)

        assert contract.rubric_name == "Accuracy"
        assert accuracy.accuracy == 0.8
        assert len(results) == 10

    def test_build_base_scoring_contract_raises_when_rubric_is_missing(
        self,
        test_db,
        sample_snapshot,
    ):
        """Runtime fixed-accuracy lookups should fail loudly instead of auto-creating a rubric."""
        service = MetricsService(test_db)

        with pytest.raises(ValueError, match="Rubric 9999 not found"):
            service._build_base_scoring_contract(sample_snapshot.id, 9999)

    def test_alignment_uses_rubric_annotations_as_ground_truth(
        self,
        test_db,
        sample_snapshot,
        sample_answer,
        sample_judge_claim_based,
    ):
        """Rubric-backed annotations should drive alignment."""
        sample_answer.is_selected_for_annotation = True
        test_db.add(
            Annotation(
                answer_id=sample_answer.id,
                rubric_id=sample_judge_claim_based.rubric_id,
                option_value="Accurate",
                notes="Rubric row says accurate",
            )
        )
        test_db.add(
            AnswerScore(
                answer_id=sample_answer.id,
                rubric_id=sample_judge_claim_based.rubric_id,
                judge_id=sample_judge_claim_based.id,
                overall_label="Accurate",
                explanation="Judge agrees with rubric annotation",
            )
        )
        test_db.commit()

        service = MetricsService(test_db)
        metrics = service.calculate_judge_alignment(
            sample_snapshot.id,
            sample_judge_claim_based.id,
            sample_judge_claim_based.rubric_id,
        )

        assert metrics.accuracy == 1.0

    def test_alignment_requires_rubric_annotation(
        self,
        test_db,
        sample_snapshot,
        sample_answer,
        sample_judge_claim_based,
    ):
        """Alignment should fail when no rubric-backed annotation exists."""
        sample_answer.is_selected_for_annotation = True
        test_db.add(
            AnswerScore(
                answer_id=sample_answer.id,
                rubric_id=sample_judge_claim_based.rubric_id,
                judge_id=sample_judge_claim_based.id,
                overall_label="Accurate",
                explanation="Judge score exists",
            )
        )
        test_db.commit()

        service = MetricsService(test_db)
        with pytest.raises(ValueError, match="No annotations found"):
            service.calculate_judge_alignment(
                sample_snapshot.id,
                sample_judge_claim_based.id,
                sample_judge_claim_based.rubric_id,
            )

    def test_accuracy_scoring_contract_marks_rows_pending_when_reliable_judge_missing_score(
        self,
        test_db,
        sample_target,
        sample_annotations,
        sample_answer_scores,
        sample_snapshot,
        sample_judge_claim_based,
    ):
        """Rows stay pending until every reliable accuracy judge has scored them."""
        second_judge = Judge(
            target_id=sample_target.id,
            rubric_id=sample_judge_claim_based.rubric_id,
            name="Judge 2",
            model_name="gemini/gemini-3.1-flash-lite",
            prompt_template="Second accuracy judge",
            params={"temperature": 0.0},
            is_baseline=False,
            is_editable=True,
        )
        test_db.add(second_judge)
        test_db.commit()
        test_db.refresh(second_judge)

        for annotation in sample_annotations[1:]:
            test_db.add(AnswerScore(
                answer_id=annotation.answer_id,
                rubric_id=second_judge.rubric_id,
                judge_id=second_judge.id,
                overall_label="Accurate" if annotation.label else "Inaccurate",
                explanation="Reliable second judge",
            ))
        test_db.commit()

        service = MetricsService(test_db)
        contract = service._build_base_scoring_contract(sample_snapshot.id, sample_judge_claim_based.rubric_id)

        target_row = next(row for row in contract.rows if row.answer_id == sample_annotations[0].answer_id)
        assert any(summary.judge_id == second_judge.id for summary in contract.judge_summaries)
        assert any(judge.judge_id == second_judge.id for judge in contract.aligned_judges)
        assert target_row.aggregated_result.method == "pending"
        assert target_row.aggregated_result.value is None

    def test_accuracy_scoring_contract_returns_unavailable_summary_for_judge_with_no_scores(
        self,
        test_db,
        sample_target,
        sample_snapshot,
        sample_annotations,
        sample_judge_claim_based,
    ):
        """A created judge without any run data should expose unavailable summary values."""
        unused_judge = Judge(
            target_id=sample_target.id,
            rubric_id=sample_judge_claim_based.rubric_id,
            name="Unrun Accuracy Judge",
            model_name="gemini/gemini-3.1-flash-lite",
            prompt_template="Accuracy prompt",
            params={"temperature": 0.0},
            is_baseline=False,
            is_editable=True,
        )
        test_db.add(unused_judge)
        test_db.commit()
        test_db.refresh(unused_judge)

        service = MetricsService(test_db)
        contract = service._build_base_scoring_contract(sample_snapshot.id, sample_judge_claim_based.rubric_id)

        summary = next(summary for summary in contract.judge_summaries if summary.judge_id == unused_judge.id)
        assert summary.accuracy is None
        assert summary.reliability is None
        assert summary.accurate_count == 0
        assert summary.total_answers == 0

    def test_accuracy_scoring_contract_uses_persisted_override_for_row_state(
        self,
        test_db,
        sample_annotations,
        sample_answer_scores,
        sample_snapshot,
    ):
        """Persisted accuracy overrides should remain visible in the scoring contract after refresh."""
        from src.rubric.services.system_rubrics import ensure_system_rubrics
        ensure_system_rubrics(test_db, sample_snapshot.target_id)
        accuracy_rubric_id = self._accuracy_rubric_id(test_db, sample_snapshot.target_id)
        target_answer_id = sample_annotations[8].answer_id
        test_db.add(AnswerLabelOverride(answer_id=target_answer_id, rubric_id=accuracy_rubric_id, edited_value="Accurate"))
        test_db.commit()

        service = MetricsService(test_db)
        contract = service._build_base_scoring_contract(sample_snapshot.id, accuracy_rubric_id)

        row = next(row for row in contract.rows if row.answer_id == target_answer_id)
        assert row.aggregated_result.method == "override"
        assert row.aggregated_result.value == "Accurate"
        assert row.aggregated_result.baseline_value == "Inaccurate"
        assert row.aggregated_result.is_edited is True
        assert contract.accurate_count == 9
        assert contract.inaccurate_count == 1
        assert contract.edited_count == 1

    def test_rubric_scoring_contract_ignores_rubric_annotations_as_scoring_overrides(
        self,
        test_db,
        sample_target,
        sample_snapshot,
        sample_annotations,
        sample_rubric,
    ):
        """Rubric annotations remain ground truth and do not change the scoring-table aggregate by themselves."""
        rubric_judge = Judge(
            target_id=sample_target.id,
            rubric_id=sample_rubric.id,
            name="Tone Judge",
            model_name="gemini/gemini-3.1-flash-lite",
            prompt_template="Tone prompt",
            params={"temperature": 0.0},
            is_baseline=False,
            is_editable=True,
        )
        test_db.add(rubric_judge)
        test_db.commit()
        test_db.refresh(rubric_judge)

        answers = [annotation.answer for annotation in sample_annotations]
        overridden_answer_id = answers[0].id
        negative_control_answer_id = answers[1].id
        for answer in answers:
            test_db.add(AnswerScore(
                answer_id=answer.id,
                rubric_id=sample_rubric.id,
                judge_id=rubric_judge.id,
                overall_label="Casual" if answer.id in {overridden_answer_id, negative_control_answer_id} else "Professional",
                explanation="Judged tone",
            ))
            test_db.add(Annotation(
                answer_id=answer.id,
                rubric_id=sample_rubric.id,
                option_value="Casual" if answer.id == negative_control_answer_id else "Professional",
            ))
        test_db.commit()

        service = MetricsService(test_db)
        contract = service._build_base_scoring_contract(sample_snapshot.id, sample_rubric.id)

        row = next(row for row in contract.rows if row.answer_id == overridden_answer_id)
        assert row.aggregated_result.method == "majority"
        assert row.aggregated_result.value == "Casual"
        assert row.aggregated_result.baseline_value == "Casual"
        assert row.aggregated_result.is_edited is False
        assert row.human_label == "Professional"
        assert contract.accurate_count == 8
        assert contract.inaccurate_count == 2
        assert contract.edited_count == 0
        assert contract.aggregated_score == 0.8

    def test_rubric_scoring_contract_counts_scoring_override_in_aggregate_summary(
        self,
        test_db,
        sample_target,
        sample_snapshot,
        sample_annotations,
        sample_rubric,
    ):
        """Rubric metric summaries should recalculate when a saved human rubric label differs from judge majority."""
        rubric_judge = Judge(
            target_id=sample_target.id,
            rubric_id=sample_rubric.id,
            name="Tone Judge",
            model_name="gemini/gemini-3.1-flash-lite",
            prompt_template="Tone prompt",
            params={"temperature": 0.0},
            is_baseline=False,
            is_editable=True,
        )
        test_db.add(rubric_judge)
        test_db.commit()
        test_db.refresh(rubric_judge)

        answers = [annotation.answer for annotation in sample_annotations]
        overridden_answer_id = answers[0].id
        negative_control_answer_id = answers[1].id
        for answer in answers:
            test_db.add(AnswerScore(
                answer_id=answer.id,
                rubric_id=sample_rubric.id,
                judge_id=rubric_judge.id,
                overall_label="Casual" if answer.id in {overridden_answer_id, negative_control_answer_id} else "Professional",
                explanation="Judged tone",
            ))
            test_db.add(Annotation(
                answer_id=answer.id,
                rubric_id=sample_rubric.id,
                option_value="Casual" if answer.id == negative_control_answer_id else "Professional",
            ))
        test_db.commit()

        test_db.add(AnswerLabelOverride(
            answer_id=overridden_answer_id,
            rubric_id=sample_rubric.id,
            edited_value="Professional",
        ))
        test_db.commit()

        service = MetricsService(test_db)
        contract = service._build_base_scoring_contract(sample_snapshot.id, sample_rubric.id)

        row = next(row for row in contract.rows if row.answer_id == overridden_answer_id)
        assert row.aggregated_result.method == "override"
        assert row.aggregated_result.value == "Professional"
        assert row.aggregated_result.baseline_value == "Casual"
        assert row.aggregated_result.is_edited is True
        assert row.human_label == "Professional"
        assert contract.accurate_count == 9
        assert contract.inaccurate_count == 1
        assert contract.edited_count == 1
        assert contract.aggregated_score == 0.9

    def test_judge_without_annotations_is_not_calibrated_not_zero(
        self, test_db, sample_snapshot, sample_answer, sample_judge_claim_based
    ):
        """No human labels must surface as 'not calibrated', never as reliability 0.0."""
        sample_answer.is_selected_for_annotation = True
        test_db.add(AnswerScore(
            answer_id=sample_answer.id, rubric_id=sample_judge_claim_based.rubric_id,
            judge_id=sample_judge_claim_based.id, overall_label="Accurate", explanation="x",
        ))
        test_db.commit()

        service = MetricsService(test_db)
        contract = service._build_base_scoring_contract(sample_snapshot.id, sample_judge_claim_based.rubric_id)
        summary = next(s for s in contract.judge_summaries if s.judge_id == sample_judge_claim_based.id)
        assert summary.reliability is None
        assert summary.sample_count == 0
        assert summary.reliability_status == "not_calibrated"
        assert contract.aligned_judges == []

    def test_judge_below_calibration_floor_is_not_aligned(
        self, test_db, sample_annotations, sample_answer_scores, sample_snapshot, sample_judge_claim_based
    ):
        """Ten labels with a floor of twenty: reliability is shown but the judge is not gated in."""
        from tests.conftest import override_settings

        service = MetricsService(test_db)
        with override_settings(min_calibration_samples=20, recommended_calibration_samples=30):
            contract = service._build_base_scoring_contract(sample_snapshot.id, sample_judge_claim_based.rubric_id)
        summary = next(s for s in contract.judge_summaries if s.judge_id == sample_judge_claim_based.id)
        assert summary.sample_count == 10
        assert summary.reliability is not None and summary.reliability >= 0.5
        assert summary.reliability_status == "insufficient_calibration"
        assert contract.aligned_judges == []

    def test_judge_at_floor_and_above_threshold_is_aligned_with_sample_count(
        self, test_db, sample_annotations, sample_answer_scores, sample_snapshot, sample_judge_claim_based
    ):
        service = MetricsService(test_db)
        contract = service._build_base_scoring_contract(sample_snapshot.id, sample_judge_claim_based.rubric_id)
        summary = next(s for s in contract.judge_summaries if s.judge_id == sample_judge_claim_based.id)
        assert summary.reliability_status == "aligned"
        aligned = next(j for j in contract.aligned_judges if j.judge_id == sample_judge_claim_based.id)
        assert aligned.sample_count == 10

    def test_judge_below_threshold_is_unreliable(
        self, test_db, sample_annotations, sample_snapshot, sample_judge_claim_based
    ):
        """A judge that contradicts every human label is 'unreliable', not merely unaligned."""
        for annotation in sample_annotations:
            test_db.add(AnswerScore(
                answer_id=annotation.answer_id, rubric_id=sample_judge_claim_based.rubric_id,
                judge_id=sample_judge_claim_based.id,
                overall_label="Inaccurate" if annotation.label else "Accurate", explanation="inverted",
            ))
        test_db.commit()
        service = MetricsService(test_db)
        contract = service._build_base_scoring_contract(sample_snapshot.id, sample_judge_claim_based.rubric_id)
        summary = next(s for s in contract.judge_summaries if s.judge_id == sample_judge_claim_based.id)
        assert summary.reliability_status == "unreliable"
        assert summary.reliability == 0.0
        assert contract.aligned_judges == []

    def test_contract_withholds_score_when_no_judge_is_aligned(
        self, test_db, sample_annotations, sample_snapshot, sample_judge_claim_based
    ):
        for annotation in sample_annotations:
            test_db.add(AnswerScore(
                answer_id=annotation.answer_id, rubric_id=sample_judge_claim_based.rubric_id,
                judge_id=sample_judge_claim_based.id,
                overall_label="Inaccurate" if annotation.label else "Accurate", explanation="inverted",
            ))
        test_db.commit()
        contract = MetricsService(test_db)._build_base_scoring_contract(sample_snapshot.id, sample_judge_claim_based.rubric_id)
        assert contract.aggregated_score is None
        assert contract.verdict_status == "no_aligned_judge"
        assert contract.calibration_count == 10

    def test_contract_reports_not_calibrated_without_labels(
        self, test_db, sample_snapshot, sample_answer, sample_judge_claim_based
    ):
        sample_answer.is_selected_for_annotation = True
        test_db.add(AnswerScore(answer_id=sample_answer.id, rubric_id=sample_judge_claim_based.rubric_id,
                                judge_id=sample_judge_claim_based.id, overall_label="Accurate", explanation="x"))
        test_db.commit()
        contract = MetricsService(test_db)._build_base_scoring_contract(sample_snapshot.id, sample_judge_claim_based.rubric_id)
        assert contract.verdict_status == "not_calibrated"
        assert contract.aggregated_score is None
        assert contract.calibration_count == 0

    def test_contract_reports_insufficient_calibration_below_floor(
        self, test_db, sample_annotations, sample_answer_scores, sample_snapshot, sample_judge_claim_based
    ):
        from tests.conftest import override_settings
        with override_settings(min_calibration_samples=20, recommended_calibration_samples=30):
            contract = MetricsService(test_db)._build_base_scoring_contract(sample_snapshot.id, sample_judge_claim_based.rubric_id)
        assert contract.verdict_status == "insufficient_calibration"
        assert contract.aggregated_score is None
        assert contract.min_calibration_samples == 20
        assert contract.recommended_calibration_samples == 30
        assert contract.reliability_threshold == 0.5

    def test_contract_is_ready_with_an_aligned_judge(
        self, test_db, sample_annotations, sample_answer_scores, sample_snapshot, sample_judge_claim_based
    ):
        contract = MetricsService(test_db)._build_base_scoring_contract(sample_snapshot.id, sample_judge_claim_based.rubric_id)
        assert contract.verdict_status == "ready"
        assert contract.aggregated_score is not None

    def test_contract_reports_insufficient_calibration_when_judge_scored_only_part_of_labels(
        self, test_db, sample_annotations, sample_snapshot, sample_judge_claim_based
    ):
        """A judge that has scored only some of the annotated answers is still calibrating, not failed."""
        from tests.conftest import override_settings

        for annotation in sample_annotations[:5]:
            test_db.add(AnswerScore(
                answer_id=annotation.answer_id,
                rubric_id=sample_judge_claim_based.rubric_id,
                judge_id=sample_judge_claim_based.id,
                overall_label="Accurate" if annotation.label else "Inaccurate",
                explanation="partial scoring",
            ))
        test_db.commit()

        service = MetricsService(test_db)
        with override_settings(min_calibration_samples=8, recommended_calibration_samples=10):
            contract = service._build_base_scoring_contract(sample_snapshot.id, sample_judge_claim_based.rubric_id)

        summary = next(s for s in contract.judge_summaries if s.judge_id == sample_judge_claim_based.id)
        assert summary.reliability_status == "insufficient_calibration"
        assert summary.sample_count == 5
        assert contract.verdict_status == "insufficient_calibration"

    def test_contract_reports_insufficient_calibration_when_judge_scored_none_of_selected_answers(
        self, test_db, sample_annotations, sample_snapshot, sample_judge_claim_based, sample_target,
        sample_job, sample_personas,
    ):
        """Scores exist for the judge, but none on a selected/annotated answer: it has not been calibrated yet."""
        unselected_question = Question(
            job_id=sample_job.id,
            target_id=sample_target.id,
            persona_id=sample_personas[0].id,
            text="An unselected question?",
            type=QuestionTypeEnum.typical,
            scope=QuestionScopeEnum.in_kb,
            status=StatusEnum.approved,
        )
        test_db.add(unselected_question)
        test_db.flush()
        unselected_answer = Answer(
            question_id=unselected_question.id,
            snapshot_id=sample_snapshot.id,
            answer_content="Not selected for annotation.",
            chat_id="chatUnselected",
            message_id="msgUnselected",
            is_selected_for_annotation=False,
        )
        test_db.add(unselected_answer)
        test_db.commit()

        test_db.add(AnswerScore(
            answer_id=unselected_answer.id,
            rubric_id=sample_judge_claim_based.rubric_id,
            judge_id=sample_judge_claim_based.id,
            overall_label="Accurate",
            explanation="scored but not selected for annotation",
        ))
        test_db.commit()

        contract = MetricsService(test_db)._build_base_scoring_contract(sample_snapshot.id, sample_judge_claim_based.rubric_id)

        summary = next(s for s in contract.judge_summaries if s.judge_id == sample_judge_claim_based.id)
        assert summary.reliability_status == "not_calibrated"
        assert contract.verdict_status == "insufficient_calibration"
        assert contract.calibration_count == 10

    def test_contract_reports_no_aligned_judge_with_one_unreliable_and_one_still_calibrating_judge(
        self, test_db, sample_annotations, sample_snapshot, sample_judge_claim_based
    ):
        """An unreliable judge plus a judge still calibrating: withheld for the failure, not the wait."""
        from tests.conftest import override_settings

        second_judge = Judge(
            name="Second Claim-Based Judge",
            model_name="gemini/gemini-3.1-flash-lite",
            prompt_template="Test prompt template",
            params={"temperature": 0.7},
            rubric_id=sample_judge_claim_based.rubric_id,
            is_baseline=False,
            is_editable=True,
        )
        test_db.add(second_judge)
        test_db.commit()
        test_db.refresh(second_judge)

        for annotation in sample_annotations:
            test_db.add(AnswerScore(
                answer_id=annotation.answer_id,
                rubric_id=sample_judge_claim_based.rubric_id,
                judge_id=sample_judge_claim_based.id,
                overall_label="Inaccurate" if annotation.label else "Accurate",
                explanation="inverted",
            ))
        for annotation in sample_annotations[:5]:
            test_db.add(AnswerScore(
                answer_id=annotation.answer_id,
                rubric_id=second_judge.rubric_id,
                judge_id=second_judge.id,
                overall_label="Accurate" if annotation.label else "Inaccurate",
                explanation="correct but still calibrating",
            ))
        test_db.commit()

        service = MetricsService(test_db)
        with override_settings(min_calibration_samples=8, recommended_calibration_samples=10):
            contract = service._build_base_scoring_contract(sample_snapshot.id, sample_judge_claim_based.rubric_id)

        first_summary = next(s for s in contract.judge_summaries if s.judge_id == sample_judge_claim_based.id)
        second_summary = next(s for s in contract.judge_summaries if s.judge_id == second_judge.id)
        assert first_summary.reliability_status == "unreliable"
        assert second_summary.reliability_status == "insufficient_calibration"
        assert contract.verdict_status == "no_aligned_judge"
