import pytest

from src.common.llm.provider_service import (
    ProviderRuntimeConfig,
    build_provider_setup_response,
    resolve_model_runtime_config,
    resolve_model_runtime_config_from_env,
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
        assert any(model.value == "gemini/gemini-3.1-flash-lite" for model in response.valid_models)

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

    def test_runtime_config_defaults_litellm_model_to_model_name(self):
        config = ProviderRuntimeConfig(provider_key="gemini", model_name="gemini/x", litellm_kwargs={})
        assert config.litellm_model == "gemini/x"

    def test_resolve_govtech_routes_to_openai_with_base(self, test_db, test_user, provider_settings):
        with provider_settings(
            platform_api_key="govtech-key",
            platform_api_base_url="https://platform.example/v1",
        ):
            runtime_config = resolve_model_runtime_config(test_db, test_user.id, "govtech/gpt-5.6-luna")

        assert runtime_config.provider_key == "govtech"
        assert runtime_config.model_name == "govtech/gpt-5.6-luna"
        assert runtime_config.litellm_model == "openai/gpt-5.6-luna"
        assert runtime_config.litellm_kwargs == {
            "api_key": "govtech-key",
            "api_base": "https://platform.example/v1",
        }

    def test_govtech_requires_both_fields(self, test_db, test_user, provider_settings):
        with provider_settings(platform_api_key="govtech-key"):
            with pytest.raises(ValueError, match="not configured"):
                resolve_model_runtime_config(test_db, test_user.id, "govtech/gpt-5.6-luna")

    def test_existing_provider_keeps_wire_model(self, test_db, test_user, provider_settings):
        with provider_settings(gemini_api_key="g"):
            runtime_config = resolve_model_runtime_config(test_db, test_user.id, "gemini/gemini-3.1-flash-lite")
        assert runtime_config.litellm_model == "gemini/gemini-3.1-flash-lite"

    def test_resolve_from_env_uses_shared_credentials_only(self, provider_settings):
        with provider_settings(
            platform_api_key="env-key",
            platform_api_base_url="https://platform.example/v1",
        ):
            runtime_config = resolve_model_runtime_config_from_env("govtech/bedrock.claude-haiku-4-5")

        assert runtime_config.litellm_model == "openai/bedrock.claude-haiku-4-5"
        assert runtime_config.litellm_kwargs["api_key"] == "env-key"

    def test_resolve_from_env_raises_when_unconfigured(self, provider_settings):
        with provider_settings():
            with pytest.raises(ValueError, match="not configured"):
                resolve_model_runtime_config_from_env("govtech/gpt-5.6-luna")
