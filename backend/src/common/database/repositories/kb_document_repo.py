"""
Repository for Knowledge Base Document database operations.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.common.database.models import KnowledgeBaseDocument


class KBDocumentRepository:
    """Repository for Knowledge Base Document CRUD operations."""

    @staticmethod
    def create(db: Session, document_data: dict) -> KnowledgeBaseDocument:
        """Create a new KB document."""
        document = KnowledgeBaseDocument(**document_data)
        db.add(document)
        db.commit()
        db.refresh(document)
        return document

    @staticmethod
    def get_by_id(db: Session, document_id: int) -> Optional[KnowledgeBaseDocument]:
        """Get KB document by ID."""
        return db.query(KnowledgeBaseDocument).filter(KnowledgeBaseDocument.id == document_id).first()

    @staticmethod
    def get_by_target(db: Session, target_id: int) -> List[KnowledgeBaseDocument]:
        """Get all KB documents for a target, ordered by sequence."""
        return (
            db.query(KnowledgeBaseDocument)
            .filter(KnowledgeBaseDocument.target_id == target_id)
            .order_by(KnowledgeBaseDocument.sequence_order, KnowledgeBaseDocument.created_at)
            .all()
        )

    @staticmethod
    def get_compiled_text(db: Session, target_id: int) -> str:
        """
        Get compiled text from all KB documents for a target.
        Returns a single string with all documents concatenated.
        """
        documents = KBDocumentRepository.get_by_target(db, target_id)

        if not documents:
            return ""

        # Concatenate all document texts with separators
        compiled_parts = []
        for doc in documents:
            compiled_parts.append(f"=== Source Document: {doc.filename} ===\n")
            compiled_parts.append(doc.processed_text)
            compiled_parts.append("\n\n")

        return "".join(compiled_parts)

    @staticmethod
    def get_stats(db: Session, target_id: int) -> dict:
        """Get statistics for KB documents of a target."""
        # Get document count
        count = (
            db.query(func.count(KnowledgeBaseDocument.id))
            .filter(KnowledgeBaseDocument.target_id == target_id)
            .scalar()
        ) or 0

        # Get total size
        total_size = (
            db.query(func.sum(KnowledgeBaseDocument.file_size))
            .filter(KnowledgeBaseDocument.target_id == target_id)
            .scalar()
        ) or 0

        return {
            "document_count": count,
            "total_size_bytes": int(total_size)
        }

    @staticmethod
    def delete(db: Session, document_id: int) -> bool:
        """Delete a KB document."""
        document = db.query(KnowledgeBaseDocument).filter(KnowledgeBaseDocument.id == document_id).first()
        if not document:
            return False

        db.delete(document)
        db.commit()
        return True
