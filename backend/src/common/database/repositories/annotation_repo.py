"""Repository for rubric-scoped annotation CRUD operations."""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from src.common.database.models import Annotation, Answer, Snapshot, TargetRubric
from src.rubric.services.system_rubrics import canonicalize_rubric_option_value


@dataclass
class AnnotationRecord:
    id: int
    answer_id: int
    rubric_id: int
    option_value: str
    notes: str | None
    created_at: datetime
    updated_at: datetime


class AnnotationRepository:
    """Repository for rubric-scoped annotation CRUD operations."""

    @staticmethod
    def _to_record(annotation: Annotation) -> AnnotationRecord:
        canonical_option = canonicalize_rubric_option_value(annotation.rubric, annotation.option_value)
        return AnnotationRecord(
            id=annotation.id,
            answer_id=annotation.answer_id,
            rubric_id=annotation.rubric_id,
            option_value=canonical_option or annotation.option_value,
            notes=annotation.notes,
            created_at=annotation.created_at,
            updated_at=annotation.updated_at,
        )

    @staticmethod
    def _require_answer(db: Session, answer_id: int) -> Answer:
        answer = db.query(Answer).filter(Answer.id == answer_id).first()
        if not answer:
            raise ValueError(f"Answer {answer_id} not found")
        return answer

    @staticmethod
    def _require_rubric(db: Session, rubric_id: int) -> TargetRubric:
        rubric = db.query(TargetRubric).filter(TargetRubric.id == rubric_id).first()
        if not rubric:
            raise ValueError(f"Rubric {rubric_id} not found")
        return rubric

    @staticmethod
    def _validate_answer_rubric_scope(db: Session, answer_id: int, rubric_id: int) -> TargetRubric:
        answer = AnnotationRepository._require_answer(db, answer_id)
        rubric = AnnotationRepository._require_rubric(db, rubric_id)
        if answer.snapshot is None:
            raise ValueError(f"Answer {answer_id} is missing snapshot context")
        if rubric.target_id != answer.snapshot.target_id:
            raise ValueError(f"Rubric {rubric_id} does not belong to answer {answer_id}")
        return rubric

    @staticmethod
    def _get_row(db: Session, answer_id: int, rubric_id: int) -> Optional[Annotation]:
        return (
            db.query(Annotation)
            .filter(
                Annotation.answer_id == answer_id,
                Annotation.rubric_id == rubric_id,
            )
            .first()
        )

    @staticmethod
    def create(db: Session, annotation_data: dict) -> AnnotationRecord:
        """Create or replace one rubric-scoped annotation row."""
        answer_id = annotation_data["answer_id"]
        rubric_id = annotation_data["rubric_id"]
        rubric = AnnotationRepository._validate_answer_rubric_scope(db, answer_id, rubric_id)
        option_value = canonicalize_rubric_option_value(rubric, annotation_data["option_value"])
        if option_value is None:
            raise ValueError("option_value is required")

        annotation = AnnotationRepository._get_row(db, answer_id, rubric_id)
        if annotation is None:
            annotation = Annotation(
                answer_id=answer_id,
                rubric_id=rubric_id,
                option_value=option_value,
                notes=annotation_data.get("notes"),
            )
            db.add(annotation)
        else:
            annotation.option_value = option_value
            annotation.notes = annotation_data.get("notes")

        db.commit()
        db.refresh(annotation)
        return AnnotationRepository._to_record(annotation)

    @staticmethod
    def create_many(db: Session, rubric_id: int, annotations_data: List[dict]) -> List[AnnotationRecord]:
        """Create or replace multiple annotation rows for one rubric."""
        records: list[Annotation] = []
        rubric = AnnotationRepository._require_rubric(db, rubric_id)
        for data in annotations_data:
            answer_id = data["answer_id"]
            answer = AnnotationRepository._require_answer(db, answer_id)
            if answer.snapshot is None or answer.snapshot.target_id != rubric.target_id:
                raise ValueError(f"Rubric {rubric_id} does not belong to answer {answer_id}")
            option_value = canonicalize_rubric_option_value(rubric, data["option_value"])
            if option_value is None:
                raise ValueError("option_value is required")

            annotation = AnnotationRepository._get_row(db, answer_id, rubric_id)
            if annotation is None:
                annotation = Annotation(
                    answer_id=answer_id,
                    rubric_id=rubric_id,
                    option_value=option_value,
                    notes=data.get("notes"),
                )
                db.add(annotation)
            else:
                annotation.option_value = option_value
                annotation.notes = data.get("notes")
            records.append(annotation)

        db.commit()
        for annotation in records:
            db.refresh(annotation)
        return [AnnotationRepository._to_record(annotation) for annotation in records]

    @staticmethod
    def get_by_id(db: Session, annotation_id: int, rubric_id: int) -> Optional[AnnotationRecord]:
        """Get one annotation row by ID scoped to a rubric."""
        annotation = (
            db.query(Annotation)
            .filter(
                Annotation.id == annotation_id,
                Annotation.rubric_id == rubric_id,
            )
            .first()
        )
        return AnnotationRepository._to_record(annotation) if annotation else None

    @staticmethod
    def get_by_answer(db: Session, answer_id: int, rubric_id: int) -> Optional[AnnotationRecord]:
        """Get one annotation row for an answer/rubric pair."""
        annotation = AnnotationRepository._get_row(db, answer_id, rubric_id)
        return AnnotationRepository._to_record(annotation) if annotation else None

    @staticmethod
    def get_by_snapshot(
        db: Session,
        snapshot_id: int,
        rubric_id: Optional[int] = None,
    ) -> List[AnnotationRecord]:
        """Get annotation rows for a snapshot, optionally filtered to one rubric."""
        query = (
            db.query(Annotation)
            .join(Answer, Annotation.answer_id == Answer.id)
            .filter(Answer.snapshot_id == snapshot_id)
        )
        if rubric_id is not None:
            query = query.filter(Annotation.rubric_id == rubric_id)
        annotations = query.order_by(Annotation.answer_id.asc(), Annotation.rubric_id.asc()).all()
        return [AnnotationRepository._to_record(annotation) for annotation in annotations]

    @staticmethod
    def get_by_snapshot_selected(db: Session, snapshot_id: int, rubric_id: int) -> List[AnnotationRecord]:
        """Get selected-answer annotation rows for one rubric."""
        annotations = (
            db.query(Annotation)
            .join(Answer, Annotation.answer_id == Answer.id)
            .filter(
                Answer.snapshot_id == snapshot_id,
                Answer.is_selected_for_annotation == True,
                Annotation.rubric_id == rubric_id,
            )
            .all()
        )
        return [AnnotationRepository._to_record(annotation) for annotation in annotations]

    @staticmethod
    def count_by_snapshot(db: Session, snapshot_id: int, rubric_id: Optional[int] = None) -> int:
        """Count annotation rows for a snapshot, optionally filtered to one rubric."""
        query = (
            db.query(Annotation)
            .join(Answer, Annotation.answer_id == Answer.id)
            .filter(Answer.snapshot_id == snapshot_id)
        )
        if rubric_id is not None:
            query = query.filter(Annotation.rubric_id == rubric_id)
        return query.count()

    @staticmethod
    def check_annotation_completion(db: Session, snapshot_id: int) -> dict:
        """Check whether selected answers are annotated across all target rubrics."""
        selected_rows = (
            db.query(Answer.question_id)
            .filter(
                Answer.snapshot_id == snapshot_id,
                Answer.is_selected_for_annotation == True,
            )
            .all()
        )
        selected_ids = [row[0] for row in selected_rows]

        selected_and_annotated_ids: list[int] = []
        target_id = db.query(Snapshot.target_id).filter(Snapshot.id == snapshot_id).scalar()
        if target_id and selected_ids:
            rubric_ids = [
                row[0]
                for row in db.query(TargetRubric.id).filter(TargetRubric.target_id == target_id).all()
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
                for answer_id, annotation_rubric_id in rubric_rows:
                    annotations_by_answer.setdefault(answer_id, set()).add(annotation_rubric_id)
                selected_and_annotated_ids = [
                    question_id
                    for question_id, answer_id in selected_answer_rows
                    if annotations_by_answer.get(answer_id, set()) >= expected_rubric_ids
                ]

        is_complete = len(selected_ids) > 0 and len(selected_ids) == len(selected_and_annotated_ids)
        completion_percentage = (
            (len(selected_and_annotated_ids) / len(selected_ids) * 100)
            if selected_ids
            else 0.0
        )
        return {
            "selected_ids": selected_ids,
            "selected_and_annotated_ids": selected_and_annotated_ids,
            "is_complete": is_complete,
            "completion_percentage": round(completion_percentage, 2),
        }

    @staticmethod
    def update(db: Session, annotation_id: int, rubric_id: int, annotation_data: dict) -> Optional[AnnotationRecord]:
        """Update one annotation row, validated against rubric scope."""
        annotation = (
            db.query(Annotation)
            .filter(
                Annotation.id == annotation_id,
                Annotation.rubric_id == rubric_id,
            )
            .first()
        )
        if not annotation:
            return None

        if "option_value" in annotation_data:
            option_value = canonicalize_rubric_option_value(annotation.rubric, annotation_data["option_value"])
            if option_value is None:
                raise ValueError("option_value is required")
            annotation.option_value = option_value
        if "notes" in annotation_data:
            annotation.notes = annotation_data["notes"]
        db.commit()
        db.refresh(annotation)
        return AnnotationRepository._to_record(annotation)

    @staticmethod
    def delete(db: Session, annotation_id: int, rubric_id: int) -> bool:
        """Delete one annotation row, validated against rubric scope."""
        annotation = (
            db.query(Annotation)
            .filter(
                Annotation.id == annotation_id,
                Annotation.rubric_id == rubric_id,
            )
            .first()
        )
        if not annotation:
            return False

        db.delete(annotation)
        db.commit()
        return True
