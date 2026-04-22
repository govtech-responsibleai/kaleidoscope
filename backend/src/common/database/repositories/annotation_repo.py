"""
Repository for legacy annotation API compatibility backed by rubric annotations.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session

from src.common.database.models import Answer, Snapshot, TargetRubric, Annotation
from src.common.services.system_rubrics import (
    FIXED_ACCURACY_NAME,
    RUBRIC_GROUP_FIXED,
    accuracy_label_from_bool,
    best_option_for_rubric,
    canonicalize_rubric_option_value,
    get_fixed_accuracy_rubric_or_raise,
)


@dataclass
class AnnotationRecord:
    id: int
    answer_id: int
    label: bool
    notes: str | None
    created_at: datetime


class AnnotationRepository:
    """Repository for legacy accuracy-annotation CRUD operations."""

    @staticmethod
    def _to_record(annotation: Annotation) -> AnnotationRecord:
        canonical_option = canonicalize_rubric_option_value(annotation.rubric, annotation.option_value)
        return AnnotationRecord(
            id=annotation.id,
            answer_id=annotation.answer_id,
            label=canonical_option == best_option_for_rubric(annotation.rubric),
            notes=annotation.notes,
            created_at=annotation.created_at,
        )

    @staticmethod
    def _get_fixed_accuracy_annotation(db: Session, answer_id: int) -> Optional[Annotation]:
        answer = db.query(Answer).filter(Answer.id == answer_id).first()
        if not answer:
            return None

        accuracy_rubric = get_fixed_accuracy_rubric_or_raise(db, answer.snapshot.target_id)
        return (
            db.query(Annotation)
            .filter(
                Annotation.answer_id == answer_id,
                Annotation.rubric_id == accuracy_rubric.id,
            )
            .first()
        )

    @staticmethod
    def _upsert_accuracy_rubric_annotation(
        db: Session,
        answer_id: int,
        label: bool,
        notes: str | None,
    ) -> Annotation:
        answer = db.query(Answer).filter(Answer.id == answer_id).first()
        if not answer:
            raise ValueError(f"Answer {answer_id} not found")

        accuracy_rubric = get_fixed_accuracy_rubric_or_raise(db, answer.snapshot.target_id)
        existing = AnnotationRepository._get_fixed_accuracy_annotation(db, answer_id)
        option_value = accuracy_label_from_bool(label, accuracy_rubric)
        if existing:
            existing.option_value = option_value
            existing.notes = notes
            return existing

        created = Annotation(
            answer_id=answer_id,
            rubric_id=accuracy_rubric.id,
            option_value=option_value,
            notes=notes,
        )
        db.add(created)
        db.flush()
        return created

    @staticmethod
    def create(db: Session, annotation_data: dict) -> AnnotationRecord:
        """Create or replace the fixed-rubric annotation for an answer."""
        annotation = AnnotationRepository._upsert_accuracy_rubric_annotation(
            db,
            answer_id=annotation_data["answer_id"],
            label=annotation_data["label"],
            notes=annotation_data.get("notes"),
        )
        db.commit()
        db.refresh(annotation)
        return AnnotationRepository._to_record(annotation)

    @staticmethod
    def create_many(db: Session, annotations_data: List[dict]) -> List[AnnotationRecord]:
        """Create or replace multiple fixed-rubric annotations."""
        created_or_updated: list[Annotation] = []
        for data in annotations_data:
            created_or_updated.append(
                AnnotationRepository._upsert_accuracy_rubric_annotation(
                    db,
                    answer_id=data["answer_id"],
                    label=data["label"],
                    notes=data.get("notes"),
                )
            )
        db.commit()
        for annotation in created_or_updated:
            db.refresh(annotation)
        return [AnnotationRepository._to_record(annotation) for annotation in created_or_updated]

    @staticmethod
    def get_by_id(db: Session, annotation_id: int) -> Optional[AnnotationRecord]:
        """Get fixed-rubric annotation by the underlying rubric-annotation ID."""
        annotation = (
            db.query(Annotation)
            .join(TargetRubric, Annotation.rubric_id == TargetRubric.id)
            .filter(
                Annotation.id == annotation_id,
                TargetRubric.group == RUBRIC_GROUP_FIXED,
                TargetRubric.name == FIXED_ACCURACY_NAME,
            )
            .first()
        )
        return AnnotationRepository._to_record(annotation) if annotation else None

    @staticmethod
    def get_by_answer(db: Session, answer_id: int) -> Optional[AnnotationRecord]:
        """Get fixed-rubric annotation for an answer."""
        annotation = AnnotationRepository._get_fixed_accuracy_annotation(db, answer_id)
        return AnnotationRepository._to_record(annotation) if annotation else None

    @staticmethod
    def get_by_snapshot(db: Session, snapshot_id: int) -> List[AnnotationRecord]:
        """Get all fixed-rubric annotations for a snapshot."""
        annotations = (
            db.query(Annotation)
            .join(Answer, Annotation.answer_id == Answer.id)
            .join(TargetRubric, Annotation.rubric_id == TargetRubric.id)
            .filter(
                Answer.snapshot_id == snapshot_id,
                TargetRubric.group == RUBRIC_GROUP_FIXED,
                TargetRubric.name == FIXED_ACCURACY_NAME,
            )
            .all()
        )
        return [AnnotationRepository._to_record(annotation) for annotation in annotations]

    @staticmethod
    def get_by_snapshot_selected(db: Session, snapshot_id: int) -> List[AnnotationRecord]:
        """
        Get annotations for answers that are selected for annotation.
        Used for judge alignment metric calculation in service layer.
        """
        annotations = (
            db.query(Annotation)
            .join(Answer, Annotation.answer_id == Answer.id)
            .join(TargetRubric, Annotation.rubric_id == TargetRubric.id)
            .filter(
                Answer.snapshot_id == snapshot_id,
                Answer.is_selected_for_annotation == True,
                TargetRubric.group == RUBRIC_GROUP_FIXED,
                TargetRubric.name == FIXED_ACCURACY_NAME,
            )
            .all()
        )
        return [AnnotationRepository._to_record(annotation) for annotation in annotations]

    @staticmethod
    def count_by_snapshot(db: Session, snapshot_id: int) -> int:
        """Count fixed-rubric annotations for a snapshot."""
        return (
            db.query(Annotation)
            .join(Answer, Annotation.answer_id == Answer.id)
            .join(TargetRubric, Annotation.rubric_id == TargetRubric.id)
            .filter(
                Answer.snapshot_id == snapshot_id,
                TargetRubric.group == RUBRIC_GROUP_FIXED,
                TargetRubric.name == FIXED_ACCURACY_NAME,
            )
            .count()
        )

    @staticmethod
    def check_annotation_completion(db: Session, snapshot_id: int) -> dict:
        """
        Check if all selected answers have labels for every target rubric.

        Args:
            db: Database session
            snapshot_id: Snapshot ID

        Returns:
            Dictionary with completion statistics:
            {
                "selected_ids": list,
                "selected_and_annotated_ids": list,
                "is_complete": bool,
                "completion_percentage": float
            }
        """
        # Get question IDs of all selected answers
        selected_rows = (
            db.query(Answer.question_id)
            .filter(
                Answer.snapshot_id == snapshot_id,
                Answer.is_selected_for_annotation == True
            )
            .all()
        )
        selected_ids = [row[0] for row in selected_rows]

        selected_and_annotated_ids: list[int] = []
        target_id = (
            db.query(Snapshot.target_id)
            .filter(Snapshot.id == snapshot_id)
            .scalar()
        )
        if target_id and selected_ids:
            rubric_ids = [
                r[0] for r in
                db.query(TargetRubric.id)
                .filter(TargetRubric.target_id == target_id)
                .all()
            ]
            if rubric_ids:
                selected_answer_rows = (
                    db.query(Answer.question_id, Answer.id)
                    .filter(
                        Answer.snapshot_id == snapshot_id,
                        Answer.is_selected_for_annotation == True,
                    )
                    .all()
                )
                selected_answer_ids = [row[1] for row in selected_answer_rows]
                rubric_rows = (
                    db.query(Annotation.answer_id, Annotation.rubric_id)
                    .filter(
                        Annotation.answer_id.in_(selected_answer_ids),
                        Annotation.rubric_id.in_(rubric_ids),
                    )
                    .all()
                )
                expected_rubric_ids = set(rubric_ids)
                annotations_by_answer: dict[int, set[int]] = {}
                for answer_id, rubric_id in rubric_rows:
                    annotations_by_answer.setdefault(answer_id, set()).add(rubric_id)
                selected_and_annotated_ids = [
                    question_id
                    for question_id, answer_id in selected_answer_rows
                    if annotations_by_answer.get(answer_id, set()) >= expected_rubric_ids
                ]

        is_complete = len(selected_ids) > 0 and len(selected_ids) == len(selected_and_annotated_ids)
        completion_percentage = (
            (len(selected_and_annotated_ids) / len(selected_ids) * 100)
            if len(selected_ids) > 0
            else 0.0
        )

        return {
            "selected_ids": selected_ids,
            "selected_and_annotated_ids": selected_and_annotated_ids,
            "is_complete": is_complete,
            "completion_percentage": round(completion_percentage, 2)
        }

    @staticmethod
    def update(db: Session, annotation_id: int, annotation_data: dict) -> Optional[AnnotationRecord]:
        """Update a fixed-rubric annotation via the legacy endpoint."""
        annotation = (
            db.query(Annotation)
            .join(TargetRubric, Annotation.rubric_id == TargetRubric.id)
            .filter(
                Annotation.id == annotation_id,
                TargetRubric.group == RUBRIC_GROUP_FIXED,
                TargetRubric.name == FIXED_ACCURACY_NAME,
            )
            .first()
        )
        if not annotation:
            return None

        if "label" in annotation_data:
            annotation.option_value = accuracy_label_from_bool(annotation_data["label"], annotation.rubric)
        if "notes" in annotation_data:
            annotation.notes = annotation_data["notes"]
        db.commit()
        db.refresh(annotation)
        return AnnotationRepository._to_record(annotation)

    @staticmethod
    def delete(db: Session, annotation_id: int) -> bool:
        """Delete a fixed-rubric annotation via the legacy endpoint."""
        annotation = (
            db.query(Annotation)
            .join(TargetRubric, Annotation.rubric_id == TargetRubric.id)
            .filter(
                Annotation.id == annotation_id,
                TargetRubric.group == RUBRIC_GROUP_FIXED,
                TargetRubric.name == FIXED_ACCURACY_NAME,
            )
            .first()
        )
        if not annotation:
            return False

        db.delete(annotation)
        db.commit()
        return True
