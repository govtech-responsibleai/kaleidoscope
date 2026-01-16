"""
Unit tests for MetricsService.
"""

import pytest

from src.scoring.services.metrics_service import MetricsService


@pytest.mark.unit
class TestMetricsService:
    """Unit tests for MetricsService class."""

    def test_calculate_judge_alignment(
        self, test_db, sample_annotations, sample_answer_scores, sample_snapshot, sample_judge_claim_based
    ):
        """Test judge alignment calculation returns correct F1, precision, recall, accuracy."""
        # Annotations: 7 True, 3 False
        # Scores: 8 True, 2 False
        # Overlap: Need to verify alignment

        service = MetricsService(test_db)
        metrics = service.calculate_judge_alignment(sample_snapshot.id, sample_judge_claim_based.id)

        # Verify metrics structure
        assert "f1" in metrics
        assert "precision" in metrics
        assert "recall" in metrics
        assert "accuracy" in metrics
        assert "sample_count" in metrics

        # Verify sample count matches
        assert metrics["sample_count"] == 10

        # Verify all metrics are between 0 and 1
        assert 0 <= metrics["f1"] <= 1
        assert 0 <= metrics["precision"] <= 1
        assert 0 <= metrics["recall"] <= 1
        assert 0 <= metrics["accuracy"] <= 1

    def test_calculate_accuracy(
        self, test_db, sample_answer_scores, sample_snapshot, sample_judge_claim_based
    ):
        """Test accuracy calculation: 8 accurate out of 10 = 0.8."""
        # Sample scores: 8 True, 2 False

        service = MetricsService(test_db)
        metrics = service.calculate_accuracy(sample_snapshot.id, sample_judge_claim_based.id)

        # Verify metrics
        assert metrics["accuracy"] == 0.8
        assert metrics["total_answers"] == 10
        assert metrics["accurate_count"] == 8

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
        """
        Test get_aggregated_results returns aggregated scores for all answers.

        Tests:
        1. Returns results for all answers in snapshot
        2. Each result has question_id, answer_id, answer_content, aggregated_accuracy
        3. Aggregated accuracy has method, label, and metadata
        """
        service = MetricsService(test_db)
        results = service.get_aggregated_results(sample_snapshot.id)

        # Verify we get results for all answers
        assert len(results) == 10

        # Verify structure of each result
        for result in results:
            assert "question_id" in result
            assert "question_text" in result
            assert "answer_id" in result
            assert "answer_content" in result
            assert "aggregated_accuracy" in result

            agg = result["aggregated_accuracy"]
            assert "method" in agg
            assert "label" in agg
            assert "metadata" in agg
            assert agg["method"] in ["majority", "majority_tied", "no_aligned_judge", "override"]

    def test_get_aggregated_results_raises_if_no_answers(self, test_db, sample_snapshot):
        """Test that get_aggregated_results raises ValueError when no answers found."""
        service = MetricsService(test_db)

        with pytest.raises(ValueError, match="No answers found"):
            service.get_aggregated_results(sample_snapshot.id)

    def test_calculate_snapshot_summary(
        self, test_db, sample_annotations, sample_answer_scores, sample_snapshot
    ):
        """
        Test calculate_snapshot_summary returns correct summary metrics.

        Tests:
        1. Returns aggregated_accuracy as a ratio
        2. Returns total_answers, accurate_count, pending_count
        3. Returns judge alignment info
        """
        service = MetricsService(test_db)
        summary = service.calculate_snapshot_summary(sample_snapshot.id)

        # Verify structure
        assert "aggregated_accuracy" in summary
        assert "total_answers" in summary
        assert "accurate_count" in summary
        assert "pending_count" in summary
        assert "edited_count" in summary
        assert "has_aligned_judges" in summary
        assert "reliable_judge_count" in summary

        # Verify aggregated_accuracy is between 0 and 1
        assert 0 <= summary["aggregated_accuracy"] <= 1

        # Verify counts are non-negative
        assert summary["total_answers"] >= 0
        assert summary["accurate_count"] >= 0
        assert summary["pending_count"] >= 0
        assert summary["edited_count"] >= 0

    def test_calculate_confusion_matrix(
        self, test_db, sample_target, sample_annotations, sample_answer_scores, sample_snapshot
    ):
        """
        Test calculate_confusion_matrix returns breakdown by question type/scope.

        Tests:
        1. Returns matrix with type_scope combinations
        2. Returns total_inaccurate count
        3. Returns snapshot_id
        """
        service = MetricsService(test_db)
        result = service.calculate_confusion_matrix(sample_target.id, sample_snapshot.id)

        # Verify structure
        assert "matrix" in result
        assert "total_inaccurate" in result
        assert "snapshot_id" in result

        # Verify matrix has all combinations
        matrix = result["matrix"]
        assert "typical_in_kb" in matrix
        assert "typical_out_kb" in matrix
        assert "edge_in_kb" in matrix
        assert "edge_out_kb" in matrix

        # Verify all counts are non-negative
        for key, value in matrix.items():
            assert value >= 0

        assert result["total_inaccurate"] >= 0
        assert result["snapshot_id"] == sample_snapshot.id
