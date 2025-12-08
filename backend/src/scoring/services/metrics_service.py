"""
Service for calculating judge alignment and accuracy metrics.
"""

import logging
from typing import Dict
from sqlalchemy.orm import Session
from sklearn.metrics import f1_score, precision_score, recall_score, accuracy_score

from src.common.database.repositories.annotation_repo import AnnotationRepository
from src.common.database.repositories.answer_score_repo import AnswerScoreRepository

logger = logging.getLogger(__name__)


class MetricsService:
    """Service for calculating judge performance metrics."""

    def __init__(self, db: Session):
        """
        Initialize metrics service.

        Args:
            db: Database session
        """
        self.db = db

    def calculate_judge_alignment(self, snapshot_id: int, judge_id: int) -> Dict:
        """
        Calculate judge alignment metrics by comparing judge scores with human annotations.

        This function:
        1. Gets selected annotations (where answer.is_selected_for_annotation=True)
        2. Gets judge scores for the same selected answers
        3. Calculates F1, precision, recall, and accuracy using sklearn

        Args:
            snapshot_id: Snapshot ID
            judge_id: Judge ID to evaluate

        Returns:
            Dict with metrics: {"f1": 0.85, "precision": 0.82, "recall": 0.88, "accuracy": 0.84}

        Raises:
            ValueError: If no annotations or scores found for comparison
        """
        # Get selected annotations
        annotations = AnnotationRepository.get_by_snapshot_selected(self.db, snapshot_id)

        if not annotations:
            raise ValueError(f"No annotations found for snapshot {snapshot_id} with is_selected_for_annotation=True")

        # Get answer IDs from annotations
        answer_ids = [ann.answer_id for ann in annotations]

        # Get judge scores for the same selected answers
        scores = AnswerScoreRepository.get_by_snapshot_and_judge_selected(self.db, snapshot_id, judge_id)

        if not scores:
            raise ValueError(f"No scores found for judge {judge_id}, snapshot {snapshot_id} on selected answers")

        # Create mapping of answer_id -> annotation label
        annotation_map = {ann.answer_id: ann.label for ann in annotations}

        # Create mapping of answer_id -> score label
        score_map = {score.answer_id: score.overall_label for score in scores}

        # Build aligned lists for sklearn
        y_true = []  # Human annotations (ground truth)
        y_pred = []  # Judge predictions

        for answer_id in answer_ids:
            if answer_id in annotation_map and answer_id in score_map:
                y_true.append(annotation_map[answer_id])
                y_pred.append(score_map[answer_id])

        if not y_true:
            raise ValueError(f"No overlapping annotations and scores found for snapshot {snapshot_id}, judge {judge_id}")

        # Calculate metrics using sklearn
        f1 = f1_score(y_true, y_pred, average='binary', pos_label=True)
        precision = precision_score(y_true, y_pred, average='binary', pos_label=True, zero_division=0)
        recall = recall_score(y_true, y_pred, average='binary', pos_label=True, zero_division=0)
        accuracy = accuracy_score(y_true, y_pred)

        logger.info(
            f"Judge alignment for judge {judge_id}, snapshot {snapshot_id}: "
            f"F1={f1:.3f}, Precision={precision:.3f}, Recall={recall:.3f}, Accuracy={accuracy:.3f} "
            f"({len(y_true)} samples)"
        )

        return {
            "f1": round(f1, 3),
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "accuracy": round(accuracy, 3),
            "sample_count": len(y_true)
        }

    def calculate_accuracy(self, snapshot_id: int, judge_id: int) -> Dict:
        """
        Calculate overall accuracy for a judge across all answers in a snapshot.

        Accuracy = (number of accurate answers) / (total answers)

        Args:
            snapshot_id: Snapshot ID
            judge_id: Judge ID

        Returns:
            Dict with: {"accuracy": 0.73, "total_answers": 100, "accurate_count": 73}

        Raises:
            ValueError: If no scores found
        """
        # Get all answer scores for this snapshot and judge
        scores = AnswerScoreRepository.get_by_snapshot_and_judge(self.db, snapshot_id, judge_id)

        if not scores:
            raise ValueError(f"No scores found for judge {judge_id}, snapshot {snapshot_id}")

        # Calculate accuracy
        total_count = len(scores)
        accurate_count = sum(1 for score in scores if score.overall_label is True)
        accuracy = accurate_count / total_count if total_count > 0 else 0.0

        logger.info(
            f"Accuracy for judge {judge_id}, snapshot {snapshot_id}: "
            f"{accurate_count}/{total_count} = {accuracy:.3f}"
        )

        return {
            "accuracy": round(accuracy, 3),
            "total_answers": total_count,
            "accurate_count": accurate_count
        }


def calculate_judge_alignment(db: Session, snapshot_id: int, judge_id: int) -> Dict:
    """
    Calculate judge alignment metrics (convenience function).

    Args:
        db: Database session
        snapshot_id: Snapshot ID
        judge_id: Judge ID to evaluate

    Returns:
        Dict with metrics
    """
    service = MetricsService(db)
    return service.calculate_judge_alignment(snapshot_id, judge_id)


def calculate_accuracy(db: Session, snapshot_id: int, judge_id: int) -> Dict:
    """
    Calculate overall accuracy for a judge (convenience function).

    Args:
        db: Database session
        snapshot_id: Snapshot ID
        judge_id: Judge ID

    Returns:
        Dict with accuracy metrics
    """
    service = MetricsService(db)
    return service.calculate_accuracy(snapshot_id, judge_id)
