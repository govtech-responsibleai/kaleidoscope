import pytest

from src.common.llm.provider_service import (
    build_provider_setup_response,
    resolve_model_runtime_config,
    store_provider_credentials,
)


class TestProviderService:
    def test_build_provider_setup_response_prefers_personal_over_shared(self, test_db, test_user, provider_settings):
        with provider_settings(gemini_api_key="shared-gemini-key"):
            store_provider_credentials(
                test_db,
                test_user.id,
                "gemini",
                {"GEMINI_API_KEY": "personal-gemini-key"},
            )
            test_db.commit()

            response = build_provider_setup_response(test_db, test_user.id)

        gemini = next(provider for provider in response.providers if provider.key == "gemini")
        assert gemini.source == "personal_override"
        assert gemini.is_valid is True
        assert any(model.value == "gemini/gemini-3.1-flash-lite-preview" for model in response.valid_models)

    def test_build_provider_setup_response_includes_openrouter_description(self, test_db, test_user, provider_settings):
        with provider_settings():
            response = build_provider_setup_response(test_db, test_user.id)

        openrouter = next(provider for provider in response.providers if provider.key == "openrouter")

        assert openrouter.description is not None
        assert "openrouter/openrouter/free" in openrouter.description
        assert openrouter.default_model == "openrouter/openrouter/free"
        assert openrouter.common_models == ["openrouter/openrouter/free"]

    def test_resolve_model_runtime_config_maps_azure_fields(self, test_db, test_user, provider_settings):
        with provider_settings(
            azure_api_key="azure-test-key",
            azure_api_base="https://example.openai.azure.com",
        ):
            runtime_config = resolve_model_runtime_config(
                test_db,
                test_user.id,
                "azure/gpt-5-mini-2025-08-07",
            )

        assert runtime_config.provider_key == "azure"
        assert runtime_config.litellm_kwargs == {
            "api_key": "azure-test-key",
            "api_base": "https://example.openai.azure.com",
        }

    def test_store_provider_credentials_requires_required_fields(self, test_db, test_user):
        with pytest.raises(ValueError, match="Missing one or more required credential fields"):
            store_provider_credentials(test_db, test_user.id, "openai", {})

    def test_build_provider_setup_response_falls_back_to_env_on_decrypt_failure(self, test_db, test_user, provider_settings):
        with provider_settings(jwt_secret_key="original-key", gemini_api_key=""):
            store_provider_credentials(
                test_db,
                test_user.id,
                "gemini",
                {"GEMINI_API_KEY": "personal-gemini-key"},
            )
            test_db.commit()

        with provider_settings(jwt_secret_key="rotated-key", gemini_api_key="shared-gemini-key"):
            response = build_provider_setup_response(test_db, test_user.id)

        gemini = next(provider for provider in response.providers if provider.key == "gemini")
        assert gemini.source == "shared"
        assert gemini.is_valid is True
