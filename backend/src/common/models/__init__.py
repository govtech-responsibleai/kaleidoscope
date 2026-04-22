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
    ProbeRequest,
    ProbeResponse,
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
    AnnotationAnswerGroupResponse,
    AnnotationCreate,
    AnnotationUpdate,
    AnnotationResponse,
    AnnotationBulkCreateItem,
    AnnotationBulkCreate,
    AnnotationListResponse
)
from src.common.models.qa_job import (
    JobStatus as QAJobStatus,
    QAJobType,
    QAJobStage,
    RubricVerdictState,
    QARubricScore,
    QARubricStatus,
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
    AggregatedScore,
    AggregatedResult,
    SnapshotResultsResponse,
    AlignedJudge,
    JudgeAlignmentResponse,
    JudgeAccuracyResponse,
    SnapshotMetric,
    MetricsByRubric,
    SnapshotMetricsResponse,
    ConfusionMatrixResponse,
    JudgeScoreSummary,
    JudgeRowResult,
    AggregatedRowResult,
    ScoringRowResult,
    ScoringContract,
    SnapshotScoringContractsResponse,
)

__all__ = [
    # Target
    "TargetBase",
    "TargetCreate",
    "TargetUpdate",
    "TargetResponse",
    "TestConnectionRequest",
    "TestConnectionResponse",
    "ProbeRequest",
    "ProbeResponse",
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
    "AnnotationAnswerGroupResponse",
    "AnnotationBulkCreateItem",
    "AnnotationBulkCreate",
    "AnnotationListResponse",
    # QAJob
    "QAJobStatus",
    "QAJobType",
    "QAJobStage",
    "RubricVerdictState",
    "QARubricScore",
    "QARubricStatus",
    "QAJobCreate",
    "QAJobStart",
    "QAJobPauseRequest",
    "QAJobResponse",
    "QAJobDetailResponse",
    "QAJobListResponse",
    "RubricQAJobStart",
    "RubricSpec",
    "UnifiedQAJobStart",
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
    "AggregatedScore",
    "AggregatedResult",
    "SnapshotResultsResponse",
    "AlignedJudge",
    "JudgeAlignmentResponse",
    "JudgeAccuracyResponse",
    "SnapshotMetric",
    "MetricsByRubric",
    "SnapshotMetricsResponse",
    "ConfusionMatrixResponse",
    "JudgeScoreSummary",
    "JudgeRowResult",
    "AggregatedRowResult",
    "ScoringRowResult",
    "ScoringContract",
    "SnapshotScoringContractsResponse",
    # TargetRubric
    "RubricOption",
    "PremadeRubricTemplateResponse",
    "TargetRubricCreate",
    "TargetRubricUpdate",
    "TargetRubricResponse",
]
