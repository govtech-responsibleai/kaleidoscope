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
from src.common.database.models import Annotation, AnswerScore, Answer, RubricAnnotation
from src.common.services.system_rubrics import (
    FIXED_ACCURACY_NAME,
    RUBRIC_GROUP_FIXED,
    accuracy_label_from_bool,
    best_option_for_rubric,
    canonicalize_rubric_option_value,
    ensure_fixed_accuracy_rubric,
)
from src.common.models.metrics import (
    AggregatedAnswerScore,
    AggregatedResult,
    AggregationMethod,
    AlignedJudge,
    JudgeAlignmentResponse,
    JudgeAccuracyResponse,
    TargetSnapshotMetric,
    ConfusionMatrixResponse,
    ScoringPendingCountsResponse,
    MetricAggregatedResult,
    MetricJudgeRowResult,
    MetricJudgeScoreSummary,
    MetricRowResult,
    MetricScoringContract,
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
    *,
    require_reliable_baseline: bool = False,
) -> MetricAggregatedResult:
    """Shared state machine for accuracy and rubric row aggregation.

    raw_values: per-judge string values (None means score missing/pending).
    require_reliable_baseline: when True, override is only applied when the
        majority baseline exists (rubric behaviour); when False, any override
        is accepted (accuracy behaviour).
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

    if require_reliable_baseline:
        is_edited = bool(
            baseline_method == "majority"
            and baseline_value is not None
            and override_value is not None
            and override_value != baseline_value
        )
    else:
        is_edited = bool(override_value is not None and override_value != baseline_value)

    if is_edited:
        return MetricAggregatedResult(
            method="override",
            value=override_value,
            baseline_value=baseline_value,
            is_edited=True,
        )
    return MetricAggregatedResult(
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
        rows: List[MetricRowResult],
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

    def _get_accuracy_human_label_map(
        self,
        answer_ids: List[int],
        accuracy_rubric,
    ) -> Dict[int, str]:
        if not answer_ids:
            return {}

        annotations = (
            self.db.query(RubricAnnotation.answer_id, RubricAnnotation.option_value)
            .filter(
                RubricAnnotation.answer_id.in_(answer_ids),
                RubricAnnotation.rubric_id == accuracy_rubric.id,
            )
            .all()
        )
        annotation_map = {
            answer_id: canonical
            for answer_id, option_value in annotations
            if (canonical := canonicalize_rubric_option_value(accuracy_rubric, option_value)) is not None
        }
        if annotation_map:
            return annotation_map
        return {
            answer_id: accuracy_label_from_bool(label, accuracy_rubric)
            for answer_id, label in (
                self.db.query(Annotation.answer_id, Annotation.label)
                .filter(Annotation.answer_id.in_(answer_ids))
                .all()
            )
        }

    def get_accuracy_scoring_contract(self, snapshot_id: int) -> MetricScoringContract:
        answers = AnswerRepository.get_with_scores_and_annotation(self.db, snapshot_id)
        answers = sorted(answers, key=lambda answer: answer.id)
        if not answers:
            raise ValueError(f"No answers found for snapshot {snapshot_id}")

        snapshot = SnapshotRepository.get_by_id(self.db, snapshot_id)
        if not snapshot:
            raise ValueError(f"Snapshot {snapshot_id} not found")
        accuracy_rubric = ensure_fixed_accuracy_rubric(self.db, snapshot.target_id)

        overrides = [
            override
            for override in AnswerLabelOverrideRepository.get_by_snapshot(self.db, snapshot_id)
            if override.rubric_id == accuracy_rubric.id
        ]
        override_map = {override.answer_id: override for override in overrides}
        human_label_map = self._get_accuracy_human_label_map(
            [answer.id for answer in answers],
            accuracy_rubric,
        )
        reliability_map, judge_name_map = self._get_accuracy_reliability_map(snapshot_id, answers)

        relevant_judges = JudgeRepository.get_for_rubric(
            self.db, accuracy_rubric.id, target_id=snapshot.target_id
        )
        judge_ids_with_scores = {
            score.judge_id
            for answer in answers
            for score in answer.scores
            if score.judge_id in {judge.id for judge in relevant_judges}
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

        judge_summaries: List[MetricJudgeScoreSummary] = []
        for judge in relevant_judges:
            has_results = judge.id in judge_ids_with_scores
            accuracy: Optional[JudgeAccuracyResponse]
            if has_results:
                try:
                    accuracy = self.calculate_accuracy(snapshot_id, judge.id)
                except ValueError:
                    accuracy = JudgeAccuracyResponse(accuracy=0.0, accurate_count=0, total_answers=0)
            else:
                accuracy = None
            judge_summaries.append(
                MetricJudgeScoreSummary(
                    judge_id=judge.id,
                    name=judge.name,
                    reliability=round(reliability_map.get(judge.id, 0.0), 3) if has_results else None,
                    accuracy=accuracy.accuracy if accuracy else None,
                    accurate_count=accuracy.accurate_count if accuracy else 0,
                    total_answers=accuracy.total_answers if accuracy else 0,
                )
            )

        rows: List[MetricRowResult] = []
        for answer in answers:
            override = override_map.get(answer.id)
            score_map = {
                score.judge_id: score
                for score in answer.scores
                if score.judge_id in reliable_judge_ids and score.rubric_id == accuracy_rubric.id
            }
            judge_results = [
                MetricJudgeRowResult(
                    judge_id=judge.id,
                    name=judge.name,
                    value=score_map.get(judge.id).overall_label if score_map.get(judge.id) else None,
                )
                for judge in reliable_judges
            ]

            metadata = [
                f"- {judge_result.name}: {judge_result.value.title() if judge_result.value else 'Pending'}"
                for judge_result in judge_results
            ]
            raw_values = [jr.value for jr in judge_results]
            override_value = override.edited_value if override else None
            aggregate = _resolve_row_aggregate(raw_values, override_value)

            question = answer.question
            rows.append(
                MetricRowResult(
                    question_id=answer.question_id,
                    question_text=question.text if question else None,
                    question_type=question.type.value if question and question.type else None,
                    question_scope=question.scope.value if question and question.scope else None,
                    answer_id=answer.id,
                    answer_content=answer.answer_content,
                    aggregated_result=aggregate,
                    human_label=human_label_map.get(answer.id),
                    judge_results=judge_results,
                )
            )

        accurate_count, inaccurate_count, pending_count, edited_count, aggregate_score = self._summarize_contract_rows(
            rows,
            lambda row: row.aggregated_result.value,
            lambda value, best_option=accuracy_rubric.best_option: value == best_option,
        )

        return MetricScoringContract(
            rubric_id=accuracy_rubric.id,
            rubric_name=accuracy_rubric.name,
            group=accuracy_rubric.group,
            target_label=accuracy_rubric.best_option,
            snapshot_id=snapshot_id,
            aggregated_accuracy=aggregate_score,
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

    def get_rubric_scoring_contracts(self, target_id: int, snapshot_id: int) -> List[MetricScoringContract]:
        snapshot = SnapshotRepository.get_by_id(self.db, snapshot_id)
        if not snapshot:
            raise ValueError(f"Snapshot {snapshot_id} not found")

        answers = AnswerRepository.get_by_snapshot(self.db, snapshot_id, eager_load=True)
        if not answers:
            return []

        answer_ids = [answer.id for answer in answers]
        human_annotations = (
            self.db.query(RubricAnnotation)
            .filter(RubricAnnotation.answer_id.in_(answer_ids))
            .all()
            if answer_ids else []
        )
        human_annotation_map: Dict[Tuple[int, int], str] = {
            (annotation.answer_id, annotation.rubric_id): annotation.option_value
            for annotation in human_annotations
        }
        overrides = AnswerLabelOverrideRepository.get_by_snapshot(self.db, snapshot_id)

        contracts: List[MetricScoringContract] = []
        rubrics = TargetRubricRepository.get_by_target(self.db, target_id)
        for rubric in rubrics:
            if rubric.group == RUBRIC_GROUP_FIXED and rubric.name == FIXED_ACCURACY_NAME:
                continue
            override_map: Dict[Tuple[int, int], str] = {
                (override.answer_id, rubric.id): override.edited_value
                for override in overrides
                if override.rubric_id == rubric.id
            }
            best_option = self._best_option_for_rubric(rubric)
            relevant_judges = JudgeRepository.get_for_rubric(
                self.db, rubric.id, target_id=target_id
            )
            relevant_judge_ids = {judge.id for judge in relevant_judges}
            rubric_score_rows = (
                self.db.query(AnswerScore.answer_id, AnswerScore.judge_id, AnswerScore.overall_label)
                .join(Answer, AnswerScore.answer_id == Answer.id)
                .filter(
                    Answer.snapshot_id == snapshot_id,
                    AnswerScore.rubric_id == rubric.id,
                    AnswerScore.judge_id.in_(relevant_judge_ids),
                )
                .all()
                if relevant_judge_ids else []
            )
            judge_ids_with_scores = {score.judge_id for score in rubric_score_rows}

            reliability_map: Dict[int, float] = {}
            for judge in relevant_judges:
                try:
                    alignment = self.calculate_rubric_judge_alignment(snapshot_id, judge.id, rubric.id, best_option)
                    reliability_map[judge.id] = alignment.f1
                except ValueError:
                    reliability_map[judge.id] = 0.0

            reliable_judges = [
                judge for judge in relevant_judges
                if reliability_map.get(judge.id, 0.0) >= RELIABILITY_THRESHOLD
            ]
            aligned_judges = [
                AlignedJudge(
                    judge_id=judge.id,
                    name=judge.name,
                    f1=round(reliability_map.get(judge.id, 0.0), 3),
                )
                for judge in reliable_judges
            ]
            judge_alignment_range = self._build_alignment_range(aligned_judges)

            judge_summaries: List[MetricJudgeScoreSummary] = []
            for judge in relevant_judges:
                has_results = judge.id in judge_ids_with_scores
                accuracy: Optional[JudgeAccuracyResponse]
                if has_results:
                    try:
                        accuracy = self.calculate_rubric_judge_accuracy(snapshot_id, judge.id, rubric.id, best_option)
                    except ValueError:
                        accuracy = JudgeAccuracyResponse(accuracy=0.0, accurate_count=0, total_answers=0)
                else:
                    accuracy = None
                judge_summaries.append(
                    MetricJudgeScoreSummary(
                        judge_id=judge.id,
                        name=judge.name,
                        reliability=round(reliability_map.get(judge.id, 0.0), 3) if has_results else None,
                        accuracy=accuracy.accuracy if accuracy else None,
                        accurate_count=accuracy.accurate_count if accuracy else 0,
                        total_answers=accuracy.total_answers if accuracy else 0,
                    )
                )

            reliable_judge_ids = {judge.id for judge in reliable_judges}
            rubric_scores = []
            if reliable_judge_ids:
                rubric_scores = (
                    self.db.query(AnswerScore)
                    .join(Answer, AnswerScore.answer_id == Answer.id)
                    .filter(
                        Answer.snapshot_id == snapshot_id,
                        AnswerScore.rubric_id == rubric.id,
                        AnswerScore.judge_id.in_(reliable_judge_ids),
                    )
                    .all()
                )
            score_map: Dict[Tuple[int, int], AnswerScore] = {
                (score.answer_id, score.judge_id): score for score in rubric_scores
            }

            rows: List[MetricRowResult] = []
            for answer in answers:
                human_option = human_annotation_map.get((answer.id, rubric.id))
                override_option = override_map.get((answer.id, rubric.id))
                judge_results = [
                    MetricJudgeRowResult(
                        judge_id=judge.id,
                        name=judge.name,
                        value=score_map.get((answer.id, judge.id)).overall_label if score_map.get((answer.id, judge.id)) else None,
                    )
                    for judge in reliable_judges
                ]
                raw_values = [jr.value for jr in judge_results]
                aggregate = _resolve_row_aggregate(raw_values, override_option, require_reliable_baseline=True)

                question = answer.question
                rows.append(
                    MetricRowResult(
                        question_id=answer.question_id,
                        question_text=question.text if question else None,
                        question_type=question.type.value if question and question.type else None,
                        question_scope=question.scope.value if question and question.scope else None,
                        answer_id=answer.id,
                        answer_content=answer.answer_content,
                        aggregated_result=aggregate,
                        human_option=human_option,
                        judge_results=judge_results,
                    )
                )

            accurate_count, inaccurate_count, pending_count, edited_count, aggregate_score = self._summarize_contract_rows(
                rows,
                lambda row: row.aggregated_result.value,
                lambda value, best_option=best_option: value == best_option,
            )

            contracts.append(
                MetricScoringContract(
                    rubric_id=rubric.id,
                    rubric_name=rubric.name,
                    group=rubric.group,
                    target_label=best_option,
                    snapshot_id=snapshot_id,
                    aggregated_accuracy=aggregate_score,
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
            )

        return contracts

    def get_snapshot_scoring_contracts(self, snapshot_id: int) -> SnapshotScoringContractsResponse:
        snapshot = SnapshotRepository.get_by_id(self.db, snapshot_id)
        if not snapshot:
            raise ValueError(f"Snapshot {snapshot_id} not found")
        metrics = [self.get_accuracy_scoring_contract(snapshot_id)]
        metrics.extend(self.get_rubric_scoring_contracts(snapshot.target_id, snapshot_id))
        return SnapshotScoringContractsResponse(snapshot_id=snapshot_id, metrics=metrics)

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
        snapshot = SnapshotRepository.get_by_id(self.db, snapshot_id)
        if not snapshot:
            raise ValueError(f"Snapshot {snapshot_id} not found")
        accuracy_rubric = ensure_fixed_accuracy_rubric(self.db, snapshot.target_id)
        selected_answers = AnswerRepository.get_selected_for_annotation(self.db, snapshot_id)
        answer_ids = [answer.id for answer in selected_answers]
        annotation_map = self._get_accuracy_human_label_map(answer_ids, accuracy_rubric)
        if not annotation_map:
            raise ValueError(f"No annotations found for snapshot {snapshot_id} with is_selected_for_annotation=True")

        scores = AnswerScoreRepository.get_by_snapshot_and_judge_selected(self.db, snapshot_id, judge_id, accuracy_rubric.id)
        if not scores:
            raise ValueError(f"No scores found for judge {judge_id}, snapshot {snapshot_id} on selected answers")

        # Label overrides take precedence over rubric annotations for ground truth
        overrides = AnswerLabelOverrideRepository.get_by_snapshot(self.db, snapshot_id)
        override_map = {
            o.answer_id: canonicalize_rubric_option_value(accuracy_rubric, o.edited_value)
            for o in overrides
            if o.rubric_id == accuracy_rubric.id
        }
        for answer_id, label in override_map.items():
            if answer_id in annotation_map and label is not None:
                annotation_map[answer_id] = label

        # Create mapping of answer_id -> score label
        score_map = {
            score.answer_id: canonicalize_rubric_option_value(accuracy_rubric, score.overall_label)
            for score in scores
        }

        # Build aligned lists for sklearn
        y_true = []  # Human annotations (ground truth)
        y_pred = []  # Judge predictions

        best_option = accuracy_rubric.best_option
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
        snapshot = SnapshotRepository.get_by_id(self.db, snapshot_id)
        if not snapshot:
            raise ValueError(f"Snapshot {snapshot_id} not found")
        accuracy_rubric = ensure_fixed_accuracy_rubric(self.db, snapshot.target_id)
        scores = AnswerScoreRepository.get_by_snapshot_and_judge(self.db, snapshot_id, judge_id, accuracy_rubric.id)

        if not scores:
            raise ValueError(f"No scores found for judge {judge_id}, snapshot {snapshot_id}")

        total_count = len(scores)
        accurate_count = sum(
            1
            for score in scores
            if canonicalize_rubric_option_value(accuracy_rubric, score.overall_label) == accuracy_rubric.best_option
        )
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
        contract = self.get_accuracy_scoring_contract(snapshot_id)
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
                    answer_id=row.answer_id,
                    answer_content=row.answer_content,
                    aggregated_accuracy=AggregatedAnswerScore(
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
        contract = self.get_accuracy_scoring_contract(snapshot_id)
        logger.info(
            "Snapshot %s summary: Accuracy=%.3f (%s/%s), Aligned judges: %s, Edited: %s",
            snapshot_id,
            contract.aggregated_accuracy,
            contract.accurate_count,
            contract.total_answers,
            len(contract.aligned_judges),
            contract.edited_count,
        )
        return TargetSnapshotMetric(
            aggregated_accuracy=contract.aggregated_accuracy,
            total_answers=contract.total_answers,
            accurate_count=contract.accurate_count,
            inaccurate_count=contract.inaccurate_count,
            pending_count=contract.pending_count,
            edited_count=contract.edited_count,
            judge_alignment_range=contract.judge_alignment_range,
            aligned_judges=contract.aligned_judges,
        )

    def get_scoring_pending_counts(self, snapshot_id: int) -> ScoringPendingCountsResponse:
        """Return snapshot-scoped pending counts for the scoring page."""
        snapshot = SnapshotRepository.get_by_id(self.db, snapshot_id)
        if not snapshot:
            raise ValueError(f"Snapshot {snapshot_id} not found")

        target_id = snapshot.target_id
        unanswered_question_count = QuestionRepository.count_approved_questions_without_answers(
            self.db,
            target_id,
            snapshot_id,
        )

        accuracy_pending_counts: Dict[str, int] = {}
        rubric_pending_counts: Dict[str, int] = {}

        accuracy_rubric = ensure_fixed_accuracy_rubric(self.db, target_id)
        for judge in JudgeRepository.get_for_rubric(
            self.db, accuracy_rubric.id, target_id=target_id
        ):
            accuracy_pending_counts[str(judge.id)] = (
                QuestionRepository.count_approved_questions_without_scores(
                    self.db,
                    target_id,
                    snapshot_id,
                    judge.id,
                )
            )

        for rubric in TargetRubricRepository.get_by_target(self.db, target_id):
            if rubric.group == RUBRIC_GROUP_FIXED and rubric.name == FIXED_ACCURACY_NAME:
                continue
            for judge in JudgeRepository.get_for_rubric(self.db, rubric.id, target_id=target_id):
                rubric_pending_counts[f"{judge.id}:{rubric.id}"] = (
                    QuestionRepository.count_approved_questions_without_scores(
                        self.db,
                        target_id,
                        snapshot_id,
                        judge.id,
                        rubric_id=rubric.id,
                    )
                )

        return ScoringPendingCountsResponse(
            unanswered_question_count=unanswered_question_count,
            accuracy_pending_counts=accuracy_pending_counts,
            rubric_pending_counts=rubric_pending_counts,
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
        accuracy_rubric = ensure_fixed_accuracy_rubric(self.db, target_id)

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
            if (
                agg.label is not None
                and agg.label != accuracy_rubric.best_option
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
        human_labels = (
            self.db.query(RubricAnnotation)
            .join(Answer, RubricAnnotation.answer_id == Answer.id)
            .filter(
                Answer.snapshot_id == snapshot_id,
                Answer.is_selected_for_annotation == True,
                RubricAnnotation.rubric_id == rubric_id,
            )
            .all()
        )
        judge_scores = AnswerScoreRepository.get_by_snapshot_and_judge_selected(
            self.db, snapshot_id, judge_id, rubric_id
        )

        if not human_labels or not judge_scores:
            raise ValueError(f"No data for rubric alignment: judge {judge_id}, rubric {rubric_id}, snapshot {snapshot_id}")

        human_map = {label.answer_id: label.option_value for label in human_labels}
        judge_map = {score.answer_id: score.overall_label for score in judge_scores}

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
        scores = AnswerScoreRepository.get_by_snapshot_and_judge(
            self.db, snapshot_id, judge_id, rubric_id
        )

        if not scores:
            raise ValueError(f"No rubric scores for judge {judge_id}, rubric {rubric_id}, snapshot {snapshot_id}")

        total = len(scores)
        accurate_count = sum(1 for s in scores if s.overall_label == best_option)
        accuracy = accurate_count / total if total > 0 else 0.0

        return JudgeAccuracyResponse(
            accuracy=round(accuracy, 3),
            total_answers=total,
            accurate_count=accurate_count,
        )

    def calculate_rubric_snapshot_metrics(
        self, target_id: int, snapshot_id: int
    ) -> List[TargetSnapshotMetric]:
        contracts = self.get_rubric_scoring_contracts(target_id, snapshot_id)
        return [
            TargetSnapshotMetric(
                snapshot_id=snapshot_id,
                rubric_id=contract.rubric_id,
                rubric_name=contract.rubric_name,
                aggregated_accuracy=contract.aggregated_accuracy,
                total_answers=contract.total_answers,
                accurate_count=contract.accurate_count,
                inaccurate_count=contract.inaccurate_count,
                pending_count=contract.pending_count,
                edited_count=contract.edited_count,
                aligned_judges=contract.aligned_judges,
                judge_alignment_range=contract.judge_alignment_range,
            )
            for contract in contracts
        ]


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
