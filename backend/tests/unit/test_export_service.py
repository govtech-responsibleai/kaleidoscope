"""
Unit tests for ExportService.
"""

import json
import zipfile
import io
import pytest

from src.common.services.export_service import ExportService, ExportFormat


@pytest.mark.unit
class TestExportService:
    """Unit tests for ExportService class."""

    @pytest.mark.parametrize("format", [ExportFormat.CSV, ExportFormat.JSON])
    def test_export_personas(self, test_db, sample_target, sample_personas, format):
        """Test exporting personas in different formats."""
        service = ExportService(test_db)
        result = service.export_personas(sample_target.id, format)

        if format == ExportFormat.CSV:
            assert isinstance(result, str)
            lines = result.strip().split("\n")
            assert len(lines) == 3  # Header + 2 personas
            assert "id" in lines[0]
            assert "title" in lines[0]
            assert "Technical Officer" in result
        else:
            assert isinstance(result, list)
            assert len(result) == 2
            assert "id" in result[0]
            assert "title" in result[0]

    def test_export_personas_raises_if_target_not_found(self, test_db):
        """Test that export_personas raises ValueError when target not found."""
        service = ExportService(test_db)

        with pytest.raises(ValueError, match="Target 9999 not found"):
            service.export_personas(9999, ExportFormat.CSV)

    @pytest.mark.parametrize("format", [ExportFormat.CSV, ExportFormat.JSON])
    def test_export_questions(self, test_db, sample_target, sample_questions, format):
        """Test exporting questions in different formats."""
        service = ExportService(test_db)
        result = service.export_questions(sample_target.id, format)

        if format == ExportFormat.CSV:
            assert isinstance(result, str)
            lines = result.strip().split("\n")
            assert len(lines) > 1
            assert "id" in lines[0]
            assert "text" in lines[0]
        else:
            assert isinstance(result, list)
            assert len(result) > 0
            assert "id" in result[0]
            assert "text" in result[0]

    def test_export_questions_raises_if_target_not_found(self, test_db):
        """Test that export_questions raises ValueError when target not found."""
        service = ExportService(test_db)

        with pytest.raises(ValueError, match="Target 9999 not found"):
            service.export_questions(9999, ExportFormat.CSV)

    @pytest.mark.parametrize("format", [ExportFormat.CSV, ExportFormat.JSON])
    def test_export_snapshot(
        self, test_db, sample_annotations, sample_answer_scores, sample_snapshot, format
    ):
        """Test exporting snapshot results in different formats."""
        service = ExportService(test_db)
        result, evaluator_payload = service.export_snapshot(sample_snapshot.id, format)

        if format == ExportFormat.CSV:
            assert isinstance(result, str)
            lines = result.strip().split("\n")
            assert len(lines) > 1
            header = lines[0]
            assert "Human_Label" in header
            assert "Human_Notes" in header
            assert "Aggregated_Accuracy" in header
        else:
            assert isinstance(result, list)
            assert len(result) > 0
            assert "human_label" in result[0]
            assert "human_notes" in result[0]
            assert "aggregated_accuracy" in result[0]

        assert evaluator_payload is None

    def test_export_snapshot_with_evaluators(
        self, test_db, sample_annotations, sample_answer_scores, sample_snapshot, sample_judge_claim_based
    ):
        """Ensure evaluator payload contains judge metrics and scores."""
        service = ExportService(test_db)
        result, evaluator_payload = service.export_snapshot(
            sample_snapshot.id,
            ExportFormat.CSV,
            include_evaluators=True
        )

        assert isinstance(result, str)
        assert evaluator_payload is not None
        assert len(evaluator_payload) >= 1

        judge_export = evaluator_payload[0]
        assert judge_export["judge_id"] == sample_judge_claim_based.id
        assert judge_export["judge_name"] == sample_judge_claim_based.name
        assert "judge_accuracy" in judge_export
        assert "judge_alignment" in judge_export
        assert isinstance(judge_export["judge_scores"], list)
        assert len(judge_export["judge_scores"]) > 0
        score_entry = judge_export["judge_scores"][0]
        assert "answer_id" in score_entry
        assert "overall_label" in score_entry

    def test_export_snapshot_raises_if_not_found(self, test_db):
        """Test that export_snapshot raises ValueError when snapshot not found."""
        service = ExportService(test_db)

        with pytest.raises(ValueError, match="Snapshot 9999 not found"):
            service.export_snapshot(9999, ExportFormat.CSV)

    @pytest.mark.parametrize("format", [ExportFormat.CSV, ExportFormat.JSON])
    def test_export_all(
        self, test_db, sample_target, sample_personas, sample_questions,
        sample_annotations, sample_answer_scores, sample_snapshot, format
    ):
        """Test exporting all data creates a valid ZIP file."""
        service = ExportService(test_db)
        zip_bytes = service.export_all(sample_target.id, format)

        assert isinstance(zip_bytes, bytes)

        file_ext = "json" if format == ExportFormat.JSON else "csv"
        zip_buffer = io.BytesIO(zip_bytes)
        with zipfile.ZipFile(zip_buffer, "r") as zf:
            names = zf.namelist()
            assert any(f"personas.{file_ext}" in name for name in names)
            assert any(f"questions.{file_ext}" in name for name in names)
            assert any("snapshot" in name and file_ext in name for name in names)

    def test_export_all_raises_if_target_not_found(self, test_db):
        """Test that export_all raises ValueError when target not found."""
        service = ExportService(test_db)

        with pytest.raises(ValueError, match="Target 9999 not found"):
            service.export_all(9999, ExportFormat.CSV)
