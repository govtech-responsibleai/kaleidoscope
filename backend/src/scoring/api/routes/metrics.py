"""
API routes for Metrics calculation and export.
"""

from typing import Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from src.common.database.connection import get_db
from src.common.database.repositories import SnapshotRepository, JudgeRepository
from src.scoring.services.metrics_service import MetricsService

router = APIRouter()



@router.get("/snapshots/{snapshot_id}/judges/{judge_id}/alignment")
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


@router.get("/snapshots/{snapshot_id}/judges/{judge_id}/accuracy")
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


@router.get("/snapshots/{snapshot_id}/results")
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
        results = metrics_service.get_aggregated_results(snapshot_id)
        return {
            "snapshot_id": snapshot_id,
            "results": results,
            "total": len(results)
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/snapshots/{snapshot_id}/export")
def export_results(
    snapshot_id: int,
    db: Session = Depends(get_db)
):
    """
    Export aggregated evaluation results as CSV.

    Args:
        snapshot_id: Snapshot ID
        db: Database session

    Returns:
        CSV file with headers: question, answer, accuracy, metadata

    Raises:
        HTTPException: If snapshot not found or no answers available
    """
    # Verify snapshot exists
    snapshot = SnapshotRepository.get_by_id(db, snapshot_id)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {snapshot_id} not found"
        )

    # Generate CSV export
    try:
        metrics_service = MetricsService(db)
        csv_content = metrics_service.export_results_csv(snapshot_id)

        # Return as downloadable CSV file
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=snapshot_{snapshot_id}_aggregated_results.csv"
            }
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
