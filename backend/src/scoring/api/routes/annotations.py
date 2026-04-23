"""API routes for Annotation management."""

from collections import defaultdict
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.common.database.connection import get_db
from src.common.database.models import Annotation, TargetRubric
from src.common.database.repositories import AnnotationRepository, AnswerRepository, SnapshotRepository
from src.common.models import (
    AnnotationAnswerGroupResponse,
    AnnotationBulkCreate,
    AnnotationCreate,
    AnnotationListResponse,
    AnnotationResponse,
    AnnotationUpdate,
)
from src.rubric.services.system_rubrics import canonicalize_rubric_option_value


class AnswerAnnotationUpsert(BaseModel):
    option_value: str
    notes: str | None = None


class AnswerAnnotationRecordResponse(BaseModel):
    id: int
    answer_id: int
    rubric_id: int
    option_value: str
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


router = APIRouter()


def _get_answer_or_404(db: Session, answer_id: int):
    answer = AnswerRepository.get_by_id(db, answer_id)
    if not answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Answer {answer_id} not found",
        )
    return answer


def _get_answer_annotation_row(db: Session, answer_id: int, rubric_id: int) -> Annotation | None:
    return (
        db.query(Annotation)
        .filter(
            Annotation.answer_id == answer_id,
            Annotation.rubric_id == rubric_id,
        )
        .first()
    )


@router.post("/annotations", response_model=AnnotationResponse, status_code=status.HTTP_201_CREATED)
def create_annotation(
    annotation: AnnotationCreate,
    db: Session = Depends(get_db)
):
    """Create a single rubric-scoped annotation."""
    _get_answer_or_404(db, annotation.answer_id)
    try:
        return AnnotationRepository.create(db, annotation.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/annotations/bulk", response_model=List[AnnotationResponse], status_code=status.HTTP_201_CREATED)
def bulk_create_annotations(
    request: AnnotationBulkCreate,
    db: Session = Depends(get_db)
):
    """Bulk create annotations for multiple answers under one rubric."""
    for annotation in request.annotations:
        _get_answer_or_404(db, annotation.answer_id)

    try:
        return AnnotationRepository.create_many(
            db,
            request.rubric_id,
            [ann.model_dump() for ann in request.annotations],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/snapshots/{snapshot_id}/annotations", response_model=AnnotationListResponse)
def list_annotations_for_snapshot(
    snapshot_id: int,
    db: Session = Depends(get_db)
):
    """List all annotations for a snapshot grouped by answer."""
    snapshot = SnapshotRepository.get_by_id(db, snapshot_id)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {snapshot_id} not found"
        )

    annotations = AnnotationRepository.get_by_snapshot(db, snapshot_id)
    grouped: dict[int, list[AnnotationResponse]] = defaultdict(list)
    for annotation in annotations:
        grouped[annotation.answer_id].append(AnnotationResponse.model_validate(annotation))

    return AnnotationListResponse(
        answers=[
            AnnotationAnswerGroupResponse(answer_id=answer_id, annotations=rows)
            for answer_id, rows in grouped.items()
        ],
        total_answers=len(grouped),
        total_annotations=len(annotations),
    )


@router.get("/snapshots/{snapshot_id}/annotations/completion-status")
def check_annotation_completion_status(
    snapshot_id: int,
    db: Session = Depends(get_db)
):
    """Check whether all selected answers are annotated across all target rubrics."""
    snapshot = SnapshotRepository.get_by_id(db, snapshot_id)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {snapshot_id} not found"
        )

    return AnnotationRepository.check_annotation_completion(db, snapshot_id)


@router.get("/answers/{answer_id}/annotations", response_model=List[AnswerAnnotationRecordResponse])
def list_annotations_for_answer(
    answer_id: int,
    db: Session = Depends(get_db)
):
    """List all annotation rows for an answer."""
    _get_answer_or_404(db, answer_id)
    return db.query(Annotation).filter(Annotation.answer_id == answer_id).all()


@router.get("/answers/{answer_id}/annotations/{rubric_id}", response_model=AnswerAnnotationRecordResponse)
def get_annotation_for_answer(
    answer_id: int,
    rubric_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific annotation row for an answer and rubric."""
    _get_answer_or_404(db, answer_id)
    annotation = _get_answer_annotation_row(db, answer_id, rubric_id)
    if not annotation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No annotation found for answer {answer_id} and rubric {rubric_id}"
        )

    return annotation


@router.get("/annotations/{annotation_id}", response_model=AnnotationResponse)
def get_annotation(
    annotation_id: int,
    rubric_id: int = Query(..., description="Rubric ID used to scope the annotation lookup"),
    db: Session = Depends(get_db)
):
    """Get one annotation row by ID, scoped to a rubric."""
    annotation = AnnotationRepository.get_by_id(db, annotation_id, rubric_id)
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
    """Update one rubric-scoped annotation row."""
    try:
        annotation = AnnotationRepository.update(
            db,
            annotation_id,
            annotation_update.rubric_id,
            annotation_update.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not annotation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Annotation {annotation_id} not found"
        )
    return annotation


@router.delete("/annotations/{annotation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_annotation(
    annotation_id: int,
    rubric_id: int = Query(..., description="Rubric ID used to scope the annotation delete"),
    db: Session = Depends(get_db)
):
    """Delete one annotation row, scoped to a rubric."""
    success = AnnotationRepository.delete(db, annotation_id, rubric_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Annotation {annotation_id} not found"
        )


@router.put("/answers/{answer_id}/annotations/{rubric_id}", response_model=AnswerAnnotationRecordResponse)
def upsert_annotation(
    answer_id: int,
    rubric_id: int,
    data: AnswerAnnotationUpsert,
    db: Session = Depends(get_db)
):
    """Create or update an annotation row for an answer and rubric."""
    _get_answer_or_404(db, answer_id)
    rubric = db.query(TargetRubric).filter(TargetRubric.id == rubric_id).first()
    option_value = canonicalize_rubric_option_value(rubric, data.option_value) if rubric else data.option_value

    existing = _get_answer_annotation_row(db, answer_id, rubric_id)

    if existing:
        existing.option_value = option_value
        if "notes" in data.model_fields_set:
            existing.notes = data.notes
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing

    annotation = Annotation(
        answer_id=answer_id,
        rubric_id=rubric_id,
        option_value=option_value,
        notes=data.notes,
    )
    db.add(annotation)
    db.commit()
    db.refresh(annotation)
    return annotation
