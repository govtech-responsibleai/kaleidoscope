"""
Integration tests for persona generation API endpoints.
"""

import pytest
from unittest.mock import patch, MagicMock

from src.common.models import PersonaBase, PersonaListOutput

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("with_provider_bypass")]

class TestPersonaGenerationAPI:
    """Integration tests for persona generation API."""

    @patch('src.query_generation.services.persona_generator.LLMClient')
    def test_persona_generation_end_to_end(self, mock_llm_class, test_client, test_db_factory, sample_target, mock_llm_response):
        """
        Test complete persona generation flow end-to-end.

        Tests:
        1. Create job and generate personas via API (runs async in background)
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

        # Patch SessionLocal so the background task uses the test DB
        with patch('src.common.database.connection.SessionLocal', test_db_factory):
            # 1. Generate personas (now runs in background, but TestClient runs background tasks synchronously)
            gen_response = test_client.post(
                "/api/v1/jobs/personas",
                json={
                    "target_id": sample_target.id,
                    "count_requested": 3,
                    "model_used": "gpt-4o-mini"
                }
            )

        assert gen_response.status_code == 201
        job_data = gen_response.json()
        assert job_data["type"] == "persona_generation"
        assert job_data["status"] == "running"
        job_id = job_data["id"]

        # Background task has already run (TestClient runs them synchronously).
        # Verify job completed by fetching it.
        job_response = test_client.get(f"/api/v1/jobs/{job_id}")
        assert job_response.status_code == 200
        assert job_response.json()["status"] == "completed"
        assert job_response.json()["total_cost"] > 0

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

    def test_delete_persona(self, test_client, sample_personas):
        """Test deleting a persona returns 204 and removes it."""
        persona_id = sample_personas[1].id
        response = test_client.delete(f"/api/v1/personas/{persona_id}")
        assert response.status_code == 204

        get_response = test_client.get(f"/api/v1/personas/{persona_id}")
        assert get_response.status_code == 404

    def test_delete_persona_not_found(self, test_client):
        """Test deleting a non-existent persona returns 404."""
        response = test_client.delete("/api/v1/personas/999999")
        assert response.status_code == 404

    def test_generate_personas_target_not_found(self, test_client):
        """Test error handling when target doesn't exist."""
        response = test_client.post(
            "/api/v1/jobs/personas",
            json={
                "target_id": 999,
                "count_requested": 3,
                "model_used": "gpt-4o-mini"
            }
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
