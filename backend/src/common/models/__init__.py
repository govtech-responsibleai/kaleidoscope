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
    QuestionType,
    QuestionScope,
    QuestionSource,
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
from src.common.models.snapshot import (
    SnapshotCreate,
    SnapshotUpdate,
    SnapshotResponse
)
from src.common.models.answer import (
    AnswerCreate,
    AnswerResponse,
    AnswerListResponse,
    AnswerBulkSelection
)
from src.common.models.judge import (
    JudgeType,
    JudgeCreate,
    JudgeUpdate,
    JudgeResponse,
    ClaimJudgmentResult,
    ResponseJudgmentResult
)
from src.common.models.answer_claim import (
    AnswerClaimResponse,
    AnswerClaimListResponse,
    CheckworthyResult
)
from src.common.models.answer_score import (
    AnswerClaimScoreResponse,
    AnswerScoreResponse,
    AnswerScoreListResponse
)
from src.common.models.annotation import (
    AnnotationCreate,
    AnnotationUpdate,
    AnnotationResponse,
    AnnotationBulkCreate,
    AnnotationListResponse
)
from src.common.models.qa_job import (
    JobStatus as QAJobStatus,
    QAJobType,
    QAJobStage,
    QAJobCreate,
    QAJobStart,
    QAJobPauseRequest,
    QAJobResponse,
    QAJobDetailResponse,
    QAJobListResponse
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
    "QuestionType",
    "QuestionScope",
    "QuestionSource",
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
    # Snapshot
    "SnapshotCreate",
    "SnapshotUpdate",
    "SnapshotResponse",
    # Answer
    "AnswerCreate",
    "AnswerResponse",
    "AnswerListResponse",
    "AnswerBulkSelection",
    # Judge
    "JudgeType",
    "JudgeCreate",
    "JudgeUpdate",
    "JudgeResponse",
    "ClaimJudgmentResult",
    "ResponseJudgmentResult",
    # AnswerClaim
    "AnswerClaimResponse",
    "AnswerClaimListResponse",
    "CheckworthyResult",
    # AnswerScore
    "AnswerClaimScoreResponse",
    "AnswerScoreResponse",
    "AnswerScoreListResponse",
    # Annotation
    "AnnotationCreate",
    "AnnotationUpdate",
    "AnnotationResponse",
    "AnnotationBulkCreate",
    "AnnotationListResponse",
    # QAJob
    "QAJobStatus",
    "QAJobType",
    "QAJobStage",
    "QAJobCreate",
    "QAJobStart",
    "QAJobPauseRequest",
    "QAJobResponse",
    "QAJobDetailResponse",
    "QAJobListResponse",
]
