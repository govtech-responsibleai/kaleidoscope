"""
Repository for Annotation database operations.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from src.common.database.models import Annotation, Answer, Snapshot, TargetRubric, RubricAnnotation
from src.common.services.system_rubrics import accuracy_label_from_bool, ensure_fixed_accuracy_rubric


class AnnotationRepository:
    """Repository for Annotation CRUD operations."""

    @staticmethod
    def _sync_accuracy_rubric_annotation(db: Session, annotation: Annotation) -> None:
        answer = db.query(Answer).filter(Answer.id == annotation.answer_id).first()
        if not answer:
            return
        accuracy_rubric = ensure_fixed_accuracy_rubric(db, answer.snapshot.target_id)
        existing = (
            db.query(RubricAnnotation)
            .filter(
                RubricAnnotation.answer_id == annotation.answer_id,
                RubricAnnotation.rubric_id == accuracy_rubric.id,
            )
            .first()
        )
        option_value = accuracy_label_from_bool(annotation.label, accuracy_rubric)
        if existing:
            existing.option_value = option_value
            existing.notes = annotation.notes
        else:
            db.add(
                RubricAnnotation(
                    answer_id=annotation.answer_id,
                    rubric_id=accuracy_rubric.id,
                    option_value=option_value,
                    notes=annotation.notes,
                )
            )

    @staticmethod
    def create(db: Session, annotation_data: dict) -> Annotation:
        """Create a new annotation."""
        annotation = Annotation(**annotation_data)
        db.add(annotation)
        db.flush()
        AnnotationRepository._sync_accuracy_rubric_annotation(db, annotation)
        db.commit()
        db.refresh(annotation)
        return annotation

    @staticmethod
    def create_many(db: Session, annotations_data: List[dict]) -> List[Annotation]:
        """Create multiple annotations."""
        annotations = [Annotation(**data) for data in annotations_data]
        db.add_all(annotations)
        db.flush()
        for annotation in annotations:
            AnnotationRepository._sync_accuracy_rubric_annotation(db, annotation)
        db.commit()
        for annotation in annotations:
            db.refresh(annotation)
        return annotations

    @staticmethod
    def get_by_id(db: Session, annotation_id: int) -> Optional[Annotation]:
        """Get annotation by ID."""
        return db.query(Annotation).filter(Annotation.id == annotation_id).first()

    @staticmethod
    def get_by_answer(db: Session, answer_id: int) -> Optional[Annotation]:
        """Get annotation for a specific answer (one-to-one relationship)."""
        return db.query(Annotation).filter(Annotation.answer_id == answer_id).first()

    @staticmethod
    def get_by_snapshot(db: Session, snapshot_id: int) -> List[Annotation]:
        """Get all annotations for a snapshot."""
        return (
            db.query(Annotation)
            .join(Answer)
            .filter(Answer.snapshot_id == snapshot_id)
            .all()
        )

    @staticmethod
    def get_by_snapshot_selected(db: Session, snapshot_id: int) -> List[Annotation]:
        """
        Get annotations for answers that are selected for annotation.
        Used for judge alignment metric calculation in service layer.
        """
        return (
            db.query(Annotation)
            .join(Answer)
            .filter(
                Answer.snapshot_id == snapshot_id,
                Answer.is_selected_for_annotation == True
            )
            .all()
        )

    @staticmethod
    def count_by_snapshot(db: Session, snapshot_id: int) -> int:
        """Count total annotations for a snapshot."""
        return (
            db.query(Annotation)
            .join(Answer)
            .filter(Answer.snapshot_id == snapshot_id)
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
                    db.query(RubricAnnotation.answer_id, RubricAnnotation.rubric_id)
                    .filter(
                        RubricAnnotation.answer_id.in_(selected_answer_ids),
                        RubricAnnotation.rubric_id.in_(rubric_ids),
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
    def update(db: Session, annotation_id: int, annotation_data: dict) -> Optional[Annotation]:
        """Update an annotation."""
        annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
        if not annotation:
            return None

        for key, value in annotation_data.items():
            if value is not None:
                setattr(annotation, key, value)

        AnnotationRepository._sync_accuracy_rubric_annotation(db, annotation)
        db.commit()
        db.refresh(annotation)
        return annotation

    @staticmethod
    def delete(db: Session, annotation_id: int) -> bool:
        """Delete an annotation."""
        annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
        if not annotation:
            return False

        answer = db.query(Answer).filter(Answer.id == annotation.answer_id).first()
        if answer:
            accuracy_rubric = ensure_fixed_accuracy_rubric(db, answer.snapshot.target_id)
            rubric_annotation = (
                db.query(RubricAnnotation)
                .filter(
                    RubricAnnotation.answer_id == annotation.answer_id,
                    RubricAnnotation.rubric_id == accuracy_rubric.id,
                )
                .first()
            )
            if rubric_annotation:
                db.delete(rubric_annotation)
        db.delete(annotation)
        db.commit()
        return True
