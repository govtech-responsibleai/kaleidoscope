"""
Pydantic models for Snapshot API requests and responses.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class SnapshotCreate(BaseModel):
    """Request model for creating a snapshot."""
    target_id: int = Field(..., description="ID of the target application")
    name: str = Field(..., description="Name of the snapshot (e.g., 'v1.0', 'Pre-launch')")
    description: str = Field("", description="Description of what this snapshot represents")


class SnapshotUpdate(BaseModel):
    """Request model for updating a snapshot."""
    name: Optional[str] = Field(None, description="Updated name")
    description: Optional[str] = Field(None, description="Updated description")


class SnapshotResponse(BaseModel):
    """Response model for Snapshot."""
    id: int
    target_id: int
    name: str
    description: str
    created_at: datetime

    class Config:
        from_attributes = True
