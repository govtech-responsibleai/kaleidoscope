"""API routes for Metrics calculation and export."""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from src.common.database.connection import get_db
from src.common.database.repositories import SnapshotRepository, JudgeRepository, TargetRepository
from src.common.database.repositories.target_rubric_repo import TargetRubricRepository
from src.common.models.metrics import (
    AggregatedResult,
    ConfusionMatrixResponse,
    JudgeAccuracyResponse,
    JudgeAlignmentResponse,
    SnapshotScoringContractsResponse,
    ScoringPendingCountsResponse,
    SnapshotMetric,
)
from src.common.services.system_rubrics import FixedAccuracyRubricInvariantError
from src.scoring.services.metrics_service import MetricsService

router = APIRouter()

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
    except FixedAccuracyRubricInvariantError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/snapshots/{snapshot_id}/scoring-contracts", response_model=SnapshotScoringContractsResponse)
def get_snapshot_scoring_contracts(
    snapshot_id: int,
    db: Session = Depends(get_db),
):
    """Get backend-owned scoring contracts for all rubric metrics in a snapshot."""
    snapshot = SnapshotRepository.get_by_id(db, snapshot_id)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {snapshot_id} not found",
        )

    try:
        service = MetricsService(db)
        return service.get_snapshot_scoring_contracts(snapshot_id)
    except FixedAccuracyRubricInvariantError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/snapshots/{snapshot_id}/rubrics/{rubric_id}/scoring-pending-counts",
    response_model=ScoringPendingCountsResponse,
)
def get_scoring_pending_counts(
    snapshot_id: int,
    rubric_id: int,
    db: Session = Depends(get_db)
):
    """Get rubric-scoped pending counts needed by one scoring section."""
    snapshot = SnapshotRepository.get_by_id(db, snapshot_id)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {snapshot_id} not found"
        )
    rubric = TargetRubricRepository.get_by_id(db, rubric_id)
    if not rubric:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rubric {rubric_id} not found"
        )

    try:
        metrics_service = MetricsService(db)
        return metrics_service.get_scoring_pending_counts(snapshot_id, rubric_id)
    except FixedAccuracyRubricInvariantError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/targets/{target_id}/snapshot-metrics", response_model=List[SnapshotMetric])
def get_target_snapshot_metrics(
    target_id: int,
    snapshot_id: Optional[int] = Query(None),
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

    metrics_service = MetricsService(db)
    try:
        return metrics_service.calculate_snapshot_metrics(target_id, snapshot_id)
    except FixedAccuracyRubricInvariantError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/targets/{target_id}/confusion-matrix",
    response_model=ConfusionMatrixResponse,
)
def get_confusion_matrix(
    target_id: int,
    rubric_id: int = Query(...),
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
        rubric_id: Rubric ID
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
        confusion_matrix = metrics_service.calculate_confusion_matrix(target_id, rubric_id, snapshot_id)
        return confusion_matrix
    except FixedAccuracyRubricInvariantError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/snapshots/{snapshot_id}/judges/{judge_id}/rubrics/{rubric_id}/alignment",
    response_model=JudgeAlignmentResponse,
)
def get_rubric_judge_alignment(
    snapshot_id: int,
    judge_id: int,
    rubric_id: int,
    db: Session = Depends(get_db),
):
    """Calculate rubric judge alignment with human labels on selected answers."""
    snapshot = SnapshotRepository.get_by_id(db, snapshot_id)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {snapshot_id} not found",
        )
    judge = JudgeRepository.get_by_id(db, judge_id)
    if not judge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Judge {judge_id} not found",
        )
    rubric = TargetRubricRepository.get_by_id(db, rubric_id)
    if not rubric:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rubric {rubric_id} not found",
        )
    best_option = rubric.best_option
    if not best_option:
        options = rubric.options or []
        best_option = options[0].get("option", "") if options and isinstance(options[0], dict) else str(options[0]) if options else ""
    try:
        service = MetricsService(db)
        return service.calculate_rubric_judge_alignment(snapshot_id, judge_id, rubric_id, best_option)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/snapshots/{snapshot_id}/judges/{judge_id}/rubrics/{rubric_id}/accuracy",
    response_model=JudgeAccuracyResponse,
)
def get_rubric_judge_accuracy(
    snapshot_id: int,
    judge_id: int,
    rubric_id: int,
    db: Session = Depends(get_db),
):
    """Calculate rubric judge accuracy (% of answers getting the best option)."""
    snapshot = SnapshotRepository.get_by_id(db, snapshot_id)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {snapshot_id} not found",
        )
    judge = JudgeRepository.get_by_id(db, judge_id)
    if not judge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Judge {judge_id} not found",
        )
    rubric = TargetRubricRepository.get_by_id(db, rubric_id)
    if not rubric:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rubric {rubric_id} not found",
        )
    best_option = rubric.best_option
    if not best_option:
        options = rubric.options or []
        best_option = options[0].get("option", "") if options and isinstance(options[0], dict) else str(options[0]) if options else ""
    try:
        service = MetricsService(db)
        return service.calculate_rubric_judge_accuracy(snapshot_id, judge_id, rubric_id, best_option)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
