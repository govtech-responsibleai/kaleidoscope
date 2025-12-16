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
    snapshot_id: int
    answer_content: str
    model: Optional[str] = None
    rag_citations: Optional[List[Dict[str, Any]]] = None
    is_selected_for_annotation: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AnswerListResponse(BaseModel):
    """Response model for listing answers."""
    answers: List[AnswerResponse]
    total: int


class AnswerBulkSelection(BaseModel):
    """Request model for bulk updating answer selection."""
    selections: List[Dict[str, Any]] = Field(
        ...,
        description="List of selections with answer_id and is_selected per answer",
        example=[
            {"answer_id": 1, "is_selected": True},
            {"answer_id": 2, "is_selected": False}
        ]
    )
