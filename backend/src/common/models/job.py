"""
Pydantic models for Job API requests and responses.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class JobType(str, Enum):
    """Type of generation job."""
    persona_generation = "persona_generation"
    question_generation = "question_generation"


class JobStatus(str, Enum):
    """Status of a generation job."""
    running = "running"
    completed = "completed"
    failed = "failed"


class JobCreate(BaseModel):
    """Request model for creating a generation job."""
    target_id: int = Field(..., description="Target ID for the generation job")
    count_requested: int = Field(..., description="Number of items to generate", gt=0)
    model_used: Optional[str] = Field(None, description="LLM model to use. If not specified, uses the configured default model.")
    persona_ids: Optional[List[int]] = Field(None, description="List of persona IDs (for question generation only). If not provided, generates for all approved personas.")


class JobResponse(BaseModel):
    """Response model for Job."""
    id: int
    target_id: int
    type: JobType
    persona_id: Optional[int] = None
    count_requested: int
    model_used: str
    generation_prompt: Optional[str] = None
    status: JobStatus
    prompt_tokens: int
    completion_tokens: int
    total_cost: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class JobStats(BaseModel):
    """Statistics for a generation job."""
    total_generated: int = Field(..., description="Total items generated")
    by_status: dict = Field(..., description="Counts by status")
    prompt_tokens: int
    completion_tokens: int
    total_cost: float
