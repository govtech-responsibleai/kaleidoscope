"""
Service for parsing question files in various formats (CSV, JSON, Excel).
"""

import csv
import json
import logging
from io import StringIO, BytesIO
from typing import List, Dict, Any, Optional

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
