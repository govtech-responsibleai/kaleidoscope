"""
Pydantic models for API requests and responses.
"""

from src.common.models.target import (
    TargetBase,
    TargetCreate,
    TargetUpdate,
    TargetResponse,
    TestConnectionRequest,
    TestConnectionResponse,
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
    PersonaSource,
    PersonaBase,
    PersonaListOutput,
    PersonaCreate,
    PersonaUpdate,
    PersonaResponse,
    PersonaApprove,
    PersonaReject,
    PersonaBulkApprove,
    NemotronSampleRequest
)
from src.common.models.question import (
    QuestionType,
    QuestionScope,
    InputStyle,
    QuestionSource,
    QuestionBase,
    QuestionListOutput,
    QuestionUpdate,
    QuestionResponse,
    QuestionListResponse,
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
    AnswerListItemResponse,
    AnswerListResponse,
    AnswerSelection,
    AnswerBulkSelection,
    DefaultSelectionResponse,
)
from src.common.models.judge import (
    JudgeType,
    JudgeCreate,
    JudgeUpdate,
    JudgeResponse,
    ClaimJudgmentResult,
    ResponseJudgmentResult,
    RubricJudgmentResult,
)
from src.common.models.answer_claim import (
    AnswerClaimResponse,
    AnswerClaimsWithScoresResponse,
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
    QAJobListResponse,
    RubricQAJobStart,
    RubricSpec,
    UnifiedQAJobStart,
)
from src.common.models.rubric_answer_score import RubricAnswerScoreResponse
from src.common.models.answer_label_override import (
    AnswerLabelOverrideCreate,
    AnswerLabelOverrideResponse
)
from src.common.models.target_rubric import (
    RubricOption,
    PremadeRubricTemplateResponse,
    TargetRubricCreate,
    TargetRubricUpdate,
    TargetRubricResponse,
)
from src.common.models.web_search import (
    SearchQueryListOutput,
    SearchResultSitelink,
    SearchResult,
    SearchResultsOutput
)

from src.common.models.metrics import (
    AggregationMethod,
    AggregatedAnswerScore,
    AggregatedResult,
    AlignedJudge,
    JudgeAlignmentResponse,
    JudgeAccuracyResponse,
    TargetSnapshotMetric,
    ConfusionMatrixResponse,
)

__all__ = [
    # Target
    "TargetBase",
    "TargetCreate",
    "TargetUpdate",
    "TargetResponse",
    "TestConnectionRequest",
    "TestConnectionResponse",
    "TargetStats",
    # Job
    "JobType",
    "JobStatus",
    "JobCreate",
    "JobResponse",
    "JobStats",
    # Persona
    "Status",
    "PersonaSource",
    "PersonaBase",
    "PersonaListOutput",
    "PersonaCreate",
    "PersonaUpdate",
    "PersonaResponse",
    "PersonaApprove",
    "PersonaReject",
    "PersonaBulkApprove",
    "NemotronSampleRequest",
    # Question
    "QuestionType",
    "QuestionScope",
    "InputStyle",
    "QuestionSource",
    "QuestionBase",
    "QuestionListOutput",
    "QuestionUpdate",
    "QuestionResponse",
    "QuestionListResponse",
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
    "AnswerListItemResponse",
    "AnswerListResponse",
    "AnswerSelection",
    "AnswerBulkSelection",
    "DefaultSelectionResponse",
    # Judge
    "JudgeType",
    "JudgeCreate",
    "JudgeUpdate",
    "JudgeResponse",
    "ClaimJudgmentResult",
    "ResponseJudgmentResult",
    "RubricJudgmentResult",
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
    "RubricQAJobStart",
    "RubricSpec",
    "UnifiedQAJobStart",
    # RubricAnswerScore
    "RubricAnswerScoreResponse",
    # AnswerLabelOverride
    "AnswerLabelOverrideCreate",
    "AnswerLabelOverrideResponse",
    # Web Search
    "SearchQueryListOutput",
    "SearchResultSitelink",
    "SearchResult",
    "SearchResultsOutput",
    # Metrics
    "AggregationMethod",
    "AggregatedAnswerScore",
    "AggregatedResult",
    "AlignedJudge",
    "JudgeAlignmentResponse",
    "JudgeAccuracyResponse",
    "TargetSnapshotMetric",
    "ConfusionMatrixResponse",
    # TargetRubric
    "RubricOption",
    "PremadeRubricTemplateResponse",
    "TargetRubricCreate",
    "TargetRubricUpdate",
    "TargetRubricResponse",
]
