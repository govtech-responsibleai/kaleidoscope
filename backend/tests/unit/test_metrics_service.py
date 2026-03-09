"""
Unit tests for MetricsService.
"""

import pytest

from src.scoring.services.metrics_service import MetricsService
from src.common.models.metrics import (
    AggregatedResult,
    ConfusionMatrixResponse,
    JudgeAccuracyResponse,
    JudgeAlignmentResponse,
    TargetSnapshotMetric,
)


@pytest.mark.unit
class TestMetricsService:
    """Unit tests for MetricsService class."""

    def test_calculate_judge_alignment(
        self, test_db, sample_annotations, sample_answer_scores, sample_snapshot, sample_judge_claim_based
    ):
        """Test judge alignment calculation returns correct F1, precision, recall, accuracy."""
        service = MetricsService(test_db)
        metrics = service.calculate_judge_alignment(sample_snapshot.id, sample_judge_claim_based.id)

        # Verify metrics structure
        assert isinstance(metrics, JudgeAlignmentResponse)

        # Verify sample count matches
        assert metrics.sample_count == 10

        # Verify all metrics are between 0 and 1
        assert 0 <= metrics.f1 <= 1
        assert 0 <= metrics.precision <= 1
        assert 0 <= metrics.recall <= 1
        assert 0 <= metrics.accuracy <= 1

    def test_calculate_accuracy(
        self, test_db, sample_answer_scores, sample_snapshot, sample_judge_claim_based
    ):
        """Test accuracy calculation: 8 accurate out of 10 = 0.8."""
        service = MetricsService(test_db)
        metrics = service.calculate_accuracy(sample_snapshot.id, sample_judge_claim_based.id)

        assert isinstance(metrics, JudgeAccuracyResponse)
        assert metrics.accuracy == 0.8
        assert metrics.total_answers == 10
        assert metrics.accurate_count == 8

    def test_alignment_raises_if_no_annotations(self, test_db, sample_snapshot, sample_judge_claim_based):
        """Test that calculate_judge_alignment raises ValueError when no annotations found."""
        service = MetricsService(test_db)

        with pytest.raises(ValueError, match="No annotations found"):
            service.calculate_judge_alignment(sample_snapshot.id, sample_judge_claim_based.id)

    def test_accuracy_raises_if_no_scores(self, test_db, sample_snapshot, sample_judge_claim_based):
        """Test that calculate_accuracy raises ValueError when no scores found."""
        service = MetricsService(test_db)

        with pytest.raises(ValueError, match="No scores found"):
            service.calculate_accuracy(sample_snapshot.id, sample_judge_claim_based.id)

    def test_get_aggregated_results(
        self, test_db, sample_annotations, sample_answer_scores, sample_snapshot
    ):
        """Test get_aggregated_results returns (list of AggregatedResult, reliability_map) tuple."""
        service = MetricsService(test_db)
        results, reliability_map = service.get_aggregated_results(sample_snapshot.id)

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
            assert result.aggregated_accuracy is not None

            agg = result.aggregated_accuracy
            assert agg.method in ["majority", "majority_tied", "no_aligned_judge", "override"]
            assert isinstance(agg.metadata, list)


    def test_get_aggregated_results_raises_if_no_answers(self, test_db, sample_snapshot):
        """Test that get_aggregated_results raises ValueError when no answers found."""
        service = MetricsService(test_db)

        with pytest.raises(ValueError, match="No answers found"):
            service.get_aggregated_results(sample_snapshot.id)

    def test_calculate_snapshot_summary(
        self, test_db, sample_annotations, sample_answer_scores, sample_snapshot
    ):
        """Test calculate_snapshot_summary returns correct summary metrics with aligned_judges."""
        service = MetricsService(test_db)
        summary = service.calculate_snapshot_summary(sample_snapshot.id)

        # Verify structure
        assert isinstance(summary, TargetSnapshotMetric)

        # Verify aligned_judges is a list (B3)
        assert isinstance(summary.aligned_judges, list)
        for judge in summary.aligned_judges:
            assert judge.judge_id is not None
            assert judge.name
            assert judge.f1 is not None

        # Verify aggregated_accuracy is between 0 and 1
        assert 0 <= summary.aggregated_accuracy <= 1

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
        self, test_db, sample_target, sample_annotations, sample_answer_scores, sample_snapshot
    ):
        """Test calculate_confusion_matrix returns breakdown by question type/scope."""
        service = MetricsService(test_db)
        result = service.calculate_confusion_matrix(sample_target.id, sample_snapshot.id)

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
