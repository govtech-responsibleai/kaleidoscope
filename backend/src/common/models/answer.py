"""
Pydantic models for Answer API requests and responses.
"""

from datetime import datetime
from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field


class AnswerCreate(BaseModel):
    """Request model for generating an answer."""
    question_id: int = Field(..., description="ID of the question to generate answer for")


class AnswerResponse(BaseModel):
    """Response model for Answer."""
    id: int
    question_id: int
    target_id: int
    answer_content: str
    model: Optional[str] = None
    rag_citations: Optional[List[Dict[str, Any]]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AnswerListResponse(BaseModel):
    """Response model for listing answers."""
    answers: List[AnswerResponse]
    total: int
