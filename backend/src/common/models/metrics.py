"""Pydantic models for metrics and aggregated scoring results."""

from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field


AggregationMethod = Literal["majority", "majority_tied", "no_aligned_judge", "override", "pending"]


class AggregatedScore(BaseModel):
    """Aggregated score for an answer using reliable judges only."""
    answer_id: int
    method: AggregationMethod
    label: Optional[str] = None
    is_edited: bool = False
    metadata: List[str] = Field(default_factory=list)


class AggregatedResult(BaseModel):
    """Full aggregated result for a single answer."""
    rubric_id: int
    rubric_name: str
    group: str
    question_id: int
    question_text: Optional[str] = None
    question_type: Optional[str] = None
    question_scope: Optional[str] = None
    answer_id: int
    answer_content: str
    aggregated_score: AggregatedScore
    human_label: Optional[str] = None
    human_notes: Optional[str] = None


class SnapshotResultsResponse(BaseModel):
    """QA-grouped aggregated results for one snapshot."""
    snapshot_id: int
    results: List[AggregatedResult] = Field(default_factory=list)


class AlignedJudge(BaseModel):
    """A judge that meets the reliability threshold."""
    judge_id: int
    name: str
    f1: float


class JudgeAlignmentResponse(BaseModel):
    """Alignment metrics for a judge on annotated answers."""
    f1: float
    precision: float
    recall: float
    accuracy: float
    sample_count: int


class JudgeAccuracyResponse(BaseModel):
    """Overall answer accuracy for a judge on a snapshot."""
    accuracy: float
    total_answers: int
    accurate_count: int


class SnapshotMetric(BaseModel):
    """Metrics for a single snapshot within a target-level metrics view."""
    snapshot_id: Optional[int] = None
    snapshot_name: Optional[str] = None
    created_at: Optional[str] = None
    rubric_id: Optional[int] = None
    rubric_name: Optional[str] = None
    aggregated_score: float
    total_answers: int
    accurate_count: int
    inaccurate_count: int
    pending_count: int
    edited_count: int
    judge_alignment_range: Optional[Dict[str, float]] = None
    aligned_judges: List[AlignedJudge] = Field(default_factory=list)


class ScoringPendingCountsResponse(BaseModel):
    """Rubric-scoped pending counts needed by one scoring section."""
    unanswered_question_count: int
    rubric_id: int
    pending_counts: Dict[str, int] = Field(default_factory=dict)


class ConfusionMatrixResponse(BaseModel):
    """Confusion matrix for inaccurate answers by question type and scope."""
    matrix: Dict[str, int]
    total_inaccurate: int


class JudgeScoreSummary(BaseModel):
    """Per-judge summary returned inside a metric-scoped scoring contract."""
    judge_id: int
    name: str
    reliability: Optional[float] = None
    accuracy: Optional[float] = None
    accurate_count: int
    total_answers: int


class JudgeRowResult(BaseModel):
    """Per-judge row-level output for a metric-scoped scoring contract."""
    judge_id: int
    name: str
    value: Optional[str] = None


class AggregatedRowResult(BaseModel):
    """Aggregated row-level output for accuracy or rubric metrics."""
    method: AggregationMethod
    value: Optional[str] = None
    baseline_value: Optional[str] = None
    is_edited: bool = False


class ScoringRowResult(BaseModel):
    """One answer row within a metric-scoped scoring contract."""
    question_id: int
    question_text: Optional[str] = None
    question_type: Optional[str] = None
    question_scope: Optional[str] = None
    answer_id: int
    answer_content: str
    aggregated_result: AggregatedRowResult
    human_label: Optional[str] = None
    judge_results: List[JudgeRowResult] = Field(default_factory=list)


class ScoringContract(SnapshotMetric):
    """Backend-owned scoring contract for one rubric context."""
    rubric_id: int
    rubric_name: str
    group: str
    best_option: Optional[str] = None
    judge_summaries: List[JudgeScoreSummary] = Field(default_factory=list)
    rows: List[ScoringRowResult] = Field(default_factory=list)


class SnapshotScoringContractsResponse(BaseModel):
    """All rubric-scoped scoring contracts for one snapshot."""
    snapshot_id: int
    rubrics: List[ScoringContract] = Field(default_factory=list)


class MetricsByRubric(BaseModel):
    """Grouped snapshot metrics for one rubric."""
    rubric_id: int
    rubric_name: str
    group: str
    snapshots: List[SnapshotMetric] = Field(default_factory=list)


class SnapshotMetricsResponse(BaseModel):
    """All-rubrics grouped snapshot metrics for one target."""
    target_id: int
    rubrics: List[MetricsByRubric] = Field(default_factory=list)


# Legacy aliases kept temporarily while callers migrate to rubric-oriented names.
TargetSnapshotMetric = SnapshotMetric
AggregatedAnswerScore = AggregatedScore
MetricJudgeScoreSummary = JudgeScoreSummary
MetricJudgeRowResult = JudgeRowResult
MetricAggregatedResult = AggregatedRowResult
MetricRowResult = ScoringRowResult
MetricScoringContract = ScoringContract
