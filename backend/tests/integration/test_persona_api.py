"""
Integration tests for persona generation API endpoints.
"""

import pytest
from unittest.mock import patch, MagicMock

from src.common.models import PersonaBase, PersonaListOutput


@pytest.mark.integration
class TestPersonaGenerationAPI:
    """Integration tests for persona generation API."""

    @patch('src.query_generation.services.persona_generator.LLMClient')
    def test_persona_generation_end_to_end(self, mock_llm_class, test_client, sample_target, mock_llm_response):
        """
        Test complete persona generation flow end-to-end.

        Tests:
        1. Create job and generate personas via API
        2. Personas are saved to database
        3. Job status is updated
        4. Can retrieve and approve personas
        """
        # Setup mock LLM client to return structured output
        mock_llm_instance = MagicMock()

        # Create mock PersonaListOutput from the mock_llm_response fixture
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
            "prompt_tokens": mock_llm_response["prompt_tokens"],
            "completion_tokens": mock_llm_response["completion_tokens"],
            "total_tokens": mock_llm_response["total_tokens"],
            "model": mock_llm_response["model"],
            "cost": mock_llm_response["cost"]
        }

        mock_llm_instance.generate_structured.return_value = (mock_persona_list, mock_metadata)
        mock_llm_class.return_value = mock_llm_instance

        # 1. Generate personas
        gen_response = test_client.post(
            f"/api/v1/targets/{sample_target.id}/jobs/personas",
            json={
                "count_requested": 3,
                "model_used": "gpt-4o-mini"
            }
        )

        assert gen_response.status_code == 201
        job_data = gen_response.json()
        assert job_data["type"] == "persona_generation"
        assert job_data["status"] == "completed"
        assert job_data["total_cost"] > 0
        job_id = job_data["id"]

        # 2. Get personas from job
        personas_response = test_client.get(f"/api/v1/jobs/{job_id}/personas")
        assert personas_response.status_code == 200
        personas = personas_response.json()
        assert len(personas) == 3
        assert personas[0]["title"] == "AI Ethics Researcher"
        assert personas[0]["status"] == "pending"

        # 3. Approve a persona
        persona_id = personas[0]["id"]
        approve_response = test_client.post(f"/api/v1/personas/{persona_id}/approve")
        assert approve_response.status_code == 200
        assert approve_response.json()["status"] == "approved"

        # 4. Verify stats updated
        stats_response = test_client.get(f"/api/v1/targets/{sample_target.id}/stats")
        assert stats_response.status_code == 200
        stats = stats_response.json()
        assert stats["personas"]["approved"] == 1
        assert stats["personas"]["pending"] == 2

    def test_generate_personas_target_not_found(self, test_client):
        """Test error handling when target doesn't exist."""
        response = test_client.post(
            "/api/v1/targets/999/jobs/personas",
            json={
                "count_requested": 3,
                "model_used": "gpt-4o-mini"
            }
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
