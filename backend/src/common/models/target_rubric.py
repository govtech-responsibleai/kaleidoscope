"""
Pydantic models for TargetRubric API requests and responses.
"""

from datetime import datetime
from typing import List
from pydantic import BaseModel


class RubricOption(BaseModel):
    option: str
    description: str


class PremadeRubricTemplateResponse(BaseModel):
    key: str
    name: str
    criteria: str
    options: List[RubricOption]
    best_option: str
    recommended_model: str


class TargetRubricCreate(BaseModel):
    name: str
    criteria: str = ""
    options: List[RubricOption] = []
    best_option: str | None = None
    template_key: str | None = None


class TargetRubricUpdate(BaseModel):
    name: str | None = None
    criteria: str | None = None
    options: List[RubricOption] | None = None
    best_option: str | None = None
    judge_prompt: str | None = None
    template_key: str | None = None


class TargetRubricResponse(BaseModel):
    id: int
    target_id: int
    name: str
    criteria: str
    options: List[RubricOption]
    best_option: str | None = None
    position: int
    category: str = "default"
    judge_prompt: str | None = None
    template_key: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
