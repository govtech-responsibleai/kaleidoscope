"""
Service for calculating judge alignment and accuracy metrics.
"""

import csv
import io
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional
from collections import Counter
from sqlalchemy.orm import Session
from sklearn.metrics import f1_score, precision_score, recall_score, accuracy_score

from src.common.database.repositories.annotation_repo import AnnotationRepository
from src.common.database.repositories.answer_score_repo import AnswerScoreRepository
from src.common.database.repositories.answer_repo import AnswerRepository
from src.common.database.repositories.judge_repo import JudgeRepository
from src.common.database.models import AnswerScore

logger = logging.getLogger(__name__)

AggregationMethod = Literal["majority", "majority_tied", "no_aligned_judge"]


@dataclass
class AggregatedAnswerScore:
    """Aggregated score for an answer using reliable judges only."""

    answer_id: int
    method: AggregationMethod
    label: Optional[bool]
    metadata: List[str] = field(default_factory=list)
    accepted_scores: List[AnswerScore] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "answer_id": self.answer_id,
            "method": self.method,
            "label": self.label,
            "metadata": self.metadata,
        }


def _format_label(label: Optional[bool]) -> str:
    if label is None:
        return "Pending"
    return "Accurate" if label else "Inaccurate"


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

        # Calculate metrics using sklearn. Positive Label: False (Inaccurate), Negative Label: True (Accurate)
        f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
        precision = precision_score(y_true, y_pred, average='binary', pos_label=False, zero_division=0)
        recall = recall_score(y_true, y_pred, average='binary', pos_label=False, zero_division=0)
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

    def get_aggregated_results(self, snapshot_id: int) -> List[Dict]:
        """
        Get aggregated evaluation results for all answers in a snapshot.

        For each answer:
        1. Gets scores from all judges
        2. Computes per-judge reliability (F1) and filters to judges above 0.5
        3. Aggregates the reliable labels via majority vote (ties captured explicitly)

        Args:
            snapshot_id: Snapshot ID

        Returns:
            List of dicts with:
            [{
                "question_id": 1,
                "question_text": "What is...",
                "answer_id": 10,
                "answer_content": "The answer is...",
                "aggregated_accuracy": {
                    "answer_id": 10,
                    "method": "majority",
                    "label": True,
                    "metadata": ["Judge A: Accurate", "Judge B: excluded as not reliable"]
                }
            }]

        Raises:
            ValueError: If no answers found for snapshot
        """
        # Get all answers for the snapshot with question info
        answers = AnswerRepository.get_by_snapshot(self.db, snapshot_id)

        if not answers:
            raise ValueError(f"No answers found for snapshot {snapshot_id}")

        # Get all judges and their reliability (F1) scores
        judges = JudgeRepository.get_all(self.db)
        judge_map = {judge.id: judge.name for judge in judges}
        reliability_map: Dict[int, float] = {}

        for judge in judges:
            reliability = 0.0
            try:
                metrics = self.calculate_judge_alignment(snapshot_id, judge.id)
                reliability = metrics.get("f1", 0.0) or 0.0
            except ValueError:
                # No overlapping annotations/scores – treat as unreliable
                reliability = 0.0
            except Exception:
                logger.exception(
                    "Failed to calculate reliability for judge %s", judge.id
                )
                reliability = 0.0
            reliability_map[judge.id] = reliability

        results = []

        for answer in answers:
            # Get all scores for this answer across all judges
            answer_scores = AnswerScoreRepository.get_by_answer(self.db, answer.id)

            metadata: List[str] = []
            reliable_scores: List[AnswerScore] = []

            for score in answer_scores:
                judge_name = judge_map.get(score.judge_id, "Unknown")
                reliability = reliability_map.get(score.judge_id, 0.0)
                if reliability > 0.5:
                    reliable_scores.append(score)
                    metadata.append(f"- {judge_name}: {_format_label(score.overall_label)}")
                else:
                    metadata.append(f"- {judge_name}: excluded as not reliable")

            if not reliable_scores:
                aggregated_score = AggregatedAnswerScore(
                    answer_id=answer.id,
                    method="no_aligned_judge",
                    label=None,
                    metadata=metadata,
                    accepted_scores=reliable_scores
                )
            else:
                labels = [score.overall_label for score in reliable_scores if score.overall_label is not None]
                if not labels:
                    aggregated_score = AggregatedAnswerScore(
                        answer_id=answer.id,
                        method="majority_tied",
                        label=None,
                        metadata=metadata,
                        accepted_scores=reliable_scores
                    )
                else:
                    label_counts = Counter(labels)
                    most_common = label_counts.most_common()
                    if len(most_common) > 1 and most_common[0][1] == most_common[1][1]:
                        aggregated_score = AggregatedAnswerScore(
                            answer_id=answer.id,
                            method="majority_tied",
                            label=None,
                            metadata=metadata,
                            accepted_scores=reliable_scores
                        )
                    else:
                        aggregated_score = AggregatedAnswerScore(
                            answer_id=answer.id,
                            method="majority",
                            label=most_common[0][0],
                            metadata=metadata,
                            accepted_scores=reliable_scores
                        )

            results.append({
                "question_id": answer.question_id,
                "question_text": answer.question.text if answer.question else None,
                "answer_id": answer.id,
                "answer_content": answer.answer_content,
                "aggregated_accuracy": aggregated_score.to_dict()
            })

        logger.info(f"Generated aggregated results for {len(results)} answers in snapshot {snapshot_id}")

        return results

    def export_results_csv(self, snapshot_id: int) -> str:
        """
        Export aggregated evaluation results as CSV.

        Args:
            snapshot_id: Snapshot ID

        Returns:
            CSV string with headers: question, answer, accuracy, metadata

        Raises:
            ValueError: If no answers found for the snapshot
        """
        # Reuse aggregated results that power the frontend view
        aggregated_results = self.get_aggregated_results(snapshot_id)

        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)

        # Write headers that match the frontend columns
        writer.writerow(["Question", "Answer", "Accuracy", "Metadata"])

        for result in aggregated_results:
            aggregated_accuracy = result.get("aggregated_accuracy", {})
            metadata_parts = aggregated_accuracy.get("metadata", [])

            writer.writerow([
                result.get("question_text", ""),
                result.get("answer_content", ""),
                _format_label(aggregated_accuracy.get("label")),
                " | ".join(metadata_parts)
            ])

        csv_content = output.getvalue()
        output.close()

        logger.info(
            f"Exported {len(aggregated_results)} aggregated results for snapshot {snapshot_id}"
        )

        return csv_content


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
