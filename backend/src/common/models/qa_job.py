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



class RubricSpec(BaseModel):
    """Specifies a rubric and its judge for the unified start endpoint."""
    rubric_id: int = Field(..., description="Custom rubric ID")
    judge_id: int = Field(..., description="Judge ID for this rubric")


class UnifiedQAJobStart(BaseModel):
    """Request model for starting all QA jobs (accuracy + rubric) in one call."""
    snapshot_id: int = Field(..., description="Snapshot ID")
    judge_id: int = Field(..., description="Accuracy judge ID")
    question_ids: list[int] = Field(..., description="List of question IDs to process")
    rubric_specs: Optional[list[RubricSpec]] = Field(None, description="Custom rubrics with their judges")
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


class QAJobListResponse(BaseModel):
    """Response model for listing QA jobs."""
    jobs: list[QAJobResponse]
    total: int


