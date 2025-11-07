"""
Pytest fixtures for testing.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from src.common.database.connection import Base
from src.common.database.models import Target, Job, Persona, Question, StatusEnum, JobTypeEnum, JobStatusEnum


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
        knowledge_base_path="/data/test"
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
