"""
API routes for Web Document management (web search context).
"""

import logging
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.common.database.connection import get_db
from src.common.database.repositories import TargetRepository, WebDocumentRepository
from src.common.llm import CostTracker

logger = logging.getLogger(__name__)

router = APIRouter()


def _run_web_search(target_id: int, num_queries: int = 1):
    """
    Run web search for a target and save results as a WebDocument.

    Uses a fresh DB session since this runs in a background task.
    """
    from src.common.database.connection import SessionLocal
    from src.query_generation.services.web_search_service import WebSearchService

    db = SessionLocal()
    try:
        cost_tracker = CostTracker()
        service = WebSearchService(
            db=db,
            target_id=target_id,
            cost_tracker=cost_tracker,
            num_queries=num_queries,
        )
        context = service.get_search_context()
        if context:
            logger.info(f"Web search completed for target {target_id}")
        else:
            logger.warning(f"Web search returned no results for target {target_id}")
    except Exception as e:
        logger.error(f"Web search failed for target {target_id}: {e}", exc_info=True)
    finally:
        db.close()


@router.post(
    "/targets/{target_id}/web-search",
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_web_search(
    target_id: int,
    background_tasks: BackgroundTasks,
    num_queries: int = 1,
    db: Session = Depends(get_db),
):
    """
    Trigger a web search for a target.

    Runs the web search service in the background and saves results
    as a WebDocument.

    Args:
        target_id: Target ID
        background_tasks: FastAPI background tasks
        num_queries: Number of search queries to generate (default 1)
        db: Database session

    Returns:
        Acceptance message
    """
    target = TargetRepository.get_by_id(db, target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target {target_id} not found",
        )

    background_tasks.add_task(_run_web_search, target_id, num_queries)

    return {"message": f"Web search triggered for target {target_id}"}


@router.get("/targets/{target_id}/web-documents")
def list_web_documents(
    target_id: int,
    db: Session = Depends(get_db),
):
    """
    List all web documents for a target.

    Args:
        target_id: Target ID
        db: Database session

    Returns:
        List of web documents
    """
    target = TargetRepository.get_by_id(db, target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target {target_id} not found",
        )

    documents = WebDocumentRepository.get_by_target(db, target_id)
    return [
        {
            "id": doc.id,
            "target_id": doc.target_id,
            "search_queries": doc.search_queries,
            "results": doc.results,
            "created_at": doc.created_at,
        }
        for doc in documents
    ]
