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
from src.common.database.repositories.answer_label_override_repo import AnswerLabelOverrideRepository
from src.common.database.models import AnswerScore

logger = logging.getLogger(__name__)

AggregationMethod = Literal["majority", "majority_tied", "no_aligned_judge", "override"]


@dataclass
class AggregatedAnswerScore:
    """Aggregated score for an answer using reliable judges only."""

    answer_id: int
    method: AggregationMethod
    label: Optional[bool]
    is_edited: bool = False
    metadata: List[str] = field(default_factory=list)
    accepted_scores: List[AnswerScore] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "answer_id": self.answer_id,
            "method": self.method,
            "label": self.label,
            "is_edited": self.is_edited,
            "metadata": self.metadata,
            "reliable_judge_count": len(self.accepted_scores),
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

    def _calculate_judge_reliability_map(self, snapshot_id: int) -> Dict[int, float]:
        """
        Calculate reliability (F1 score) for all judges on a snapshot.

        Helper method that computes judge alignment for each judge and returns
        a mapping of judge_id to F1 score. Judges with no annotations or errors
        are assigned a reliability of 0.0.

        Args:
            snapshot_id: Snapshot ID

        Returns:
            Dict mapping judge_id to F1 score (reliability)
        """
        judges = JudgeRepository.get_all(self.db)
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

        return reliability_map

    def get_aggregated_results(self, snapshot_id: int) -> List[Dict]:
        """
        Get aggregated evaluation results across all answers in a snapshot.

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
        reliability_map = self._calculate_judge_reliability_map(snapshot_id)

        results = []

        for answer in answers:
            # Check for user override first
            override = AnswerLabelOverrideRepository.get_by_answer(self.db, answer.id)

            # Get all scores for this answer across all judges
            answer_scores = AnswerScoreRepository.get_by_answer(self.db, answer.id)

            metadata: List[str] = []
            reliable_scores: List[AnswerScore] = []

            for score in answer_scores:
                judge_name = judge_map.get(score.judge_id, "Unknown")
                reliability = reliability_map.get(score.judge_id, 0.0)
                if reliability >= 0.5:
                    reliable_scores.append(score)
                    metadata.append(f"- {judge_name}: {_format_label(score.overall_label)}")
                else:
                    metadata.append(f"- {judge_name}: excluded as not reliable")

            # If there's an override, use it instead of majority vote
            if override:
                aggregated_score = AggregatedAnswerScore(
                    answer_id=answer.id,
                    method="override",
                    label=override.edited_label,
                    is_edited=True,
                    metadata=metadata,
                    accepted_scores=reliable_scores
                )
            elif not reliable_scores:
                aggregated_score = AggregatedAnswerScore(
                    answer_id=answer.id,
                    method="no_aligned_judge",
                    label=None,
                    is_edited=False,
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
                        is_edited=False,
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
                            is_edited=False,
                            metadata=metadata,
                            accepted_scores=reliable_scores
                        )
                    else:
                        aggregated_score = AggregatedAnswerScore(
                            answer_id=answer.id,
                            method="majority",
                            label=most_common[0][0],
                            is_edited=False,
                            metadata=metadata,
                            accepted_scores=reliable_scores
                        )

            # Get annotation for this answer
            annotation = AnnotationRepository.get_by_answer(self.db, answer.id)

            results.append({
                "question_id": answer.question_id,
                "question_text": answer.question.text if answer.question else None,
                "answer_id": answer.id,
                "answer_content": answer.answer_content,
                "aggregated_accuracy": aggregated_score.to_dict(),
                "human_label": annotation.label if annotation else None,
                "human_notes": annotation.notes if annotation else None,
            })

        logger.info(f"Generated aggregated results for {len(results)} answers in snapshot {snapshot_id}")

        return results

    def calculate_snapshot_summary(self, snapshot_id: int) -> Dict:
        """
        Calculate summary metrics for a snapshot.

        This method aggregates results across all answers and judges to provide
        high-level metrics for visualization and reporting.

        Args:
            snapshot_id: Snapshot ID

        Returns:
            Dict with summary metrics:
            {
                "aggregated_accuracy": 0.73,        # % of answers with majority "accurate"
                "total_answers": 100,
                "accurate_count": 73,
                "pending_count": 12,                # None/ties/no aligned judges
                "judge_alignment_range": {
                    "min": 0.50,
                    "max": 0.85
                },
                "has_aligned_judges": True,         # any F1 >= 0.5
                "reliable_judge_count": 3
            }

        Raises:
            ValueError: If no answers found for snapshot
        """
        # Get aggregated results for all answers
        # Part of the response contains a list of QAs with its aggregated score.
        aggregated_results = self.get_aggregated_results(snapshot_id)

        print("Aggregated results:", [{"aggregated_accuracy": x["aggregated_accuracy"]} for x in aggregated_results])

        # Get judge reliability scores and calculate reliable judge count early
        reliability_map = self._calculate_judge_reliability_map(snapshot_id)

        # Calculate judge alignment range and check for aligned judges
        if reliability_map:
            judge_alignment_range = {
                "min": 2,
                "max": 0
            }
            reliable_judge_count = 0
            for v in reliability_map.values():
                if v >= 0.5:
                    reliable_judge_count += 1
                    judge_alignment_range["min"] = min(judge_alignment_range["min"], v)
                    judge_alignment_range["max"] = max(judge_alignment_range["max"], v)
            has_aligned_judges = reliable_judge_count > 0
        else:
            judge_alignment_range = None
            reliable_judge_count = 0
            has_aligned_judges = False

        # Filter out QAs with no reliable judges or incomplete judge coverage
        # But include overrides even if they have no reliable judges
        filtered_results = [
            r for r in aggregated_results
            if (r.get("aggregated_accuracy", {}).get("method") == "override") or
            (r.get("aggregated_accuracy", {}).get("method") != "no_aligned_judge"
             and r.get("aggregated_accuracy", {}).get("reliable_judge_count", 0) == reliable_judge_count)
        ]

        # Count accurate vs pending answers (using filtered results)
        total_answers = len(filtered_results)
        accurate_count = 0
        pending_count = 0
        edited_count = 0

        for result in filtered_results:
            aggregated_accuracy = result.get("aggregated_accuracy", {})
            label = aggregated_accuracy.get("label")
            method = aggregated_accuracy.get("method")
            is_edited = aggregated_accuracy.get("is_edited", False)

            if is_edited:
                edited_count += 1

            # Count accurate if label is True (either from majority vote or override)
            if (method == "majority" or method == "override") and label is True:
                accurate_count += 1
            else:
                # Includes: label=False (inaccurate), label=None (tied)
                pending_count += 1

        # Calculate overall aggregated accuracy
        aggregated_accuracy = accurate_count / total_answers if total_answers > 0 else 0.0

        logger.info(
            f"Snapshot {snapshot_id} summary: "
            f"Accuracy={aggregated_accuracy:.3f} ({accurate_count}/{total_answers}), "
            f"Reliable judges: {reliable_judge_count}, Edited: {edited_count}"
        )

        return {
            "aggregated_accuracy": round(aggregated_accuracy, 3),
            "total_answers": total_answers,
            "accurate_count": accurate_count,
            "pending_count": pending_count,
            "edited_count": edited_count,
            "judge_alignment_range": judge_alignment_range,
            "has_aligned_judges": has_aligned_judges,
            "reliable_judge_count": reliable_judge_count
        }

    def calculate_confusion_matrix(self, target_id: int, snapshot_id: Optional[int] = None) -> Dict:
        """
        Calculate confusion matrix for question types/scopes vs inaccurate responses.

        Shows distribution of inaccurate responses across question type (typical/edge)
        and scope (in_kb/out_kb) combinations.

        Args:
            target_id: Target ID
            snapshot_id: Optional snapshot ID (if None, uses latest snapshot)

        Returns:
            Dict with confusion matrix data:
            {
                "matrix": {
                    "typical_in_kb": 5,
                    "typical_out_kb": 3,
                    "edge_in_kb": 2,
                    "edge_out_kb": 7
                },
                "total_inaccurate": 17,
                "snapshot_id": 1
            }

        Raises:
            ValueError: If no snapshot found or no answers available
        """
        from src.common.database.repositories import SnapshotRepository, TargetRepository

        # Verify target exists
        target = TargetRepository.get_by_id(self.db, target_id)
        if not target:
            raise ValueError(f"Target {target_id} not found")

        # Get snapshot (latest if not specified)
        if snapshot_id is None:
            snapshots = SnapshotRepository.get_by_target(self.db, target_id)
            if not snapshots:
                raise ValueError(f"No snapshots found for target {target_id}")
            # Sort by created_at descending and take the first one
            snapshot = sorted(snapshots, key=lambda s: s.created_at, reverse=True)[0]
            snapshot_id = snapshot.id
        else:
            snapshot = SnapshotRepository.get_by_id(self.db, snapshot_id)
            if not snapshot:
                raise ValueError(f"Snapshot {snapshot_id} not found")

        # Get aggregated results for the snapshot
        try:
            aggregated_results = self.get_aggregated_results(snapshot_id)
        except ValueError as e:
            raise ValueError(f"Failed to get aggregated results: {str(e)}")

        # Initialize confusion matrix counters
        matrix = {
            "typical_in_kb": 0,
            "typical_out_kb": 0,
            "edge_in_kb": 0,
            "edge_out_kb": 0,
        }

        # Count inaccurate responses by question type and scope
        for result in aggregated_results:
            aggregated_accuracy = result.get("aggregated_accuracy", {})
            label = aggregated_accuracy.get("label")
            method = aggregated_accuracy.get("method")

            # Only count answers that have been evaluated and are inaccurate
            if method == "majority" and label is False:
                # Get question details from the answer
                answer = AnswerRepository.get_by_id(self.db, result["answer_id"])
                if answer and answer.question:
                    q_type = answer.question.type.value  # "typical" or "edge"
                    q_scope = answer.question.scope.value  # "in_kb" or "out_kb"
                    key = f"{q_type}_{q_scope}"
                    if key in matrix:
                        matrix[key] += 1

        total_inaccurate = sum(matrix.values())

        logger.info(
            f"Confusion matrix for target {target_id}, snapshot {snapshot_id}: "
            f"Total inaccurate={total_inaccurate}"
        )

        return {
            "matrix": matrix,
            "total_inaccurate": total_inaccurate,
            "snapshot_id": snapshot_id,
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
