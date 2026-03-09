"""
Pydantic models for Target API requests and responses.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, model_validator


class EndpointType(str, Enum):
    """Supported endpoint types."""
    aibots = "aibots"


class TargetBase(BaseModel):
    """Base fields for Target."""
    name: str = Field(..., description="Name of the target application")
    agency: Optional[str] = Field(None, description="Agency owning the target")
    purpose: Optional[str] = Field(None, description="Purpose of the target application")
    target_users: Optional[str] = Field(None, description="Expected target users")
    api_endpoint: Optional[str] = Field(None, description="API endpoint to call for generating responses")
    endpoint_type: Optional[EndpointType] = Field(None, description="Endpoint type: 'aibots', etc.")
    endpoint_config: Optional[Dict[str, Any]] = Field(None, description="Type-specific endpoint config")

    @model_validator(mode='after')
    def validate_endpoint_config(self):
        if self.endpoint_type == EndpointType.aibots:
            config = self.endpoint_config or {}
            if not config.get("api_key"):
                raise ValueError("api_key is required in endpoint_config for aibots endpoint")
        return self


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
    endpoint_type: Optional[EndpointType] = None
    endpoint_config: Optional[Dict[str, Any]] = None

    @model_validator(mode='after')
    def validate_endpoint_config(self):
        if self.endpoint_type == EndpointType.aibots:
            config = self.endpoint_config or {}
            if not config.get("api_key"):
                raise ValueError("api_key is required in endpoint_config for aibots endpoint")
        return self


class TargetResponse(TargetBase):
    """Response model for Target."""
    id: int
    user_id: Optional[int] = None
    owner_username: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TargetStats(BaseModel):
    """Statistics for a target."""
    personas: dict = Field(..., description="Persona counts by status")
    questions: dict = Field(..., description="Question counts by status")
    total_cost: float = Field(..., description="Total generation cost in USD")
