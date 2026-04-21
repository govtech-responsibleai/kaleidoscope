"""
Main FastAPI application entry point for Kaleidoscope API.

This is the root API that includes all service modules:
- Query Generation (personas, questions)
- Scoring (future)
- etc.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from src.common.config import get_settings
from src.common.auth import auth_router, get_scoped_db
from src.common.database.connection import init_db, SessionLocal, engine
from src.common.database.seed import ensure_system_judges, run_manual_migrations
from src.common.services.system_rubrics import ensure_system_rubrics
from src.common.llm.instrumentation import setup_phoenix_instrumentation

# Import routers from query generation
from src.query_generation.api.routes import targets, personas, questions, jobs, kb_documents, web_documents, answers

# Import routers from scoring
from src.scoring.api.routes import snapshots, judges, qa_jobs, annotations, metrics

settings = get_settings()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle manager for FastAPI app.

    Runs on startup and shutdown.
    """
    # Startup
    logger.info("🚀 Starting Kaleidoscope API...")

    # Initialize database
    init_db()
    logger.info("✓ Database initialized")

    # Run manual migrations (e.g. adding columns to existing tables)
    run_manual_migrations(engine)

    # Seed default data
    db = SessionLocal()
    try:
        ensure_system_rubrics(db)
        ensure_system_judges(db)
    except Exception as e:
        logger.error(f"Failed to seed default data: {e}")
    finally:
        db.close()

    # Load connector extensions (e.g. KALEIDOSCOPE_EXTENSIONS=aibots)
    from src.extensions import load_extensions
    load_extensions()
    logger.info("✓ Extensions loaded")

    # Setup Phoenix instrumentation for LLM tracking
    phoenix_url = setup_phoenix_instrumentation(project_name="kaleidoscope-api")
    if phoenix_url:
        logger.info(f"✓ Phoenix instrumentation enabled: {phoenix_url}")

    logger.info("✓ API ready")

    yield

    # Shutdown
    logger.info("👋 Shutting down Kaleidoscope API...")
    engine.dispose()
    logger.info("✓ Database connections closed")


# Create FastAPI app
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://kaleidoscope.app.tc1.airbase.sg",
        "http://localhost:3000",
        "http://127.0.2.2:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler for database connection errors
# This ensures CORS headers are included even on 500 errors
@app.exception_handler(OperationalError)
async def database_exception_handler(request: Request, exc: OperationalError):
    """Handle database connection errors gracefully."""
    logger.error(f"Database error: {exc}")
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Database temporarily unavailable. Please try again.",
            "error_type": "database_connection"
        }
    )

# Auth router (no auth required - users need to log in)
app.include_router(auth_router, prefix=f"{settings.api_prefix}/auth", tags=["Auth"])

# Include routers from query generation service (all require auth + user scoping)
app.include_router(targets.router, prefix=f"{settings.api_prefix}/targets", tags=["Targets"], dependencies=[Depends(get_scoped_db)])
app.include_router(personas.router, prefix=f"{settings.api_prefix}/personas", tags=["Personas"], dependencies=[Depends(get_scoped_db)])
app.include_router(questions.router, prefix=f"{settings.api_prefix}/questions", tags=["Questions"], dependencies=[Depends(get_scoped_db)])
app.include_router(jobs.router, prefix=f"{settings.api_prefix}", tags=["Jobs"], dependencies=[Depends(get_scoped_db)])
app.include_router(kb_documents.router, prefix=settings.api_prefix, tags=["Knowledge Base"], dependencies=[Depends(get_scoped_db)])
app.include_router(web_documents.router, prefix=settings.api_prefix, tags=["Web Documents"], dependencies=[Depends(get_scoped_db)])
app.include_router(answers.router, prefix=f"{settings.api_prefix}/answers", tags=["Answers"], dependencies=[Depends(get_scoped_db)])

# Include routers from scoring service (all require auth + user scoping)
app.include_router(snapshots.router, prefix=f"{settings.api_prefix}", tags=["Snapshots"], dependencies=[Depends(get_scoped_db)])
app.include_router(judges.router, prefix=f"{settings.api_prefix}", tags=["Judges"], dependencies=[Depends(get_scoped_db)])
app.include_router(qa_jobs.router, prefix=f"{settings.api_prefix}", tags=["QA Jobs"], dependencies=[Depends(get_scoped_db)])
app.include_router(annotations.router, prefix=f"{settings.api_prefix}", tags=["Annotations"], dependencies=[Depends(get_scoped_db)])
app.include_router(metrics.router, prefix=f"{settings.api_prefix}", tags=["Metrics"], dependencies=[Depends(get_scoped_db)])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Kaleidoscope API",
        "version": settings.api_version,
        "services": ["query_generation", "scoring"],
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    # Run server
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
