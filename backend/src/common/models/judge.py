"""
Pydantic models for Judge API requests and responses.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class JudgeCreate(BaseModel):
    """Request model for creating a judge."""
    target_id: Optional[int] = Field(None, description="Target to scope this judge to (NULL = global)")
    name: str = Field(..., description="Name of the judge (e.g., 'Baseline Judge', 'GPT-4 Judge')")
    model_name: str = Field(..., description="LLM model to use (e.g., 'gemini/gemini-2.5-flash-lite')")
    model_label: Optional[str] = Field(None, description="Display label for the model")
    prompt_template: str = Field(..., description="Jinja2 prompt template for the judge")
    params: Dict[str, Any] = Field(default_factory=dict, description="Additional parameters (temperature, etc.)")
    is_baseline: bool = Field(default=False, description="Whether this is the baseline judge")
    is_editable: bool = Field(default=True, description="Whether this judge can be edited/deleted")
    rubric_id: Optional[int] = Field(None, description="Optional rubric to scope this judge to")


class JudgeUpdate(BaseModel):
    """Request model for updating a judge."""
    name: Optional[str] = None
    model_name: Optional[str] = None
    model_label: Optional[str] = None
    prompt_template: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    rubric_id: Optional[int] = None


class JudgeResponse(BaseModel):
    """Response model for Judge."""
    id: int
    target_id: Optional[int] = None
    name: str
    model_name: str
    model_label: Optional[str] = None
    prompt_template: str
    params: Dict[str, Any]
    is_baseline: bool
    is_editable: bool
    rubric_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

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


class RubricJudgmentResult(BaseModel):
    """Pydantic model for rubric-based judge response."""
    chosen_option: str = Field(..., description="Exactly one option value from the rubric options list")
    explanation: str = Field(..., description="1-2 sentence explanation of why this option was chosen")
