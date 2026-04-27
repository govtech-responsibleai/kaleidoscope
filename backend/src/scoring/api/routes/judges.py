"""
API routes for Judge management.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.common.database.connection import get_db
from src.common.database.repositories import JudgeRepository
from src.common.llm.provider_service import get_valid_model_options, require_valid_model_for_user
from src.common.models import (
    JudgeCreate,
    JudgeUpdate,
    JudgeResponse
)
from src.common.auth import get_current_user_id

router = APIRouter()


@router.post("/judges", response_model=JudgeResponse, status_code=status.HTTP_201_CREATED)
def create_judge(
    judge: JudgeCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Create a new judge configuration.

    Args:
        judge: Judge creation data
        user_id: Current user's ID (injected)
        db: Database session

    Returns:
        Created judge
    """
    judge_data = judge.model_dump()
    try:
        require_valid_model_for_user(db, user_id, judge_data["model_name"])
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if judge_data.get("rubric_id") is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="rubric_id is required for user-created judges",
        )
    judge_data["user_id"] = user_id
    created_judge = JudgeRepository.create(db, judge_data)
    return created_judge


@router.get("/judges", response_model=List[JudgeResponse])
def list_judges(
    target_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    List all judges, optionally filtered by target.

    Only rubric-scoped, user-facing judges are returned.

    Args:
        target_id: Optional target ID to filter by
        db: Database session

    Returns:
        List of judges
    """
    return JudgeRepository.get_all(db, target_id=target_id)


@router.get("/judges/available-models")
def list_available_models(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Return the current user's valid judge models.
    """
    return get_valid_model_options(db, user_id)


@router.get("/judges/by-rubric/{rubric_id}", response_model=List[JudgeResponse])
def list_judges_by_rubric(
    rubric_id: int,
    target_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get judges for a specific rubric, optionally filtered by target."""
    return JudgeRepository.get_for_rubric(db, rubric_id, target_id=target_id)


@router.get("/judges/by-rubric/{rubric_id}/baseline", response_model=JudgeResponse)
def get_baseline_judge_by_rubric(
    rubric_id: int,
    target_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get the baseline judge explicitly bound to a rubric."""
    judge = JudgeRepository.get_baseline(db, rubric_id=rubric_id, target_id=target_id)
    if not judge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Baseline judge not found for rubric {rubric_id}"
        )
    return judge


@router.get("/judges/{judge_id}", response_model=JudgeResponse)
def get_judge(
    judge_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific judge by ID.

    Args:
        judge_id: Judge ID
        db: Database session

    Returns:
        Judge details

    Raises:
        HTTPException: If judge not found
    """
    judge = JudgeRepository.get_by_id(db, judge_id)
    if not judge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Judge {judge_id} not found"
        )
    return judge


@router.put("/judges/{judge_id}", response_model=JudgeResponse)
def update_judge(
    judge_id: int,
    judge_update: JudgeUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a judge configuration.

    Only editable judges (is_editable=True) can be updated.

    Args:
        judge_id: Judge ID
        judge_update: Fields to update
        db: Database session

    Returns:
        Updated judge

    Raises:
        HTTPException: If judge not found or not editable
    """
    # Check if judge exists and is editable
    judge = JudgeRepository.get_by_id(db, judge_id)
    if not judge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Judge {judge_id} not found"
        )

    if not judge.is_editable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Judge {judge_id} is not editable"
        )

    update_data = judge_update.model_dump(exclude_unset=True)
    if "model_name" in update_data and update_data["model_name"] is not None:
        try:
            require_valid_model_for_user(db, int(judge.user_id), update_data["model_name"])
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    updated_judge = JudgeRepository.update(db, judge_id, update_data)
    return updated_judge


@router.delete("/judges/{judge_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_judge(
    judge_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a judge.

    Only editable judges (is_editable=True) can be deleted.

    Args:
        judge_id: Judge ID
        db: Database session

    Raises:
        HTTPException: If judge not found or not editable
    """
    # Check if judge exists and is editable
    judge = JudgeRepository.get_by_id(db, judge_id)
    if not judge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Judge {judge_id} not found"
        )

    if not judge.is_editable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Judge {judge_id} is not editable and cannot be deleted"
        )

    success = JudgeRepository.delete(db, judge_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete judge {judge_id}"
        )
