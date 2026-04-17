"""Pydantic models for metrics and aggregated scoring results."""

from typing import Dict, List, Literal, Optional
from pydantic import BaseModel


AggregationMethod = Literal["majority", "majority_tied", "no_aligned_judge", "override"]


class AggregatedAnswerScore(BaseModel):
    """Aggregated score for an answer using reliable judges only."""
    answer_id: int
    method: AggregationMethod
    label: Optional[bool] = None
    is_edited: bool = False
    metadata: List[str] = []


class AggregatedResult(BaseModel):
    """Full aggregated result for a single answer."""
    question_id: int
    question_text: Optional[str] = None
    question_type: Optional[str] = None
    question_scope: Optional[str] = None
    answer_id: int
    answer_content: str
    aggregated_accuracy: AggregatedAnswerScore
    human_label: Optional[bool] = None
    human_notes: Optional[str] = None


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


class TargetSnapshotMetric(BaseModel):
    """Metrics for a single snapshot within a target-level metrics view."""
    snapshot_id: Optional[int] = None
    snapshot_name: Optional[str] = None
    created_at: Optional[str] = None
    rubric_id: Optional[int] = None
    rubric_name: Optional[str] = None
    aggregated_accuracy: float
    total_answers: int
    accurate_count: int
    inaccurate_count: int
    pending_count: int
    edited_count: int
    judge_alignment_range: Optional[Dict[str, float]] = None
    aligned_judges: List[AlignedJudge] = []


class ScoringPendingCountsResponse(BaseModel):
    """Snapshot-scoped pending counts needed by the scoring page."""
    unanswered_question_count: int
    accuracy_pending_counts: Dict[str, int] = {}
    rubric_pending_counts: Dict[str, int] = {}


class ConfusionMatrixResponse(BaseModel):
    """Confusion matrix for inaccurate answers by question type and scope."""
    matrix: Dict[str, int]
    total_inaccurate: int

