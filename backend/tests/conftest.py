"""
Pytest fixtures for testing.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from src.common.database.connection import Base
from src.common.database.models import (
    Target, Job, Persona, Question, Answer, AnswerClaim, AnswerScore, AnswerClaimScore,
    Annotation, QAJob, Snapshot, Judge, KnowledgeBaseDocument,
    StatusEnum, JobTypeEnum, JobStatusEnum, QAJobTypeEnum, QAJobStageEnum, JudgeTypeEnum,
    QuestionTypeEnum, QuestionScopeEnum
)


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
    from src.common.config import get_settings
    from src.query_generation.api.routes import targets, personas, questions, jobs
    from src.common.database.connection import get_db

    settings = get_settings()

    # Create test app WITHOUT lifespan
    test_app = FastAPI(
        title=settings.api_title,
        version=settings.api_version
    )

    # Include routers
    test_app.include_router(targets.router, prefix=f"{settings.api_prefix}/targets", tags=["Targets"])
    test_app.include_router(personas.router, prefix=f"{settings.api_prefix}/personas", tags=["Personas"])
    test_app.include_router(questions.router, prefix=f"{settings.api_prefix}/questions", tags=["Questions"])
    # Jobs router has no prefix because routes define full paths (e.g., /targets/{id}/jobs/...)
    test_app.include_router(jobs.router, prefix=f"{settings.api_prefix}", tags=["Jobs"])

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
def sample_target(test_db):
    """Create a sample target for testing.

    Args:
        test_db: Database session for test
    """
    target = Target(
        name="Test RAI Bot",
        agency="GovTech",
        purpose="Test chatbot for responsible AI",
        target_users="Government officers",
        api_endpoint="https://api.test.com/chat",
        endpoint_type="aibots"
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
    # Create a judge first
    judge = Judge(
        name="Test Judge",
        model_name="gemini/gemini-2.5-flash-lite",
        prompt_template="Test template",
        params={},
        judge_type=JudgeTypeEnum.claim_based,
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
def sample_judge_claim_based(test_db):
    """Create a claim-based judge for testing."""
    judge = Judge(
        name="Claim-Based Judge",
        model_name="gemini/gemini-2.5-flash-lite",
        prompt_template="Test prompt template",
        params={"temperature": 0.7},
        judge_type=JudgeTypeEnum.claim_based,
        is_baseline=False,
        is_editable=True
    )
    test_db.add(judge)
    test_db.commit()
    test_db.refresh(judge)
    return judge


@pytest.fixture
def sample_judge_response_level(test_db):
    """Create a response-level judge for testing."""
    judge = Judge(
        name="Response-Level Judge",
        model_name="gemini/gemini-2.5-flash-lite",
        prompt_template="Test prompt template",
        params={"temperature": 0.5},
        judge_type=JudgeTypeEnum.response_level,
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
    from datetime import datetime
    claims = [
        AnswerClaim(
            answer_id=sample_answer.id,
            claim_index=0,
            claim_text="AI poses privacy risks.",
            checkworthy=True,
            created_at=datetime.utcnow(),
            checked_at=datetime.utcnow()
        ),
        AnswerClaim(
            answer_id=sample_answer.id,
            claim_index=1,
            claim_text="Bias is a concern.",
            checkworthy=True,
            created_at=datetime.utcnow(),
            checked_at=datetime.utcnow()
        ),
        AnswerClaim(
            answer_id=sample_answer.id,
            claim_index=2,
            claim_text="Transparency is important.",
            checkworthy=True,
            created_at=datetime.utcnow(),
            checked_at=datetime.utcnow()
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
    annotations = []
    all_answers = [sample_answer] + additional_answers
    labels = [True, True, True, True, True, True, True, False, False, False]

    for answer, label in zip(all_answers, labels):
        answer.is_selected_for_annotation = True
        annotation = Annotation(
            answer_id=answer.id,
            label=label,
            notes="Test notes"
        )
        test_db.add(annotation)
        annotations.append(annotation)

    test_db.commit()
    for annotation in annotations:
        test_db.refresh(annotation)
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
            judge_id=sample_judge_claim_based.id,
            overall_label=label,
            explanation="Test explanation"
        )
        test_db.add(score)
        scores.append(score)

    test_db.commit()
    for score in scores:
        test_db.refresh(score)
    return scores
