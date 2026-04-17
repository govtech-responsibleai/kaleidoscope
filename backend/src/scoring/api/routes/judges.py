"""
API routes for Judge management.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.common.database.connection import get_db
from src.common.database.repositories import JudgeRepository
from src.common.database.seed import AVAILABLE_MODELS
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
    judge_data["user_id"] = user_id
    created_judge = JudgeRepository.create(db, judge_data)
    print(f"[DEBUG] Created judge: id={created_judge.id}, category={created_judge.category}, target_id={created_judge.target_id}, user_id={created_judge.user_id}", flush=True)
    return created_judge


@router.get("/judges", response_model=List[JudgeResponse])
def list_judges(
    target_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    List all judges, optionally filtered by target.

    When target_id is provided, returns judges scoped to that target
    plus global default judges (target_id=NULL).

    Args:
        target_id: Optional target ID to filter by
        db: Database session

    Returns:
        List of judges
    """
    judges = JudgeRepository.get_all(db, target_id=target_id)
    print(f"[DEBUG] list_judges(target_id={target_id}): {len(judges)} judges, ids={[j.id for j in judges]}, categories={[j.category for j in judges]}", flush=True)
    return judges


@router.get("/judges/baseline", response_model=JudgeResponse)
def get_baseline_judge(
    db: Session = Depends(get_db)
):
    """
    Get the baseline judge configuration.

    Args:
        db: Database session

    Returns:
        Baseline judge

    Raises:
        HTTPException: If baseline judge not found
    """
    judge = JudgeRepository.get_baseline(db)
    if not judge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Baseline judge not found"
        )
    return judge


@router.get("/judges/available-models")
def list_available_models():
    """
    Return the static list of available judge models.
    """
    return AVAILABLE_MODELS


@router.get("/judges/by-category/{category}", response_model=List[JudgeResponse])
def list_judges_by_category(
    category: str,
    target_id: Optional[int] = None,
    rubric_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Get judges for a specific rubric category, optionally filtered by target.

    Returns judges whose category exactly matches the given value.
    When target_id is provided, includes target-scoped and global judges.
    """
    judges = JudgeRepository.get_by_category(
        db,
        category,
        target_id=target_id,
        rubric_id=rubric_id,
    )
    return judges


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
