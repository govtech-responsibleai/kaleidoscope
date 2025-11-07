"""
Pydantic models for API requests and responses.
"""

from src.common.models.target import (
    TargetBase,
    TargetCreate,
    TargetUpdate,
    TargetResponse,
    TargetStats
)
from src.common.models.job import (
    JobType,
    JobStatus,
    JobCreate,
    JobResponse,
    JobStats
)
from src.common.models.persona import (
    Status,
    PersonaBase,
    PersonaListOutput,
    PersonaUpdate,
    PersonaResponse,
    PersonaApprove,
    PersonaReject,
    PersonaBulkApprove
)
from src.common.models.question import (
    QuestionBase,
    QuestionListOutput,
    QuestionUpdate,
    QuestionResponse,
    QuestionApprove,
    QuestionReject,
    QuestionBulkApprove,
    SimilarQuestionsRequest,
    SimilarQuestion,
    QuerySimilarQuestions,
    SimilarQuestionsResponse
)
from src.common.models.kb_document import (
    KBDocumentBase,
    KBDocumentResponse,
    KBDocumentTextResponse,
    KBDocumentListResponse,
    KBCompiledTextResponse
)

__all__ = [
    # Target
    "TargetBase",
    "TargetCreate",
    "TargetUpdate",
    "TargetResponse",
    "TargetStats",
    # Job
    "JobType",
    "JobStatus",
    "JobCreate",
    "JobResponse",
    "JobStats",
    # Persona
    "Status",
    "PersonaBase",
    "PersonaListOutput",
    "PersonaUpdate",
    "PersonaResponse",
    "PersonaApprove",
    "PersonaReject",
    "PersonaBulkApprove",
    # Question
    "QuestionBase",
    "QuestionListOutput",
    "QuestionUpdate",
    "QuestionResponse",
    "QuestionApprove",
    "QuestionReject",
    "QuestionBulkApprove",
    "SimilarQuestionsRequest",
    "SimilarQuestion",
    "QuerySimilarQuestions",
    "SimilarQuestionsResponse",
    # KB Document
    "KBDocumentBase",
    "KBDocumentResponse",
    "KBDocumentTextResponse",
    "KBDocumentListResponse",
    "KBCompiledTextResponse",
]
