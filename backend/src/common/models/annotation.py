"""
Pydantic models for Annotation API requests and responses.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class AnnotationCreate(BaseModel):
    """Request model for creating an annotation."""
    answer_id: int = Field(..., description="ID of the answer being annotated")
    label: bool = Field(..., description="True if answer is accurate, False if inaccurate")
    notes: Optional[str] = Field(None, description="Optional notes from the annotator")


class AnnotationUpdate(BaseModel):
    """Request model for updating an annotation."""
    label: Optional[bool] = None
    notes: Optional[str] = None


class AnnotationResponse(BaseModel):
    """Response model for Annotation."""
    id: int
    answer_id: int
    label: bool
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AnnotationBulkCreate(BaseModel):
    """Request model for bulk creating annotations."""
    annotations: List[AnnotationCreate] = Field(..., description="List of annotations to create")


class AnnotationListResponse(BaseModel):
    """Response model for listing annotations."""
    annotations: List[AnnotationResponse]
    total: int
