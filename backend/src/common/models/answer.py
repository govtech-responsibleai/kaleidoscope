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
    chat_id: Optional[str] = None
    message_id: Optional[str] = None
    answer_content: str
    model: Optional[str] = None
    guardrails: Optional[Any] = None
    rag_citations: Optional[List[Dict[str, Any]]] = None
    is_selected_for_annotation: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AnswerListItemResponse(AnswerResponse):
    """Enriched response model for answer list views."""
    question_text: Optional[str] = None
    has_annotation: bool = False


class AnswerListResponse(BaseModel):
    """Response model for listing answers."""
    answers: List[AnswerListItemResponse]
    total: int


class AnswerSelection(BaseModel):
    """A single answer selection entry."""
    answer_id: int
    is_selected: bool


class AnswerBulkSelection(BaseModel):
    """Request model for bulk updating answer selection."""
    selections: List[AnswerSelection] = Field(
        ...,
        description="List of selections with answer_id and is_selected per answer",
    )


class DefaultSelectionResponse(BaseModel):
    """Response model for default answer selection."""
    snapshot_id: int
    selected_count: int
    total_answers: int
