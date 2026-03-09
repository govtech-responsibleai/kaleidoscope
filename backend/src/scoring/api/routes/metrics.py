"""API routes for Metrics calculation and export."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.common.database.connection import get_db
from src.common.database.repositories import SnapshotRepository, JudgeRepository, TargetRepository
from src.common.models.metrics import (
    AggregatedResult,
    ConfusionMatrixResponse,
    JudgeAccuracyResponse,
    JudgeAlignmentResponse,
    TargetSnapshotMetric,
)
from src.scoring.services.metrics_service import MetricsService

router = APIRouter()



@router.get(
    "/snapshots/{snapshot_id}/judges/{judge_id}/alignment",
    response_model=JudgeAlignmentResponse,
)
def get_judge_alignment(
    snapshot_id: int,
    judge_id: int,
    db: Session = Depends(get_db)
):
    """
    Calculate judge alignment metrics.

    Compares the judge's labels with human annotations on the selected subset
    to calculate F1 score, precision, recall, and accuracy.

    Args:
        snapshot_id: Snapshot ID
        judge_id: Judge ID to evaluate
        db: Database session

    Returns:
        Dict with metrics: {f1, precision, recall, accuracy, sample_count}

    Raises:
        HTTPException: If snapshot, judge not found, or no data for comparison
    """
    # Verify snapshot exists
    snapshot = SnapshotRepository.get_by_id(db, snapshot_id)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {snapshot_id} not found"
        )

    # Verify judge exists
    judge = JudgeRepository.get_by_id(db, judge_id)
    if not judge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Judge {judge_id} not found"
        )

    # Calculate alignment metrics
    try:
        metrics_service = MetricsService(db)
        metrics = metrics_service.calculate_judge_alignment(snapshot_id, judge_id)
        return metrics
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/snapshots/{snapshot_id}/judges/{judge_id}/accuracy",
    response_model=JudgeAccuracyResponse,
)
def get_chatbot_accuracy(
    snapshot_id: int,
    judge_id: int,
    db: Session = Depends(get_db)
):
    """
    Calculate chatbot accuracy based on judge scores.

    Calculates the percentage of accurate responses as determined by
    the judge's evaluation of all responses in the snapshot.

    Args:
        snapshot_id: Snapshot ID
        judge_id: Judge ID
        db: Database session

    Returns:
        Dict with: {accuracy, total_answers, accurate_count}

    Raises:
        HTTPException: If snapshot, judge not found, or no scores available
    """
    # Verify snapshot exists
    snapshot = SnapshotRepository.get_by_id(db, snapshot_id)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {snapshot_id} not found"
        )

    # Verify judge exists
    judge = JudgeRepository.get_by_id(db, judge_id)
    if not judge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Judge {judge_id} not found"
        )

    # Calculate accuracy
    try:
        metrics_service = MetricsService(db)
        accuracy_data = metrics_service.calculate_accuracy(snapshot_id, judge_id)
        return accuracy_data
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/snapshots/{snapshot_id}/results", response_model=List[AggregatedResult])
def get_aggregated_results(
    snapshot_id: int,
    db: Session = Depends(get_db)
):
    """
    Get aggregated evaluation results for all answers in a snapshot.

    Returns results with majority-vote (or tied) aggregated accuracy
    plus reliability metadata per judge.

    Args:
        snapshot_id: Snapshot ID
        db: Database session

    Returns:
        List of results with question, answer, and aggregated accuracy metadata

    Raises:
        HTTPException: If snapshot not found or no results available
    """
    # Verify snapshot exists
    snapshot = SnapshotRepository.get_by_id(db, snapshot_id)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {snapshot_id} not found"
        )

    # Get aggregated results
    try:
        metrics_service = MetricsService(db)
        results, _ = metrics_service.get_aggregated_results(snapshot_id)
        return results
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/targets/{target_id}/snapshot-metrics", response_model=List[TargetSnapshotMetric])
def get_target_snapshot_metrics(
    target_id: int,
    db: Session = Depends(get_db)
):
    """
    Get aggregated metrics for all snapshots of a target.

    Returns summary metrics for each snapshot including aggregated accuracy,
    judge alignment ranges, and aligned judges list.

    Args:
        target_id: Target ID
        db: Database session

    Returns:
        List of snapshot metrics

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

    # Get all snapshots for the target
    snapshots = SnapshotRepository.get_by_target(db, target_id)

    # Calculate metrics for each snapshot
    metrics_service = MetricsService(db)
    snapshot_metrics = []

    for snapshot in snapshots:
        try:
            summary = metrics_service.calculate_snapshot_summary(snapshot.id)
            snapshot_metrics.append(
                summary.model_copy(
                    update={
                        "snapshot_id": snapshot.id,
                        "snapshot_name": snapshot.name,
                        "created_at": snapshot.created_at.isoformat(),
                    }
                )
            )
        except ValueError:
            # No answers for this snapshot, skip it
            continue
        except Exception:
            # Log but don't fail the entire request
            import logging
            logger = logging.getLogger(__name__)
            logger.exception(f"Failed to calculate metrics for snapshot {snapshot.id}")
            continue

    return snapshot_metrics


@router.get(
    "/targets/{target_id}/confusion-matrix",
    response_model=ConfusionMatrixResponse,
)
def get_confusion_matrix(
    target_id: int,
    snapshot_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Get confusion matrix for question types/scopes vs inaccurate responses.

    Shows the distribution of inaccurate responses across:
    - Question type: typical, edge
    - Question scope: in_kb, out_kb

    Args:
        target_id: Target ID
        snapshot_id: Optional snapshot ID (uses latest if not provided)
        db: Database session

    Returns:
        Confusion matrix response

    Raises:
        HTTPException: If target not found or no snapshots available
    """
    # Verify target exists
    target = TargetRepository.get_by_id(db, target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target {target_id} not found"
        )

    # Calculate confusion matrix
    try:
        metrics_service = MetricsService(db)
        confusion_matrix = metrics_service.calculate_confusion_matrix(target_id, snapshot_id)
        return confusion_matrix
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
