"""
Main FastAPI application entry point for Kaleidoscope API.

This is the root API that includes all service modules:
- Query Generation (personas, questions)
- Scoring (future)
- etc.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.common.config import get_settings
from src.common.database.connection import init_db
from src.common.llm.instrumentation import setup_phoenix_instrumentation

# Import routers from services
from src.query_generation.api.routes import targets, personas, questions, jobs, kb_documents, answers

settings = get_settings()
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

    # Setup Phoenix instrumentation for LLM tracking
    phoenix_url = setup_phoenix_instrumentation(project_name="kaleidoscope-api")
    if phoenix_url:
        logger.info(f"✓ Phoenix instrumentation enabled: {phoenix_url}")

    logger.info("✓ API ready")

    yield

    # Shutdown
    logger.info("👋 Shutting down Kaleidoscope API...")


# Create FastAPI app
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers from query generation service
app.include_router(targets.router, prefix=f"{settings.api_prefix}/targets", tags=["Targets"])
app.include_router(personas.router, prefix=f"{settings.api_prefix}/personas", tags=["Personas"])
app.include_router(questions.router, prefix=f"{settings.api_prefix}/questions", tags=["Questions"])
# Jobs router has no prefix because routes define full paths (e.g., /targets/{id}/jobs/...)
app.include_router(jobs.router, prefix=f"{settings.api_prefix}", tags=["Jobs"])
app.include_router(kb_documents.router, prefix=settings.api_prefix, tags=["Knowledge Base"])
app.include_router(answers.router, prefix=f"{settings.api_prefix}/answers", tags=["Answers"])

# Future: Include routers from other services
# from src.scoring.api.routes import scores
# app.include_router(scores.router, prefix=f"{settings.api_prefix}/scores", tags=["Scoring"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Kaleidoscope API",
        "version": settings.api_version,
        "services": ["query_generation"],
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
