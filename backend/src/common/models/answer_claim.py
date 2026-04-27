"""
Pydantic models for AnswerClaim API requests and responses.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from src.common.models.answer_score import AnswerClaimScoreResponse


class AnswerClaimResponse(BaseModel):
    """Response model for AnswerClaim."""
    id: int
    answer_id: int
    claim_index: int
    claim_text: str
    checkworthy: bool
    created_at: datetime
    checked_at: datetime
    score: Optional[AnswerClaimScoreResponse] = None

    class Config:
        from_attributes = True


class AnswerClaimsWithScoresResponse(BaseModel):
    """Response model for answer claims with scores from a specific judge."""
    answer_id: int
    claims: List[AnswerClaimResponse]


class CheckworthyResult(BaseModel):
    """Pydantic model for checkworthy LLM response."""
    checkworthy: bool = Field(..., description="True if claim is worth fact-checking, False otherwise")
    reasoning: str = Field(..., description="Brief explanation for the decision")
