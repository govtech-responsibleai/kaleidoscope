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
    start_stage: Optional[QAJobStage] = Field(None, description="Optional starting stage (default: starting)")


class QAJobResume(BaseModel):
    """Request model for resuming a paused QA job."""
    job_id: int = Field(..., description="QA job ID to resume")
    override_stage: Optional[QAJobStage] = Field(None, description="Optional stage override (use with caution)")


class QAJobResponse(BaseModel):
    """Response model for QAJob."""
    id: int
    snapshot_id: int
    question_id: int
    answer_id: int
    judge_id: int
    type: QAJobType
    status: JobStatus
    stage: QAJobStage
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
