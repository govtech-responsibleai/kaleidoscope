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
    aggregated_accuracy: float
    total_answers: int
    accurate_count: int
    inaccurate_count: int
    pending_count: int
    edited_count: int
    judge_alignment_range: Optional[Dict[str, float]] = None
    aligned_judges: List[AlignedJudge] = []


class ConfusionMatrixResponse(BaseModel):
    """Confusion matrix for inaccurate answers by question type and scope."""
    matrix: Dict[str, int]
    total_inaccurate: int


class RubricJudgeAlignmentResponse(BaseModel):
    """Alignment of a rubric judge with human labels on selected answers."""
    accuracy: float  # % match with human labels
    sample_count: int


class RubricJudgeAccuracyResponse(BaseModel):
    """Per-judge rubric scoring summary."""
    score: float  # % of answers getting the best option
    total_answers: int
    best_option_count: int
    best_option: str


class RubricSnapshotMetric(BaseModel):
    """Aggregated rubric metric for a snapshot."""
    rubric_id: int
    rubric_name: str
    aggregated_score: float  # % of answers where majority chose best option
    total_answers: int
    best_option: str
    best_option_count: int
    aligned_judges: List[AlignedJudge] = []
    judge_alignment_range: Optional[Dict[str, float]] = None
