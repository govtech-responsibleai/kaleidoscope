import pytest

from src.common.database.models import Question, StatusEnum, Target


@pytest.mark.integration
class TestProviderApi:
    def test_provider_setup_reports_shared_provider_source(
        self,
        auth_client,
        auth_headers,
        provider_settings,
    ):
        with provider_settings(gemini_api_key="shared-gemini-key"):
            response = auth_client.get("/api/v1/providers/setup", headers=auth_headers)

        assert response.status_code == 200
        payload = response.json()
        gemini = next(provider for provider in payload["providers"] if provider["key"] == "gemini")

        assert gemini["source"] == "shared"
        assert gemini["is_valid"] is True

    def test_provider_setup_reports_personal_provider_source(
        self,
        auth_client,
        auth_headers,
        provider_settings,
    ):
        with provider_settings():
            upsert_response = auth_client.put(
                "/api/v1/providers/openai",
                json={"credentials": {"OPENAI_API_KEY": "sk-openai-test"}},
                headers=auth_headers,
            )
            assert upsert_response.status_code == 204

            response = auth_client.get("/api/v1/providers/setup", headers=auth_headers)

        assert response.status_code == 200
        payload = response.json()
        openai = next(provider for provider in payload["providers"] if provider["key"] == "openai")

        assert openai["source"] == "personal"
        assert openai["is_valid"] is True
        assert any(model["provider_key"] == "openai" for model in payload["valid_models"])

    def test_target_creation_is_blocked_without_valid_provider(
        self,
        auth_client,
        auth_headers,
        provider_settings,
    ):
        with provider_settings():
            response = auth_client.post(
                "/api/v1/targets",
                json={"name": "Blocked Target"},
                headers=auth_headers,
            )

        assert response.status_code == 400
        assert response.json()["detail"] == "No model set up. Add a valid provider before creating a target."

    def test_judge_available_models_only_include_configured_provider(
        self,
        auth_client,
        auth_headers,
        provider_settings,
    ):
        with provider_settings(gemini_api_key="shared-gemini-key"):
            response = auth_client.get("/api/v1/judges/available-models", headers=auth_headers)

        assert response.status_code == 200
        judge_models = response.json()
        assert judge_models
        assert all(model["provider_key"] == "gemini" for model in judge_models)

    def test_generation_job_rejects_model_outside_valid_provider_set(
        self,
        auth_client,
        auth_headers,
        test_db,
        test_user,
        provider_settings,
    ):
        target = Target(name="Owned Target", user_id=test_user.id)
        test_db.add(target)
        test_db.commit()
        test_db.refresh(target)

        with provider_settings(gemini_api_key="shared-gemini-key"):
            response = auth_client.post(
                "/api/v1/jobs/personas",
                json={
                    "target_id": target.id,
                    "count_requested": 1,
                    "model_used": "openai/gpt-4.1-mini",
                },
                headers=auth_headers,
            )

        assert response.status_code == 400
        assert response.json()["detail"] == "Selected model is not configured for this user."

    def test_similar_questions_requires_embedding_provider_for_owned_target(
        self,
        auth_client,
        auth_headers,
        test_db,
        test_user,
        provider_settings,
    ):
        target = Target(name="Owned Target", user_id=test_user.id)
        test_db.add(target)
        test_db.commit()
        test_db.refresh(target)

        first = Question(target_id=target.id, text="How do I apply?", status=StatusEnum.approved)
        second = Question(target_id=target.id, text="How can I submit an application?", status=StatusEnum.approved)
        test_db.add_all([first, second])
        test_db.commit()
        test_db.refresh(first)
        test_db.refresh(second)

        with provider_settings():
            response = auth_client.post(
                "/api/v1/questions/similar",
                json={
                    "target_id": target.id,
                    "question_ids": [first.id],
                    "similarity_threshold": 0.5,
                },
                headers=auth_headers,
            )

        assert response.status_code == 400
        assert "No embedding model set up" in response.json()["detail"]
