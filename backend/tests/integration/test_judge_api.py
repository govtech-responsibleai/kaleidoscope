"""
Integration tests for judge API endpoints.
"""

import pytest
from contextlib import contextmanager

from src.common.config import get_settings

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("with_provider_bypass")]


@contextmanager
def override_settings(**values):
    settings = get_settings()
    original = {key: getattr(settings, key) for key in values}
    try:
        for key, value in values.items():
            setattr(settings, key, value)
        yield settings
    finally:
        for key, value in original.items():
            setattr(settings, key, value)


class TestJudgeAPI:
    """Integration tests for judge API."""

    def test_judge_crud_flow(self, auth_client, auth_headers, sample_target, sample_rubric):
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
                "target_id": sample_target.id,
                "rubric_id": sample_rubric.id,
                "name": "Custom Judge",
                "model_name": "litellm_proxy/gemini-3.1-flash-lite-preview-global",
                "prompt_template": "Test prompt template",
                "params": {"temperature": 0.7},
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

    def test_judge_language_params_round_trip(
        self, auth_client, auth_headers, sample_target, sample_rubric
    ):
        """Language configuration stored in judge.params persists through create and update."""
        # Create a judge with language configuration in params.
        create_response = auth_client.post(
            "/api/v1/judges",
            json={
                "target_id": sample_target.id,
                "rubric_id": sample_rubric.id,
                "name": "Multilingual Judge",
                "model_name": "litellm_proxy/gemini-3.1-flash-lite-preview-global",
                "prompt_template": "Test prompt template",
                "params": {
                    "temperature": 0.0,
                    "language": "Malay",
                    "language_aware": True,
                    "language_output": False,
                },
            },
            headers=auth_headers,
        )

        assert create_response.status_code == 201
        judge = create_response.json()
        assert judge["params"]["language"] == "Malay"
        assert judge["params"]["language_aware"] is True
        assert judge["params"]["language_output"] is False
        judge_id = judge["id"]

        # Update the language configuration (independent toggles).
        update_response = auth_client.put(
            f"/api/v1/judges/{judge_id}",
            json={
                "params": {
                    "temperature": 0.0,
                    "language": "Tamil",
                    "language_aware": True,
                    "language_output": True,
                },
            },
            headers=auth_headers,
        )

        assert update_response.status_code == 200
        updated = update_response.json()
        assert updated["params"]["language"] == "Tamil"
        assert updated["params"]["language_aware"] is True
        assert updated["params"]["language_output"] is True

    def test_create_judge_requires_rubric_id(self, auth_client, auth_headers, sample_target):
        response = auth_client.post(
            "/api/v1/judges",
            json={
                "target_id": sample_target.id,
                "name": "Judge Without Rubric",
                "model_name": "litellm_proxy/gemini-3.1-flash-lite-preview-global",
                "prompt_template": "Test prompt template",
                "params": {"temperature": 0.7},
            },
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "rubric_id is required for user-created judges"

    def test_create_judge_without_auth_returns_401(self, auth_client):
        """Test that creating a judge without authentication returns 401."""
        response = auth_client.post(
            "/api/v1/judges",
            json={
                "name": "Test Judge",
                "model_name": "litellm_proxy/gemini-3.1-flash-lite-preview-global",
                "prompt_template": "Test",
                "params": {},
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

    def test_list_judges_by_rubric_excludes_other_rubric_judges(
        self,
        auth_client,
        auth_headers,
        sample_target,
        sample_rubric_second,
        test_db,
    ):
        """Rubric lookup should return only judges scoped to that rubric."""
        from src.common.database.models import TargetRubric

        other_rubric = TargetRubric(
            target_id=sample_target.id,
            name="Helpfulness",
            criteria="Evaluate whether the response is helpful",
            options=[
                {"option": "Helpful", "description": "Directly helpful"},
                {"option": "Not Helpful", "description": "Does not help"},
            ],
            best_option="Helpful",
            position=2,
        )
        test_db.add(other_rubric)
        test_db.commit()
        test_db.refresh(other_rubric)

        response_a = auth_client.post(
            "/api/v1/judges",
            json={
                "target_id": sample_target.id,
                "rubric_id": sample_rubric_second.id,
                "name": "Custom Default Judge A",
                "model_name": "litellm_proxy/gemini-3.1-flash-lite-preview-global",
                "prompt_template": "Rubric A prompt",
                "params": {"temperature": 0.7},
            },
            headers=auth_headers,
        )
        assert response_a.status_code == 201

        response_b = auth_client.post(
            "/api/v1/judges",
            json={
                "target_id": sample_target.id,
                "rubric_id": other_rubric.id,
                "name": "Custom Default Judge B",
                "model_name": "litellm_proxy/gemini-3.1-flash-lite-preview-global",
                "prompt_template": "Rubric B prompt",
                "params": {"temperature": 0.7},
            },
            headers=auth_headers,
        )
        assert response_b.status_code == 201

        lookup_response = auth_client.get(
            f"/api/v1/judges/by-rubric/{sample_rubric_second.id}?target_id={sample_target.id}",
            headers=auth_headers,
        )

        assert lookup_response.status_code == 200
        names = [judge["name"] for judge in lookup_response.json()]
        assert "Custom Default Judge A" in names
        assert "Custom Default Judge B" not in names

    def test_get_baseline_by_rubric_returns_rubric_scoped_baseline(
        self,
        auth_client,
        auth_headers,
        sample_target,
        sample_rubric_second,
        test_db,
    ):
        from src.common.database.models import Judge

        rubric_baseline = Judge(
            target_id=sample_target.id,
            rubric_id=sample_rubric_second.id,
            name="Scoped Baseline",
            model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
            prompt_template="Scoped prompt",
            params={},
            is_baseline=True,
            is_editable=False,
        )
        global_baseline = Judge(
            name="Global Baseline",
            model_name="azure/gpt-5-mini-2025-08-07",
            prompt_template="Global prompt",
            params={},
            is_baseline=True,
            is_editable=False,
        )
        test_db.add_all([rubric_baseline, global_baseline])
        test_db.commit()
        test_db.refresh(rubric_baseline)

        response = auth_client.get(
            f"/api/v1/judges/by-rubric/{sample_rubric_second.id}/baseline?target_id={sample_target.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["id"] == rubric_baseline.id
        assert payload["rubric_id"] == sample_rubric_second.id
        assert payload["is_baseline"] is True

    def test_get_baseline_by_rubric_does_not_fall_back_to_global_baseline(
        self,
        auth_client,
        auth_headers,
        sample_rubric_second,
        test_db,
    ):
        from src.common.database.models import Judge

        global_baseline = Judge(
            name="Global Baseline",
            model_name="azure/gpt-5-mini-2025-08-07",
            prompt_template="Global prompt",
            params={},
            is_baseline=True,
            is_editable=False,
        )
        test_db.add(global_baseline)
        test_db.commit()
        test_db.refresh(global_baseline)

        response = auth_client.get(
            f"/api/v1/judges/by-rubric/{sample_rubric_second.id}/baseline",
            headers=auth_headers,
        )

        assert response.status_code == 404
        assert response.json()["detail"] == f"Baseline judge not found for rubric {sample_rubric_second.id}"
