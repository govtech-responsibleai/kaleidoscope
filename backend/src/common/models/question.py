"""
Pydantic models for Question API requests and responses.
"""

from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field
from src.common.models.persona import Status


class QuestionType(str, Enum):
    """Type of question."""
    typical = "typical"
    edge = "edge"


class QuestionScope(str, Enum):
    """Scope of question relative to knowledge base."""
    in_kb = "in_kb"
    out_kb = "out_kb"


class QuestionBase(BaseModel):
    """Base fields for Question."""
    text: str = Field(..., description="The question text")
    type: QuestionType = Field(..., description="Type of question (typical or edge)")
    scope: QuestionScope = Field(..., description="Scope relative to KB (in_kb or out_kb)")


class QuestionListOutput(BaseModel):
    """LLM structured output for question generation - a list of questions."""
    questions: List[QuestionBase] = Field(
        ...,
        description="List of generated questions"
    )


class QuestionUpdate(BaseModel):
    """Request model for updating a question."""
    text: Optional[str] = None
    type: Optional[QuestionType] = None
    scope: Optional[QuestionScope] = None


class QuestionResponse(QuestionBase):
    """Response model for Question."""
    id: int
    job_id: int
    persona_id: int
    target_id: int
    status: Status
    created_at: datetime
    updated_at: datetime
    persona_title: Optional[str] = Field(None, description="Title of the persona (populated when needed)")

    class Config:
        from_attributes = True


class QuestionApprove(BaseModel):
    """Request model for approving a question."""
    pass


class QuestionReject(BaseModel):
    """Request model for rejecting a question."""
    reason: Optional[str] = Field(None, description="Reason for rejection")


class QuestionBulkApprove(BaseModel):
    """Request model for bulk approving questions."""
    question_ids: list[int] = Field(..., description="List of question IDs to approve")


class SimilarQuestionsRequest(BaseModel):
    """Request model for finding similar questions."""
    target_id: int = Field(..., description="Target ID to search within")
    question_ids: List[int] = Field(..., description="Question IDs to find similar questions for")
    similarity_threshold: float = Field(0.7, description="Minimum similarity score (0-1)", ge=0, le=1)


class SimilarQuestion(BaseModel):
    """A similar question with similarity score."""
    question_id: int = Field(..., description="ID of the similar question")
    similarity_score: float = Field(..., description="Cosine similarity score (0-1)")


class QuerySimilarQuestions(BaseModel):
    """Similar questions for a single query."""
    query_question_id: int = Field(..., description="ID of the query question")
    similar_questions: List[SimilarQuestion] = Field(..., description="List of similar question IDs with similarity scores, sorted by score descending")


class SimilarQuestionsResponse(BaseModel):
    """Response model for similar questions."""
    results: List[QuerySimilarQuestions] = Field(..., description="Results for each query question")
