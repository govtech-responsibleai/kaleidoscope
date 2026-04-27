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

from src.common.database.repositories.answer_score_repo import AnswerScoreRepository
from src.common.database.repositories.answer_repo import AnswerRepository
from src.common.database.repositories.judge_repo import JudgeRepository
from src.common.database.repositories.answer_label_override_repo import AnswerLabelOverrideRepository
from src.common.database.repositories.question_repo import QuestionRepository
from src.common.database.repositories.snapshot_repo import SnapshotRepository
from src.common.database.repositories.target_rubric_repo import TargetRubricRepository
from src.common.database.models import AnswerScore, Answer, Annotation
from src.rubric.services.system_rubrics import best_option_for_rubric, canonicalize_rubric_option_value
from src.common.models.metrics import (
    AggregatedScore,
    AggregatedResult,
    SnapshotResultsResponse,
    AggregatedRowResult,
    AggregationMethod,
    AlignedJudge,
    JudgeAlignmentResponse,
    JudgeAccuracyResponse,
    JudgeRowResult,
    JudgeScoreSummary,
    ScoringContract,
    ScoringRowResult,
    SnapshotMetric,
    MetricsByRubric,
    SnapshotMetricsResponse,
    ConfusionMatrixResponse,
    ScoringPendingCountsResponse,
    SnapshotScoringContractsResponse,
)

logger = logging.getLogger(__name__)
RELIABILITY_THRESHOLD = 0.5


def _format_label(label: Optional[str]) -> str:
    if label is None:
        return "Pending"
    return label


def _resolve_row_aggregate(
    raw_values: List[Optional[str]],
    override_value: Optional[str],
) -> AggregatedRowResult:
    """Shared state machine for rubric row aggregation.

    raw_values: per-judge string values (None means score missing/pending).
    """
    if not raw_values:
        baseline_method: AggregationMethod = "no_aligned_judge"
        baseline_value: Optional[str] = None
    elif any(v is None for v in raw_values):
        baseline_method = "pending"
        baseline_value = None
    else:
        counts = Counter(raw_values)
        most_common = counts.most_common()
        if len(most_common) > 1 and most_common[0][1] == most_common[1][1]:
            baseline_method = "majority_tied"
            baseline_value = None
        else:
            baseline_method = "majority"
            baseline_value = most_common[0][0]

    is_edited = bool(
        baseline_method == "majority"
        and baseline_value is not None
        and override_value is not None
        and override_value != baseline_value
    )

    if is_edited:
        return AggregatedRowResult(
            method="override",
            value=override_value,
            baseline_value=baseline_value,
            is_edited=True,
        )
    return AggregatedRowResult(
        method=baseline_method,
        value=baseline_value,
        baseline_value=baseline_value,
        is_edited=False,
    )


class MetricsService:
    """Service for calculating judge performance metrics."""

    def __init__(self, db: Session):
        """
        Initialize metrics service.

        Args:
            db: Database session
        """
        self.db = db

    def _best_option_for_rubric(self, rubric) -> str:
        return best_option_for_rubric(rubric)

    def _build_alignment_range(self, aligned_judges: List[AlignedJudge]) -> Optional[Dict[str, float]]:
        if not aligned_judges:
            return None
        scores = [judge.f1 for judge in aligned_judges]
        return {"min": min(scores), "max": max(scores)}

    def _summarize_contract_rows(
        self,
        rows: List[ScoringRowResult],
        resolved_value,
        is_positive,
    ) -> Tuple[int, int, int, int, float]:
        total_answers = len(rows)
        accurate_count = 0
        inaccurate_count = 0
        pending_count = 0
        edited_count = 0

        for row in rows:
            aggregate = row.aggregated_result
            value = resolved_value(row)
            if aggregate.is_edited:
                edited_count += 1
            if value is None:
                pending_count += 1
            elif is_positive(value):
                accurate_count += 1
            else:
                inaccurate_count += 1

        aggregate_score = accurate_count / total_answers if total_answers > 0 else 0.0
        return accurate_count, inaccurate_count, pending_count, edited_count, round(aggregate_score, 3)

    def _get_accuracy_reliability_map(
        self,
        snapshot_id: int,
        answers: List[Answer],
    ) -> Tuple[Dict[int, float], Dict[int, str]]:
        judge_ids_in_snapshot = set()
        for answer in answers:
            for score in answer.scores:
                judge_ids_in_snapshot.add(score.judge_id)

        judges = JudgeRepository.get_all(self.db)
        judge_name_map = {judge.id: judge.name for judge in judges}
        reliability_map: Dict[int, float] = {}

        for judge_id in judge_ids_in_snapshot:
            try:
                metrics = self.calculate_judge_alignment(snapshot_id, judge_id)
                reliability_map[judge_id] = metrics.f1 or 0.0
            except ValueError:
                reliability_map[judge_id] = 0.0
            except Exception:
                logger.exception("Failed to calculate reliability for judge %s", judge_id)
                reliability_map[judge_id] = 0.0

        return reliability_map, judge_name_map

    def _get_human_label_map(
        self,
        answer_ids: List[int],
        rubric,
    ) -> Dict[int, str]:
        if not answer_ids:
            return {}

        annotations = (
            self.db.query(Annotation.answer_id, Annotation.option_value)
            .filter(
                Annotation.answer_id.in_(answer_ids),
                Annotation.rubric_id == rubric.id,
            )
            .all()
        )
        return {
            answer_id: canonical
            for answer_id, option_value in annotations
            if (canonical := canonicalize_rubric_option_value(rubric, option_value)) is not None
        }

    def _calculate_judge_reliability(
        self,
        snapshot_id: int,
        judge_id: int,
        rubric_id: int,
    ) -> float:
        try:
            return self.calculate_judge_alignment(snapshot_id, judge_id, rubric_id).f1 or 0.0
        except ValueError:
            return 0.0
        except Exception:
            logger.exception(
                "Failed to calculate reliability for judge %s on rubric %s",
                judge_id,
                rubric_id,
            )
            return 0.0

    def build_scoring_contract(self, snapshot_id: int, rubric_id: int) -> ScoringContract:
        snapshot = SnapshotRepository.get_by_id(self.db, snapshot_id)
        if not snapshot:
            raise ValueError(f"Snapshot {snapshot_id} not found")

        rubric = TargetRubricRepository.get_by_id(self.db, rubric_id)
        if not rubric:
            raise ValueError(f"Rubric {rubric_id} not found")
        if rubric.target_id != snapshot.target_id:
            raise ValueError(f"Rubric {rubric_id} does not belong to snapshot {snapshot_id}")

        answers = AnswerRepository.get_with_scores_and_annotation(self.db, snapshot_id)
        answers = sorted(answers, key=lambda answer: answer.id)
        if not answers:
            raise ValueError(f"No answers found for snapshot {snapshot_id}")

        answer_ids = [answer.id for answer in answers]
        overrides = [
            override
            for override in AnswerLabelOverrideRepository.get_by_snapshot(self.db, snapshot_id)
            if override.rubric_id == rubric.id
        ]
        override_map = {override.answer_id: override for override in overrides}
        human_label_map = self._get_human_label_map(answer_ids, rubric)

        relevant_judges = JudgeRepository.get_for_rubric(
            self.db, rubric.id, target_id=snapshot.target_id
        )
        relevant_judge_ids = {judge.id for judge in relevant_judges}
        judge_ids_with_scores = {
            score.judge_id
            for answer in answers
            for score in answer.scores
            if score.rubric_id == rubric.id and score.judge_id in relevant_judge_ids
        }

        reliability_map = {
            judge.id: self._calculate_judge_reliability(snapshot_id, judge.id, rubric.id)
            for judge in relevant_judges
        }
        reliable_judges = [
            judge for judge in relevant_judges
            if reliability_map.get(judge.id, 0.0) >= RELIABILITY_THRESHOLD
        ]
        reliable_judge_ids = {judge.id for judge in reliable_judges}
        aligned_judges = [
            AlignedJudge(
                judge_id=judge.id,
                name=judge.name,
                f1=round(reliability_map.get(judge.id, 0.0), 3),
            )
            for judge in reliable_judges
        ]
        judge_alignment_range = self._build_alignment_range(aligned_judges)

        judge_summaries: List[JudgeScoreSummary] = []
        for judge in relevant_judges:
            has_results = judge.id in judge_ids_with_scores
            judge_accuracy: Optional[JudgeAccuracyResponse]
            if has_results:
                try:
                    judge_accuracy = self.calculate_accuracy(snapshot_id, judge.id, rubric.id)
                except ValueError:
                    judge_accuracy = JudgeAccuracyResponse(accuracy=0.0, accurate_count=0, total_answers=0)
            else:
                judge_accuracy = None

            judge_summaries.append(
                JudgeScoreSummary(
                    judge_id=judge.id,
                    name=judge.name,
                    reliability=round(reliability_map.get(judge.id, 0.0), 3) if has_results else None,
                    accuracy=judge_accuracy.accuracy if judge_accuracy else None,
                    accurate_count=judge_accuracy.accurate_count if judge_accuracy else 0,
                    total_answers=judge_accuracy.total_answers if judge_accuracy else 0,
                )
            )

        score_map: Dict[Tuple[int, int], AnswerScore] = {
            (score.answer_id, score.judge_id): score
            for answer in answers
            for score in answer.scores
            if score.rubric_id == rubric.id and score.judge_id in reliable_judge_ids
        }

        rows: List[ScoringRowResult] = []
        for answer in answers:
            override = override_map.get(answer.id)
            judge_results = [
                JudgeRowResult(
                    judge_id=judge.id,
                    name=judge.name,
                    value=score_map.get((answer.id, judge.id)).overall_label
                    if score_map.get((answer.id, judge.id))
                    else None,
                )
                for judge in reliable_judges
            ]
            raw_values = [judge_result.value for judge_result in judge_results]
            override_value = override.edited_value if override else None
            aggregate = _resolve_row_aggregate(raw_values, override_value)

            question = answer.question
            row = ScoringRowResult(
                question_id=answer.question_id,
                question_text=question.text if question else None,
                question_type=question.type.value if question and question.type else None,
                question_scope=question.scope.value if question and question.scope else None,
                answer_id=answer.id,
                answer_content=answer.answer_content,
                aggregated_result=aggregate,
                judge_results=judge_results,
            )
            human_value = human_label_map.get(answer.id)
            row.human_label = human_value
            rows.append(row)

        best_option = self._best_option_for_rubric(rubric)
        accurate_count, inaccurate_count, pending_count, edited_count, aggregate_score = self._summarize_contract_rows(
            rows,
            lambda row: row.aggregated_result.value,
            lambda value, best_option=best_option: value == best_option,
        )

        return ScoringContract(
            rubric_id=rubric.id,
            rubric_name=rubric.name,
            group=rubric.group,
            best_option=best_option,
            snapshot_id=snapshot_id,
            aggregated_score=aggregate_score,
            total_answers=len(rows),
            accurate_count=accurate_count,
            inaccurate_count=inaccurate_count,
            pending_count=pending_count,
            edited_count=edited_count,
            judge_alignment_range=judge_alignment_range,
            aligned_judges=aligned_judges,
            judge_summaries=judge_summaries,
            rows=rows,
        )

    def get_snapshot_scoring_contracts(self, snapshot_id: int) -> SnapshotScoringContractsResponse:
        snapshot = SnapshotRepository.get_by_id(self.db, snapshot_id)
        if not snapshot:
            raise ValueError(f"Snapshot {snapshot_id} not found")
        rubrics = [
            self.build_scoring_contract(snapshot_id, rubric.id)
            for rubric in TargetRubricRepository.get_by_target(self.db, snapshot.target_id)
        ]
        return SnapshotScoringContractsResponse(snapshot_id=snapshot_id, rubrics=rubrics)

    def calculate_judge_alignment(
        self, snapshot_id: int, judge_id: int, rubric_id: int
    ) -> JudgeAlignmentResponse:
        """
        Calculate judge alignment metrics by comparing judge scores with human annotations.

        Args:
            snapshot_id: Snapshot ID
            judge_id: Judge ID to evaluate
            rubric_id: Rubric ID to evaluate against.

        Returns:
            Dict with metrics: {"f1": 0.85, "precision": 0.82, "recall": 0.88, "accuracy": 0.84}

        Raises:
            ValueError: If no annotations or scores found for comparison
        """
        snapshot = SnapshotRepository.get_by_id(self.db, snapshot_id)
        if not snapshot:
            raise ValueError(f"Snapshot {snapshot_id} not found")

        rubric = TargetRubricRepository.get_by_id(self.db, rubric_id)
        if not rubric:
            raise ValueError(f"Rubric {rubric_id} not found")
        if rubric.target_id != snapshot.target_id:
            raise ValueError(f"Rubric {rubric.id} does not belong to snapshot {snapshot_id}")

        selected_answers = AnswerRepository.get_selected_for_annotation(self.db, snapshot_id)
        answer_ids = [answer.id for answer in selected_answers]
        annotation_map = self._get_human_label_map(answer_ids, rubric)
        if not annotation_map:
            raise ValueError(f"No annotations found for snapshot {snapshot_id} with is_selected_for_annotation=True")

        scores = AnswerScoreRepository.get_by_snapshot_and_judge_selected(
            self.db,
            snapshot_id,
            judge_id,
            rubric.id,
        )
        if not scores:
            raise ValueError(f"No scores found for judge {judge_id}, snapshot {snapshot_id} on selected answers")

        # Label overrides take precedence over rubric annotations for ground truth
        overrides = AnswerLabelOverrideRepository.get_by_snapshot(self.db, snapshot_id)
        override_map = {
            o.answer_id: canonicalize_rubric_option_value(rubric, o.edited_value)
            for o in overrides
            if o.rubric_id == rubric.id
        }
        for answer_id, label in override_map.items():
            if answer_id in annotation_map and label is not None:
                annotation_map[answer_id] = label

        # Create mapping of answer_id -> score label
        score_map = {
            score.answer_id: canonicalize_rubric_option_value(rubric, score.overall_label)
            for score in scores
        }

        # Build aligned lists for sklearn
        y_true = []  # Human annotations (ground truth)
        y_pred = []  # Judge predictions

        best_option = self._best_option_for_rubric(rubric)
        for answer_id in answer_ids:
            if answer_id in annotation_map and answer_id in score_map:
                score_value = score_map[answer_id]
                if score_value is None:
                    continue
                y_true.append(annotation_map[answer_id] == best_option)
                y_pred.append(score_value == best_option)

        if not y_true:
            raise ValueError(f"No overlapping annotations and scores found for snapshot {snapshot_id}, judge {judge_id}")

        # Positive outcome follows the rubric's best_option.
        f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
        precision = precision_score(y_true, y_pred, average='binary', pos_label=True, zero_division=0)
        recall = recall_score(y_true, y_pred, average='binary', pos_label=True, zero_division=0)
        accuracy = accuracy_score(y_true, y_pred)

        logger.debug(
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

    def calculate_accuracy(
        self,
        snapshot_id: int,
        judge_id: int,
        rubric_id: int,
    ) -> JudgeAccuracyResponse:
        """
        Calculate overall accuracy for a judge across all answers in a snapshot.

        Args:
            snapshot_id: Snapshot ID
            judge_id: Judge ID
            rubric_id: Rubric ID to evaluate.

        Returns:
            Dict with: {"accuracy": 0.73, "total_answers": 100, "accurate_count": 73}

        Raises:
            ValueError: If no scores found
        """
        snapshot = SnapshotRepository.get_by_id(self.db, snapshot_id)
        if not snapshot:
            raise ValueError(f"Snapshot {snapshot_id} not found")

        rubric = TargetRubricRepository.get_by_id(self.db, rubric_id)
        if not rubric:
            raise ValueError(f"Rubric {rubric_id} not found")
        if rubric.target_id != snapshot.target_id:
            raise ValueError(f"Rubric {rubric.id} does not belong to snapshot {snapshot_id}")

        scores = AnswerScoreRepository.get_by_snapshot_and_judge(
            self.db,
            snapshot_id,
            judge_id,
            rubric.id,
        )

        if not scores:
            raise ValueError(f"No scores found for judge {judge_id}, snapshot {snapshot_id}")

        total_count = len(scores)
        accurate_count = sum(
            1
            for score in scores
            if canonicalize_rubric_option_value(rubric, score.overall_label) == self._best_option_for_rubric(rubric)
        )
        accuracy = accurate_count / total_count if total_count > 0 else 0.0

        logger.debug(
            f"Accuracy for judge {judge_id}, snapshot {snapshot_id}: "
            f"{accurate_count}/{total_count} = {accuracy:.3f}"
        )

        return JudgeAccuracyResponse(
            accuracy=round(accuracy, 3),
            total_answers=total_count,
            accurate_count=accurate_count,
        )

    def get_aggregated_results(
        self, snapshot_id: int, rubric_id: int
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
            rubric_id: Rubric ID to aggregate.

        Returns:
            Tuple of (list of AggregatedResult, reliability_map dict)

        Raises:
            ValueError: If no answers found for snapshot
        """
        contract = self.build_scoring_contract(snapshot_id, rubric_id)
        reliability_map = {judge.judge_id: judge.f1 for judge in contract.aligned_judges}
        results: List[AggregatedResult] = []

        for row in contract.rows:
            metadata = [
                f"- {judge_result.name}: {judge_result.value.title() if judge_result.value else 'Pending'}"
                for judge_result in row.judge_results
            ]
            results.append(
                AggregatedResult(
                    question_id=row.question_id,
                    question_text=row.question_text,
                    question_type=row.question_type,
                    question_scope=row.question_scope,
                    rubric_id=contract.rubric_id,
                    rubric_name=contract.rubric_name,
                    group=contract.group,
                    answer_id=row.answer_id,
                    answer_content=row.answer_content,
                    aggregated_score=AggregatedScore(
                        answer_id=row.answer_id,
                        method=row.aggregated_result.method,
                        label=row.aggregated_result.value,
                        is_edited=row.aggregated_result.is_edited,
                        metadata=metadata,
                    ),
                    human_label=row.human_label,
                    human_notes=None,
                )
            )

        logger.info("Generated aggregated results for %s answers in snapshot %s", len(results), snapshot_id)
        return results, reliability_map

    def get_snapshot_results(self, snapshot_id: int) -> SnapshotResultsResponse:
        snapshot = SnapshotRepository.get_by_id(self.db, snapshot_id)
        if not snapshot:
            raise ValueError(f"Snapshot {snapshot_id} not found")

        results: List[AggregatedResult] = []
        for rubric in TargetRubricRepository.get_by_target(self.db, snapshot.target_id):
            rubric_results, _ = self.get_aggregated_results(snapshot_id, rubric.id)
            results.extend(rubric_results)
        return SnapshotResultsResponse(snapshot_id=snapshot_id, results=results)

    def calculate_snapshot_summary(self, snapshot_id: int, rubric_id: int) -> SnapshotMetric:
        """
        Calculate summary metrics for a snapshot.

        Args:
            snapshot_id: Snapshot ID

        Returns:
            Dict with summary metrics including aligned_judges list

        Raises:
            ValueError: If no answers found for snapshot
        """
        contract = self.build_scoring_contract(snapshot_id, rubric_id)
        logger.info(
            "Snapshot %s summary: Accuracy=%.3f (%s/%s), Aligned judges: %s, Edited: %s",
            snapshot_id,
            contract.aggregated_score,
            contract.accurate_count,
            contract.total_answers,
            len(contract.aligned_judges),
            contract.edited_count,
        )
        return SnapshotMetric(
            aggregated_score=contract.aggregated_score,
            total_answers=contract.total_answers,
            accurate_count=contract.accurate_count,
            inaccurate_count=contract.inaccurate_count,
            pending_count=contract.pending_count,
            edited_count=contract.edited_count,
            judge_alignment_range=contract.judge_alignment_range,
            aligned_judges=contract.aligned_judges,
        )

    def get_scoring_pending_counts(self, snapshot_id: int, rubric_id: int) -> ScoringPendingCountsResponse:
        """Return rubric-scoped pending counts for one scoring section."""
        snapshot = SnapshotRepository.get_by_id(self.db, snapshot_id)
        if not snapshot:
            raise ValueError(f"Snapshot {snapshot_id} not found")

        target_id = snapshot.target_id
        rubric = TargetRubricRepository.get_by_id(self.db, rubric_id)
        if not rubric:
            raise ValueError(f"Rubric {rubric_id} not found")
        if rubric.target_id != target_id:
            raise ValueError(f"Rubric {rubric_id} does not belong to snapshot {snapshot_id}")

        unanswered_question_count = QuestionRepository.count_approved_questions_without_answers(
            self.db,
            target_id,
            snapshot_id,
        )

        pending_counts: Dict[str, int] = {}
        for judge in JudgeRepository.get_for_rubric(self.db, rubric.id, target_id=target_id):
            pending_counts[str(judge.id)] = QuestionRepository.count_approved_questions_without_scores(
                self.db,
                target_id,
                snapshot_id,
                judge.id,
                rubric_id=rubric.id,
            )

        return ScoringPendingCountsResponse(
            unanswered_question_count=unanswered_question_count,
            rubric_id=rubric.id,
            pending_counts=pending_counts,
        )

    def calculate_confusion_matrix(
        self,
        target_id: int,
        rubric_id: int,
        snapshot_id: Optional[int] = None,
    ) -> ConfusionMatrixResponse:
        """
        Calculate confusion matrix for question types/scopes vs inaccurate responses.

        Args:
            target_id: Target ID
            rubric_id: Rubric ID to evaluate
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

        rubric = TargetRubricRepository.get_by_id(self.db, rubric_id)
        if not rubric:
            raise ValueError(f"Rubric {rubric_id} not found")
        if rubric.target_id != target_id:
            raise ValueError(f"Rubric {rubric_id} does not belong to target {target_id}")

        # Get aggregated results for the snapshot
        try:
            aggregated_results, _ = self.get_aggregated_results(snapshot_id, rubric_id)
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
            agg = result.aggregated_score
            # Include overridden inaccurate answers
            if (
                agg.label is not None
                and agg.label != self._best_option_for_rubric(rubric)
                and agg.method in ("majority", "override")
            ):
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
        return self.calculate_judge_alignment(snapshot_id, judge_id, rubric_id)

    def calculate_rubric_judge_accuracy(
        self, snapshot_id: int, judge_id: int, rubric_id: int, best_option: str
    ) -> JudgeAccuracyResponse:
        """
        Calculate what % of answers this judge gave the best option for a rubric.
        best_option is treated as "accurate" (positive label).
        """
        return self.calculate_accuracy(snapshot_id, judge_id, rubric_id)

    def calculate_snapshot_metrics(
        self, target_id: int, snapshot_id: Optional[int] = None
    ) -> SnapshotMetricsResponse:
        snapshots = (
            [SnapshotRepository.get_by_id(self.db, snapshot_id)]
            if snapshot_id is not None
            else SnapshotRepository.get_by_target(self.db, target_id)
        )
        if snapshot_id is not None and snapshots[0] is None:
            raise ValueError(f"Snapshot {snapshot_id} not found")

        grouped_metrics: Dict[int, MetricsByRubric] = {}
        for snapshot in snapshots:
            if snapshot is None:
                continue
            try:
                contracts = self.get_snapshot_scoring_contracts(snapshot.id).rubrics
            except ValueError:
                continue

            for contract in contracts:
                metric = SnapshotMetric(
                    snapshot_id=snapshot.id,
                    snapshot_name=snapshot.name,
                    created_at=snapshot.created_at.isoformat(),
                    rubric_id=contract.rubric_id,
                    rubric_name=contract.rubric_name,
                    aggregated_score=contract.aggregated_score,
                    total_answers=contract.total_answers,
                    accurate_count=contract.accurate_count,
                    inaccurate_count=contract.inaccurate_count,
                    pending_count=contract.pending_count,
                    edited_count=contract.edited_count,
                    aligned_judges=contract.aligned_judges,
                    judge_alignment_range=contract.judge_alignment_range,
                )
                group = grouped_metrics.setdefault(
                    contract.rubric_id,
                    MetricsByRubric(
                        rubric_id=contract.rubric_id,
                        rubric_name=contract.rubric_name,
                        group=contract.group,
                        snapshots=[],
                    ),
                )
                group.snapshots.append(metric)
        return SnapshotMetricsResponse(target_id=target_id, rubrics=list(grouped_metrics.values()))


def calculate_judge_alignment(
    db: Session, snapshot_id: int, judge_id: int, rubric_id: int
) -> JudgeAlignmentResponse:
    """Calculate judge alignment metrics (convenience function)."""
    service = MetricsService(db)
    return service.calculate_judge_alignment(snapshot_id, judge_id, rubric_id)


def calculate_accuracy(
    db: Session, snapshot_id: int, judge_id: int, rubric_id: int
) -> JudgeAccuracyResponse:
    """Calculate overall accuracy for a judge (convenience function)."""
    service = MetricsService(db)
    return service.calculate_accuracy(snapshot_id, judge_id, rubric_id)


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
