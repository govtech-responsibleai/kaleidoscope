"""
Service for calculating judge alignment and accuracy metrics.
"""

import csv
import io
import logging
from typing import Dict, List, Optional, Tuple
from collections import Counter
from sqlalchemy.orm import Session
from sklearn.metrics import f1_score, precision_score, recall_score, accuracy_score

from src.common.database.repositories.annotation_repo import AnnotationRepository
from src.common.database.repositories.answer_score_repo import AnswerScoreRepository
from src.common.database.repositories.answer_repo import AnswerRepository
from src.common.database.repositories.judge_repo import JudgeRepository
from src.common.database.repositories.answer_label_override_repo import AnswerLabelOverrideRepository
from src.common.database.repositories.rubric_answer_score_repo import RubricAnswerScoreRepository
from src.common.database.models import AnswerScore
from src.common.models.metrics import (
    AggregatedAnswerScore,
    AggregatedResult,
    AlignedJudge,
    JudgeAlignmentResponse,
    JudgeAccuracyResponse,
    TargetSnapshotMetric,
    ConfusionMatrixResponse,
)

logger = logging.getLogger(__name__)


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

    def calculate_judge_alignment(
        self, snapshot_id: int, judge_id: int
    ) -> JudgeAlignmentResponse:
        """
        Calculate judge alignment metrics by comparing judge scores with human annotations.

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

        # Label overrides take precedence over annotations for ground truth
        overrides = AnswerLabelOverrideRepository.get_by_snapshot(self.db, snapshot_id)
        override_map = {o.answer_id: o.edited_label for o in overrides}
        for answer_id, label in override_map.items():
            if answer_id in annotation_map:
                annotation_map[answer_id] = label

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
        f1 = f1_score(y_true, y_pred, average="macro", pos_label=False, zero_division=0)
        precision = precision_score(y_true, y_pred, average='binary', pos_label=False, zero_division=0)
        recall = recall_score(y_true, y_pred, average='binary', pos_label=False, zero_division=0)
        accuracy = accuracy_score(y_true, y_pred)

        logger.info(
            f"Judge alignment for judge {judge_id}, snapshot {snapshot_id}: "
            f"F1={f1:.3f}, Precision={precision:.3f}, Recall={recall:.3f}, Accuracy={accuracy:.3f} "
            f"({len(y_true)} samples)"
        )

        return JudgeAlignmentResponse(
            f1=round(f1, 3),
            precision=round(precision, 3),
            recall=round(recall, 3),
            accuracy=round(accuracy, 3),
            sample_count=len(y_true),
        )

    def calculate_accuracy(self, snapshot_id: int, judge_id: int) -> JudgeAccuracyResponse:
        """
        Calculate overall accuracy for a judge across all answers in a snapshot.

        Args:
            snapshot_id: Snapshot ID
            judge_id: Judge ID

        Returns:
            Dict with: {"accuracy": 0.73, "total_answers": 100, "accurate_count": 73}

        Raises:
            ValueError: If no scores found
        """
        scores = AnswerScoreRepository.get_by_snapshot_and_judge(self.db, snapshot_id, judge_id)

        if not scores:
            raise ValueError(f"No scores found for judge {judge_id}, snapshot {snapshot_id}")

        total_count = len(scores)
        accurate_count = sum(1 for score in scores if score.overall_label is True)
        accuracy = accurate_count / total_count if total_count > 0 else 0.0

        logger.info(
            f"Accuracy for judge {judge_id}, snapshot {snapshot_id}: "
            f"{accurate_count}/{total_count} = {accuracy:.3f}"
        )

        return JudgeAccuracyResponse(
            accuracy=round(accuracy, 3),
            total_answers=total_count,
            accurate_count=accurate_count,
        )

    def get_aggregated_results(
        self, snapshot_id: int
    ) -> Tuple[List[AggregatedResult], Dict[int, float]]:
        """
        Get aggregated evaluation results across all answers in a snapshot.

        For each answer:
        1. Gets scores from all judges
        2. Computes per-judge reliability (F1) and filters to judges above 0.5
        3. Aggregates the reliable labels via majority vote (ties captured explicitly)

        Also computes and returns the judge reliability map (B2: inlined).

        Args:
            snapshot_id: Snapshot ID

        Returns:
            Tuple of (list of AggregatedResult, reliability_map dict)

        Raises:
            ValueError: If no answers found for snapshot
        """
        # Load answers with scores, annotations, and question data in one pass.
        answers = AnswerRepository.get_with_scores_and_annotation(self.db, snapshot_id)
        answers = sorted(answers, key=lambda answer: answer.id)

        if not answers:
            raise ValueError(f"No answers found for snapshot {snapshot_id}")

        overrides = AnswerLabelOverrideRepository.get_by_snapshot(self.db, snapshot_id)
        override_map = {override.answer_id: override for override in overrides}

        # Get reliability only for judges that actually have scores on this snapshot
        # (avoids querying all judges in the system, most of which have no scores)
        judge_ids_in_snapshot = set()
        for answer in answers:
            for score in answer.scores:
                judge_ids_in_snapshot.add(score.judge_id)

        judges = JudgeRepository.get_all(self.db)
        judge_map = {judge.id: judge.name for judge in judges}
        reliability_map: Dict[int, float] = {}

        for judge_id in judge_ids_in_snapshot:
            reliability = 0.0
            try:
                metrics = self.calculate_judge_alignment(snapshot_id, judge_id)
                reliability = metrics.f1 or 0.0
            except ValueError:
                reliability = 0.0
            except Exception:
                logger.exception(
                    "Failed to calculate reliability for judge %s", judge_id
                )
                reliability = 0.0
            reliability_map[judge_id] = reliability

        results: List[AggregatedResult] = []

        for answer in answers:
            # Check for user override first
            override = override_map.get(answer.id)

            # Scores and annotation are already eager loaded on the answer.
            answer_scores = answer.scores

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

                )
            elif not reliable_scores:
                aggregated_score = AggregatedAnswerScore(
                    answer_id=answer.id,
                    method="no_aligned_judge",
                    label=None,
                    is_edited=False,
                    metadata=metadata,
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
        
                        )
                    else:
                        aggregated_score = AggregatedAnswerScore(
                            answer_id=answer.id,
                            method="majority",
                            label=most_common[0][0],
                            is_edited=False,
                            metadata=metadata,
        
                        )

            # Get annotation for this answer
            annotation = answer.annotation

            # Include question_type and question_scope from answer.question
            question = answer.question
            results.append(AggregatedResult(
                question_id=answer.question_id,
                question_text=question.text if question else None,
                question_type=question.type.value if question and question.type else None,
                question_scope=question.scope.value if question and question.scope else None,
                answer_id=answer.id,
                answer_content=answer.answer_content,
                aggregated_accuracy=aggregated_score,
                human_label=annotation.label if annotation else None,
                human_notes=annotation.notes if annotation else None,
            ))

        logger.info(f"Generated aggregated results for {len(results)} answers in snapshot {snapshot_id}")

        return results, reliability_map

    def calculate_snapshot_summary(self, snapshot_id: int) -> TargetSnapshotMetric:
        """
        Calculate summary metrics for a snapshot.

        Args:
            snapshot_id: Snapshot ID

        Returns:
            Dict with summary metrics including aligned_judges list

        Raises:
            ValueError: If no answers found for snapshot
        """
        # Single call to get_aggregated_results for both results and reliability map
        aggregated_results, reliability_map = self.get_aggregated_results(snapshot_id)

        logger.debug(
            "Aggregated results: %s",
            [{"aggregated_accuracy": r.aggregated_accuracy.model_dump()} for r in aggregated_results]
        )

        # Build aligned_judges list (reuse judges from DB, no re-fetch needed)
        judges = JudgeRepository.get_all(self.db)
        judge_map = {judge.id: judge.name for judge in judges}
        aligned_judges: List[AlignedJudge] = []

        # Calculate judge alignment range; fix sentinel leak
        judge_alignment_range = None
        if reliability_map:
            range_min = None
            range_max = None
            for judge_id, f1_val in reliability_map.items():
                if f1_val >= 0.5:
                    aligned_judges.append(AlignedJudge(
                        judge_id=judge_id,
                        name=judge_map.get(judge_id, "Unknown"),
                        f1=round(f1_val, 3),
                    ))
                    if range_min is None or f1_val < range_min:
                        range_min = f1_val
                    if range_max is None or f1_val > range_max:
                        range_max = f1_val

            # Only set range if we find aligned judges 
            if aligned_judges:
                judge_alignment_range = {
                    "min": range_min,
                    "max": range_max,
                }

        # Count answers by label category
        # All QA rows are included — unreliable judges are already excluded
        # per-answer in get_aggregated_results.
        total_answers = len(aggregated_results)
        accurate_count = 0
        inaccurate_count = 0
        pending_count = 0  # True pending: ties, None labels, no aligned judges
        edited_count = 0

        for result in aggregated_results:
            agg = result.aggregated_accuracy
            if agg.is_edited:
                edited_count += 1

            if (agg.method == "majority" or agg.method == "override") and agg.label is True:
                accurate_count += 1
            elif (agg.method == "majority" or agg.method == "override") and agg.label is False:
                inaccurate_count += 1
            else:
                # label is None: tied vote, no aligned judges, or pending evaluation
                pending_count += 1

        # Calculate overall aggregated accuracy
        agg_accuracy = accurate_count / total_answers if total_answers > 0 else 0.0

        logger.info(
            f"Snapshot {snapshot_id} summary: "
            f"Accuracy={agg_accuracy:.3f} ({accurate_count}/{total_answers}), "
            f"Aligned judges: {len(aligned_judges)}, Edited: {edited_count}"
        )

        return TargetSnapshotMetric(
            aggregated_accuracy=round(agg_accuracy, 3),
            total_answers=total_answers,
            accurate_count=accurate_count,
            inaccurate_count=inaccurate_count,
            pending_count=pending_count,
            edited_count=edited_count,
            judge_alignment_range=judge_alignment_range,
            aligned_judges=aligned_judges,
        )

    def calculate_confusion_matrix(
        self, target_id: int, snapshot_id: Optional[int] = None
    ) -> ConfusionMatrixResponse:
        """
        Calculate confusion matrix for question types/scopes vs inaccurate responses.

        Args:
            target_id: Target ID
            snapshot_id: Optional snapshot ID (if None, uses latest snapshot)

        Returns:
            Dict with confusion matrix data

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
            snapshot = sorted(snapshots, key=lambda s: s.created_at, reverse=True)[0]
            snapshot_id = snapshot.id
        else:
            snapshot = SnapshotRepository.get_by_id(self.db, snapshot_id)
            if not snapshot:
                raise ValueError(f"Snapshot {snapshot_id} not found")

        # Get aggregated results for the snapshot
        try:
            aggregated_results, _ = self.get_aggregated_results(snapshot_id)
        except ValueError as e:
            raise ValueError(f"Failed to get aggregated results: {str(e)}")

        # Initialize confusion matrix counters
        matrix = {
            "typical_in_kb": 0,
            "typical_out_kb": 0,
            "edge_in_kb": 0,
            "edge_out_kb": 0,
        }

        # Use question_type/question_scope from AggregatedResult
        for result in aggregated_results:
            agg = result.aggregated_accuracy
            # Include overridden inaccurate answers
            if agg.label is False and agg.method in ("majority", "override"):
                q_type = result.question_type
                q_scope = result.question_scope
                if q_type and q_scope:
                    key = f"{q_type}_{q_scope}"
                    if key in matrix:
                        matrix[key] += 1

        total_inaccurate = sum(matrix.values())

        logger.info(
            f"Confusion matrix for target {target_id}, snapshot {snapshot_id}: "
            f"Total inaccurate={total_inaccurate}"
        )

        # Remove snapshot_id from return (caller already knows it)
        return ConfusionMatrixResponse(
            matrix=matrix,
            total_inaccurate=total_inaccurate,
        )

    def calculate_rubric_judge_alignment(
        self, snapshot_id: int, judge_id: int, rubric_id: int, best_option: str
    ) -> JudgeAlignmentResponse:
        """
        Calculate how well a rubric judge agrees with human rubric labels on selected answers.
        Treats best_option as the positive class (True), all others as negative (False).
        Returns f1, precision, recall, accuracy, and sample_count.
        """
        human_labels = RubricAnswerScoreRepository.get_human_labels_by_snapshot_selected(
            self.db, snapshot_id, rubric_id
        )
        judge_scores = RubricAnswerScoreRepository.get_by_snapshot_and_rubric_and_judge_selected(
            self.db, snapshot_id, rubric_id, judge_id
        )

        if not human_labels or not judge_scores:
            raise ValueError(f"No data for rubric alignment: judge {judge_id}, rubric {rubric_id}, snapshot {snapshot_id}")

        human_map = {label.answer_id: label.option_value for label in human_labels}
        judge_map = {score.answer_id: score.option_chosen for score in judge_scores}

        # Convert to binary: best_option → True, anything else → False
        y_true = []
        y_pred = []
        for answer_id in human_map:
            if answer_id in judge_map:
                y_true.append(human_map[answer_id] == best_option)
                y_pred.append(judge_map[answer_id] == best_option)

        if not y_true:
            raise ValueError(f"No overlapping data for rubric alignment")

        f1 = f1_score(y_true, y_pred, average="macro", pos_label=True, zero_division=0)
        precision = precision_score(y_true, y_pred, average="binary", pos_label=True, zero_division=0)
        recall = recall_score(y_true, y_pred, average="binary", pos_label=True, zero_division=0)
        acc = accuracy_score(y_true, y_pred)

        return JudgeAlignmentResponse(
            f1=round(f1, 3),
            precision=round(precision, 3),
            recall=round(recall, 3),
            accuracy=round(acc, 3),
            sample_count=len(y_true),
        )

    def calculate_rubric_judge_accuracy(
        self, snapshot_id: int, judge_id: int, rubric_id: int, best_option: str
    ) -> JudgeAccuracyResponse:
        """
        Calculate what % of answers this judge gave the best option for a rubric.
        best_option is treated as "accurate" (positive label).
        """
        scores = RubricAnswerScoreRepository.get_by_snapshot_and_rubric_and_judge(
            self.db, snapshot_id, rubric_id, judge_id
        )

        if not scores:
            raise ValueError(f"No rubric scores for judge {judge_id}, rubric {rubric_id}, snapshot {snapshot_id}")

        total = len(scores)
        accurate_count = sum(1 for s in scores if s.option_chosen == best_option)
        accuracy = accurate_count / total if total > 0 else 0.0

        return JudgeAccuracyResponse(
            accuracy=round(accuracy, 3),
            total_answers=total,
            accurate_count=accurate_count,
        )

    def calculate_rubric_snapshot_metrics(
        self, target_id: int, snapshot_id: int
    ) -> List[TargetSnapshotMetric]:
        """
        Calculate aggregated rubric metrics for a snapshot.
        For each rubric: determine reliable judges, aggregate via majority vote,
        calculate % of answers getting best option (treated as "accurate").
        """
        from src.common.database.repositories.target_rubric_repo import TargetRubricRepository

        rubrics = TargetRubricRepository.get_by_target(self.db, target_id)
        judges = JudgeRepository.get_all(self.db)
        judge_map = {j.id: j.name for j in judges}

        results = []
        for rubric in rubrics:
            options = rubric.options or []
            if not options:
                continue
            # Use user-specified best_option if set, otherwise fall back to first option
            if rubric.best_option:
                best_option = rubric.best_option
            else:
                best_option = options[0].get("option", "") if isinstance(options[0], dict) else str(options[0])

            # Find all judges that have scores for this rubric in this snapshot
            from src.common.database.models import RubricAnswerScore, Answer
            judge_rows = (
                self.db.query(RubricAnswerScore.judge_id)
                .join(Answer, RubricAnswerScore.answer_id == Answer.id)
                .filter(Answer.snapshot_id == snapshot_id, RubricAnswerScore.rubric_id == rubric.id)
                .distinct()
                .all()
            )
            judge_ids_with_scores = {row[0] for row in judge_rows}

            if not judge_ids_with_scores:
                continue

            # Calculate reliability for each judge (now using f1 via binary classification)
            reliability_map = {}
            for jid in judge_ids_with_scores:
                try:
                    alignment = self.calculate_rubric_judge_alignment(snapshot_id, jid, rubric.id, best_option)
                    reliability_map[jid] = alignment.f1
                except ValueError:
                    reliability_map[jid] = 0.0

            # Filter to reliable judges (>= 0.5)
            aligned_judges = []
            range_min = None
            range_max = None
            for jid, f1_val in reliability_map.items():
                if f1_val >= 0.5:
                    aligned_judges.append(AlignedJudge(
                        judge_id=jid,
                        name=judge_map.get(jid, "Unknown"),
                        f1=round(f1_val, 3),
                    ))
                    if range_min is None or f1_val < range_min:
                        range_min = f1_val
                    if range_max is None or f1_val > range_max:
                        range_max = f1_val

            judge_alignment_range = None
            if aligned_judges:
                judge_alignment_range = {"min": range_min, "max": range_max}

            # Aggregate: for each answer, get majority vote from reliable judges
            reliable_judge_ids = {j.judge_id for j in aligned_judges}
            scoring_judge_ids = reliable_judge_ids if reliable_judge_ids else judge_ids_with_scores

            all_scores = (
                self.db.query(RubricAnswerScore)
                .join(Answer, RubricAnswerScore.answer_id == Answer.id)
                .filter(
                    Answer.snapshot_id == snapshot_id,
                    RubricAnswerScore.rubric_id == rubric.id,
                    RubricAnswerScore.judge_id.in_(scoring_judge_ids),
                )
                .all()
            )

            # Group by answer_id, majority vote
            answer_options = {}
            for score in all_scores:
                answer_options.setdefault(score.answer_id, []).append(score.option_chosen)

            total_answers = len(answer_options)
            accurate_count = 0
            inaccurate_count = 0
            pending_count = 0
            for aid, options_list in answer_options.items():
                counter = Counter(options_list)
                most_common = counter.most_common()
                if len(most_common) > 1 and most_common[0][1] == most_common[1][1]:
                    pending_count += 1  # tied vote
                elif most_common[0][0] == best_option:
                    accurate_count += 1
                else:
                    inaccurate_count += 1

            agg_accuracy = accurate_count / total_answers if total_answers > 0 else 0.0

            results.append(TargetSnapshotMetric(
                snapshot_id=snapshot_id,
                rubric_id=rubric.id,
                rubric_name=rubric.name,
                aggregated_accuracy=round(agg_accuracy, 3),
                total_answers=total_answers,
                accurate_count=accurate_count,
                inaccurate_count=inaccurate_count,
                pending_count=pending_count,
                edited_count=0,
                aligned_judges=aligned_judges,
                judge_alignment_range=judge_alignment_range,
            ))

        return results


def calculate_judge_alignment(
    db: Session, snapshot_id: int, judge_id: int
) -> JudgeAlignmentResponse:
    """Calculate judge alignment metrics (convenience function)."""
    service = MetricsService(db)
    return service.calculate_judge_alignment(snapshot_id, judge_id)


def calculate_accuracy(
    db: Session, snapshot_id: int, judge_id: int
) -> JudgeAccuracyResponse:
    """Calculate overall accuracy for a judge (convenience function)."""
    service = MetricsService(db)
    return service.calculate_accuracy(snapshot_id, judge_id)


def calculate_rubric_judge_alignment(
    db: Session, snapshot_id: int, judge_id: int, rubric_id: int, best_option: str
) -> JudgeAlignmentResponse:
    """Calculate rubric judge alignment (convenience function)."""
    service = MetricsService(db)
    return service.calculate_rubric_judge_alignment(snapshot_id, judge_id, rubric_id, best_option)


def calculate_rubric_judge_accuracy(
    db: Session, snapshot_id: int, judge_id: int, rubric_id: int, best_option: str
) -> JudgeAccuracyResponse:
    """Calculate rubric judge accuracy (convenience function)."""
    service = MetricsService(db)
    return service.calculate_rubric_judge_accuracy(snapshot_id, judge_id, rubric_id, best_option)
