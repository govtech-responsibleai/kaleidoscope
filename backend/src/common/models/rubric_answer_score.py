"""
Pydantic models for RubricAnswerScore API responses.
"""

from datetime import datetime
from pydantic import BaseModel


class RubricAnswerScoreResponse(BaseModel):
    """Response model for a rubric answer score."""
    id: int
    answer_id: int
    rubric_id: int
    judge_id: int
    option_chosen: str
    explanation: str
    created_at: datetime

    class Config:
        from_attributes = True
