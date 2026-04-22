"""
Pydantic models for QAJob API requests and responses.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Status of a QA job."""
    running = "running"
    completed = "completed"
    failed = "failed"
    paused = "paused"


class QAJobType(str, Enum):
    """Type of QA job."""
    claim_scoring_full = "claim_scoring_full"
    response_scoring_full = "response_scoring_full"
    claim_scoring_only = "claim_scoring_only"
    response_scoring_only = "response_scoring_only"


class QAJobStage(str, Enum):
    """Current stage of a QA job."""
    starting = "starting"
    generating_answers = "generating_answers"
    processing_answers = "processing_answers"
    scoring_answers = "scoring_answers"
    completed = "completed"


class RubricVerdictState(str, Enum):
    """Availability state for one rubric's verdict on the annotation page."""

    no_judge_configured = "no_judge_configured"
    awaiting_answer = "awaiting_answer"
    pending_evaluation = "pending_evaluation"
    job_failed = "job_failed"
    success = "success"


class QARubricScore(BaseModel):
    """Resolved verdict details for one rubric in a QA job."""

    judge_id: int
    value: str
    explanation: Optional[str] = None
    created_at: datetime


class QARubricStatus(BaseModel):
    """Backend-owned verdict availability for one rubric in a QA job."""

    rubric_id: int
    rubric_name: str
    group: str
    state: RubricVerdictState
    message: str
    judge_id: Optional[int] = None
    judge_name: Optional[str] = None
    score: Optional[QARubricScore] = None


class QAJobCreate(BaseModel):
    """Request model for creating a QA job."""
    snapshot_id: int = Field(..., description="Snapshot ID")
    question_id: int = Field(..., description="Question ID")
    judge_id: int = Field(..., description="Judge ID to use for scoring")
    type: QAJobType = Field(..., description="Type of QA job")
    start_stage: Optional[QAJobStage] = Field(None, description="Optional starting stage (default: starting)")


class QAJobStart(BaseModel):
    """Request model for starting QA jobs in batch."""
    snapshot_id: int = Field(..., description="Snapshot ID")
    judge_id: int = Field(..., description="Judge ID to use for scoring")
    question_ids: list[int] = Field(..., description="List of question IDs to process")
    job_ids: Optional[list[int]] = Field(None, description="List of QA job IDs to resume")


class QAJobPauseRequest(BaseModel):
    """Request model for pausing QA jobs in batch."""
    job_ids: list[int] = Field(..., description="List of QA job IDs to pause")


class RubricQAJobStart(BaseModel):
    """Request model for starting rubric QA jobs in batch."""
    judge_id: int = Field(..., description="Judge ID to use for rubric scoring")
    question_ids: list[int] = Field(..., description="List of question IDs to process")
    rubric_id: int = Field(..., description="Custom rubric ID to evaluate against")


class RubricSpec(BaseModel):
    """Specifies a rubric and its judge for a QA job run."""
    rubric_id: int = Field(..., description="Target rubric ID")
    judge_id: int = Field(..., description="Judge ID for this rubric")


class UnifiedQAJobStart(BaseModel):
    """Request model for starting unified rubric-scoped QA jobs."""
    snapshot_id: int = Field(..., description="Snapshot ID")
    question_ids: list[int] = Field(..., description="List of question IDs to process")
    rubric_specs: Optional[list[RubricSpec]] = Field(
        None,
        description="Optional explicit rubric specs. If omitted, backend resolves the target baseline spec set.",
    )
    job_ids: Optional[list[int]] = Field(None, description="List of QA job IDs to resume")


class QAJobResponse(BaseModel):
    """Response model for QAJob."""
    id: int
    snapshot_id: int
    question_id: int
    answer_id: Optional[int] = None
    judge_id: Optional[int] = None
    rubric_specs: Optional[list[RubricSpec]] = None
    type: QAJobType
    status: JobStatus
    stage: QAJobStage
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class QAJobDetailResponse(QAJobResponse):
    """Detailed response model for QAJob with cost tracking."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_cost: float = 0.0
    rubric_statuses: list[QARubricStatus] = Field(default_factory=list)


class QAJobListResponse(BaseModel):
    """Response model for listing QA jobs."""
    jobs: list[QAJobResponse]
    total: int
