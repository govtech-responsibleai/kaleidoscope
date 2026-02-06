"""
API routes for Snapshot management.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from src.common.database.connection import get_db
from src.common.database.repositories import SnapshotRepository, TargetRepository, QuestionRepository
from src.common.models import (
    SnapshotCreate,
    SnapshotUpdate,
    SnapshotResponse,
    QuestionResponse
)
from src.common.services.export_service import ExportService, ExportFormat

router = APIRouter()


@router.post("/snapshots", response_model=SnapshotResponse, status_code=status.HTTP_201_CREATED)
def create_snapshot(
    snapshot: SnapshotCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new snapshot for a target.

    Args:
        snapshot: Snapshot creation data
        db: Database session

    Returns:
        Created snapshot

    Raises:
        HTTPException: If target not found
    """
    # Verify target exists
    target = TargetRepository.get_by_id(db, snapshot.target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target {snapshot.target_id} not found"
        )

    snapshot_data = snapshot.model_dump()
    created_snapshot = SnapshotRepository.create(db, snapshot_data)
    return created_snapshot


@router.get("/targets/{target_id}/snapshots", response_model=List[SnapshotResponse])
def list_snapshots_for_target(
    target_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    List all snapshots for a target.

    Args:
        target_id: Target ID
        skip: Pagination offset
        limit: Pagination limit
        db: Database session

    Returns:
        List of snapshots ordered by created_at descending

    Raises:
        HTTPException: If target not found
    """
    # Verify target exists
    target = TargetRepository.get_by_id(db, target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target {target_id} not found"
        )

    snapshots = SnapshotRepository.get_by_target(db, target_id, skip, limit)
    return snapshots


@router.get("/snapshots/{snapshot_id}", response_model=SnapshotResponse)
def get_snapshot(
    snapshot_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific snapshot by ID.

    Args:
        snapshot_id: Snapshot ID
        db: Database session

    Returns:
        Snapshot details

    Raises:
        HTTPException: If snapshot not found
    """
    snapshot = SnapshotRepository.get_by_id(db, snapshot_id)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {snapshot_id} not found"
        )
    return snapshot


@router.put("/snapshots/{snapshot_id}", response_model=SnapshotResponse)
def update_snapshot(
    snapshot_id: int,
    snapshot_update: SnapshotUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a snapshot's name or description.

    Args:
        snapshot_id: Snapshot ID
        snapshot_update: Fields to update
        db: Database session

    Returns:
        Updated snapshot

    Raises:
        HTTPException: If snapshot not found
    """
    update_data = snapshot_update.model_dump(exclude_unset=True)
    snapshot = SnapshotRepository.update(db, snapshot_id, update_data)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {snapshot_id} not found"
        )
    return snapshot


@router.delete("/snapshots/{snapshot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_snapshot(
    snapshot_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a snapshot.

    Args:
        snapshot_id: Snapshot ID
        db: Database session

    Raises:
        HTTPException: If snapshot not found
    """
    success = SnapshotRepository.delete(db, snapshot_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {snapshot_id} not found"
        )


@router.get("/snapshots/{snapshot_id}/stats")
def get_snapshot_stats(
    snapshot_id: int,
    db: Session = Depends(get_db)
):
    """
    Get statistics for a snapshot.

    Args:
        snapshot_id: Snapshot ID
        db: Database session

    Returns:
        Snapshot statistics including total answers, selected count, and annotation progress

    Raises:
        HTTPException: If snapshot not found
    """
    stats_data = SnapshotRepository.get_with_answer_count(db, snapshot_id)
    if not stats_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {snapshot_id} not found"
        )

    return {
        "snapshot_id": snapshot_id,
        "total_answers": stats_data["total_answers"],
        "selected_for_annotation": stats_data["selected_for_annotation"]
    }


@router.get("/snapshots/{snapshot_id}/questions/approved/without-answers", response_model=List[QuestionResponse])
def get_approved_questions_without_answers(
    snapshot_id: int,
    judge_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get approved questions that don't have QA jobs for this snapshot/judge.

    Args:
        snapshot_id: Snapshot ID
        judge_id: Judge ID to check for QA jobs
        skip: Pagination offset
        limit: Pagination limit
        db: Database session

    Returns:
        List of approved questions without QA jobs

    Raises:
        HTTPException: If snapshot not found
    """
    # Verify snapshot exists
    snapshot = SnapshotRepository.get_by_id(db, snapshot_id)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {snapshot_id} not found"
        )

    questions = QuestionRepository.get_approved_questions_without_answers(
        db,
        target_id=snapshot.target_id,
        snapshot_id=snapshot_id,
        judge_id=judge_id,
        skip=skip,
        limit=limit
    )
    return questions


@router.get("/snapshots/{snapshot_id}/questions/approved/without-scores", response_model=List[QuestionResponse])
def get_approved_questions_without_scores(
    snapshot_id: int,
    judge_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get approved questions that have answers but no scores for this snapshot/judge.

    Args:
        snapshot_id: Snapshot ID
        judge_id: Judge ID to check for scores
        skip: Pagination offset
        limit: Pagination limit
        db: Database session

    Returns:
        List of approved questions with answers but no scores

    Raises:
        HTTPException: If snapshot not found
    """
    # Verify snapshot exists
    snapshot = SnapshotRepository.get_by_id(db, snapshot_id)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {snapshot_id} not found"
        )

    questions = QuestionRepository.get_approved_questions_without_scores(
        db,
        target_id=snapshot.target_id,
        snapshot_id=snapshot_id,
        judge_id=judge_id,
        skip=skip,
        limit=limit
    )
    return questions
