"""
Pydantic models for Judge API requests and responses.
"""

from typing import Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class JudgeType(str, Enum):
    """Type of judge evaluation."""
    claim_based = "claim_based"
    response_level = "response_level"


class JudgeCreate(BaseModel):
    """Request model for creating a judge."""
    name: str = Field(..., description="Name of the judge (e.g., 'Baseline Judge', 'GPT-4 Judge')")
    model_name: str = Field(..., description="LLM model to use (e.g., 'gemini/gemini-2.0-flash-lite')")
    prompt_template: str = Field(..., description="Jinja2 prompt template for the judge")
    params: Dict[str, Any] = Field(default_factory=dict, description="Additional parameters (temperature, etc.)")
    judge_type: JudgeType = Field(..., description="Type of judging (claim_based or response_level)")
    is_baseline: bool = Field(default=False, description="Whether this is the baseline judge")
    is_editable: bool = Field(default=True, description="Whether this judge can be edited/deleted")


class JudgeUpdate(BaseModel):
    """Request model for updating a judge."""
    name: Optional[str] = None
    model_name: Optional[str] = None
    prompt_template: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    judge_type: Optional[JudgeType] = None


class JudgeResponse(BaseModel):
    """Response model for Judge."""
    id: int
    name: str
    model_name: str
    prompt_template: str
    params: Dict[str, Any]
    judge_type: JudgeType
    is_baseline: bool
    is_editable: bool

    class Config:
        from_attributes = True


class ClaimJudgmentResult(BaseModel):
    """Pydantic model for claim-level judge response."""
    label: bool = Field(..., description="True if claim is supported by knowledge base, False if hallucinated")
    reasoning: str = Field(..., description="Detailed explanation of why the claim is accurate or inaccurate")


class ResponseJudgmentResult(BaseModel):
    """Pydantic model for response-level judge response."""
    label: bool = Field(..., description="True if response is overall accurate, False if inaccurate")
    reasoning: str = Field(..., description="Detailed explanation of the judgment")
