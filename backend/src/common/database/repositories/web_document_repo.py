"""
Repository for Web Document database operations.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from src.common.database.models import WebDocument


class WebDocumentRepository:
    """Repository for Web Document CRUD operations."""

    @staticmethod
    def create(db: Session, document_data: dict) -> WebDocument:
        """Create a new web document."""
        document = WebDocument(**document_data)
        db.add(document)
        db.commit()
        db.refresh(document)
        return document

    @staticmethod
    def get_by_id(db: Session, document_id: int) -> Optional[WebDocument]:
        """Get web document by ID."""
        return db.query(WebDocument).filter(WebDocument.id == document_id).first()

    @staticmethod
    def get_by_target(db: Session, target_id: int) -> List[WebDocument]:
        """Get all web documents for a target, ordered by creation date."""
        return (
            db.query(WebDocument)
            .filter(WebDocument.target_id == target_id)
            .order_by(WebDocument.created_at.desc())
            .all()
        )

    @staticmethod
    def update(db: Session, document_id: int, update_data: dict) -> Optional[WebDocument]:
        """Update a web document."""
        document = db.query(WebDocument).filter(WebDocument.id == document_id).first()
        if not document:
            return None
        for key, value in update_data.items():
            setattr(document, key, value)
        db.commit()
        db.refresh(document)
        return document

    @staticmethod
    def upsert_for_target(db: Session, target_id: int, document_data: dict) -> WebDocument:
        """Create or replace the web document for a target.

        Keeps only one WebDocument per target to prevent unbounded growth.
        """
        existing = (
            db.query(WebDocument)
            .filter(WebDocument.target_id == target_id)
            .first()
        )
        if existing:
            for key, value in document_data.items():
                setattr(existing, key, value)
            db.commit()
            db.refresh(existing)
            return existing

        document = WebDocument(target_id=target_id, **document_data)
        db.add(document)
        db.commit()
        db.refresh(document)
        return document

    @staticmethod
    def get_compiled_context(db: Session, target_id: int) -> str:
        """
        Get formatted context from the latest web document for a target.

        Returns:
            Formatted string of search results, or empty string if none exist.
        """
        latest = (
            db.query(WebDocument)
            .filter(WebDocument.target_id == target_id)
            .order_by(WebDocument.created_at.desc())
            .first()
        )

        if not latest or not latest.results:
            return ""

        results = latest.results
        if isinstance(results, dict):
            results = results.get("results", [])

        formatted_blocks = []
        for result in results:
            formatted_blocks.append(
                f"Source: {result.get('title', '')}\n"
                f"URL: {result.get('url', '')}\n"
                f"Content: {result.get('snippet', '')}"
            )

        return "\n\n".join(formatted_blocks)
