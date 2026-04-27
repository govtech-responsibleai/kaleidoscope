"""
Pydantic models for AnswerLabelOverride API requests and responses.
"""

from datetime import datetime
from pydantic import BaseModel, Field


class AnswerLabelOverrideCreate(BaseModel):
    """Request model for creating/updating a label override."""
    edited_value: str = Field(..., description="Rubric value to use as the effective final row label")


class AnswerLabelOverrideResponse(BaseModel):
    """Response model for AnswerLabelOverride."""
    id: int
    answer_id: int
    rubric_id: int
    edited_value: str
    edited_at: datetime

    class Config:
        from_attributes = True
