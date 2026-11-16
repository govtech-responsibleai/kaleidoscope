from unittest.mock import patch

import litellm
import pytest

from src.common.llm.pricing import build_litellm_pricing_map, register_catalog_pricing
from src.common.llm.provider_catalog import (
    ProviderCatalog,
    ProviderCatalogEntry,
    ProviderCredentialField,
)


def _catalog(pricing: dict, route: str | None = "openai/") -> ProviderCatalog:
    entry = ProviderCatalogEntry(
        key="govtech",
        display_name="GovTech",
        litellm_prefix="govtech/",
        litellm_route=route,
        logo_path="/icons/x.svg",
        credential_fields=[ProviderCredentialField(key="K", label="K", env_var="K")],
        default_model="govtech/a",
        pricing=pricing,
    )
    return ProviderCatalog(providers=[entry])


class TestPricingMap:
    def test_scales_per_million_to_per_token_and_uses_wire_name(self):
        catalog = _catalog({"govtech/a": {"input": 1.0, "output": 5.0, "cache_read": 0.1}})
        result = build_litellm_pricing_map(catalog, known_providers={})

        assert result["openai/a"]["input_cost_per_token"] == pytest.approx(1e-6)
        assert result["openai/a"]["output_cost_per_token"] == pytest.approx(5e-6)
        assert result["openai/a"]["cache_read_input_token_cost"] == pytest.approx(1e-7)
        assert result["openai/a"]["litellm_provider"] == "openai"
        assert result["openai/a"]["mode"] == "chat"
        # Bare name registered too, so cost lookup works whichever form LiteLLM echoes back
        assert result["a"] == result["openai/a"]

    def test_skips_entire_entry_when_litellm_knows_bare_name_under_same_provider(self, caplog):
        catalog = _catalog({"govtech/gpt-4o": {"input": 1.0, "output": 2.0}})
        with caplog.at_level("WARNING"):
            result = build_litellm_pricing_map(catalog, known_providers={"gpt-4o": "openai"})
        assert "openai/gpt-4o" not in result
        assert "gpt-4o" not in result
        assert "already prices" in caplog.text

    def test_registers_routed_name_only_when_bare_known_under_other_provider(self):
        catalog = _catalog({"govtech/gemini-x": {"input": 0.3, "output": 2.5}})
        result = build_litellm_pricing_map(catalog, known_providers={"gemini-x": "vertex_ai-language-models"})
        assert set(result) == {"openai/gemini-x"}
        assert result["openai/gemini-x"]["litellm_provider"] == "openai"

    def test_omits_cache_read_when_absent(self):
        catalog = _catalog({"govtech/a": {"input": 1.0, "output": 2.0}})
        assert "cache_read_input_token_cost" not in build_litellm_pricing_map(catalog, {})["openai/a"]

    def test_register_calls_litellm_and_returns_count(self):
        catalog = _catalog({"govtech/a": {"input": 1.0, "output": 2.0}})
        with patch("src.common.llm.pricing.load_provider_catalog", return_value=catalog), \
             patch("src.common.llm.pricing.litellm.register_model") as mock_register, \
             patch("src.common.llm.pricing.litellm.model_cost", {}):
            assert register_catalog_pricing() == 2
        mock_register.assert_called_once()
        assert set(mock_register.call_args.args[0]) == {"openai/a", "a"}

    def test_register_is_noop_without_pricing(self):
        with patch("src.common.llm.pricing.load_provider_catalog", return_value=_catalog({})), \
             patch("src.common.llm.pricing.litellm.register_model") as mock_register:
            assert register_catalog_pricing() == 0
        mock_register.assert_not_called()

    def test_register_model_collision_is_avoided_end_to_end(self):
        bare_model = "gpt-4o-mini"
        if bare_model not in litellm.model_cost:
            pytest.skip(f"LiteLLM does not know '{bare_model}'; nothing to collide with")
        original_input_cost = litellm.model_cost[bare_model]["input_cost_per_token"]

        catalog = _catalog({f"govtech/{bare_model}": {"input": 999.0, "output": 999.0}})
        with patch("src.common.llm.pricing.load_provider_catalog", return_value=catalog):
            registered = register_catalog_pricing()

        assert registered == 0
        assert litellm.model_cost[bare_model]["input_cost_per_token"] == original_input_cost

    def test_routed_registration_prices_gateway_model_without_touching_bare_entry(self):
        bare_model = "gemini-3.5-flash-lite"
        existing = litellm.model_cost.get(bare_model)
        if not existing or existing.get("litellm_provider") == "openai":
            pytest.skip(f"LiteLLM does not know '{bare_model}' under a non-openai provider")
        routed = f"openai/{bare_model}"
        original = dict(existing)
        # Another test may already have registered the real catalog; restore whatever was there.
        prior_routed = litellm.model_cost.get(routed)

        catalog = _catalog({f"govtech/{bare_model}": {"input": 999.0, "output": 1.0}})
        try:
            with patch("src.common.llm.pricing.load_provider_catalog", return_value=catalog):
                assert register_catalog_pricing() == 1
            assert litellm.model_cost[bare_model]["input_cost_per_token"] == original["input_cost_per_token"]
            assert litellm.model_cost[routed]["input_cost_per_token"] == pytest.approx(999e-6)
            prompt_cost, _ = litellm.cost_per_token(
                model=bare_model, custom_llm_provider="openai", prompt_tokens=1000, completion_tokens=0
            )
            assert prompt_cost == pytest.approx(0.999)
        finally:
            if prior_routed is None:
                litellm.model_cost.pop(routed, None)
            else:
                litellm.model_cost[routed] = prior_routed
