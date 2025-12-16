"""
Pydantic models for AnswerScore and AnswerClaimScore API requests and responses.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class AnswerClaimScoreResponse(BaseModel):
    """Response model for AnswerClaimScore."""
    id: int
    claim_id: int
    answer_score_id: int
    label: bool
    explanation: str
    created_at: datetime

    class Config:
        from_attributes = True


class AnswerScoreResponse(BaseModel):
    """Response model for AnswerScore."""
    id: int
    answer_id: int
    judge_id: int
    overall_label: bool
    explanation: Optional[str] = None
    created_at: datetime
    claim_scores: Optional[List[AnswerClaimScoreResponse]] = None

    class Config:
        from_attributes = True


class AnswerScoreListResponse(BaseModel):
    """Response model for listing answer scores."""
    scores: List[AnswerScoreResponse]
    total: int
