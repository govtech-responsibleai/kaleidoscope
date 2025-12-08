"""
Repository for Annotation database operations.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from src.common.database.models import Annotation, Answer


class AnnotationRepository:
    """Repository for Annotation CRUD operations."""

    @staticmethod
    def create(db: Session, annotation_data: dict) -> Annotation:
        """Create a new annotation."""
        annotation = Annotation(**annotation_data)
        db.add(annotation)
        db.commit()
        db.refresh(annotation)
        return annotation

    @staticmethod
    def create_many(db: Session, annotations_data: List[dict]) -> List[Annotation]:
        """Create multiple annotations."""
        annotations = [Annotation(**data) for data in annotations_data]
        db.add_all(annotations)
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
    def update(db: Session, annotation_id: int, annotation_data: dict) -> Optional[Annotation]:
        """Update an annotation."""
        annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
        if not annotation:
            return None

        for key, value in annotation_data.items():
            if value is not None:
                setattr(annotation, key, value)

        db.commit()
        db.refresh(annotation)
        return annotation

    @staticmethod
    def delete(db: Session, annotation_id: int) -> bool:
        """Delete an annotation."""
        annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
        if not annotation:
            return False

        db.delete(annotation)
        db.commit()
        return True
