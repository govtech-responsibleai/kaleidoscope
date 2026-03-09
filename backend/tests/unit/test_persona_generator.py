"""
Unit tests for PersonaGenerator service.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.query_generation.services.persona_generator import PersonaGenerator
from src.common.database.models import JobStatusEnum, StatusEnum
from src.common.models import PersonaBase, PersonaListOutput


@pytest.mark.unit
class TestPersonaGenerator:
    """Unit tests for PersonaGenerator class."""

    def test_init(self, test_db, sample_job):
        """Test PersonaGenerator initialization."""
        generator = PersonaGenerator(test_db, sample_job.id)

        assert generator.job_id == sample_job.id
        assert generator.job is not None
        assert generator.target is not None
        assert generator.llm_client is not None
        assert generator.cost_tracker is not None

    def test_init_invalid_job(self, test_db):
        """Test PersonaGenerator with invalid job ID."""
        with pytest.raises(ValueError, match="Job 999 not found"):
            PersonaGenerator(test_db, 999)

    def test_render_prompt_no_approved_personas(self, test_db, sample_job):
        """Test prompt rendering with no approved personas."""
        generator = PersonaGenerator(test_db, sample_job.id)
        prompt = generator._render_prompt([])

        assert "Test RAI Bot" in prompt
        assert "GovTech" in prompt
        assert "Test chatbot for responsible AI" in prompt
        assert "No confirmed personas yet" in prompt

    def test_render_prompt_with_approved_personas(self, test_db, sample_job, sample_personas):
        """Test prompt rendering with approved personas."""
        generator = PersonaGenerator(test_db, sample_job.id)
        approved = [p for p in sample_personas if p.status == StatusEnum.approved]
        prompt = generator._render_prompt(approved)

        assert "Technical Officer" in prompt
        assert "Software engineer" in prompt
        # Should not include pending personas
        assert "Policy Maker" not in prompt

    def test_save_personas(self, test_db, sample_job):
        """Test saving personas to database."""
        generator = PersonaGenerator(test_db, sample_job.id)

        personas_data = [
            PersonaBase(
                title="Test Persona 1",
                info="Info 1",
                style="Style 1",
                use_case="Use case 1"
            ),
            PersonaBase(
                title="Test Persona 2",
                info="Info 2",
                style="Style 2",
                use_case="Use case 2"
            )
        ]

        personas = generator._save_personas(personas_data, [])

        assert len(personas) == 2
        assert personas[0].title == "Test Persona 1"
        assert personas[0].job_id == sample_job.id
        assert personas[0].target_id == generator.target.id
        assert personas[0].status.value == "pending"

    def test_update_job_status(self, test_db, sample_job):
        """Test updating job status."""
        generator = PersonaGenerator(test_db, sample_job.id)

        # Add some mock costs to tracker
        generator.cost_tracker.add_call({
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "cost": 0.0001
        })

        generator._update_job_status(JobStatusEnum.completed)

        test_db.refresh(sample_job)
        assert sample_job.status == JobStatusEnum.completed
        assert sample_job.prompt_tokens == 100
        assert sample_job.completion_tokens == 50
        assert sample_job.total_cost == 0.0001

    @patch('src.query_generation.services.persona_generator.LLMClient')
    def test_generate_success(self, mock_llm_class, test_db, sample_job, mock_llm_response):
        """Test successful persona generation."""
        # Setup mock LLM client to return structured output
        mock_llm_instance = MagicMock()

        # Create mock PersonaListOutput
        mock_persona_list = PersonaListOutput(personas=[
            PersonaBase(
                title="AI Ethics Researcher",
                info="Academic researcher focusing on AI ethics and policy",
                style="Analytical and research-oriented",
                use_case="Seeking evidence-based guidance on AI risks"
            ),
            PersonaBase(
                title="Data Scientist",
                info="Technical expert in data science",
                style="Technical and detail-oriented",
                use_case="Looking for practical guidance"
            ),
            PersonaBase(
                title="Policy Officer",
                info="Government policy maker",
                style="Formal and structured",
                use_case="Seeking policy frameworks"
            )
        ])

        mock_metadata = {
            "prompt_tokens": 500,
            "completion_tokens": 200,
            "total_tokens": 700,
            "model": "gpt-4o-mini",
            "cost": 0.0002
        }

        mock_llm_instance.generate_structured.return_value = (mock_persona_list, mock_metadata)
        mock_llm_class.return_value = mock_llm_instance

        generator = PersonaGenerator(test_db, sample_job.id)
        personas_data = generator.generate()

        # Verify LLM was called with structured output
        mock_llm_instance.generate_structured.assert_called_once()

        # Verify personas were generated
        assert len(personas_data) == 3
        assert personas_data[0]["title"] == "AI Ethics Researcher"

        # Verify personas were saved to database
        test_db.refresh(sample_job)
        assert len(sample_job.personas_generated) == 3

        # Verify job status updated
        assert sample_job.status == JobStatusEnum.completed
        assert sample_job.total_cost > 0

    @patch('src.query_generation.services.persona_generator.LLMClient')
    def test_generate_llm_failure(self, mock_llm_class, test_db, sample_job):
        """Test persona generation with LLM failure."""
        # Setup mock LLM client to raise error
        mock_llm_instance = MagicMock()
        mock_llm_instance.generate_structured.side_effect = Exception("LLM API error")
        mock_llm_class.return_value = mock_llm_instance

        generator = PersonaGenerator(test_db, sample_job.id)

        with pytest.raises(Exception, match="LLM API error"):
            generator.generate()

        # Verify job status updated to failed
        test_db.refresh(sample_job)
        assert sample_job.status == JobStatusEnum.failed
