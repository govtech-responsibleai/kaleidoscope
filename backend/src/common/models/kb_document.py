"""
Pydantic models for Knowledge Base Document API requests and responses.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class KBDocumentBase(BaseModel):
    """Base fields for Knowledge Base Document."""
    filename: str = Field(..., description="Filename of the document")
    content_type: str = Field(..., description="MIME type of the document")
    file_size: int = Field(..., description="File size in bytes")
    page_count: Optional[int] = Field(None, description="Number of pages (for PDFs/DOCX)")


class KBDocumentResponse(KBDocumentBase):
    """Response model for Knowledge Base Document."""
    id: int
    target_id: int
    sequence_order: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class KBDocumentTextResponse(BaseModel):
    """Response model for document text content."""
    id: int
    filename: str
    processed_text: str

    class Config:
        from_attributes = True


class KBDocumentListResponse(BaseModel):
    """Response model for list of KB documents."""
    documents: list[KBDocumentResponse]
    total_count: int
    total_size_bytes: int


class KBCompiledTextResponse(BaseModel):
    """Response model for compiled KB text from all documents."""
    target_id: int
    compiled_text: str
    document_count: int
    total_size_bytes: int
    documents: list[dict]  # List of {id, filename, size} for reference
