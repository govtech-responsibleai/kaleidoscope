"""
Service for calculating judge alignment and accuracy metrics.
"""

import csv
import io
import logging
from typing import Dict, Iterable, List, Optional, Tuple
from collections import Counter
from sqlalchemy.orm import Session
from sklearn.metrics import f1_score, precision_score, recall_score, accuracy_score

from src.common.config import get_settings
from src.common.database.repositories.answer_score_repo import AnswerScoreRepository
from src.common.database.repositories.answer_repo import AnswerRepository
from src.common.database.repositories.annotation_repo import AnnotationRepository
from src.common.database.repositories.judge_repo import JudgeRepository
from src.common.database.repositories.answer_label_override_repo import AnswerLabelOverrideRepository
from src.common.database.repositories.question_repo import QuestionRepository
from src.common.database.repositories.snapshot_repo import SnapshotRepository
from src.common.database.repositories.target_rubric_repo import TargetRubricRepository
from src.common.database.models import AnswerScore, Answer, Annotation
from src.common.models.judge import JudgeResponse
from src.common.models.target_rubric import TargetRubricResponse
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
    JudgeReliabilityStatus,
    JudgeRowResult,
    JudgeScoreSummary,
    ScoringContract,
    ScoringRowResult,
    SnapshotMetric,
    VerdictStatus,
    MetricsByRubric,
    SnapshotMetricsResponse,
    ConfusionMatrixResponse,
    ScoringStatusResponse,
    ScoringPendingCountsResponse,
    ScoringRubricResponse,
    ScoringRubricsResponse,
    ScoringResultsFilters,
    ScoringResultsResponse,
    ScoringPersonaOption,
)

logger = logging.getLogger(__name__)


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
    ) -> Optional[JudgeAlignmentResponse]:
        """Alignment of one judge against human labels, or None when nothing can be compared.

        A missing result means "not calibrated"; it is deliberately distinct from
        a judge that was compared and scored 0.0.
        """
        try:
            return self.calculate_judge_alignment(snapshot_id, judge_id, rubric_id)
        except ValueError:
            return None
        except Exception:
            logger.exception(
                "Failed to calculate reliability for judge %s on rubric %s",
                judge_id,
                rubric_id,
            )
            return None

    def _reliability_status(self, alignment: Optional[JudgeAlignmentResponse]) -> JudgeReliabilityStatus:
        """Classify an alignment result against the configured gate."""
        settings = get_settings()
        if alignment is None or alignment.sample_count == 0:
            return "not_calibrated"
        if alignment.sample_count < settings.min_calibration_samples:
            return "insufficient_calibration"
        if alignment.f1 >= settings.reliability_threshold:
            return "aligned"
        return "unreliable"

    def _verdict_status(
        self,
        judge_statuses: Iterable[Optional[JudgeReliabilityStatus]],
        calibration_count: int,
    ) -> VerdictStatus:
        """Why an aggregate is or is not available for a rubric.

        Decision order:
        1. Any judge status is "aligned" -> "ready".
        2. `calibration_count == 0` -> "not_calibrated" (no human labels yet).
        3. `calibration_count` is below the configured floor -> "insufficient_calibration"
           (not enough labels exist yet, independent of judge state).
        4. Any judge status is "unreliable" -> "no_aligned_judge" (a judge was measured
           on enough labels and failed).
        5. Any judge status is "insufficient_calibration" or "not_calibrated", or `None`
           (a configured judge that has not produced results) -> "insufficient_calibration"
           (labels exist but no judge has scored enough of them yet).
        6. Otherwise (no judges configured) -> "no_aligned_judge".
        """
        statuses = list(judge_statuses)
        if any(status == "aligned" for status in statuses):
            return "ready"
        if calibration_count == 0:
            return "not_calibrated"
        if calibration_count < get_settings().min_calibration_samples:
            return "insufficient_calibration"
        if any(status == "unreliable" for status in statuses):
            return "no_aligned_judge"
        if any(status in ("insufficient_calibration", "not_calibrated", None) for status in statuses):
            return "insufficient_calibration"
        return "no_aligned_judge"

    def _require_snapshot_and_rubric(self, snapshot_id: int, rubric_id: int):
        """Validate a snapshot/rubric pair and return both rows."""
        snapshot = SnapshotRepository.get_by_id(self.db, snapshot_id)
        if not snapshot:
            raise ValueError(f"Snapshot {snapshot_id} not found")

        rubric = TargetRubricRepository.get_by_id(self.db, rubric_id)
        if not rubric:
            raise ValueError(f"Rubric {rubric_id} not found")
        if rubric.target_id != snapshot.target_id:
            raise ValueError(f"Rubric {rubric_id} does not belong to snapshot {snapshot_id}")

        return snapshot, rubric

    def _get_snapshot_answers(self, snapshot_id: int) -> List[Answer]:
        """Load answers for one snapshot with the relationships needed for scoring."""
        answers = AnswerRepository.get_with_scores_and_annotation(self.db, snapshot_id)
        return sorted(answers, key=lambda answer: answer.id)

    def _build_judge_summaries(
        self,
        snapshot_id: int,
        rubric,
        answers: List[Answer],
        relevant_judges,
    ) -> Tuple[List[JudgeScoreSummary], List[AlignedJudge], List]:
        """Return all-judge summaries plus the aligned judges currently visible in rows."""
        relevant_judge_ids = {judge.id for judge in relevant_judges}
        judge_ids_with_scores = {
            score.judge_id
            for answer in answers
            for score in answer.scores
            if score.rubric_id == rubric.id and score.judge_id in relevant_judge_ids
        }

        alignment_map = {
            judge.id: self._calculate_judge_reliability(snapshot_id, judge.id, rubric.id)
            for judge in relevant_judges
        }
        status_map = {judge_id: self._reliability_status(a) for judge_id, a in alignment_map.items()}
        aligned_judge_rows = [judge for judge in relevant_judges if status_map[judge.id] == "aligned"]
        aligned_judges = [
            AlignedJudge(
                judge_id=judge.id,
                name=judge.name,
                f1=round(alignment_map[judge.id].f1, 3),
                sample_count=alignment_map[judge.id].sample_count,
            )
            for judge in aligned_judge_rows
        ]

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
                    reliability=round(alignment_map[judge.id].f1, 3) if has_results and alignment_map[judge.id] else None,
                    sample_count=alignment_map[judge.id].sample_count if alignment_map[judge.id] else 0,
                    reliability_status=status_map[judge.id] if has_results else None,
                    accuracy=judge_accuracy.accuracy if judge_accuracy else None,
                    accurate_count=judge_accuracy.accurate_count if judge_accuracy else 0,
                    total_answers=judge_accuracy.total_answers if judge_accuracy else 0,
                )
            )

        return judge_summaries, aligned_judges, aligned_judge_rows

    def _build_visible_score_map(
        self,
        answers: List[Answer],
        rubric_id: int,
        visible_judge_ids: set[int],
    ) -> Dict[Tuple[int, int], AnswerScore]:
        """Map visible rubric scores by (answer_id, judge_id)."""
        return {
            (score.answer_id, score.judge_id): score
            for answer in answers
            for score in answer.scores
            if score.rubric_id == rubric_id and score.judge_id in visible_judge_ids
        }

    def _serialize_scoring_row(
        self,
        answer: Answer,
        visible_judges,
        score_map: Dict[Tuple[int, int], AnswerScore],
        override_value: Optional[str],
        human_label: Optional[str],
    ) -> ScoringRowResult:
        """Serialize one scoring table row with inline question and persona metadata."""
        judge_results = [
            JudgeRowResult(
                judge_id=judge.id,
                name=judge.name,
                value=score_map.get((answer.id, judge.id)).overall_label
                if score_map.get((answer.id, judge.id))
                else None,
            )
            for judge in visible_judges
        ]
        raw_values = [judge_result.value for judge_result in judge_results]
        aggregate = _resolve_row_aggregate(raw_values, override_value)

        question = answer.question
        persona = question.persona if question else None
        row = ScoringRowResult(
            question_id=answer.question_id,
            question_text=question.text if question else None,
            question_type=question.type.value if question and question.type else None,
            question_scope=question.scope.value if question and question.scope else None,
            persona_id=question.persona_id if question else None,
            persona_title=persona.title if persona else None,
            answer_id=answer.id,
            answer_content=answer.answer_content,
            aggregated_result=aggregate,
            human_label=human_label,
            judge_results=judge_results,
        )
        return row

    def _build_base_scoring_contract(
        self,
        snapshot_id: int,
        rubric_id: int,
    ) -> ScoringContract:
        """Build one rubric's scoring contract without going through the all-rubric endpoint."""
        snapshot, rubric = self._require_snapshot_and_rubric(snapshot_id, rubric_id)
        answers = self._get_snapshot_answers(snapshot_id)

        answer_ids = [answer.id for answer in answers]
        overrides = [
            override
            for override in AnswerLabelOverrideRepository.get_by_snapshot(self.db, snapshot_id)
            if override.rubric_id == rubric.id
        ]
        override_map = {override.answer_id: override for override in overrides}
        human_label_map = self._get_human_label_map(answer_ids, rubric)
        selected_ids = [answer.id for answer in answers if answer.is_selected_for_annotation]
        calibration_count = len(self._get_human_label_map(selected_ids, rubric))

        relevant_judges = JudgeRepository.get_for_rubric(
            self.db, rubric.id, target_id=snapshot.target_id
        )
        judge_summaries, aligned_judges, visible_judges = self._build_judge_summaries(
            snapshot_id,
            rubric,
            answers,
            relevant_judges,
        )
        visible_judge_ids = {judge.id for judge in visible_judges}
        score_map = self._build_visible_score_map(answers, rubric.id, visible_judge_ids)

        rows = [
            self._serialize_scoring_row(
                answer=answer,
                visible_judges=visible_judges,
                score_map=score_map,
                override_value=override_map.get(answer.id).edited_value if override_map.get(answer.id) else None,
                human_label=human_label_map.get(answer.id),
            )
            for answer in answers
        ]

        best_option = self._best_option_for_rubric(rubric)
        accurate_count, inaccurate_count, pending_count, edited_count, aggregate_score = self._summarize_contract_rows(
            rows,
            lambda row: row.aggregated_result.value,
            lambda value, best_option=best_option: value == best_option,
        )

        settings = get_settings()
        verdict_status = self._verdict_status(
            [summary.reliability_status for summary in judge_summaries],
            calibration_count,
        )
        return ScoringContract(
            rubric_id=rubric.id,
            rubric_name=rubric.name,
            group=rubric.group,
            best_option=best_option,
            snapshot_id=snapshot_id,
            aggregated_score=aggregate_score if verdict_status == "ready" else None,
            verdict_status=verdict_status,
            calibration_count=calibration_count,
            reliability_threshold=settings.reliability_threshold,
            min_calibration_samples=settings.min_calibration_samples,
            recommended_calibration_samples=settings.recommended_calibration_samples,
            total_answers=len(rows),
            accurate_count=accurate_count,
            inaccurate_count=inaccurate_count,
            pending_count=pending_count,
            edited_count=edited_count,
            judge_alignment_range=self._build_alignment_range(aligned_judges),
            aligned_judges=aligned_judges,
            judge_summaries=judge_summaries,
            rows=rows,
        )

    def _rows_match_disagreement(
        self,
        row: ScoringRowResult,
        selected_judge_ids: set[int],
    ) -> bool:
        """Return true when the selected visible judges disagree on a row."""
        selected_values = [
            judge_result.value
            for judge_result in row.judge_results
            if judge_result.judge_id in selected_judge_ids and judge_result.value
        ]
        return len(set(selected_values)) > 1

    def _apply_results_filters(
        self,
        rows: List[ScoringRowResult],
        filters: ScoringResultsFilters,
    ) -> Tuple[List[ScoringRowResult], List[ScoringPersonaOption]]:
        """Apply backend-owned scoring filters and return filtered rows plus persona options."""
        filtered = rows

        if filters.labels:
            filtered = [
                row for row in filtered
                if row.aggregated_result.value is not None and row.aggregated_result.value in filters.labels
            ]

        if filters.question_types:
            allowed_types = set(filters.question_types)
            filtered = [row for row in filtered if row.question_type is None or row.question_type in allowed_types]

        if filters.question_scopes:
            allowed_scopes = set(filters.question_scopes)
            filtered = [row for row in filtered if row.question_scope is None or row.question_scope in allowed_scopes]

        disagreement_base = filtered
        if filters.disagreements_only:
            selected_judge_ids = set(filters.judge_ids)
            disagreement_base = [
                row for row in disagreement_base
                if self._rows_match_disagreement(row, selected_judge_ids)
            ]

        persona_options = [
            ScoringPersonaOption(id=persona_id, title=title)
            for persona_id, title in sorted(
                {
                    (row.persona_id, row.persona_title)
                    for row in disagreement_base
                    if row.persona_id is not None and row.persona_title
                },
                key=lambda item: item[1].lower(),
            )
        ]

        if filters.persona_ids:
            allowed_persona_ids = set(filters.persona_ids)
            disagreement_base = [
                row for row in disagreement_base
                if row.persona_id is None or row.persona_id in allowed_persona_ids
            ]

        return disagreement_base, persona_options

    def get_scoring_status(self, snapshot_id: int) -> ScoringStatusResponse:
        """Return snapshot-scoped gating data for the scoring page."""
        snapshot = SnapshotRepository.get_by_id(self.db, snapshot_id)
        if not snapshot:
            raise ValueError(f"Snapshot {snapshot_id} not found")

        annotation_status = AnnotationRepository.check_annotation_completion(self.db, snapshot_id)
        unanswered_question_count = QuestionRepository.count_approved_questions_without_answers(
            self.db,
            snapshot.target_id,
            snapshot_id,
        )

        return ScoringStatusResponse(
            snapshot_id=snapshot_id,
            selected_ids=annotation_status["selected_ids"],
            selected_and_annotated_ids=annotation_status["selected_and_annotated_ids"],
            is_complete=annotation_status["is_complete"],
            completion_percentage=annotation_status["completion_percentage"],
            unanswered_question_count=unanswered_question_count,
        )

    def get_scoring_rubrics(self, snapshot_id: int) -> ScoringRubricsResponse:
        """Return rubric display metadata with inline judges for one snapshot."""
        snapshot = SnapshotRepository.get_by_id(self.db, snapshot_id)
        if not snapshot:
            raise ValueError(f"Snapshot {snapshot_id} not found")

        rubrics = []
        for rubric in TargetRubricRepository.get_by_target(self.db, snapshot.target_id):
            judges = [
                JudgeResponse.model_validate(judge, from_attributes=True)
                for judge in JudgeRepository.get_for_rubric(self.db, rubric.id, target_id=snapshot.target_id)
            ]
            rubrics.append(
                ScoringRubricResponse(
                    **TargetRubricResponse.model_validate(rubric, from_attributes=True).model_dump(),
                    judges=judges,
                )
            )

        return ScoringRubricsResponse(snapshot_id=snapshot_id, rubrics=rubrics)

    def get_scoring_results(
        self,
        snapshot_id: int,
        rubric_id: int,
        filters: Optional[ScoringResultsFilters] = None,
        page: int = 0,
        page_size: int = 10,
    ) -> ScoringResultsResponse:
        """Return one rubric's paginated scoring rows plus backend-owned filter metadata."""
        contract = self._build_base_scoring_contract(snapshot_id, rubric_id)
        filters = filters or ScoringResultsFilters()
        filtered_rows, persona_options = self._apply_results_filters(contract.rows, filters)
        total_count = len(filtered_rows)
        start = max(page, 0) * max(page_size, 1)
        end = start + max(page_size, 1)
        pending_counts_response = self.get_scoring_pending_counts(snapshot_id, rubric_id)

        return ScoringResultsResponse(
            **contract.model_dump(exclude={"rows", "snapshot_id"}),
            snapshot_id=snapshot_id,
            total_count=total_count,
            page=max(page, 0),
            page_size=max(page_size, 1),
            pending_counts=pending_counts_response.pending_counts,
            persona_options=persona_options,
            rows=filtered_rows[start:end],
        )

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

        Ground truth is the rubric annotation only; scoring-page label overrides are not consulted.

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
        2. Computes per-judge reliability (F1) and filters to judges at or above the configured reliability threshold
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
        contract = self._build_base_scoring_contract(snapshot_id, rubric_id)
        if not contract.rows:
            raise ValueError(f"No answers found for snapshot {snapshot_id}")
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
        contract = self._build_base_scoring_contract(snapshot_id, rubric_id)
        logger.info(
            "Snapshot %s summary: Accuracy=%.3f (%s/%s), Aligned judges: %s, Edited: %s",
            snapshot_id,
            contract.aggregated_score if contract.aggregated_score is not None else float("nan"),
            contract.accurate_count,
            contract.total_answers,
            len(contract.aligned_judges),
            contract.edited_count,
        )
        return SnapshotMetric(
            aggregated_score=contract.aggregated_score,
            verdict_status=contract.verdict_status,
            calibration_count=contract.calibration_count,
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
            rubrics = TargetRubricRepository.get_by_target(self.db, snapshot.target_id)
            contracts = []
            for rubric in rubrics:
                try:
                    contracts.append(self._build_base_scoring_contract(snapshot.id, rubric.id))
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
                    verdict_status=contract.verdict_status,
                    calibration_count=contract.calibration_count,
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
