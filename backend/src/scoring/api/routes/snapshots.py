"""
API routes for Snapshot management.
"""

import math
import random
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from src.common.database.connection import get_db
from src.common.database.repositories import SnapshotRepository, TargetRepository, QuestionRepository, AnswerRepository
from src.common.models import (
    AnswerBulkSelection,
    AnswerListResponse,
    AnswerListItemResponse,
    AnswerResponse,
    AnswerSelection,
    DefaultSelectionResponse,
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


@router.get("/snapshots/{snapshot_id}/answers", response_model=AnswerListResponse)
def list_answers_for_snapshot(
    snapshot_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    List all answers for a snapshot.

    Returns answers with question text and annotation status for the mailbox UI.
    """
    snapshot = SnapshotRepository.get_by_id(db, snapshot_id)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {snapshot_id} not found"
        )

    answers = AnswerRepository.get_by_snapshot(db, snapshot_id, skip, limit, eager_load=True)

    enriched_answers = [
        AnswerListItemResponse(
            id=a.id,
            snapshot_id=a.snapshot_id,
            question_id=a.question_id,
            chat_id=a.chat_id,
            message_id=a.message_id,
            answer_content=a.answer_content,
            model=a.model,
            guardrails=a.guardrails,
            rag_citations=a.rag_citations,
            is_selected_for_annotation=a.is_selected_for_annotation,
            created_at=a.created_at,
            question_text=a.question.text if a.question else None,
            has_annotation=a.annotation is not None,
        )
        for a in answers
    ]

    total = AnswerRepository.count_by_snapshot(db, snapshot_id)
    return AnswerListResponse(answers=enriched_answers, total=total)


@router.post("/snapshots/{snapshot_id}/answers/bulk-selection", response_model=List[AnswerResponse])
def bulk_update_answer_selection(
    snapshot_id: int,
    request: AnswerBulkSelection,
    db: Session = Depends(get_db)
):
    """
    Bulk update is_selected_for_annotation for multiple answers in a snapshot.
    """
    snapshot = SnapshotRepository.get_by_id(db, snapshot_id)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {snapshot_id} not found"
        )

    answer_ids = [s.answer_id for s in request.selections]
    existing = AnswerRepository.get_by_ids(db, answer_ids)
    existing_ids = {a.id for a in existing}
    missing = set(answer_ids) - existing_ids
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Answers not found: {sorted(missing)}"
        )

    wrong_snapshot = sorted(a.id for a in existing if a.snapshot_id != snapshot_id)
    if wrong_snapshot:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Answers do not belong to snapshot {snapshot_id}: {wrong_snapshot}"
        )

    updated_answers = AnswerRepository.update_annotation_selection(db, request.selections)
    return updated_answers


@router.post("/snapshots/{snapshot_id}/answers/select-default", response_model=DefaultSelectionResponse)
def select_default_answers(
    snapshot_id: int,
    selection_pct: float = 0.2,
    db: Session = Depends(get_db)
):
    """
    Auto-select a percentage of answers for annotation.
    """
    snapshot = SnapshotRepository.get_by_id(db, snapshot_id)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {snapshot_id} not found"
        )

    answers = AnswerRepository.get_by_snapshot(db, snapshot_id, skip=0, limit=1000)

    if not answers:
        return DefaultSelectionResponse(
            snapshot_id=snapshot_id,
            selected_count=0,
            total_answers=0
        )

    random.seed(42)
    selected_answers = random.sample(answers, math.ceil(len(answers) * selection_pct))
    selections = [
        AnswerSelection(answer_id=answer.id, is_selected=True)
        for answer in selected_answers
    ]
    AnswerRepository.update_annotation_selection(db, selections)

    return DefaultSelectionResponse(
        snapshot_id=snapshot_id,
        selected_count=len(selected_answers),
        total_answers=len(answers)
    )


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


@router.get("/snapshots/{snapshot_id}/questions/approved/without-rubric-scores", response_model=List[QuestionResponse])
def get_approved_questions_without_rubric_scores(
    snapshot_id: int,
    judge_id: int,
    rubric_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get approved questions that have answers but no rubric scores
    for this snapshot/judge/rubric combination.
    """
    snapshot = SnapshotRepository.get_by_id(db, snapshot_id)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {snapshot_id} not found"
        )

    questions = QuestionRepository.get_approved_questions_without_rubric_scores(
        db,
        target_id=snapshot.target_id,
        snapshot_id=snapshot_id,
        judge_id=judge_id,
        rubric_id=rubric_id,
        skip=skip,
        limit=limit
    )
    return questions
