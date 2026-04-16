"""
Pydantic models for Target API requests and responses.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger(__name__)


class TargetBase(BaseModel):
    """Base fields for Target."""
    name: str = Field(..., description="Name of the target application")
    agency: Optional[str] = Field(None, description="Agency owning the target")
    purpose: Optional[str] = Field(None, description="Purpose of the target application")
    target_users: Optional[str] = Field(None, description="Expected target users")
    api_endpoint: Optional[str] = Field(None, description="API endpoint to call for generating responses")
    endpoint_type: Optional[str] = Field(None, description="Endpoint type: 'http', 'aibots', etc. See GET /targets/connector-types for the full list.")
    endpoint_config: Optional[Dict[str, Any]] = Field(None, description="Type-specific endpoint config")

    @model_validator(mode='after')
    def validate_endpoint_config(self):
        if self.endpoint_type:
            from src.common.connectors.registry import validate_connector_config
            validate_connector_config(self.endpoint_type, self.endpoint_config or {})
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
    endpoint_type: Optional[str] = None
    endpoint_config: Optional[Dict[str, Any]] = None

    @model_validator(mode='after')
    def validate_endpoint_config(self):
        if self.endpoint_type:
            from src.common.connectors.registry import validate_connector_config
            validate_connector_config(self.endpoint_type, self.endpoint_config or {})
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


class TestConnectionRequest(BaseModel):
    """Request model for testing a connector configuration."""
    target_id: Optional[int] = Field(None, description="Existing target ID for resolving managed auth.")
    endpoint_type: str = Field(..., description="Connector type to test. See GET /targets/connector-types.")
    api_endpoint: str = Field(..., description="API endpoint URL")
    endpoint_config: Dict[str, Any] = Field(default_factory=dict, description="Type-specific config")
    prompt: str = Field(default="Hello, this is a probe message.", description="Prompt text to send.")


class TestConnectionResponse(BaseModel):
    """Response model for a test connection attempt."""
    success: bool
    content: Optional[str] = None
    model: Optional[str] = None
    error: Optional[str] = None


class ProbeRequest(BaseModel):
    """Request model for probing a target endpoint without requiring an extraction path.

    Unlike TestConnectionRequest, probe does NOT trigger connector-specific config
    validation (e.g. response_content_path is not required). The endpoint is called
    and the raw response body is returned for inspection.
    """
    target_id: Optional[int] = Field(None, description="Existing target ID for resolving managed auth.")
    endpoint_type: str = Field(..., description="Connector type to probe.")
    api_endpoint: str = Field(..., description="API endpoint URL")
    endpoint_config: Dict[str, Any] = Field(default_factory=dict, description="Type-specific config")
    prompt: str = Field(default="Hello, this is a probe message.", description="Prompt text to send.")


class ProbeResponse(BaseModel):
    """Response model for a probe attempt.

    Distinct from TestConnectionResponse: probe returns the raw response body and
    status code so the caller can inspect shape before declaring an extraction path.
    """
    success: bool
    status_code: Optional[int] = None
    raw_body: Optional[Any] = None
    headers: Optional[Dict[str, str]] = None
    error: Optional[str] = None


class TargetStats(BaseModel):
    """Statistics for a target."""
    personas: dict = Field(..., description="Persona counts by status")
    questions: dict = Field(..., description="Question counts by status")
    total_cost: float = Field(..., description="Total generation cost in USD")
