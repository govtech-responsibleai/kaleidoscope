import pytest
from pydantic import ValidationError

from src.common.llm.provider_catalog import (
    ModelPricing,
    ProviderCatalogEntry,
    ProviderCredentialField,
    get_provider_entry,
    load_provider_catalog,
)


def _entry(**overrides) -> ProviderCatalogEntry:
    base = dict(
        key="x",
        display_name="X",
        litellm_prefix="x/",
        logo_path="/icons/x.png",
        credential_fields=[ProviderCredentialField(key="X_KEY", label="Key", env_var="X_KEY")],
        default_model="x/model-a",
    )
    base.update(overrides)
    return ProviderCatalogEntry(**base)


class TestCatalogSchema:
    def test_to_litellm_model_is_identity_without_route(self):
        assert _entry().to_litellm_model("x/model-a") == "x/model-a"

    def test_to_litellm_model_swaps_prefix_for_route(self):
        entry = _entry(litellm_route="openai/")
        assert entry.to_litellm_model("x/bedrock.claude-haiku-4-5") == "openai/bedrock.claude-haiku-4-5"

    def test_route_must_end_with_slash(self):
        with pytest.raises(ValidationError):
            _entry(litellm_route="openai")

    def test_pricing_parses_and_defaults_mode_to_chat(self):
        entry = _entry(pricing={"x/model-a": {"input": 1.0, "output": 5.0, "cache_read": 0.1}})
        pricing = entry.pricing["x/model-a"]
        assert pricing == ModelPricing(input=1.0, output=5.0, cache_read=0.1, mode="chat")


class TestGovtechCatalogEntry:
    def test_govtech_entry_routes_to_openai(self):
        govtech = get_provider_entry("govtech")
        assert govtech.litellm_prefix == "govtech/"
        assert govtech.litellm_route == "openai/"
        assert govtech.default_model == "govtech/gpt-5.6-luna"
        assert "govtech/bedrock.claude-haiku-4-5" in govtech.common_models
        assert "govtech/gemini-3.5-flash-lite" in govtech.common_models
        assert [f.env_var for f in govtech.credential_fields] == ["PLATFORM_API_KEY", "PLATFORM_API_BASE_URL"]
        assert all(f.required for f in govtech.credential_fields)

    def test_existing_providers_have_no_route(self):
        for provider in load_provider_catalog().providers:
            if provider.key != "govtech":
                assert provider.litellm_route is None
