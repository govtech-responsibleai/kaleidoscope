"""
Repository for Persona database operations.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.common.database.models import Persona, StatusEnum


class PersonaRepository:
    """Repository for Persona CRUD operations."""

    @staticmethod
    def create(db: Session, persona_data: dict) -> Persona:
        """Create a new persona."""
        persona = Persona(**persona_data)
        db.add(persona)
        db.commit()
        db.refresh(persona)
        return persona

    @staticmethod
    def create_many(db: Session, personas_data: List[dict]) -> List[Persona]:
        """Create multiple personas."""
        personas = [Persona(**data) for data in personas_data]
        db.add_all(personas)
        db.commit()
        for persona in personas:
            db.refresh(persona)
        return personas

    @staticmethod
    def get_by_id(db: Session, persona_id: int) -> Optional[Persona]:
        """Get persona by ID."""
        return db.query(Persona).filter(Persona.id == persona_id).first()

    @staticmethod
    def get_by_target(
        db: Session,
        target_id: int,
        status: Optional[StatusEnum] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Persona]:
        """Get personas for a target, optionally filtered by status."""
        query = db.query(Persona).filter(Persona.target_id == target_id)
        if status:
            query = query.filter(Persona.status == status)
        return query.offset(skip).limit(limit).all()

    @staticmethod
    def get_by_job(db: Session, job_id: int) -> List[Persona]:
        """Get all personas from a specific job."""
        return db.query(Persona).filter(Persona.job_id == job_id).all()

    @staticmethod
    def update(db: Session, persona_id: int, persona_data: dict) -> Optional[Persona]:
        """Update a persona."""
        persona = db.query(Persona).filter(Persona.id == persona_id).first()
        if not persona:
            return None

        for key, value in persona_data.items():
            if value is not None:
                setattr(persona, key, value)

        # Mark as edited if content changed
        if any(key in persona_data for key in ['title', 'info', 'style', 'use_case']):
            persona.status = StatusEnum.edited

        db.commit()
        db.refresh(persona)
        return persona

    @staticmethod
    def approve(db: Session, persona_id: int) -> Optional[Persona]:
        """Approve a persona."""
        persona = db.query(Persona).filter(Persona.id == persona_id).first()
        if not persona:
            return None

        persona.status = StatusEnum.approved
        db.commit()
        db.refresh(persona)
        return persona

    @staticmethod
    def reject(db: Session, persona_id: int) -> Optional[Persona]:
        """Reject a persona."""
        persona = db.query(Persona).filter(Persona.id == persona_id).first()
        if not persona:
            return None

        persona.status = StatusEnum.rejected
        db.commit()
        db.refresh(persona)
        return persona

    @staticmethod
    def bulk_approve(db: Session, persona_ids: List[int]) -> List[Persona]:
        """Approve multiple personas."""
        personas = db.query(Persona).filter(Persona.id.in_(persona_ids)).all()
        for persona in personas:
            persona.status = StatusEnum.approved
        db.commit()
        return personas

    @staticmethod
    def get_approved_by_target(db: Session, target_id: int) -> List[Persona]:
        """Get all approved personas for a target."""
        return (
            db.query(Persona)
            .filter(
                Persona.target_id == target_id,
                Persona.status == StatusEnum.approved
            )
            .all()
        )
