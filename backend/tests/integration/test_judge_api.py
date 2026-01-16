"""
Integration tests for judge API endpoints.
"""

import pytest


@pytest.mark.integration
class TestJudgeAPI:
    """Integration tests for judge API."""

    def test_judge_crud_flow(self, auth_client, auth_headers):
        """
        Test complete judge CRUD flow with authentication.

        Tests:
        1. Create a new custom judge
        2. List judges (includes user's judges and baseline)
        3. Get judge by ID
        4. Update judge (only editable judges)
        5. Delete judge (only editable judges)
        """
        # 1. Create judge
        create_response = auth_client.post(
            "/api/v1/judges",
            json={
                "name": "Custom Judge",
                "model_name": "gemini/gemini-2.5-flash-lite",
                "prompt_template": "Test prompt template",
                "params": {"temperature": 0.7},
                "judge_type": "claim_based"
            },
            headers=auth_headers
        )

        assert create_response.status_code == 201
        judge_data = create_response.json()
        assert judge_data["name"] == "Custom Judge"
        assert judge_data["is_editable"] is True
        assert judge_data["is_baseline"] is False
        judge_id = judge_data["id"]

        # 2. List judges
        list_response = auth_client.get(
            "/api/v1/judges",
            headers=auth_headers
        )

        assert list_response.status_code == 200
        judges = list_response.json()
        judge_names = [j["name"] for j in judges]
        assert "Custom Judge" in judge_names

        # 3. Get judge by ID
        get_response = auth_client.get(
            f"/api/v1/judges/{judge_id}",
            headers=auth_headers
        )

        assert get_response.status_code == 200
        assert get_response.json()["id"] == judge_id

        # 4. Update judge
        update_response = auth_client.put(
            f"/api/v1/judges/{judge_id}",
            json={"name": "Updated Judge"},
            headers=auth_headers
        )

        assert update_response.status_code == 200
        assert update_response.json()["name"] == "Updated Judge"

        # 5. Delete judge
        delete_response = auth_client.delete(
            f"/api/v1/judges/{judge_id}",
            headers=auth_headers
        )

        assert delete_response.status_code == 204

        # Verify deleted
        get_deleted = auth_client.get(
            f"/api/v1/judges/{judge_id}",
            headers=auth_headers
        )
        assert get_deleted.status_code == 404

    def test_create_judge_without_auth_returns_401(self, auth_client):
        """Test that creating a judge without authentication returns 401."""
        response = auth_client.post(
            "/api/v1/judges",
            json={
                "name": "Test Judge",
                "model_name": "gemini/gemini-2.5-flash-lite",
                "prompt_template": "Test",
                "params": {},
                "judge_type": "claim_based"
            }
        )

        assert response.status_code == 401

    def test_get_judge_not_found(self, auth_client, auth_headers):
        """Test error handling when judge doesn't exist."""
        response = auth_client.get(
            "/api/v1/judges/99999",
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_update_judge_not_found(self, auth_client, auth_headers):
        """Test error handling when updating non-existent judge."""
        response = auth_client.put(
            "/api/v1/judges/99999",
            json={"name": "New Name"},
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_delete_judge_not_found(self, auth_client, auth_headers):
        """Test error handling when deleting non-existent judge."""
        response = auth_client.delete(
            "/api/v1/judges/99999",
            headers=auth_headers
        )

        assert response.status_code == 404
