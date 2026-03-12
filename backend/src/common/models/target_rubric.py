"""
Pydantic models for TargetRubric API requests and responses.
"""

from datetime import datetime
from typing import List
from pydantic import BaseModel


class RubricOption(BaseModel):
    option: str
    description: str


class TargetRubricCreate(BaseModel):
    name: str
    criteria: str = ""
    options: List[RubricOption] = []


class TargetRubricUpdate(BaseModel):
    name: str | None = None
    criteria: str | None = None
    options: List[RubricOption] | None = None


class TargetRubricResponse(BaseModel):
    id: int
    target_id: int
    name: str
    criteria: str
    options: List[RubricOption]
    position: int
    category: str  # "accuracy" | "voice" | "relevancy" | "default"
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
