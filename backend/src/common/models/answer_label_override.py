"""
Pydantic models for AnswerLabelOverride API requests and responses.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class AnswerLabelOverrideCreate(BaseModel):
    """Request model for creating/updating a label override."""
    edited_label: bool = Field(..., description="True if answer is accurate, False if inaccurate")


class AnswerLabelOverrideResponse(BaseModel):
    """Response model for AnswerLabelOverride."""
    id: int
    answer_id: int
    metric_name: str
    edited_label: bool
    edited_at: datetime

    class Config:
        from_attributes = True
