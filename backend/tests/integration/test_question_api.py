"""
Integration tests for question generation API endpoints.
"""

import pytest


@pytest.mark.integration
class TestQuestionGenerationAPI:
    """Integration tests for question generation API."""

    def test_question_generation_all_approved_personas(
        self, test_client, sample_target, sample_personas
    ):
        """
        Test question generation job creation for all approved personas.

        Tests:
        1. Create job without persona_ids (generates for all approved personas)
        2. Job is created with status="running" (async processing)
        3. Endpoint returns immediately without waiting for completion

        Note: This test verifies async job creation. The actual generation
        runs in background and is tested separately in unit tests.
        """
        # 1. Generate questions for all approved personas
        gen_response = test_client.post(
            f"/api/v1/targets/{sample_target.id}/jobs/questions",
            json={
                "count_requested": 10,
                "model_used": "gpt-4o-mini"
            }
        )

        assert gen_response.status_code == 201
        job_data = gen_response.json()
        assert job_data["type"] == "question_generation"
        assert job_data["status"] == "running"  # Returns immediately with running status
        assert job_data["count_requested"] == 10
        job_id = job_data["id"]

        # 2. Verify job exists and can be retrieved
        job_response = test_client.get(f"/api/v1/jobs/{job_id}")
        assert job_response.status_code == 200
        assert job_response.json()["id"] == job_id

    def test_question_generation_specific_personas(
        self, test_client, sample_target, sample_personas
    ):
        """
        Test question generation job creation for specific personas using persona_ids.

        Tests:
        1. Create job with persona_ids in body
        2. Job is created with status="running"
        3. Endpoint validates persona_ids belong to target

        Note: This test verifies async job creation with persona_ids.
        """
        # Get the first persona ID (which is approved)
        approved_persona_id = sample_personas[0].id

        # 1. Generate questions for specific persona
        gen_response = test_client.post(
            f"/api/v1/targets/{sample_target.id}/jobs/questions",
            json={
                "count_requested": 5,
                "model_used": "gpt-4o-mini",
                "persona_ids": [approved_persona_id]
            }
        )

        assert gen_response.status_code == 201
        job_data = gen_response.json()
        assert job_data["type"] == "question_generation"
        assert job_data["status"] == "running"  # Returns immediately
        assert job_data["count_requested"] == 5
        job_id = job_data["id"]

        # 2. Verify job was created correctly
        job_response = test_client.get(f"/api/v1/jobs/{job_id}")
        assert job_response.status_code == 200

    def test_question_generation_invalid_persona_id(self, test_client, sample_target):
        """Test error handling when persona_id doesn't exist."""
        response = test_client.post(
            f"/api/v1/targets/{sample_target.id}/jobs/questions",
            json={
                "count_requested": 5,
                "model_used": "gpt-4o-mini",
                "persona_ids": [9999]  # Non-existent persona
            }
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_question_generation_persona_wrong_target(
        self, test_client, sample_target, sample_personas
    ):
        """Test error handling when persona doesn't belong to target."""
        # Create another target
        other_target_response = test_client.post(
            "/api/v1/targets",
            json={
                "name": "Other Bot",
                "agency": "Other Agency",
                "purpose": "Different purpose",
                "target_users": "Different users"
            }
        )
        assert other_target_response.status_code == 201
        other_target_id = other_target_response.json()["id"]

        # Try to generate questions for sample_target using a persona that belongs to it
        # but specify other_target_id in the URL
        persona_id = sample_personas[0].id

        response = test_client.post(
            f"/api/v1/targets/{other_target_id}/jobs/questions",
            json={
                "count_requested": 5,
                "model_used": "gpt-4o-mini",
                "persona_ids": [persona_id]
            }
        )

        assert response.status_code == 400
        assert "does not belong to target" in response.json()["detail"].lower()

    def test_question_generation_no_approved_personas(self, test_client, sample_target):
        """Test error handling when target has no approved personas."""
        response = test_client.post(
            f"/api/v1/targets/{sample_target.id}/jobs/questions",
            json={
                "count_requested": 5,
                "model_used": "gpt-4o-mini"
                # No persona_ids, should use all approved personas
            }
        )

        # Since sample_target fixture doesn't automatically have approved personas,
        # this should fail
        # Note: sample_personas fixture creates personas but they may not all be approved
        # by default in the fixture
        assert response.status_code == 400
        assert "no approved personas" in response.json()["detail"].lower()

    def test_question_generation_target_not_found(self, test_client):
        """Test error handling when target doesn't exist."""
        response = test_client.post(
            "/api/v1/targets/999/jobs/questions",
            json={
                "count_requested": 5,
                "model_used": "gpt-4o-mini"
            }
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_question_generation_multiple_personas(
        self, test_client, sample_target, sample_personas
    ):
        """Test question generation job creation for multiple specific personas."""
        # Get multiple persona IDs
        persona_ids = [p.id for p in sample_personas[:2]]  # First 2 personas

        # Generate questions for multiple personas
        gen_response = test_client.post(
            f"/api/v1/targets/{sample_target.id}/jobs/questions",
            json={
                "count_requested": 10,
                "model_used": "gpt-4o-mini",
                "persona_ids": persona_ids
            }
        )

        assert gen_response.status_code == 201
        job_data = gen_response.json()
        assert job_data["type"] == "question_generation"
        assert job_data["status"] == "running"  # Returns immediately
        assert job_data["count_requested"] == 10
        job_id = job_data["id"]

        # Verify job was created correctly
        job_response = test_client.get(f"/api/v1/jobs/{job_id}")
        assert job_response.status_code == 200
        assert job_response.json()["id"] == job_id
