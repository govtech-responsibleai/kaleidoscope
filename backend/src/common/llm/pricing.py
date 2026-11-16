"""Register catalog-declared model pricing with LiteLLM.

LiteLLM computes cost from a built-in price table keyed by model name and
provider. Models served through an OpenAI-compatible gateway (e.g. the GovTech
AI Platform) are called under the ``openai`` provider with names LiteLLM either
does not know at all (``bedrock.claude-haiku-4-5``) or knows only under another
provider (``gemini-3.5-flash-lite`` is a Vertex model to LiteLLM). In both
cases ``completion_cost`` fails and CostTracker under-reports. Providers may
declare ``pricing`` in ``provider_catalog.yaml``; this module turns those
entries into ``litellm.register_model`` calls.

``litellm.register_model`` resolves a routed key such as ``openai/<bare>`` to
an existing entry when LiteLLM already prices ``<bare>`` under that same
provider, and merges into it, silently re-pricing the real model. So three
cases apply per catalog entry:

- bare name unknown to LiteLLM: register the routed name and the bare name
  (gateways often echo the bare name back in responses);
- bare name known under a different provider: register the routed name only,
  which LiteLLM stores as its own key and finds via ``provider/model`` lookup;
- bare name known under the same provider as the route: register nothing and
  warn; LiteLLM's own price is used and the catalog entry is ignored.
"""

from __future__ import annotations

import logging
from typing import Any

import litellm

from src.common.llm.provider_catalog import ProviderCatalog, load_provider_catalog

logger = logging.getLogger(__name__)

_PER_MILLION = 1_000_000


def build_litellm_pricing_map(
    catalog: ProviderCatalog,
    known_providers: dict[str, str | None],
) -> dict[str, dict[str, Any]]:
    """Translate catalog pricing into LiteLLM's ``model_cost`` entry format.

    See the module docstring for the three cases that decide which keys are
    produced for each catalog entry.

    Args:
        catalog: Parsed provider catalog.
        known_providers: Bare model names LiteLLM already prices, mapped to the
            ``litellm_provider`` recorded for each (``None`` when unset).

    Returns:
        Mapping of model name to LiteLLM cost entry.
    """
    entries: dict[str, dict[str, Any]] = {}
    for provider in catalog.providers:
        route_provider = (provider.litellm_route or provider.litellm_prefix).rstrip("/")
        for model_name, pricing in provider.pricing.items():
            wire_model = provider.to_litellm_model(model_name)
            bare_model = wire_model.split("/", 1)[-1]
            known_under = known_providers.get(bare_model) if bare_model in known_providers else None
            if bare_model in known_providers and known_under == route_provider:
                logger.warning(
                    "Catalog pricing for %s ignored: LiteLLM already prices '%s' under '%s'",
                    model_name,
                    bare_model,
                    route_provider,
                )
                continue
            entry: dict[str, Any] = {
                "input_cost_per_token": pricing.input / _PER_MILLION,
                "output_cost_per_token": pricing.output / _PER_MILLION,
                "litellm_provider": route_provider,
                "mode": pricing.mode,
            }
            if pricing.cache_read is not None:
                entry["cache_read_input_token_cost"] = pricing.cache_read / _PER_MILLION
            entries[wire_model] = entry
            if bare_model in known_providers:
                logger.info(
                    "Catalog pricing for %s registered as '%s' only: LiteLLM prices '%s' under '%s'",
                    model_name,
                    wire_model,
                    bare_model,
                    known_under,
                )
            else:
                entries[bare_model] = dict(entry)
    return entries


def _known_providers() -> dict[str, str | None]:
    """Bare model names LiteLLM prices, mapped to their ``litellm_provider``."""
    return {
        name: (info.get("litellm_provider") if isinstance(info, dict) else None)
        for name, info in litellm.model_cost.items()
    }


def register_catalog_pricing() -> int:
    """Register every catalog pricing entry with LiteLLM.

    Returns:
        Number of model names registered (0 when nothing needs registering).
    """
    pricing_map = build_litellm_pricing_map(load_provider_catalog(), _known_providers())
    if not pricing_map:
        return 0
    litellm.register_model(pricing_map)
    logger.info("Registered LiteLLM pricing for %d catalog model names", len(pricing_map))
    return len(pricing_map)
