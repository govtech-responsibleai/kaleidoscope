"""
API routes for Target management.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.common.database.connection import get_db
from src.common.database.repositories import TargetRepository, PersonaRepository, QuestionRepository
from src.common.models import TargetCreate, TargetUpdate, TargetResponse, TargetStats, PersonaResponse, QuestionResponse
from src.common.database.models import StatusEnum
from src.common.auth import get_current_user_id

router = APIRouter()


@router.post("", response_model=TargetResponse, status_code=status.HTTP_201_CREATED)
def create_target(
    target: TargetCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Create a new target application.

    Args:
        target: Target creation data
        user_id: Current user's ID (injected)
        db: Database session

    Returns:
        Created target
    """
    target_data = target.model_dump()
    target_data["user_id"] = user_id
    created_target = TargetRepository.create(db, target_data)
    return created_target


@router.get("", response_model=List[TargetResponse])
def list_targets(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    List all targets.

    Args:
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return
        db: Database session

    Returns:
        List of targets
    """
    targets = TargetRepository.get_all(db, skip=skip, limit=limit)
    return targets


@router.get("/{target_id}", response_model=TargetResponse)
def get_target(
    target_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific target by ID.

    Args:
        target_id: Target ID
        db: Database session

    Returns:
        Target details

    Raises:
        HTTPException: If target not found
    """
    target = TargetRepository.get_by_id(db, target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target {target_id} not found"
        )
    return target


@router.put("/{target_id}", response_model=TargetResponse)
def update_target(
    target_id: int,
    target_update: TargetUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a target.

    Args:
        target_id: Target ID
        target_update: Fields to update
        db: Database session

    Returns:
        Updated target

    Raises:
        HTTPException: If target not found
    """
    update_data = target_update.model_dump(exclude_unset=True)
    target = TargetRepository.update(db, target_id, update_data)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target {target_id} not found"
        )
    return target


@router.delete("/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_target(
    target_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a target.

    Args:
        target_id: Target ID
        db: Database session

    Raises:
        HTTPException: If target not found
    """
    success = TargetRepository.delete(db, target_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target {target_id} not found"
        )


@router.get("/{target_id}/stats", response_model=TargetStats)
def get_target_stats(
    target_id: int,
    db: Session = Depends(get_db)
):
    """
    Get statistics for a target.

    Args:
        target_id: Target ID
        db: Database session

    Returns:
        Target statistics (persona counts, question counts, total cost)

    Raises:
        HTTPException: If target not found
    """
    # Check if target exists
    target = TargetRepository.get_by_id(db, target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target {target_id} not found"
        )

    stats = TargetRepository.get_stats(db, target_id)
    return stats


@router.get("/{target_id}/personas", response_model=List[PersonaResponse])
def list_personas_for_target(
    target_id: int,
    status_filter: Optional[StatusEnum] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    List all personas for a target.

    Args:
        target_id: Target ID
        status_filter: Optional filter by status
        skip: Pagination offset
        limit: Pagination limit
        db: Database session

    Returns:
        List of personas
    """
    # Verify target exists
    target = TargetRepository.get_by_id(db, target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target {target_id} not found"
        )

    personas = PersonaRepository.get_by_target(db, target_id, status_filter, skip, limit)
    return personas


@router.get("/{target_id}/questions", response_model=List[QuestionResponse])
def list_questions_for_target(
    target_id: int,
    status_filter: Optional[StatusEnum] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    List all questions for a target.

    Args:
        target_id: Target ID
        status_filter: Optional filter by status
        skip: Pagination offset
        limit: Pagination limit
        db: Database session

    Returns:
        List of questions with persona titles
    """
    # Verify target exists
    target = TargetRepository.get_by_id(db, target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target {target_id} not found"
        )

    questions = QuestionRepository.get_by_target(db, target_id, status_filter, skip, limit)

    # Add persona_title to each question
    response = []
    for question in questions:
        question_dict = {
            "id": question.id,
            "source": question.source,
            "job_id": question.job_id,
            "persona_id": question.persona_id,
            "target_id": question.target_id,
            "orig_id": question.orig_id,
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
