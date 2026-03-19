"""
API routes for Annotation management.
"""

from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from src.common.database.connection import get_db
from src.common.database.repositories import AnnotationRepository, AnswerRepository, SnapshotRepository
from src.common.database.models import RubricAnnotation
from src.common.models import (
    AnnotationCreate,
    AnnotationUpdate,
    AnnotationResponse,
    AnnotationBulkCreate,
    AnnotationListResponse
)


class RubricAnnotationUpsert(BaseModel):
    option_value: str


class RubricAnnotationResponse(BaseModel):
    id: int
    answer_id: int
    rubric_id: int
    option_value: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

router = APIRouter()


@router.post("/annotations", response_model=AnnotationResponse, status_code=status.HTTP_201_CREATED)
def create_annotation(
    annotation: AnnotationCreate,
    db: Session = Depends(get_db)
):
    """
    Create a single annotation.

    Args:
        annotation: Annotation creation data (answer_id, label, notes)
        db: Database session

    Returns:
        Created annotation

    Raises:
        HTTPException: If answer not found
    """
    # Verify answer exists
    answer = AnswerRepository.get_by_id(db, annotation.answer_id)
    if not answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Answer {annotation.answer_id} not found"
        )

    annotation_data = annotation.model_dump()
    created_annotation = AnnotationRepository.create(db, annotation_data)
    return created_annotation


@router.post("/annotations/bulk", response_model=List[AnnotationResponse], status_code=status.HTTP_201_CREATED)
def bulk_create_annotations(
    request: AnnotationBulkCreate,
    db: Session = Depends(get_db)
):
    """
    Bulk create annotations for multiple answers.

    Used when user submits all annotations at once.

    Args:
        request: List of annotations to create
        db: Database session

    Returns:
        List of created annotations

    Raises:
        HTTPException: If any answer not found
    """
    # Verify all answers exist
    for annotation in request.annotations:
        answer = AnswerRepository.get_by_id(db, annotation.answer_id)
        if not answer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Answer {annotation.answer_id} not found"
            )

    # Create all annotations
    annotations_data = [ann.model_dump() for ann in request.annotations]
    created_annotations = AnnotationRepository.create_many(db, annotations_data)
    return created_annotations


@router.get("/snapshots/{snapshot_id}/annotations", response_model=AnnotationListResponse)
def list_annotations_for_snapshot(
    snapshot_id: int,
    db: Session = Depends(get_db)
):
    """
    List all annotations for a snapshot.

    Args:
        snapshot_id: Snapshot ID
        db: Database session

    Returns:
        List of annotations

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

    annotations = AnnotationRepository.get_by_snapshot(db, snapshot_id)
    return AnnotationListResponse(annotations=annotations, total=len(annotations))


@router.get("/snapshots/{snapshot_id}/annotations/completion-status")
def check_annotation_completion_status(
    snapshot_id: int,
    db: Session = Depends(get_db)
):
    """
    Check if all selected answers have been annotated.

    Returns completion statistics for the snapshot's selected answers.
    Useful for UI progress tracking and enabling/disabling submit buttons.

    Args:
        snapshot_id: Snapshot ID
        db: Database session

    Returns:
        Dictionary with:
        - total_selected: Count of answers where is_selected_for_annotation=True
        - total_selected_and_annotated: Count of selected answers that have annotations
        - is_complete: Boolean indicating if all selected answers are annotated
        - completion_percentage: Percentage of selected answers that are annotated

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

    completion_status = AnnotationRepository.check_annotation_completion(db, snapshot_id)
    return completion_status


@router.get("/answers/{answer_id}/annotations", response_model=AnnotationResponse)
def get_annotation_for_answer(
    answer_id: int,
    db: Session = Depends(get_db)
):
    """
    Get annotation for a specific answer.

    There is a one-to-one relationship between answers and annotations.

    Args:
        answer_id: Answer ID
        db: Database session

    Returns:
        Annotation for the answer

    Raises:
        HTTPException: If answer or annotation not found
    """
    # Verify answer exists
    answer = AnswerRepository.get_by_id(db, answer_id)
    if not answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Answer {answer_id} not found"
        )

    annotation = AnnotationRepository.get_by_answer(db, answer_id)
    if not annotation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No annotation found for answer {answer_id}"
        )

    return annotation


@router.get("/annotations/{annotation_id}", response_model=AnnotationResponse)
def get_annotation(
    annotation_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific annotation by ID.

    Args:
        annotation_id: Annotation ID
        db: Database session

    Returns:
        Annotation details

    Raises:
        HTTPException: If annotation not found
    """
    annotation = AnnotationRepository.get_by_id(db, annotation_id)
    if not annotation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Annotation {annotation_id} not found"
        )
    return annotation


@router.put("/annotations/{annotation_id}", response_model=AnnotationResponse)
def update_annotation(
    annotation_id: int,
    annotation_update: AnnotationUpdate,
    db: Session = Depends(get_db)
):
    """
    Update an annotation.

    Args:
        annotation_id: Annotation ID
        annotation_update: Fields to update
        db: Database session

    Returns:
        Updated annotation

    Raises:
        HTTPException: If annotation not found
    """
    update_data = annotation_update.model_dump(exclude_unset=True)
    annotation = AnnotationRepository.update(db, annotation_id, update_data)
    if not annotation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Annotation {annotation_id} not found"
        )
    return annotation


@router.delete("/annotations/{annotation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_annotation(
    annotation_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete an annotation.

    Args:
        annotation_id: Annotation ID
        db: Database session

    Raises:
        HTTPException: If annotation not found
    """
    success = AnnotationRepository.delete(db, annotation_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Annotation {annotation_id} not found"
        )


@router.get("/answers/{answer_id}/rubric-annotations", response_model=List[RubricAnnotationResponse])
def get_rubric_annotations_for_answer(
    answer_id: int,
    db: Session = Depends(get_db)
):
    """Get all custom rubric labels for an answer."""
    answer = AnswerRepository.get_by_id(db, answer_id)
    if not answer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Answer {answer_id} not found")
    return db.query(RubricAnnotation).filter(RubricAnnotation.answer_id == answer_id).all()


@router.put("/answers/{answer_id}/rubric-annotations/{rubric_id}", response_model=RubricAnnotationResponse)
def upsert_rubric_annotation(
    answer_id: int,
    rubric_id: int,
    data: RubricAnnotationUpsert,
    db: Session = Depends(get_db)
):
    """Create or update a custom rubric label for an answer."""
    answer = AnswerRepository.get_by_id(db, answer_id)
    if not answer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Answer {answer_id} not found")

    existing = db.query(RubricAnnotation).filter(
        RubricAnnotation.answer_id == answer_id,
        RubricAnnotation.rubric_id == rubric_id
    ).first()

    if existing:
        existing.option_value = data.option_value
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing
    else:
        label = RubricAnnotation(answer_id=answer_id, rubric_id=rubric_id, option_value=data.option_value)
        db.add(label)
        db.commit()
        db.refresh(label)
        return label
