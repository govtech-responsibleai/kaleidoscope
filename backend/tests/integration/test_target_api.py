"""
Integration tests for target API endpoints.
"""

import pytest

from src.common.database.models import Judge, TargetRubric
from src.common.connectors.http_auth import decrypt_http_auth_secret
from src.common.database.repositories import TargetHttpAuthSecretRepository, TargetRepository
from src.rubric.services.fixed_rubrics import get_fixed_template


@pytest.mark.integration
class TestTargetAPI:
    """Integration tests for target API."""

    @staticmethod
    def _fixed_accuracy_name() -> str:
        return get_fixed_template("accuracy")["name"]

    def test_target_crud_flow(self, auth_client, auth_headers):
        """
        Test complete target CRUD flow with authentication.

        Tests:
        1. Create a new target
        2. List targets (user sees own targets)
        3. Get target by ID
        4. Update target
        5. Delete target
        """
        # 1. Create target
        create_response = auth_client.post(
            "/api/v1/targets",
            json={
                "name": "Test Bot",
                "agency": "Test Agency",
                "purpose": "Testing purposes",
                "target_users": "Test users"
            },
            headers=auth_headers
        )

        assert create_response.status_code == 201
        target_data = create_response.json()
        assert target_data["name"] == "Test Bot"
        assert target_data["agency"] == "Test Agency"
        target_id = target_data["id"]

        rubrics_response = auth_client.get(
            f"/api/v1/targets/{target_id}/rubrics",
            headers=auth_headers,
        )
        assert rubrics_response.status_code == 200
        rubrics = rubrics_response.json()
        assert len(rubrics) == 1
        accuracy_rubric = next((rubric for rubric in rubrics if rubric["name"] == self._fixed_accuracy_name()), None)
        assert accuracy_rubric is not None
        assert accuracy_rubric["group"] == "fixed"

        rubric_judges_response = auth_client.get(
            f"/api/v1/judges/by-rubric/{accuracy_rubric['id']}?target_id={target_id}",
            headers=auth_headers,
        )
        assert rubric_judges_response.status_code == 200
        rubric_judges = rubric_judges_response.json()
        assert len(rubric_judges) == 3
        assert all(judge["rubric_id"] == accuracy_rubric["id"] for judge in rubric_judges)

        # 2. List targets
        list_response = auth_client.get(
            "/api/v1/targets",
            headers=auth_headers
        )

        assert list_response.status_code == 200
        targets = list_response.json()
        assert len(targets) >= 1
        target_names = [t["name"] for t in targets]
        assert "Test Bot" in target_names

        # 3. Get target by ID
        get_response = auth_client.get(
            f"/api/v1/targets/{target_id}",
            headers=auth_headers
        )

        assert get_response.status_code == 200
        assert get_response.json()["id"] == target_id

        # 4. Update target
        update_response = auth_client.put(
            f"/api/v1/targets/{target_id}",
            json={"name": "Updated Bot"},
            headers=auth_headers
        )

        assert update_response.status_code == 200
        assert update_response.json()["name"] == "Updated Bot"

        # 5. Delete target
        delete_response = auth_client.delete(
            f"/api/v1/targets/{target_id}",
            headers=auth_headers
        )

        assert delete_response.status_code == 204

        # Verify deleted
        get_deleted = auth_client.get(
            f"/api/v1/targets/{target_id}",
            headers=auth_headers
        )
        assert get_deleted.status_code == 404

    def test_create_target_without_auth_returns_401(self, auth_client):
        """Test that creating a target without authentication returns 401."""
        response = auth_client.post(
            "/api/v1/targets",
            json={
                "name": "Test Bot",
                "agency": "Test Agency",
                "purpose": "Testing",
                "target_users": "Users"
            }
        )

        assert response.status_code == 401

    def test_list_targets_without_auth_returns_401(self, auth_client):
        """Test that listing targets without authentication returns 401."""
        response = auth_client.get("/api/v1/targets")

        assert response.status_code == 401

    def test_get_target_not_found(self, auth_client, auth_headers):
        """Test error handling when target doesn't exist."""
        response = auth_client.get(
            "/api/v1/targets/99999",
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_update_target_not_found(self, auth_client, auth_headers):
        """Test error handling when updating non-existent target."""
        response = auth_client.put(
            "/api/v1/targets/99999",
            json={"name": "New Name"},
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_delete_target_not_found(self, auth_client, auth_headers):
        """Test error handling when deleting non-existent target."""
        response = auth_client.delete(
            "/api/v1/targets/99999",
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_create_target_with_managed_http_auth(self, auth_client, auth_headers, test_db_factory):
        response = auth_client.post(
            "/api/v1/targets",
            json={
                "name": "Managed Auth Bot",
                "api_endpoint": "https://api.example.com",
                "endpoint_type": "http",
                "endpoint_config": {
                    "response_content_path": "output",
                    "auth": {
                        "preset": "x-api-key",
                        "secret_value": "sk-secret-1234",
                    },
                },
            },
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["endpoint_config"]["auth"]["preset"] == "x-api-key"
        assert data["endpoint_config"]["auth"]["is_configured"] is True
        assert data["endpoint_config"]["auth"]["masked_value"] != "sk-secret-1234"
        assert "secret_value" not in data["endpoint_config"]["auth"]

        db = test_db_factory()
        try:
            target = TargetRepository.get_by_id(db, data["id"])
            secret = TargetHttpAuthSecretRepository.get_by_target_id(db, data["id"])
            assert target is not None
            assert target.endpoint_config["auth"]["masked_value"] == data["endpoint_config"]["auth"]["masked_value"]
            assert secret is not None
            assert decrypt_http_auth_secret(secret.encrypted_secret) == "sk-secret-1234"
        finally:
            db.close()

    def test_update_target_can_clear_managed_http_auth(self, auth_client, auth_headers, test_db_factory):
        create_response = auth_client.post(
            "/api/v1/targets",
            json={
                "name": "Managed Auth Bot",
                "api_endpoint": "https://api.example.com",
                "endpoint_type": "http",
                "endpoint_config": {
                    "response_content_path": "output",
                    "auth": {
                        "preset": "bearer",
                        "secret_value": "sk-secret-1234",
                    },
                },
            },
            headers=auth_headers,
        )
        target_id = create_response.json()["id"]

        update_response = auth_client.put(
            f"/api/v1/targets/{target_id}",
            json={
                "endpoint_type": "http",
                "endpoint_config": {
                    "response_content_path": "output",
                    "auth": {
                        "preset": "bearer",
                        "clear_secret": True,
                    },
                },
            },
            headers=auth_headers,
        )

        assert update_response.status_code == 200
        data = update_response.json()
        assert "auth" not in (data["endpoint_config"] or {})

        db = test_db_factory()
        try:
            target = TargetRepository.get_by_id(db, target_id)
            secret = TargetHttpAuthSecretRepository.get_by_target_id(db, target_id)
            assert target is not None
            assert "auth" not in (target.endpoint_config or {})
            assert secret is None
        finally:
            db.close()

    def test_get_target_rubric_specs_returns_one_baseline_per_rubric(
        self,
        auth_client,
        auth_headers,
        test_db_factory,
    ):
        create_response = auth_client.post(
            "/api/v1/targets",
            json={"name": "Rubric Spec Bot"},
            headers=auth_headers,
        )
        assert create_response.status_code == 201
        target_id = create_response.json()["id"]

        rubrics_response = auth_client.get(
            f"/api/v1/targets/{target_id}/rubrics",
            headers=auth_headers,
        )
        assert rubrics_response.status_code == 200
        accuracy_rubric = next(
            rubric for rubric in rubrics_response.json() if rubric["name"] == self._fixed_accuracy_name()
        )

        db = test_db_factory()
        try:
            empathy_rubric = TargetRubric(
                target_id=target_id,
                name="Empathy",
                criteria="Evaluate empathy",
                options=[
                    {"option": "Empathetic", "description": "Shows empathy"},
                    {"option": "Not Empathetic", "description": "Lacks empathy"},
                ],
                best_option="Empathetic",
                group="preset",
                position=1,
            )
            db.add(empathy_rubric)
            db.commit()
            db.refresh(empathy_rubric)

            empathy_baseline = Judge(
                target_id=target_id,
                rubric_id=empathy_rubric.id,
                name="Empathy Baseline",
                model_name="litellm_proxy/gemini-3.1-flash-lite-preview-global",
                prompt_template="Score empathy",
                params={},
                is_baseline=True,
                is_editable=False,
            )
            db.add(empathy_baseline)
            db.commit()
            db.refresh(empathy_baseline)
            empathy_rubric_id = empathy_rubric.id
        finally:
            db.close()

        specs_response = auth_client.get(
            f"/api/v1/targets/{target_id}/rubric-specs",
            headers=auth_headers,
        )
        assert specs_response.status_code == 200
        specs = specs_response.json()
        updated_rubrics_response = auth_client.get(
            f"/api/v1/targets/{target_id}/rubrics",
            headers=auth_headers,
        )
        assert updated_rubrics_response.status_code == 200
        rubric_ids = {str(rubric["id"]) for rubric in updated_rubrics_response.json()}

        assert set(specs.keys()) == rubric_ids
        assert str(accuracy_rubric["id"]) in specs
        assert str(empathy_rubric_id) in specs

        baseline_judge_count = sum(1 for spec in specs.values() if spec["judge_id"])
        assert baseline_judge_count == len(specs)

    def test_get_target_rubric_specs_returns_409_for_missing_baseline_judge(
        self,
        auth_client,
        auth_headers,
        test_db_factory,
    ):
        create_response = auth_client.post(
            "/api/v1/targets",
            json={"name": "Missing Baseline Bot"},
            headers=auth_headers,
        )
        assert create_response.status_code == 201
        target_id = create_response.json()["id"]

        db = test_db_factory()
        try:
            rubric = TargetRubric(
                target_id=target_id,
                name="Tone",
                criteria="Evaluate tone",
                options=[
                    {"option": "Professional"},
                    {"option": "Casual"},
                ],
                best_option="Professional",
                group="custom",
                position=1,
            )
            db.add(rubric)
            db.commit()
        finally:
            db.close()

        specs_response = auth_client.get(
            f"/api/v1/targets/{target_id}/rubric-specs",
            headers=auth_headers,
        )
        assert specs_response.status_code == 409
        detail = specs_response.json()["detail"]
        assert "exactly one baseline judge" in detail["message"].lower()
        assert any(error["rubric_name"] == "Tone" for error in detail["errors"])

    def test_target_preset_rubrics_start_empty_and_can_be_added_and_deleted(
        self,
        auth_client,
        auth_headers,
    ):
        create_response = auth_client.post(
            "/api/v1/targets",
            json={"name": "Preset Flow Bot"},
            headers=auth_headers,
        )
        assert create_response.status_code == 201
        target_id = create_response.json()["id"]

        initial_rubrics_response = auth_client.get(
            f"/api/v1/targets/{target_id}/rubrics",
            headers=auth_headers,
        )
        assert initial_rubrics_response.status_code == 200
        initial_rubrics = initial_rubrics_response.json()
        assert len(initial_rubrics) == 1
        assert initial_rubrics[0]["group"] == "fixed"

        premade_response = auth_client.get(
            f"/api/v1/targets/{target_id}/premade-rubrics",
            headers=auth_headers,
        )
        assert premade_response.status_code == 200
        premade_templates = premade_response.json()
        assert len(premade_templates) >= 1

        template = premade_templates[0]
        create_preset_response = auth_client.post(
            f"/api/v1/targets/{target_id}/rubrics",
            json={
                "name": template["name"],
                "criteria": template["criteria"],
                "options": template["options"],
                "best_option": template["best_option"],
                "group": "preset",
            },
            headers=auth_headers,
        )
        assert create_preset_response.status_code == 201
        created_preset = create_preset_response.json()
        assert created_preset["group"] == "preset"
        assert created_preset["name"] == template["name"]

        preset_judges_response = auth_client.get(
            f"/api/v1/judges/by-rubric/{created_preset['id']}?target_id={target_id}",
            headers=auth_headers,
        )
        assert preset_judges_response.status_code == 200
        assert len(preset_judges_response.json()) == 3

        updated_rubrics_response = auth_client.get(
            f"/api/v1/targets/{target_id}/rubrics",
            headers=auth_headers,
        )
        assert updated_rubrics_response.status_code == 200
        updated_rubrics = updated_rubrics_response.json()
        assert len(updated_rubrics) == 2
        assert [rubric["group"] for rubric in updated_rubrics] == ["fixed", "preset"]
        assert any(rubric["id"] == created_preset["id"] for rubric in updated_rubrics)

        updated_premade_response = auth_client.get(
            f"/api/v1/targets/{target_id}/premade-rubrics",
            headers=auth_headers,
        )
        assert updated_premade_response.status_code == 200
        assert all(item["name"] != template["name"] for item in updated_premade_response.json())

        delete_response = auth_client.delete(
            f"/api/v1/targets/{target_id}/rubrics/{created_preset['id']}",
            headers=auth_headers,
        )
        assert delete_response.status_code == 204

        final_rubrics_response = auth_client.get(
            f"/api/v1/targets/{target_id}/rubrics",
            headers=auth_headers,
        )
        assert final_rubrics_response.status_code == 200
        final_rubrics = final_rubrics_response.json()
        assert len(final_rubrics) == 1
        assert final_rubrics[0]["group"] == "fixed"
