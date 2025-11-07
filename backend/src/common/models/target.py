"""
Pydantic models for Target API requests and responses.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class TargetBase(BaseModel):
    """Base fields for Target."""
    name: str = Field(..., description="Name of the target application")
    agency: Optional[str] = Field(None, description="Agency owning the target")
    purpose: Optional[str] = Field(None, description="Purpose of the target application")
    target_users: Optional[str] = Field(None, description="Expected target users")
    api_endpoint: Optional[str] = Field(None, description="API endpoint to call for generating responses")
    knowledge_base_path: Optional[str] = Field(None, description="Path to knowledge base documents")


class TargetCreate(TargetBase):
    """Request model for creating a new target."""
    pass


class TargetUpdate(BaseModel):
    """Request model for updating a target."""
    name: Optional[str] = None
    agency: Optional[str] = None
    purpose: Optional[str] = None
    target_users: Optional[str] = None
    api_endpoint: Optional[str] = None
    knowledge_base_path: Optional[str] = None


class TargetResponse(TargetBase):
    """Response model for Target."""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TargetStats(BaseModel):
    """Statistics for a target."""
    personas: dict = Field(..., description="Persona counts by status")
    questions: dict = Field(..., description="Question counts by status")
    total_cost: float = Field(..., description="Total generation cost in USD")
