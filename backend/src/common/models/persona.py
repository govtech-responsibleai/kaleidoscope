"""
Pydantic models for Persona API requests and responses.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class Status(str, Enum):
    """Status for personas and questions."""
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    edited = "edited"


class PersonaSource(str, Enum):
    """Source of persona creation."""
    generated = "generated"
    nemotron = "nemotron"


class PersonaBase(BaseModel):
    """Base fields for Persona."""
    title: str = Field(..., description="Title of the persona")
    info: Optional[str] = Field(None, description="Background and role context")
    style: Optional[str] = Field(None, description="Communication style")
    use_case: Optional[str] = Field(None, description="Use case for engaging with target application")


class PersonaListOutput(BaseModel):
    """LLM structured output for persona generation - a list of personas."""
    personas: List[PersonaBase] = Field(
        ...,
        description="List of generated personas"
    )


class PersonaCreate(BaseModel):
    """Request model for manually creating a persona."""
    target_id: int = Field(..., description="Target ID to associate persona with")
    title: str = Field(..., description="Title of the persona")
    info: Optional[str] = Field(None, description="Background and role context")
    style: Optional[str] = Field(None, description="Communication style")
    use_case: Optional[str] = Field(None, description="Use case for engaging with target application")


class PersonaUpdate(BaseModel):
    """Request model for updating a persona."""
    title: Optional[str] = None
    info: Optional[str] = None
    style: Optional[str] = None
    use_case: Optional[str] = None


class PersonaResponse(PersonaBase):
    """Response model for Persona."""
    id: int
    source: PersonaSource
    job_id: Optional[int] = None  # NULL for nemotron personas
    target_id: int
    status: Status
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PersonaApprove(BaseModel):
    """Request model for approving a persona."""
    pass


class PersonaReject(BaseModel):
    """Request model for rejecting a persona."""
    reason: Optional[str] = Field(None, description="Reason for rejection")


class PersonaBulkApprove(BaseModel):
    """Request model for bulk approving personas."""
    persona_ids: list[int] = Field(..., description="List of persona IDs to approve")


class NemotronSampleRequest(BaseModel):
    """Request model for sampling personas from the Nemotron dataset."""
    target_id: int = Field(..., description="Target ID to associate personas with")
    n: int = Field(..., description="Number of personas to sample", gt=0)
