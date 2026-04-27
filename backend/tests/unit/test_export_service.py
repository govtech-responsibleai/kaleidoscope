"""
Unit tests for ExportService.
"""

import json
import zipfile
import io
import pytest

from src.common.database.repositories.target_rubric_repo import TargetRubricRepository
from src.common.services.export_service import ExportService, ExportFormat


def _accuracy_rubric_id(test_db, target_id: int) -> int:
    return TargetRubricRepository.get_by_target(
        test_db, target_id, group="fixed", name="Accuracy"
    )[0].id


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
        result, evaluator_payload = service.export_snapshot(
            sample_snapshot.id,
            format,
            rubric_id=_accuracy_rubric_id(test_db, sample_snapshot.target_id),
        )

        if format == ExportFormat.CSV:
            assert isinstance(result, str)
            lines = result.strip().split("\n")
            assert len(lines) > 1
            header = lines[0]
            assert "Human_Label" in header
            assert "Human_Notes" in header
            assert "Aggregated_Score" in header
        else:
            assert isinstance(result, list)
            assert len(result) > 0
            assert "human_label" in result[0]
            assert "human_notes" in result[0]
            assert "aggregated_score" in result[0]

        assert evaluator_payload is None

    def test_export_snapshot_with_evaluators(
        self, test_db, sample_annotations, sample_answer_scores, sample_snapshot, sample_judge_claim_based
    ):
        """Ensure evaluator payload contains judge metrics and scores."""
        service = ExportService(test_db)
        result, evaluator_payload = service.export_snapshot(
            sample_snapshot.id,
            ExportFormat.CSV,
            include_evaluators=True,
            rubric_id=_accuracy_rubric_id(test_db, sample_snapshot.target_id),
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
            service.export_snapshot(9999, ExportFormat.CSV, rubric_id=1)

    def test_export_snapshot_scopes_evaluator_exports_to_requested_rubric(
        self,
        test_db,
        sample_target,
        sample_snapshot,
        sample_annotations,
        sample_answer_scores,
        sample_rubric,
    ):
        """Rubric-scoped export should only include rows and evaluator stats for that rubric."""
        from src.common.database.models import AnswerScore, Judge, Annotation

        rubric_judge = Judge(
            target_id=sample_target.id,
            rubric_id=sample_rubric.id,
            name="Tone Judge",
            model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
            prompt_template="Tone prompt",
            params={"temperature": 0.0},
            is_baseline=False,
            is_editable=True,
        )
        test_db.add(rubric_judge)
        test_db.commit()
        test_db.refresh(rubric_judge)

        negative_answer_id = sample_annotations[1].answer_id
        for annotation in sample_annotations:
            test_db.add(AnswerScore(
                answer_id=annotation.answer_id,
                rubric_id=sample_rubric.id,
                judge_id=rubric_judge.id,
                overall_label="Casual" if annotation.answer_id == negative_answer_id else "Professional",
                explanation="Tone score",
            ))
            test_db.add(Annotation(
                answer_id=annotation.answer_id,
                rubric_id=sample_rubric.id,
                option_value="Casual" if annotation.answer_id == negative_answer_id else "Professional",
            ))
        test_db.commit()

        service = ExportService(test_db)
        result, evaluator_payload = service.export_snapshot(
            sample_snapshot.id,
            ExportFormat.CSV,
            include_evaluators=True,
            rubric_id=sample_rubric.id,
        )

        assert isinstance(result, str)
        assert "Aggregated_Score" in result.splitlines()[0]
        assert evaluator_payload is not None
        assert [entry["judge_id"] for entry in evaluator_payload] == [rubric_judge.id]
        assert evaluator_payload[0]["judge_accuracy"]["accuracy"] == 0.9

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
