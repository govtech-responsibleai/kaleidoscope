"""
Pytest fixtures for testing.
"""

import os
import pytest
import shutil
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("ADMIN_API_KEY", "test-admin-key")

from src.common.database.connection import Base
from src.common.database.repositories.target_rubric_repo import TargetRubricRepository
from src.common.database.models import (
    Target, Job, Persona, Question, Answer, AnswerClaim, AnswerScore, AnswerClaimScore,
    QAJob, Snapshot, Judge, KnowledgeBaseDocument, User,
    TargetRubric, Annotation,
    StatusEnum, JobTypeEnum, JobStatusEnum, QAJobTypeEnum, QAJobStageEnum,
    QuestionTypeEnum, QuestionScopeEnum
)
from src.common.auth.utils import create_access_token
from src.rubric.services.prompt_files import generated_custom_prompts_dir

# Pre-computed bcrypt hashes for test passwords (avoids passlib/bcrypt compatibility issues)
# These are bcrypt hashes computed with cost factor 12
TEST_PASSWORD_HASHES = {
    "testpassword": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.njBGSCRsLXGDOK",
    "adminpassword": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.njBGSCRsLXGDOK",
    "inactivepassword": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.njBGSCRsLXGDOK",
    "password_a": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.njBGSCRsLXGDOK",
    "password_b": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.njBGSCRsLXGDOK",
    "adminpass": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.njBGSCRsLXGDOK",
}

PROVIDER_SETTING_DEFAULTS = {
    "openai_api_key": None,
    "azure_api_key": None,
    "azure_api_base": None,
    "anthropic_api_key": None,
    "gemini_api_key": None,
    "aws_bearer_token_bedrock": None,
    "openrouter_api_key": None,
    "openrouter_api_base": None,
    "fireworks_ai_api_key": None,
    "serper_api_key": None,
}


@dataclass
class SampleAnnotationRecord:
    answer: Answer
    answer_id: int
    label: bool
    notes: str | None


def get_test_password_hash(password: str) -> str:
    """Get a pre-computed hash for test passwords."""
    # All test passwords use the same hash for simplicity in tests
    # The actual password verification is tested separately
    return TEST_PASSWORD_HASHES.get(password, TEST_PASSWORD_HASHES["testpassword"])


def get_accuracy_rubric(db, target_id: int) -> TargetRubric:
    """Return the built-in Accuracy rubric for a target."""
    rubrics = TargetRubricRepository.get_by_target(db, target_id, group="fixed", name="Accuracy")
    if len(rubrics) != 1:
        raise AssertionError(f"Expected exactly one fixed Accuracy rubric for target {target_id}")
    return rubrics[0]


@contextmanager
def override_settings(**values):
    """Temporarily override cached application settings."""
    from src.common.config import get_settings

    settings = get_settings()
    original = {key: getattr(settings, key) for key in values}
    try:
        for key, value in values.items():
            setattr(settings, key, value)
        yield settings
    finally:
        for key, value in original.items():
            setattr(settings, key, value)


@pytest.fixture(autouse=True)
def cleanup_generated_custom_prompt_files():
    """Keep generated custom rubric prompt files isolated per test."""
    shutil.rmtree(generated_custom_prompts_dir().parent, ignore_errors=True)
    yield
    shutil.rmtree(generated_custom_prompts_dir().parent, ignore_errors=True)


@pytest.fixture(autouse=True)
def mock_provider_resolution(request):
    """Stub out DB-backed provider resolution for unit tests.

    Services instantiated in unit tests call provider helpers through direct imports in
    their own modules. Patch those call sites so unrelated unit tests stay focused.
    """
    if "unit" not in (m.name for m in request.node.iter_markers()):
        yield
        return

    from unittest.mock import patch
    from src.common.llm.provider_service import ProviderRuntimeConfig

    default_runtime = ProviderRuntimeConfig(
        provider_key="gemini",
        model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
        litellm_kwargs={},
    )
    default_model = "litellm_proxy/gemini-3.1-flash-lite-preview-global"

    patch_targets = [
        ("src.query_generation.services.persona_generator.resolve_model_runtime_config_for_target", default_runtime),
        ("src.query_generation.services.question_generator.resolve_model_runtime_config_for_target", default_runtime),
        ("src.scoring.services.judge_scoring.resolve_model_runtime_config_for_target", default_runtime),
        ("src.query_generation.services.web_search_service.require_default_generation_model", default_model),
        ("src.query_generation.services.web_search_service.resolve_model_runtime_config", default_runtime),
        ("src.query_generation.services.web_search_service.resolve_serper_api_key", None),
        ("src.scoring.services.claim_processor.require_default_generation_model", default_model),
        ("src.scoring.services.claim_processor.resolve_model_runtime_config", default_runtime),
        ("src.rubric.services.rubric_augmenter.require_default_generation_model", default_model),
        ("src.rubric.services.rubric_augmenter.resolve_model_runtime_config", default_runtime),
    ]

    with ExitStack() as stack:
        for target, value in patch_targets:
            stack.enter_context(patch(target, return_value=value))
        yield


@pytest.fixture
def with_provider_bypass():
    """Bypass provider validation for tests that are not about provider behavior.

    This fixture is explicit on purpose: provider-focused integration tests should not use it.
    """
    from unittest.mock import patch
    from src.common.llm.provider_service import ResolvedProvider
    from src.common.llm.provider_service import ProviderRuntimeConfig
    from src.common.models.provider_setup import ProviderModelOption
    from src.common.llm.provider_catalog import get_provider_entry

    default_runtime = ProviderRuntimeConfig(
        provider_key="gemini",
        model_name="gemini/gemini-3.1-flash-lite-preview",
        litellm_kwargs={},
    )
    gemini_provider = get_provider_entry("gemini")
    default_model_option = ProviderModelOption(
        value=default_runtime.model_name,
        label="gemini-3.1-flash-lite-preview",
        provider_key=gemini_provider.key,
        provider_name=gemini_provider.display_name,
        logo_path=gemini_provider.logo_path,
    )
    seeded_model_options = [
        default_model_option,
        ProviderModelOption(
            value="gemini/gemini-3.1-pro-preview",
            label="gemini-3.1-pro-preview",
            provider_key=gemini_provider.key,
            provider_name=gemini_provider.display_name,
            logo_path=gemini_provider.logo_path,
        ),
        ProviderModelOption(
            value="gemini/gemini-2.5-flash",
            label="gemini-2.5-flash",
            provider_key=gemini_provider.key,
            provider_name=gemini_provider.display_name,
            logo_path=gemini_provider.logo_path,
        ),
    ]
    seeded_models = [option.value for option in seeded_model_options]
    resolved_provider = ResolvedProvider(
        catalog=gemini_provider,
        source="shared",
        credentials={"GEMINI_API_KEY": "test-gemini-key"},
        is_valid=True,
        shared_values={"GEMINI_API_KEY": "test-gemini-key"},
        personal_values={},
    )

    patch_targets = [
        ("src.query_generation.api.routes.targets.require_user_has_valid_provider", None),
        ("src.query_generation.api.routes.jobs.require_valid_model_for_user", None),
        ("src.query_generation.api.routes.jobs.require_default_generation_model", default_runtime.model_name),
        ("src.scoring.api.routes.judges.require_valid_model_for_user", None),
        ("src.scoring.api.routes.judges.get_valid_model_options", seeded_model_options),
        ("src.rubric.services.system_rubrics.list_resolved_providers", [resolved_provider]),
        ("src.rubric.services.system_rubrics.get_valid_model_options", seeded_model_options),
        ("src.rubric.services.system_rubrics._select_seed_models", seeded_models),
        ("src.query_generation.services.persona_generator.resolve_model_runtime_config_for_target", default_runtime),
        ("src.query_generation.services.question_generator.resolve_model_runtime_config_for_target", default_runtime),
        ("src.scoring.services.judge_scoring.resolve_model_runtime_config_for_target", default_runtime),
        ("src.rubric.services.rubric_augmenter.require_default_generation_model", default_runtime.model_name),
        ("src.rubric.services.rubric_augmenter.resolve_model_runtime_config", default_runtime),
    ]

    with ExitStack() as stack:
        for target, value in patch_targets:
            stack.enter_context(patch(target, return_value=value))
        yield


@pytest.fixture
def provider_settings():
    """Return a context manager that clears provider settings unless explicitly set."""

    @contextmanager
    def _provider_settings(**overrides):
        settings = {**PROVIDER_SETTING_DEFAULTS, **overrides}
        with override_settings(**settings):
            yield

    return _provider_settings


@pytest.fixture(scope="function")
def test_db_factory():
    """
    Create a test database session factory for each test function.

    Uses in-memory SQLite database with StaticPool.
    Returns a session factory (sessionmaker) bound to the test engine.
    """
    # Create in-memory SQLite database with check_same_thread=False for FastAPI TestClient
    # Use StaticPool to ensure all sessions share the same in-memory database
    from sqlalchemy.pool import StaticPool
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # Share single connection for in-memory database
        echo=False
    )

    # Create all tables
    Base.metadata.create_all(engine)

    # Create session factory
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Yield the session factory
    yield TestSessionLocal

    # Cleanup
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def test_db(test_db_factory):
    """
    Create a test database session for unit tests.

    Uses the session factory from test_db_factory.
    Returns a single session.
    """
    db = test_db_factory()
    yield db
    db.close()


@pytest.fixture(scope="function")
def test_client(test_db_factory):
    """
    Create a test client for API testing.

    Overrides the database dependency to use test database.
    Creates a FastAPI app without lifespan to avoid production DB connections.

    Args:
        test_db_factory: Session factory for test database
    """
    from fastapi import FastAPI
    from src.common.api.routes import providers
    from src.common.config import get_settings
    from src.query_generation.api.routes import targets, personas, questions, jobs, kb_documents, answers
    from src.rubric.api.routes import rubrics
    from src.scoring.api.routes import snapshots, metrics, annotations, qa_jobs, judges
    from src.common.database.connection import get_db

    settings = get_settings()

    # Create test app WITHOUT lifespan
    test_app = FastAPI(
        title=settings.api_title,
        version=settings.api_version
    )

    # Include routers
    test_app.include_router(providers.router, prefix=settings.api_prefix, tags=["Providers"])
    test_app.include_router(targets.router, prefix=f"{settings.api_prefix}/targets", tags=["Targets"])
    test_app.include_router(rubrics.router, prefix=f"{settings.api_prefix}/targets", tags=["Rubrics"])
    test_app.include_router(personas.router, prefix=f"{settings.api_prefix}/personas", tags=["Personas"])
    test_app.include_router(questions.router, prefix=f"{settings.api_prefix}/questions", tags=["Questions"])
    # Jobs router has no prefix because routes define full paths (e.g., /targets/{id}/jobs/...)
    test_app.include_router(jobs.router, prefix=f"{settings.api_prefix}", tags=["Jobs"])
    # Snapshots and KB documents routers
    test_app.include_router(snapshots.router, prefix=f"{settings.api_prefix}", tags=["Snapshots"])
    test_app.include_router(kb_documents.router, prefix=f"{settings.api_prefix}", tags=["Knowledge Base"])
    # Answers and metrics routers
    test_app.include_router(answers.router, prefix=f"{settings.api_prefix}/answers", tags=["Answers"])
    test_app.include_router(metrics.router, prefix=f"{settings.api_prefix}", tags=["Metrics"])
    test_app.include_router(annotations.router, prefix=f"{settings.api_prefix}", tags=["Annotations"])
    test_app.include_router(qa_jobs.router, prefix=f"{settings.api_prefix}", tags=["QA Jobs"])
    test_app.include_router(judges.router, prefix=f"{settings.api_prefix}", tags=["Judges"])

    # Override database dependency to use test session factory
    def override_get_db():
        db = test_db_factory()
        try:
            yield db
        finally:
            db.close()

    test_app.dependency_overrides[get_db] = override_get_db

    client = TestClient(test_app)

    yield client

    # Cleanup
    test_app.dependency_overrides.clear()


@pytest.fixture
def sample_target(test_db, test_user):
    """Create a sample target for testing.

    Args:
        test_db: Database session for test
        test_user: Owner user (required for provider-scoped service resolution)
    """
    target = Target(
        name="Test RAI Bot",
        agency="GovTech",
        purpose="Test target for responsible AI",
        target_users="Government officers",
        api_endpoint="https://api.test.com/chat",
        endpoint_type="http",
        endpoint_config={"response_content_path": "output"},
        user_id=test_user.id,
    )
    test_db.add(target)
    test_db.commit()
    test_db.refresh(target)
    return target


@pytest.fixture
def other_target(test_db, test_user):
    """Create a second target for cross-target tests."""
    target = Target(
        name="Other Bot",
        agency="Other Agency",
        purpose="Different purpose",
        target_users="Different users",
        user_id=test_user.id,
    )
    test_db.add(target)
    test_db.commit()
    test_db.refresh(target)
    return target


@pytest.fixture
def sample_job(test_db, sample_target):
    """Create a sample job for testing.

    Args:
        test_db: Database session for test
        sample_target: Sample target fixture
    """
    job = Job(
        target_id=sample_target.id,
        type=JobTypeEnum.persona_generation,
        count_requested=3,
        model_used="gpt-4o-mini",
        status=JobStatusEnum.running
    )
    test_db.add(job)
    test_db.commit()
    test_db.refresh(job)
    return job


@pytest.fixture
def sample_personas(test_db, sample_target, sample_job):
    """Create sample personas for testing.

    Args:
        test_db: Database session for test
        sample_target: Sample target fixture
        sample_job: Sample job fixture
    """
    personas = [
        Persona(
            job_id=sample_job.id,
            target_id=sample_target.id,
            title="Technical Officer",
            info="Software engineer working on AI projects",
            style="Direct and technical",
            use_case="Looking for technical implementation details",
            status=StatusEnum.approved
        ),
        Persona(
            job_id=sample_job.id,
            target_id=sample_target.id,
            title="Policy Maker",
            info="Government policy officer",
            style="Formal and cautious",
            use_case="Seeking policy guidance",
            status=StatusEnum.pending
        )
    ]
    test_db.add_all(personas)
    test_db.commit()
    for persona in personas:
        test_db.refresh(persona)
    return personas


@pytest.fixture
def mock_llm_response():
    """Mock LLM response for persona generation."""
    return {
        "content": """[
            {
                "title": "AI Ethics Researcher",
                "info": "Academic researcher focusing on AI ethics and policy",
                "style": "Analytical and research-oriented",
                "use_case": "Seeking evidence-based guidance on AI risks"
            },
            {
                "title": "Product Manager",
                "info": "Managing AI product development",
                "style": "Pragmatic and business-focused",
                "use_case": "Looking for practical risk mitigation strategies"
            },
            {
                "title": "Legal Counsel",
                "info": "Government legal advisor",
                "style": "Precise and compliance-focused",
                "use_case": "Needs clarity on legal requirements for AI systems"
            }
        ]""",
        "prompt_tokens": 500,
        "completion_tokens": 200,
        "total_tokens": 700,
        "model": "gpt-4o-mini",
        "cost": 0.0002
    }


# ============================================================================
# Scoring Service Fixtures
# ============================================================================

@pytest.fixture
def sample_snapshot(test_db, sample_target):
    """Create a sample snapshot for testing."""
    snapshot = Snapshot(
        target_id=sample_target.id,
        name="v1.0",
        description="Test snapshot"
    )
    test_db.add(snapshot)
    test_db.commit()
    test_db.refresh(snapshot)
    return snapshot


@pytest.fixture
def sample_question(test_db, sample_target, sample_job, sample_personas):
    """Create a sample question for testing."""
    question = Question(
        job_id=sample_job.id,
        persona_id=sample_personas[0].id,
        target_id=sample_target.id,
        text="What are the main risks associated with AI systems?",
        type=QuestionTypeEnum.typical,
        scope=QuestionScopeEnum.in_kb,
        status=StatusEnum.approved
    )
    test_db.add(question)
    test_db.commit()
    test_db.refresh(question)
    return question


@pytest.fixture
def sample_questions(test_db, sample_target, sample_job, sample_personas):
    """Create multiple sample questions for testing."""
    questions = [
        Question(
            job_id=sample_job.id,
            persona_id=sample_personas[0].id,
            target_id=sample_target.id,
            text="What are the main risks associated with AI systems?",
            type=QuestionTypeEnum.typical,
            scope=QuestionScopeEnum.in_kb,
            status=StatusEnum.approved
        ),
        Question(
            job_id=sample_job.id,
            persona_id=sample_personas[1].id,
            target_id=sample_target.id,
            text="How do I implement a new policy?",
            type=QuestionTypeEnum.edge,
            scope=QuestionScopeEnum.out_kb,
            status=StatusEnum.pending
        ),
    ]
    test_db.add_all(questions)
    test_db.commit()
    for q in questions:
        test_db.refresh(q)
    return questions


@pytest.fixture
def sample_answer(test_db, sample_question, sample_snapshot):
    """Create a sample answer with multi-sentence content."""
    answer = Answer(
        question_id=sample_question.id,
        snapshot_id=sample_snapshot.id,
        answer_content="AI poses privacy risks. Bias is a concern. Transparency is important.",
        chat_id="chat123",
        message_id="msg456",
        is_selected_for_annotation=False
    )
    test_db.add(answer)
    test_db.commit()
    test_db.refresh(answer)
    return answer


@pytest.fixture
def sample_qa_job(test_db, sample_snapshot, sample_question, sample_answer):
    """Create a sample QA job for testing."""
    from src.rubric.services.system_rubrics import ensure_system_rubrics

    # Create the fixed Accuracy rubric for the target (scoring_mode='claim_based')
    ensure_system_rubrics(test_db, sample_snapshot.target_id)
    accuracy_rubric = get_accuracy_rubric(test_db, sample_snapshot.target_id)

    # Create a judge bound to the accuracy rubric
    judge = Judge(
        name="Test Judge",
        model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
        prompt_template="Test template",
        params={},
        rubric_id=accuracy_rubric.id,
        is_baseline=True,
        is_editable=False
    )
    test_db.add(judge)
    test_db.commit()
    test_db.refresh(judge)

    qa_job = QAJob(
        snapshot_id=sample_snapshot.id,
        question_id=sample_question.id,
        judge_id=judge.id,
        answer_id=sample_answer.id,
        type=QAJobTypeEnum.claim_scoring_full,
        status=JobStatusEnum.running,
        stage=QAJobStageEnum.starting
    )
    test_db.add(qa_job)
    test_db.commit()
    test_db.refresh(qa_job)
    return qa_job


@pytest.fixture
def sample_qa_job_no_answer(test_db, sample_target, sample_job, sample_personas):
    """Create a QA job without an existing answer for testing API errors."""
    from src.rubric.services.system_rubrics import ensure_system_rubrics

    # Create snapshot
    snapshot = Snapshot(
        target_id=sample_target.id,
        name="error_test_snapshot",
        description="Snapshot for error testing"
    )
    test_db.add(snapshot)
    test_db.commit()
    test_db.refresh(snapshot)

    # Create question
    question = Question(
        job_id=sample_job.id,
        persona_id=sample_personas[0].id,
        target_id=sample_target.id,
        text="Test question for error handling?",
        type=QuestionTypeEnum.typical,
        scope=QuestionScopeEnum.in_kb,
        status=StatusEnum.approved
    )
    test_db.add(question)
    test_db.commit()
    test_db.refresh(question)

    # Create the fixed Accuracy rubric for the target (scoring_mode='claim_based')
    ensure_system_rubrics(test_db, sample_target.id)
    accuracy_rubric = get_accuracy_rubric(test_db, sample_target.id)

    # Create judge bound to the accuracy rubric
    judge = Judge(
        name="Error Test Judge",
        model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
        prompt_template="Test template",
        params={},
        rubric_id=accuracy_rubric.id,
        is_baseline=True,
        is_editable=False
    )
    test_db.add(judge)
    test_db.commit()
    test_db.refresh(judge)

    # Create QA job WITHOUT answer_id
    qa_job = QAJob(
        snapshot_id=snapshot.id,
        question_id=question.id,
        judge_id=judge.id,
        answer_id=None,  # No answer yet
        type=QAJobTypeEnum.claim_scoring_full,
        status=JobStatusEnum.running,
        stage=QAJobStageEnum.starting
    )
    test_db.add(qa_job)
    test_db.commit()
    test_db.refresh(qa_job)

    return {
        "job": qa_job,
        "question": question,
        "snapshot": snapshot,
        "target": sample_target
    }


@pytest.fixture
def sample_judge_claim_based(test_db, sample_target):
    """Create a claim-based judge (with accuracy rubric) for testing."""
    from src.rubric.services.system_rubrics import ensure_system_rubrics

    ensure_system_rubrics(test_db, sample_target.id)
    accuracy_rubric = get_accuracy_rubric(test_db, sample_target.id)

    judge = Judge(
        name="Claim-Based Judge",
        model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
        prompt_template="Test prompt template",
        params={"temperature": 0.7},
        rubric_id=accuracy_rubric.id,
        is_baseline=False,
        is_editable=True
    )
    test_db.add(judge)
    test_db.commit()
    test_db.refresh(judge)
    return judge


@pytest.fixture
def sample_judge_response_level(test_db, sample_rubric):
    """Create a rubric-bound response-level judge for testing."""
    judge = Judge(
        name="Response-Level Judge",
        model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
        prompt_template="Test prompt template",
        params={"temperature": 0.5},
        rubric_id=sample_rubric.id,
        is_baseline=False,
        is_editable=True
    )
    test_db.add(judge)
    test_db.commit()
    test_db.refresh(judge)
    return judge


@pytest.fixture
def sample_claims(test_db, sample_answer):
    """Create sample claims for testing."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    claims = [
        AnswerClaim(
            answer_id=sample_answer.id,
            claim_index=0,
            claim_text="AI poses privacy risks.",
            checkworthy=True,
            created_at=now,
            checked_at=now
        ),
        AnswerClaim(
            answer_id=sample_answer.id,
            claim_index=1,
            claim_text="Bias is a concern.",
            checkworthy=True,
            created_at=now,
            checked_at=now
        ),
        AnswerClaim(
            answer_id=sample_answer.id,
            claim_index=2,
            claim_text="Transparency is important.",
            checkworthy=True,
            created_at=now,
            checked_at=now
        )
    ]
    test_db.add_all(claims)
    test_db.commit()
    for claim in claims:
        test_db.refresh(claim)
    return claims


@pytest.fixture
def sample_kb_documents(test_db, sample_target):
    """Create sample KB documents for testing."""
    docs = [
        KnowledgeBaseDocument(
            target_id=sample_target.id,
            filename="doc1.pdf",
            content_type="application/pdf",
            file_size=1024,
            processed_text="Privacy is a major concern with AI systems. Personal data can be exposed."
        ),
        KnowledgeBaseDocument(
            target_id=sample_target.id,
            filename="doc2.pdf",
            content_type="application/pdf",
            file_size=2048,
            processed_text="Bias in AI can lead to unfair outcomes. Training data quality matters."
        )
    ]
    test_db.add_all(docs)
    test_db.commit()
    for doc in docs:
        test_db.refresh(doc)
    return docs


@pytest.fixture
def sample_annotations(test_db, sample_answer, sample_target, sample_job, sample_personas):
    """Create sample annotations for testing."""
    from src.rubric.services.system_rubrics import ensure_system_rubrics

    # Create additional questions and snapshots to avoid UNIQUE constraint
    additional_answers = []
    for i in range(9):
        # Create a new question for each additional answer
        question = Question(
            job_id=sample_job.id,
            target_id=sample_target.id,
            persona_id=sample_personas[0].id,  # Use first persona
            text=f"Test question {i}?",
            type=QuestionTypeEnum.typical,
            scope=QuestionScopeEnum.in_kb,
            status=StatusEnum.approved
        )
        test_db.add(question)
        test_db.flush()

        answer = Answer(
            question_id=question.id,
            snapshot_id=sample_answer.snapshot_id,
            answer_content=f"Test answer {i}",
            chat_id=f"chat{i}",
            message_id=f"msg{i}",
            is_selected_for_annotation=True
        )
        test_db.add(answer)
        additional_answers.append(answer)

    test_db.commit()

    # Create annotations (7 accurate, 3 inaccurate)
    annotations: list[SampleAnnotationRecord] = []
    all_answers = [sample_answer] + additional_answers
    labels = [True, True, True, True, True, True, True, False, False, False]
    ensure_system_rubrics(test_db, sample_target.id)
    accuracy_rubric = get_accuracy_rubric(test_db, sample_target.id)

    for answer, label in zip(all_answers, labels):
        answer.is_selected_for_annotation = True
        test_db.add(
            Annotation(
                answer_id=answer.id,
                rubric_id=accuracy_rubric.id,
                option_value="Accurate" if label else "Inaccurate",
                notes="Test notes",
            )
        )
        annotations.append(
            SampleAnnotationRecord(
                answer=answer,
                answer_id=answer.id,
                label=label,
                notes="Test notes",
            )
        )

    test_db.commit()
    return annotations


@pytest.fixture
def sample_answer_scores(test_db, sample_annotations, sample_judge_claim_based):
    """Create sample answer scores for testing."""
    # Create scores for all annotated answers (8 accurate, 2 inaccurate)
    scores = []
    labels = [True, True, True, True, True, True, True, True, False, False]

    for annotation, label in zip(sample_annotations, labels):
        score = AnswerScore(
            answer_id=annotation.answer_id,
            rubric_id=sample_judge_claim_based.rubric_id,
            judge_id=sample_judge_claim_based.id,
            overall_label="Accurate" if label else "Inaccurate",
            explanation="Test explanation"
        )
        test_db.add(score)
        scores.append(score)

    test_db.commit()
    for score in scores:
        test_db.refresh(score)
    return scores


# ============================================================================
# Auth Fixtures
# ============================================================================

@pytest.fixture
def test_user(test_db):
    """Create a regular active user for testing."""
    user = User(
        username="testuser",
        hashed_password=get_test_password_hash("testpassword"),
        is_active=True,
        is_admin=False
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def test_admin_user(test_db):
    """Create an admin user for testing."""
    user = User(
        username="adminuser",
        hashed_password=get_test_password_hash("adminpassword"),
        is_active=True,
        is_admin=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def test_inactive_user(test_db):
    """Create an inactive user for testing."""
    user = User(
        username="inactiveuser",
        hashed_password=get_test_password_hash("inactivepassword"),
        is_active=False,
        is_admin=False
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    """Generate Authorization headers for a test user."""
    token = create_access_token(test_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers(test_admin_user):
    """Generate Authorization headers for an admin user."""
    token = create_access_token(test_admin_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_client(test_db_factory, test_user):
    """
    Create a test client with auth router included.

    This client has all routes protected by authentication.
    """
    from fastapi import FastAPI, Depends
    from src.common.api.routes import providers
    from src.common.config import get_settings
    from src.common.database.connection import get_db
    from src.common.auth import auth_router, get_scoped_db
    from src.query_generation.api.routes import targets, personas, questions, jobs, kb_documents
    from src.rubric.api.routes import rubrics
    from src.scoring.api.routes import judges, snapshots

    settings = get_settings()

    test_app = FastAPI(
        title=settings.api_title,
        version=settings.api_version
    )

    # Auth router (public)
    test_app.include_router(auth_router, prefix=f"{settings.api_prefix}/auth", tags=["Auth"])

    # Protected routes
    test_app.include_router(
        providers.router,
        prefix=f"{settings.api_prefix}",
        tags=["Providers"],
        dependencies=[Depends(get_scoped_db)]
    )
    test_app.include_router(
        targets.router,
        prefix=f"{settings.api_prefix}/targets",
        tags=["Targets"],
        dependencies=[Depends(get_scoped_db)]
    )
    test_app.include_router(
        rubrics.router,
        prefix=f"{settings.api_prefix}/targets",
        tags=["Rubrics"],
        dependencies=[Depends(get_scoped_db)]
    )
    test_app.include_router(
        judges.router,
        prefix=f"{settings.api_prefix}",
        tags=["Judges"],
        dependencies=[Depends(get_scoped_db)]
    )
    test_app.include_router(
        snapshots.router,
        prefix=f"{settings.api_prefix}",
        tags=["Snapshots"],
        dependencies=[Depends(get_scoped_db)]
    )
    test_app.include_router(
        questions.router,
        prefix=f"{settings.api_prefix}/questions",
        tags=["Questions"],
        dependencies=[Depends(get_scoped_db)]
    )
    test_app.include_router(
        jobs.router,
        prefix=f"{settings.api_prefix}",
        tags=["Jobs"],
        dependencies=[Depends(get_scoped_db)]
    )
    test_app.include_router(
        kb_documents.router,
        prefix=f"{settings.api_prefix}",
        tags=["Knowledge Base"],
        dependencies=[Depends(get_scoped_db)]
    )

    # Override database dependency
    def override_get_db():
        db = test_db_factory()
        try:
            yield db
        finally:
            db.close()

    test_app.dependency_overrides[get_db] = override_get_db

    client = TestClient(test_app)
    yield client
    test_app.dependency_overrides.clear()


# ============================================================================
# Rubric Fixtures
# ============================================================================

@pytest.fixture
def sample_rubric(test_db, sample_target):
    """Create a valid rubric with 2 options and best_option set."""
    rubric = TargetRubric(
        target_id=sample_target.id,
        name="Tone of Voice",
        criteria="Evaluate the tone of the response",
        options=[
            {"option": "Professional", "description": "Formal and professional tone"},
            {"option": "Casual", "description": "Informal and casual tone"},
        ],
        best_option="Professional",
        position=0,
    )
    test_db.add(rubric)
    test_db.commit()
    test_db.refresh(rubric)
    return rubric


@pytest.fixture
def sample_rubric_second(test_db, sample_target):
    """Create a second rubric on the same target for multi-rubric tests."""
    rubric = TargetRubric(
        target_id=sample_target.id,
        name="Response Relevance",
        criteria="Is the response relevant to the question?",
        options=[
            {"option": "Relevant", "description": "Directly answers the question"},
            {"option": "Irrelevant", "description": "Does not address the question"},
        ],
        best_option="Relevant",
        position=1,
    )
    test_db.add(rubric)
    test_db.commit()
    test_db.refresh(rubric)
    return rubric
