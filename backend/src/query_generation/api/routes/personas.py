"""
API routes for Persona management and generation.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from src.common.database.connection import get_db
from src.common.database.repositories import PersonaRepository, QuestionRepository, TargetRepository
from src.common.models import (
    PersonaResponse,
    PersonaUpdate,
    PersonaBulkApprove,
    NemotronSampleRequest,
    QuestionResponse
)
from src.common.database.models import StatusEnum
from src.query_generation.services import sample_personas_from_nemotron

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/sample-nemotron",
    response_model=List[PersonaResponse],
    status_code=status.HTTP_201_CREATED
)
def sample_nemotron_personas(
    request: NemotronSampleRequest,
    db: Session = Depends(get_db)
):
    """
    Sample personas from the Nemotron dataset for a target.

    Randomly samples N personas from the NVIDIA Nemotron-Personas-Singapore
    dataset and maps them to the Kaleidoscope persona schema using heuristic
    field mapping. No LLM call is made.

    Args:
        request: Target ID and number of personas to sample
        db: Database session

    Returns:
        List of created personas with status="pending"

    Raises:
        HTTPException: If target not found or sampling fails
    """
    # Verify target exists
    target = TargetRepository.get_by_id(db, request.target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target {request.target_id} not found"
        )

    try:
        personas = sample_personas_from_nemotron(db, request.target_id, n=request.n)
        logger.info(f"Sampled {len(personas)} Nemotron personas for target {request.target_id}")
        return personas
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Nemotron persona sampling failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Persona sampling failed: {str(e)}"
        )


@router.get("/{persona_id}", response_model=PersonaResponse)
def get_persona(
    persona_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific persona by ID.

    Args:
        persona_id: Persona ID
        db: Database session

    Returns:
        Persona details
    """
    persona = PersonaRepository.get_by_id(db, persona_id)
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona {persona_id} not found"
        )
    return persona


@router.put("/{persona_id}", response_model=PersonaResponse)
def update_persona(
    persona_id: int,
    persona_update: PersonaUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a persona's fields.

    Args:
        persona_id: Persona ID
        persona_update: Fields to update
        db: Database session

    Returns:
        Updated persona
    """
    update_data = persona_update.model_dump(exclude_unset=True)
    persona = PersonaRepository.update(db, persona_id, update_data)
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona {persona_id} not found"
        )
    return persona


@router.post("/{persona_id}/approve", response_model=PersonaResponse)
def approve_persona(
    persona_id: int,
    db: Session = Depends(get_db)
):
    """
    Approve a persona.

    Args:
        persona_id: Persona ID
        db: Database session

    Returns:
        Approved persona
    """
    persona = PersonaRepository.approve(db, persona_id)
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona {persona_id} not found"
        )
    return persona


@router.post("/{persona_id}/reject", response_model=PersonaResponse)
def reject_persona(
    persona_id: int,
    db: Session = Depends(get_db)
):
    """
    Reject a persona.

    Args:
        persona_id: Persona ID
        db: Database session

    Returns:
        Rejected persona
    """
    persona = PersonaRepository.reject(db, persona_id)
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona {persona_id} not found"
        )
    return persona


@router.post("/bulk-approve", response_model=List[PersonaResponse])
def bulk_approve_personas(
    request: PersonaBulkApprove,
    db: Session = Depends(get_db)
):
    """
    Approve multiple personas at once.

    Args:
        request: List of persona IDs to approve
        db: Database session

    Returns:
        List of approved personas
    """
    personas = PersonaRepository.bulk_approve(db, request.persona_ids)
    return personas


@router.get("/{persona_id}/questions", response_model=List[QuestionResponse])
def list_questions_for_persona(
    persona_id: int,
    status_filter: Optional[StatusEnum] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    List all questions for a specific persona.

    Args:
        persona_id: Persona ID
        status_filter: Optional filter by status
        skip: Pagination offset
        limit: Pagination limit
        db: Database session

    Returns:
        List of questions
    """
    # Verify persona exists
    persona = PersonaRepository.get_by_id(db, persona_id)
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona {persona_id} not found"
        )

    questions = QuestionRepository.get_by_persona(db, persona_id, status_filter, skip, limit)

    # Add persona_title to each question
    response = []
    for question in questions:
        question_dict = {
            "id": question.id,
            "job_id": question.job_id,
            "persona_id": question.persona_id,
            "target_id": question.target_id,
            "text": question.text,
            "type": question.type,
            "scope": question.scope,
            "status": question.status,
            "created_at": question.created_at,
            "updated_at": question.updated_at,
            "persona_title": question.persona.title if question.persona else None
        }
        response.append(question_dict)

    return response
