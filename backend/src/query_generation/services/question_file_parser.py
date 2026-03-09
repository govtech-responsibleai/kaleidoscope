"""
Service for parsing question files in various formats (CSV, JSON, Excel).
"""

import csv
import json
import logging
from io import StringIO, BytesIO
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session

from src.common.database.models import StatusEnum, QuestionTypeEnum, QuestionScopeEnum, QuestionSourceEnum
from src.common.database.repositories.persona_repo import PersonaRepository

logger = logging.getLogger(__name__)


class QuestionFileParser:
    """Parser for question files in various formats."""

    SUPPORTED_FORMATS = {
        "csv": "text/csv",
        "json": "application/json",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xls": "application/vnd.ms-excel",
    }

    # Field mapping from user file to internal format
    FIELD_MAPPING = {
        "question": "text",  # REQUIRED
        "id": "orig_id",
        "persona": "persona_title",
        "type": "type",
        "scope": "scope",
    }

    @staticmethod
    def parse_file(
        file_content: bytes,
        content_type: str,
        filename: str
    ) -> List[Dict[str, Any]]:
        """
        Parse a file and extract question data.

        Args:
            file_content: File content as bytes
            content_type: MIME type of the file
            filename: Original filename

        Returns:
            List of question dictionaries with mapped fields

        Raises:
            ValueError: If file format is not supported or parsing fails
        """
        # Determine format from content type and filename
        file_ext = filename.lower().split('.')[-1] if '.' in filename else ''

        if content_type == "text/csv" or file_ext == "csv":
            return QuestionFileParser._parse_csv(file_content)
        elif content_type == "application/json" or file_ext == "json":
            return QuestionFileParser._parse_json(file_content)
        elif content_type in [
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-excel"
        ] or file_ext in ["xlsx", "xls"]:
            return QuestionFileParser._parse_excel(file_content)
        else:
            raise ValueError(
                f"Unsupported file format. Content type: {content_type}, "
                f"Extension: {file_ext}. Supported formats: CSV, JSON, Excel (xlsx/xls)"
            )

    @staticmethod
    def _parse_csv(file_content: bytes) -> List[Dict[str, Any]]:
        """Parse CSV file."""
        try:
            # Decode bytes to string, handling BOM if present
            try:
                text_content = file_content.decode('utf-8-sig')  # Handles UTF-8 BOM
            except UnicodeDecodeError:
                text_content = file_content.decode('utf-8')

            csv_file = StringIO(text_content)
            reader = csv.DictReader(csv_file)

            questions = []
            for row_num, row in enumerate(reader, start=2):  # start=2 because row 1 is header
                # Debug: log the actual columns in the first row
                if row_num == 2:
                    logger.info(f"CSV columns detected: {list(row.keys())}")
                    logger.debug(f"First row data: {row}")

                mapped_row = QuestionFileParser._map_fields(row)
                if mapped_row:
                    questions.append(mapped_row)
                else:
                    logger.warning(f"Row {row_num} skipped: missing required 'question' field. Row keys: {list(row.keys())}")

            if not questions:
                raise ValueError("No valid questions found in CSV file")

            return questions

        except UnicodeDecodeError:
            raise ValueError("Failed to decode CSV file. Please ensure it's UTF-8 encoded.")
        except Exception as e:
            raise ValueError(f"Failed to parse CSV file: {str(e)}")

    @staticmethod
    def _parse_json(file_content: bytes) -> List[Dict[str, Any]]:
        """Parse JSON file."""
        try:
            # Decode bytes to string
            text_content = file_content.decode('utf-8')
            data = json.loads(text_content)

            # Handle both array of objects and object with questions array
            if isinstance(data, list):
                questions_data = data
            elif isinstance(data, dict) and "questions" in data:
                questions_data = data["questions"]
            else:
                raise ValueError(
                    "JSON must be either an array of question objects or "
                    "an object with a 'questions' array"
                )

            questions = []
            for idx, item in enumerate(questions_data):
                if not isinstance(item, dict):
                    logger.warning(f"Item {idx} skipped: not an object")
                    continue

                mapped_item = QuestionFileParser._map_fields(item)
                if mapped_item:
                    questions.append(mapped_item)
                else:
                    logger.warning(f"Item {idx} skipped: missing required 'question' field")

            if not questions:
                raise ValueError("No valid questions found in JSON file")

            return questions

        except UnicodeDecodeError:
            raise ValueError("Failed to decode JSON file. Please ensure it's UTF-8 encoded.")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {str(e)}")
        except Exception as e:
            raise ValueError(f"Failed to parse JSON file: {str(e)}")

    @staticmethod
    def _parse_excel(file_content: bytes) -> List[Dict[str, Any]]:
        """Parse Excel file (xlsx/xls)."""
        try:
            import pandas as pd

            # Read Excel file from bytes
            excel_file = BytesIO(file_content)
            # Use openpyxl for .xlsx and xlrd for .xls (if available)
            # pandas will auto-detect the format
            df = pd.read_excel(excel_file, engine=None)

            # Convert DataFrame to list of dicts
            questions = []
            for idx, row in df.iterrows():
                # Convert row to dict, filtering out NaN values
                row_dict = {k: v for k, v in row.to_dict().items() if pd.notna(v)}

                mapped_row = QuestionFileParser._map_fields(row_dict)
                if mapped_row:
                    questions.append(mapped_row)
                else:
                    logger.warning(f"Row {idx + 2} skipped: missing required 'question' field")

            if not questions:
                raise ValueError("No valid questions found in Excel file")

            return questions

        except ImportError:
            raise ValueError(
                "Excel parsing requires pandas and openpyxl. "
                "Please install them: pip install pandas openpyxl"
            )
        except Exception as e:
            raise ValueError(f"Failed to parse Excel file: {str(e)}")

    @staticmethod
    def _map_fields(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Map user fields to internal format.

        Args:
            row: Dictionary with user-provided field names

        Returns:
            Mapped dictionary or None if required fields are missing
        """
        mapped = {}

        # Create case-insensitive lookup for row keys
        row_lower = {k.lower(): v for k, v in row.items()}

        # Map fields according to FIELD_MAPPING
        for user_field, internal_field in QuestionFileParser.FIELD_MAPPING.items():
            if user_field in row_lower:
                value = row_lower[user_field]
                # Convert to string and strip whitespace
                if isinstance(value, str):
                    value = value.strip()
                elif value is not None:
                    value = str(value).strip()

                if value:  # Only add non-empty values
                    mapped[internal_field] = value

        # Check if required field 'text' (from 'question') is present
        if "text" not in mapped:
            return None

        return mapped

    @staticmethod
    def prepare_questions_for_target(
        parsed_questions: List[Dict[str, Any]],
        target_id: int,
        db: Session
    ) -> List[dict]:
        """
        Validate and enrich parsed questions for database insertion.

        Sets target_id, source, status, job_id. Resolves persona by title,
        validates type and scope enums.

        Args:
            parsed_questions: Output from parse_file()
            target_id: Target ID to associate questions with
            db: Database session for persona lookup

        Returns:
            List of question dicts ready for QuestionRepository.create_many()
        """
        questions_to_create: List[dict] = []

        for idx, parsed_q in enumerate(parsed_questions):
            try:
                question_data: dict = {
                    "target_id": target_id,
                    "text": parsed_q["text"],
                    "source": QuestionSourceEnum.uploaded,
                    "status": StatusEnum.pending,
                    "job_id": None,
                    "persona_id": None,
                }

                if "orig_id" in parsed_q:
                    question_data["orig_id"] = parsed_q["orig_id"]

                # Lookup persona by title
                if "persona_title" in parsed_q:
                    persona = PersonaRepository.get_by_title(
                        db, target_id, parsed_q["persona_title"]
                    )
                    if persona:
                        question_data["persona_id"] = persona.id
                    else:
                        logger.warning(
                            f"Question {idx+1}: Persona '{parsed_q['persona_title']}' "
                            f"not found for target {target_id}"
                        )

                # Validate type enum
                if "type" in parsed_q:
                    type_value = str(parsed_q["type"]).lower()
                    if type_value in ("typical", "edge"):
                        question_data["type"] = QuestionTypeEnum[type_value]
                    else:
                        logger.warning(
                            f"Question {idx+1}: Invalid type '{parsed_q['type']}', setting to null"
                        )
                        question_data["type"] = None
                else:
                    question_data["type"] = None

                # Validate scope enum
                if "scope" in parsed_q:
                    scope_value = str(parsed_q["scope"]).lower()
                    if scope_value in ("in_kb", "out_kb"):
                        question_data["scope"] = QuestionScopeEnum[scope_value]
                    else:
                        logger.warning(
                            f"Question {idx+1}: Invalid scope '{parsed_q['scope']}', setting to null"
                        )
                        question_data["scope"] = None
                else:
                    question_data["scope"] = None

                questions_to_create.append(question_data)

            except Exception as e:
                logger.error(f"Failed to process question {idx+1}: {e}", exc_info=True)

        return questions_to_create
