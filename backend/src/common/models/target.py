"""
Pydantic models for Target API requests and responses.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger(__name__)


class EndpointType(str, Enum):
    """Supported endpoint types.

    Built-in types are defined here. Extensions can add values at
    startup via ``extend_endpoint_type()``.
    """
    http = "http"


def extend_endpoint_type(name: str) -> None:
    """Dynamically add a value to the EndpointType enum.

    Called by the connector registry when an extension registers a new
    connector type. No-op if the value already exists.
    """
    if name in EndpointType.__members__:
        return

    # Use the internal Enum API to extend the enum at runtime
    new_member = str.__new__(EndpointType, name)
    new_member._name_ = name
    new_member._value_ = name
    EndpointType._member_map_[name] = new_member
    EndpointType._value2member_map_[name] = new_member
    logger.debug(f"Extended EndpointType enum with '{name}'")


class TargetBase(BaseModel):
    """Base fields for Target."""
    name: str = Field(..., description="Name of the target application")
    agency: Optional[str] = Field(None, description="Agency owning the target")
    purpose: Optional[str] = Field(None, description="Purpose of the target application")
    target_users: Optional[str] = Field(None, description="Expected target users")
    api_endpoint: Optional[str] = Field(None, description="API endpoint to call for generating responses")
    endpoint_type: Optional[EndpointType] = Field(None, description="Endpoint type: 'http', etc.")
    endpoint_config: Optional[Dict[str, Any]] = Field(None, description="Type-specific endpoint config")

    @model_validator(mode='after')
    def validate_endpoint_config(self):
        if self.endpoint_type:
            from src.common.connectors.registry import validate_connector_config
            validate_connector_config(self.endpoint_type.value, self.endpoint_config or {})
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
        if self.endpoint_type:
            from src.common.connectors.registry import validate_connector_config
            validate_connector_config(self.endpoint_type.value, self.endpoint_config or {})
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
    endpoint_type: EndpointType = Field(..., description="Connector type to test")
    api_endpoint: str = Field(..., description="API endpoint URL")
    endpoint_config: Dict[str, Any] = Field(default_factory=dict, description="Type-specific config")


class TestConnectionResponse(BaseModel):
    """Response model for a test connection attempt."""
    success: bool
    content: Optional[str] = None
    model: Optional[str] = None
    error: Optional[str] = None


class TargetStats(BaseModel):
    """Statistics for a target."""
    personas: dict = Field(..., description="Persona counts by status")
    questions: dict = Field(..., description="Question counts by status")
    total_cost: float = Field(..., description="Total generation cost in USD")
