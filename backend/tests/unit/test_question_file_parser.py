"""
Unit tests for QuestionFileParser.
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from src.query_generation.services.question_file_parser import QuestionFileParser
from src.common.database.models import QuestionTypeEnum, QuestionScopeEnum, QuestionSourceEnum, StatusEnum


@pytest.mark.unit
class TestQuestionFileParserCSV:
    """Tests for CSV parsing."""

    def test_parse_csv_basic(self):
        """Parse a simple CSV with the required 'question' column."""
        csv_bytes = b"question,type,scope\nWhat is AI?,typical,in_kb\nHow does ML work?,edge,out_kb\n"
        result = QuestionFileParser.parse_file(csv_bytes, "text/csv", "questions.csv")

        assert len(result) == 2
        assert result[0]["text"] == "What is AI?"
        assert result[0]["type"] == "typical"
        assert result[0]["scope"] == "in_kb"

    def test_parse_csv_with_bom(self):
        """CSV with UTF-8 BOM should parse correctly."""
        csv_bytes = b"\xef\xbb\xbfquestion\nWhat is AI?\n"
        result = QuestionFileParser.parse_file(csv_bytes, "text/csv", "q.csv")

        assert len(result) == 1
        assert result[0]["text"] == "What is AI?"

    def test_parse_csv_case_insensitive_fields(self):
        """Field mapping should be case-insensitive."""
        csv_bytes = b"Question,Type,Scope\nWhat is AI?,typical,in_kb\n"
        result = QuestionFileParser.parse_file(csv_bytes, "text/csv", "q.csv")

        assert len(result) == 1
        assert result[0]["text"] == "What is AI?"

    def test_parse_csv_missing_required_field(self):
        """CSV without 'question' column should raise ValueError."""
        csv_bytes = b"name,description\nAlice,Something\n"
        with pytest.raises(ValueError, match="No valid questions"):
            QuestionFileParser.parse_file(csv_bytes, "text/csv", "q.csv")

    def test_parse_csv_with_persona_and_id(self):
        """CSV with persona and id columns should map correctly."""
        csv_bytes = b"id,question,persona\n42,What?,Alice\n"
        result = QuestionFileParser.parse_file(csv_bytes, "text/csv", "q.csv")

        assert len(result) == 1
        assert result[0]["text"] == "What?"
        assert result[0]["orig_id"] == "42"
        assert result[0]["persona_title"] == "Alice"


@pytest.mark.unit
class TestQuestionFileParserJSON:
    """Tests for JSON parsing."""

    def test_parse_json_array(self):
        """Parse a JSON array of question objects."""
        data = [{"question": "What is AI?"}, {"question": "How does ML work?"}]
        json_bytes = json.dumps(data).encode("utf-8")
        result = QuestionFileParser.parse_file(json_bytes, "application/json", "q.json")

        assert len(result) == 2
        assert result[0]["text"] == "What is AI?"

    def test_parse_json_object_with_questions_key(self):
        """Parse a JSON object with a 'questions' array."""
        data = {"questions": [{"question": "What is AI?"}]}
        json_bytes = json.dumps(data).encode("utf-8")
        result = QuestionFileParser.parse_file(json_bytes, "application/json", "q.json")

        assert len(result) == 1

    def test_parse_json_invalid_structure(self):
        """JSON with wrong structure should raise ValueError."""
        data = {"name": "not questions"}
        json_bytes = json.dumps(data).encode("utf-8")
        with pytest.raises(ValueError):
            QuestionFileParser.parse_file(json_bytes, "application/json", "q.json")

    def test_parse_json_missing_question_field(self):
        """JSON items without 'question' field should be skipped."""
        data = [{"description": "no question field"}]
        json_bytes = json.dumps(data).encode("utf-8")
        with pytest.raises(ValueError, match="No valid questions"):
            QuestionFileParser.parse_file(json_bytes, "application/json", "q.json")


@pytest.mark.unit
class TestQuestionFileParserUnsupported:
    """Tests for unsupported formats."""

    def test_unsupported_format_raises(self):
        """Unsupported content type should raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported file format"):
            QuestionFileParser.parse_file(b"data", "text/plain", "q.txt")


@pytest.mark.unit
class TestPrepareQuestionsForTarget:
    """Tests for prepare_questions_for_target."""

    def test_basic_preparation(self, test_db, sample_target):
        """Should set target_id, source, status on each question."""
        parsed = [{"text": "What is AI?"}]
        result = QuestionFileParser.prepare_questions_for_target(parsed, sample_target.id, test_db)

        assert len(result) == 1
        q = result[0]
        assert q["target_id"] == sample_target.id
        assert q["source"] == QuestionSourceEnum.uploaded
        assert q["status"] == StatusEnum.pending
        assert q["text"] == "What is AI?"
        assert q["persona_id"] is None
        assert q["type"] is None
        assert q["scope"] is None

    def test_persona_lookup(self, test_db, sample_target, sample_personas):
        """Should resolve persona by title to persona_id."""
        parsed = [{"text": "Q?", "persona_title": "Technical Officer"}]
        result = QuestionFileParser.prepare_questions_for_target(parsed, sample_target.id, test_db)

        assert len(result) == 1
        assert result[0]["persona_id"] == sample_personas[0].id

    def test_unknown_persona(self, test_db, sample_target):
        """Unknown persona title should result in persona_id=None."""
        parsed = [{"text": "Q?", "persona_title": "NonExistent"}]
        result = QuestionFileParser.prepare_questions_for_target(parsed, sample_target.id, test_db)

        assert len(result) == 1
        assert result[0]["persona_id"] is None

    def test_valid_type_enum(self, test_db, sample_target):
        """Valid type values should be converted to enum."""
        parsed = [{"text": "Q?", "type": "typical"}]
        result = QuestionFileParser.prepare_questions_for_target(parsed, sample_target.id, test_db)

        assert result[0]["type"] == QuestionTypeEnum.typical

    def test_valid_scope_enum(self, test_db, sample_target):
        """Valid scope values should be converted to enum."""
        parsed = [{"text": "Q?", "scope": "out_kb"}]
        result = QuestionFileParser.prepare_questions_for_target(parsed, sample_target.id, test_db)

        assert result[0]["scope"] == QuestionScopeEnum.out_kb

    def test_invalid_type_set_to_none(self, test_db, sample_target):
        """Invalid type value should be set to None."""
        parsed = [{"text": "Q?", "type": "invalid_type"}]
        result = QuestionFileParser.prepare_questions_for_target(parsed, sample_target.id, test_db)

        assert result[0]["type"] is None

    def test_invalid_scope_set_to_none(self, test_db, sample_target):
        """Invalid scope value should be set to None."""
        parsed = [{"text": "Q?", "scope": "invalid_scope"}]
        result = QuestionFileParser.prepare_questions_for_target(parsed, sample_target.id, test_db)

        assert result[0]["scope"] is None
