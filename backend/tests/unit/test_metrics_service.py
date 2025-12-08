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
