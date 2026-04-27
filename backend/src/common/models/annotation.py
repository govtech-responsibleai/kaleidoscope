"""Pydantic models for rubric-scoped Annotation API requests and responses."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class AnnotationCreate(BaseModel):
    """Request model for creating one rubric-scoped annotation."""
    answer_id: int = Field(..., description="ID of the answer being annotated")
    rubric_id: int = Field(..., description="ID of the rubric being annotated")
    option_value: str = Field(..., description="Rubric option chosen for this answer")
    notes: Optional[str] = Field(None, description="Optional notes from the annotator")


class AnnotationUpdate(BaseModel):
    """Request model for updating one rubric-scoped annotation."""
    rubric_id: int = Field(..., description="ID of the rubric that scopes the annotation row")
    option_value: Optional[str] = None
    notes: Optional[str] = None


class AnnotationResponse(BaseModel):
    """Response model for one rubric-scoped annotation row."""
    id: int
    answer_id: int
    rubric_id: int
    option_value: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AnnotationBulkCreateItem(BaseModel):
    """One answer-scoped annotation payload within a single-rubric bulk batch."""
    answer_id: int
    option_value: str
    notes: Optional[str] = None


class AnnotationBulkCreate(BaseModel):
    """Request model for bulk creating annotations for one rubric."""
    rubric_id: int = Field(..., description="Rubric ID shared by all annotations in the batch")
    annotations: List[AnnotationBulkCreateItem] = Field(..., description="List of answer-scoped annotations")


class AnnotationAnswerGroupResponse(BaseModel):
    """Snapshot annotation rows grouped by answer."""
    answer_id: int
    annotations: List[AnnotationResponse] = Field(default_factory=list)


class AnnotationListResponse(BaseModel):
    """Response model for grouped snapshot annotation listing."""
    answers: List[AnnotationAnswerGroupResponse]
    total_answers: int
    total_annotations: int
