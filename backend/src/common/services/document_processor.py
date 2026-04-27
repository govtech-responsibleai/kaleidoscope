"""
Document processing service for extracting text from various file formats.
"""

import io
from typing import Tuple
from pypdf import PdfReader
from docx import Document as DocxDocument


class DocumentProcessor:
    """Service for processing and extracting text from documents."""

    @staticmethod
    def process_pdf(file_content: bytes) -> Tuple[str, int]:
        """
        Extract text from PDF file.

        Args:
            file_content: Binary content of the PDF file

        Returns:
            Tuple of (processed_text, page_count)
        """
        pdf_file = io.BytesIO(file_content)
        reader = PdfReader(pdf_file)

        text_parts = []
        page_count = len(reader.pages)

        for page_num, page in enumerate(reader.pages, 1):
            text = page.extract_text()
            if text.strip():
                text_parts.append(f"--- Page {page_num} ---\n{text.strip()}")

        processed_text = "\n\n".join(text_parts)
        return processed_text, page_count

    @staticmethod
    def process_docx(file_content: bytes) -> Tuple[str, int]:
        """
        Extract text from DOCX file.

        Args:
            file_content: Binary content of the DOCX file

        Returns:
            Tuple of (processed_text, page_count)
            Note: Page count for DOCX is estimated based on paragraphs
        """
        docx_file = io.BytesIO(file_content)
        doc = DocxDocument(docx_file)

        paragraphs = []
        for para in doc.paragraphs:
            if para.text.strip():
                paragraphs.append(para.text.strip())

        processed_text = "\n\n".join(paragraphs)

        # Estimate page count (rough estimate: ~10 paragraphs per page)
        page_count = max(1, len(paragraphs) // 10)

        return processed_text, page_count

    @staticmethod
    def process_text(file_content: bytes) -> Tuple[str, None]:
        """
        Process plain text file (TXT, MD).

        Args:
            file_content: Binary content of the text file

        Returns:
            Tuple of (processed_text, None) - no page count for text files
        """
        try:
            # Try UTF-8 first
            text = file_content.decode('utf-8')
        except UnicodeDecodeError:
            # Fallback to latin-1 if UTF-8 fails
            text = file_content.decode('latin-1')

        # Clean up text: normalize line endings, remove excessive whitespace
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        lines = [line.rstrip() for line in text.split('\n')]
        processed_text = '\n'.join(lines).strip()

        return processed_text, None

    @staticmethod
    def process_document(file_content: bytes, content_type: str, filename: str) -> Tuple[str, int]:
        """
        Process document based on content type.

        Args:
            file_content: Binary content of the file
            content_type: MIME type of the file
            filename: Original filename (used as fallback for type detection)

        Returns:
            Tuple of (processed_text, page_count)

        Raises:
            ValueError: If file type is not supported
        """
        # Normalize content type
        content_type_lower = content_type.lower()
        filename_lower = filename.lower()

        # Determine file type
        if content_type_lower == "application/pdf" or filename_lower.endswith('.pdf'):
            return DocumentProcessor.process_pdf(file_content)

        elif content_type_lower in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                     "application/msword"] or filename_lower.endswith(('.docx', '.doc')):
            return DocumentProcessor.process_docx(file_content)

        elif (content_type_lower.startswith("text/") or
              filename_lower.endswith(('.txt', '.md', '.markdown'))):
            return DocumentProcessor.process_text(file_content)

        else:
            raise ValueError(f"Unsupported file type: {content_type} (filename: {filename})")
