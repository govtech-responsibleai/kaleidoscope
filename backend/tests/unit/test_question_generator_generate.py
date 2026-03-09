"""
Unit tests for QuestionGenerator.generate() method.
"""

import pytest
from unittest.mock import patch, MagicMock

from src.common.database.models import JobStatusEnum
from src.common.models import QuestionListOutput, QuestionBase
from src.query_generation.services.question_generator import QuestionGenerator


def _make_llm_result(n=2):
    """Create a fake QuestionListOutput + metadata tuple."""
    questions = [
        QuestionBase(text=f"Question {i}?", type="typical", scope="in_kb")
        for i in range(n)
    ]
    result = QuestionListOutput(questions=questions)
    metadata = {
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_cost": 0.001,
        "model": "gpt-4o-mini",
    }
    return result, metadata


@pytest.mark.unit
class TestQuestionGeneratorGenerate:
    """Tests for QuestionGenerator.generate()."""

    def test_generate_no_kb_uses_only_out_kb_combos(
        self, test_db, sample_job, sample_target, sample_personas
    ):
        """Without KB content, only out_kb combinations should be used (2 combos)."""
        with patch.object(QuestionGenerator, '__init__', lambda self, *a, **kw: None):
            gen = QuestionGenerator.__new__(QuestionGenerator)
            gen.db = test_db
            gen.job_id = sample_job.id
            gen.job = sample_job
            gen.target = sample_target
            gen.persona_ids = None
            gen.sample_questions = []
            gen.cost_tracker = MagicMock()
            gen.cost_tracker.get_summary.return_value = {
                "prompt_tokens": 0, "completion_tokens": 0, "total_cost": 0.0,
            }
            gen.llm_client = MagicMock()
            gen.llm_client.generate_structured.return_value = _make_llm_result(1)

        # Patch KB to return empty
        with patch(
            "src.query_generation.services.question_generator.KBDocumentRepository"
        ) as mock_kb, patch(
            "src.query_generation.services.question_generator.PersonaRepository"
        ) as mock_persona, patch(
            "src.query_generation.services.question_generator.QuestionRepository"
        ) as mock_qr, patch(
            "src.query_generation.services.question_generator.JobRepository"
        ) as mock_jr:
            mock_kb.get_compiled_text.return_value = ""  # No KB content
            mock_persona.get_approved_by_target.return_value = [sample_personas[0]]
            mock_qr.get_approved_by_target.return_value = []
            mock_qr.create_many.return_value = []

            result = gen.generate()

        # Only 2 combos (typical/out_kb + edge/out_kb) x 1 persona = 2 LLM calls
        assert gen.llm_client.generate_structured.call_count == 2

    def test_generate_with_kb_uses_4_combos(
        self, test_db, sample_job, sample_target, sample_personas
    ):
        """With KB content, all 4 type/scope combinations should be used."""
        with patch.object(QuestionGenerator, '__init__', lambda self, *a, **kw: None):
            gen = QuestionGenerator.__new__(QuestionGenerator)
            gen.db = test_db
            gen.job_id = sample_job.id
            gen.job = sample_job
            gen.target = sample_target
            gen.persona_ids = None
            gen.sample_questions = []
            gen.cost_tracker = MagicMock()
            gen.cost_tracker.get_summary.return_value = {
                "prompt_tokens": 0, "completion_tokens": 0, "total_cost": 0.0,
            }
            gen.llm_client = MagicMock()
            gen.llm_client.generate_structured.return_value = _make_llm_result(1)

        with patch(
            "src.query_generation.services.question_generator.KBDocumentRepository"
        ) as mock_kb, patch(
            "src.query_generation.services.question_generator.PersonaRepository"
        ) as mock_persona, patch(
            "src.query_generation.services.question_generator.QuestionRepository"
        ) as mock_qr, patch(
            "src.query_generation.services.question_generator.JobRepository"
        ) as mock_jr:
            mock_kb.get_compiled_text.return_value = "Some KB content here"
            mock_persona.get_approved_by_target.return_value = [sample_personas[0]]
            mock_qr.get_approved_by_target.return_value = []
            mock_qr.create_many.return_value = []

            result = gen.generate()

        # 4 combos x 1 persona = 4 LLM calls
        assert gen.llm_client.generate_structured.call_count == 4

    def test_generate_multi_persona(
        self, test_db, sample_job, sample_target, sample_personas
    ):
        """Multiple personas should each get their own set of LLM calls."""
        with patch.object(QuestionGenerator, '__init__', lambda self, *a, **kw: None):
            gen = QuestionGenerator.__new__(QuestionGenerator)
            gen.db = test_db
            gen.job_id = sample_job.id
            gen.job = sample_job
            gen.job.persona_id = None
            gen.target = sample_target
            gen.persona_ids = [sample_personas[0].id, sample_personas[1].id]
            gen.sample_questions = []
            gen.cost_tracker = MagicMock()
            gen.cost_tracker.get_summary.return_value = {
                "prompt_tokens": 0, "completion_tokens": 0, "total_cost": 0.0,
            }
            gen.llm_client = MagicMock()
            gen.llm_client.generate_structured.return_value = _make_llm_result(1)

        with patch(
            "src.query_generation.services.question_generator.KBDocumentRepository"
        ) as mock_kb, patch(
            "src.query_generation.services.question_generator.PersonaRepository"
        ) as mock_persona, patch(
            "src.query_generation.services.question_generator.QuestionRepository"
        ) as mock_qr, patch(
            "src.query_generation.services.question_generator.JobRepository"
        ) as mock_jr:
            mock_kb.get_compiled_text.return_value = ""
            mock_persona.get_by_id.side_effect = lambda db, pid: (
                sample_personas[0] if pid == sample_personas[0].id else sample_personas[1]
            )
            # _render_prompt calls get_approved_by_target for multi-persona jobs
            mock_persona.get_approved_by_target.return_value = sample_personas
            mock_qr.get_approved_by_target.return_value = []
            mock_qr.create_many.return_value = []

            result = gen.generate()

        # 2 combos (no KB) x 2 personas = 4 LLM calls
        assert gen.llm_client.generate_structured.call_count == 4

    def test_generate_failure_sets_job_failed(
        self, test_db, sample_job, sample_target, sample_personas
    ):
        """If LLM call fails, job should be set to failed status."""
        with patch.object(QuestionGenerator, '__init__', lambda self, *a, **kw: None):
            gen = QuestionGenerator.__new__(QuestionGenerator)
            gen.db = test_db
            gen.job_id = sample_job.id
            gen.job = sample_job
            gen.target = sample_target
            gen.persona_ids = None
            gen.sample_questions = []
            gen.cost_tracker = MagicMock()
            gen.cost_tracker.get_summary.return_value = {
                "prompt_tokens": 0, "completion_tokens": 0, "total_cost": 0.0,
            }
            gen.llm_client = MagicMock()
            gen.llm_client.generate_structured.side_effect = RuntimeError("LLM down")

        with patch(
            "src.query_generation.services.question_generator.KBDocumentRepository"
        ) as mock_kb, patch(
            "src.query_generation.services.question_generator.PersonaRepository"
        ) as mock_persona, patch(
            "src.query_generation.services.question_generator.QuestionRepository"
        ) as mock_qr, patch(
            "src.query_generation.services.question_generator.JobRepository"
        ) as mock_jr:
            mock_kb.get_compiled_text.return_value = ""
            mock_persona.get_approved_by_target.return_value = [sample_personas[0]]
            mock_qr.get_approved_by_target.return_value = []

            with pytest.raises(RuntimeError, match="LLM down"):
                gen.generate()

        # Verify job was marked failed
        mock_jr.update_status.assert_called()
        call_args = mock_jr.update_status.call_args
        assert call_args[1]["status"] == JobStatusEnum.failed or call_args[0][2] == JobStatusEnum.failed
