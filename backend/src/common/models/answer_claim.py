"""
Pydantic models for AnswerClaim API requests and responses.
"""

from datetime import datetime
from typing import List
from pydantic import BaseModel, Field


class AnswerClaimResponse(BaseModel):
    """Response model for AnswerClaim."""
    id: int
    answer_id: int
    claim_index: int
    claim_text: str
    checkworthy: bool
    created_at: datetime
    checked_at: datetime

    class Config:
        from_attributes = True


class AnswerClaimListResponse(BaseModel):
    """Response model for listing answer claims."""
    claims: List[AnswerClaimResponse]
    total: int


class CheckworthyResult(BaseModel):
    """Pydantic model for checkworthy LLM response."""
    checkworthy: bool = Field(..., description="True if claim is worth fact-checking, False otherwise")
    reasoning: str = Field(..., description="Brief explanation for the decision")
