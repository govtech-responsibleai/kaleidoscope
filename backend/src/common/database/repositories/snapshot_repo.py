"""
Repository for Snapshot database operations.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.common.database.models import Snapshot, Answer


class SnapshotRepository:
    """Repository for Snapshot CRUD operations."""

    @staticmethod
    def create(db: Session, snapshot_data: dict) -> Snapshot:
        """Create a new snapshot."""
        snapshot = Snapshot(**snapshot_data)
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        return snapshot

    @staticmethod
    def get_by_id(db: Session, snapshot_id: int) -> Optional[Snapshot]:
        """Get snapshot by ID."""
        return db.query(Snapshot).filter(Snapshot.id == snapshot_id).first()

    @staticmethod
    def get_by_target(
        db: Session,
        target_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[Snapshot]:
        """Get all snapshots for a target with pagination."""
        return (
            db.query(Snapshot)
            .filter(Snapshot.target_id == target_id)
            .order_by(Snapshot.created_at.asc()) # Different from other repos that do .desc()
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def update(db: Session, snapshot_id: int, snapshot_data: dict) -> Optional[Snapshot]:
        """Update a snapshot."""
        snapshot = db.query(Snapshot).filter(Snapshot.id == snapshot_id).first()
        if not snapshot:
            return None

        for key, value in snapshot_data.items():
            if value is not None:
                setattr(snapshot, key, value)

        db.commit()
        db.refresh(snapshot)
        return snapshot

    @staticmethod
    def delete(db: Session, snapshot_id: int) -> bool:
        """Delete a snapshot."""
        snapshot = db.query(Snapshot).filter(Snapshot.id == snapshot_id).first()
        if not snapshot:
            return False

        db.delete(snapshot)
        db.commit()
        return True

    @staticmethod
    def get_with_answer_count(db: Session, snapshot_id: int) -> Optional[dict]:
        """
        Get snapshot with answer statistics.

        Returns:
            Dictionary with snapshot data and counts:
            {
                "snapshot": Snapshot object,
                "total_answers": int,
                "selected_for_annotation": int
            }
        """
        snapshot = db.query(Snapshot).filter(Snapshot.id == snapshot_id).first()
        if not snapshot:
            return None

        total_answers = (
            db.query(func.count(Answer.id))
            .filter(Answer.snapshot_id == snapshot_id)
            .scalar()
        ) or 0

        selected_count = (
            db.query(func.count(Answer.id))
            .filter(
                Answer.snapshot_id == snapshot_id,
                Answer.is_selected_for_annotation == True
            )
            .scalar()
        ) or 0

        return {
            "snapshot": snapshot,
            "total_answers": total_answers,
            "selected_for_annotation": selected_count
        }
