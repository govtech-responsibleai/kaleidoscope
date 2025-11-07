"""
API routes for Knowledge Base Document management.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session

from src.common.database.connection import get_db
from src.common.database.repositories import TargetRepository, KBDocumentRepository
from src.common.models import (
    KBDocumentResponse,
    KBDocumentTextResponse,
    KBDocumentListResponse,
    KBCompiledTextResponse
)
from src.common.services import DocumentProcessor

router = APIRouter()


@router.post(
    "/targets/{target_id}/knowledge-base/upload",
    response_model=KBDocumentResponse,
    status_code=status.HTTP_201_CREATED
)
async def upload_kb_document(
    target_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload and process a knowledge base document for a target.

    Supported file types: PDF, DOCX, TXT, MD

    Args:
        target_id: Target ID
        file: File to upload
        db: Database session

    Returns:
        Created KB document

    Raises:
        HTTPException: If target not found or file type not supported
    """
    # Check if target exists
    target = TargetRepository.get_by_id(db, target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target {target_id} not found"
        )

    # Read file content
    file_content = await file.read()
    file_size = len(file_content)

    # Process document based on type
    try:
        processed_text, page_count = DocumentProcessor.process_document(
            file_content=file_content,
            content_type=file.content_type or "application/octet-stream",
            filename=file.filename or "unknown"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    # Get the next sequence order
    existing_docs = KBDocumentRepository.get_by_target(db, target_id)
    sequence_order = len(existing_docs)

    # Create KB document record
    document_data = {
        "target_id": target_id,
        "filename": file.filename,
        "content_type": file.content_type or "application/octet-stream",
        "processed_text": processed_text,
        "file_size": file_size,
        "page_count": page_count,
        "sequence_order": sequence_order
    }

    document = KBDocumentRepository.create(db, document_data)
    return document


@router.get(
    "/targets/{target_id}/knowledge-base/documents",
    response_model=KBDocumentListResponse
)
def list_kb_documents(
    target_id: int,
    db: Session = Depends(get_db)
):
    """
    List all knowledge base documents for a target.

    Args:
        target_id: Target ID
        db: Database session

    Returns:
        List of KB documents with stats

    Raises:
        HTTPException: If target not found
    """
    # Check if target exists
    target = TargetRepository.get_by_id(db, target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target {target_id} not found"
        )

    # Get documents
    documents = KBDocumentRepository.get_by_target(db, target_id)

    # Get stats
    stats = KBDocumentRepository.get_stats(db, target_id)

    return KBDocumentListResponse(
        documents=documents,
        total_count=stats["document_count"],
        total_size_bytes=stats["total_size_bytes"]
    )


@router.get(
    "/targets/{target_id}/knowledge-base/text",
    response_model=KBCompiledTextResponse
)
def get_compiled_kb_text(
    target_id: int,
    db: Session = Depends(get_db)
):
    """
    Get compiled text from all knowledge base documents for a target.

    This returns the full concatenated text from all documents,
    which can be used for question generation with long-context LLMs.

    Args:
        target_id: Target ID
        db: Database session

    Returns:
        Compiled KB text with metadata

    Raises:
        HTTPException: If target not found
    """
    # Check if target exists
    target = TargetRepository.get_by_id(db, target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target {target_id} not found"
        )

    # Get compiled text
    compiled_text = KBDocumentRepository.get_compiled_text(db, target_id)

    # Get documents for reference
    documents = KBDocumentRepository.get_by_target(db, target_id)

    # Get stats
    stats = KBDocumentRepository.get_stats(db, target_id)

    # Create document list for reference
    doc_list = [
        {"id": doc.id, "filename": doc.filename, "size": doc.file_size}
        for doc in documents
    ]

    return KBCompiledTextResponse(
        target_id=target_id,
        compiled_text=compiled_text,
        document_count=stats["document_count"],
        total_size_bytes=stats["total_size_bytes"],
        documents=doc_list
    )


@router.get(
    "/knowledge-base/documents/{document_id}",
    response_model=KBDocumentTextResponse
)
def get_kb_document(
    document_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific knowledge base document with its text content.

    Args:
        document_id: Document ID
        db: Database session

    Returns:
        Document with text content

    Raises:
        HTTPException: If document not found
    """
    document = KBDocumentRepository.get_by_id(db, document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found"
        )

    return KBDocumentTextResponse(
        id=document.id,
        filename=document.filename,
        processed_text=document.processed_text
    )


@router.delete(
    "/knowledge-base/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_kb_document(
    document_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a knowledge base document.

    Args:
        document_id: Document ID
        db: Database session

    Raises:
        HTTPException: If document not found
    """
    success = KBDocumentRepository.delete(db, document_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found"
        )
