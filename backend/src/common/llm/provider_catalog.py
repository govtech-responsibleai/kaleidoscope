"""Backend-owned provider catalog loader and typed access helpers."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator


class ProviderCredentialField(BaseModel):
    """One credential field required or accepted by a provider."""

    key: str
    label: str
    env_var: str
    required: bool = True


class ModelPricing(BaseModel):
    """USD cost per 1M tokens for one catalog model.

    Used to register pricing with LiteLLM for models it does not know about
    (for example models served through an OpenAI-compatible gateway).
    """

    input: float
    output: float
    cache_read: float | None = None
    mode: Literal["chat", "embedding"] = "chat"


class ProviderCatalogEntry(BaseModel):
    """One LiteLLM-backed provider exposed in the setup UI and runtime."""

    key: str
    display_name: str
    litellm_prefix: str
    logo_path: str
    description: str | None = None
    credential_fields: list[ProviderCredentialField]
    default_model: str
    common_models: list[str] = Field(default_factory=list)
    embedding_models: list[str] = Field(default_factory=list)
    # When set, models under ``litellm_prefix`` are sent to LiteLLM under this
    # prefix instead (e.g. ``openai/`` for an OpenAI-compatible gateway).
    litellm_route: str | None = None
    # Optional per-model pricing keyed by the catalog-facing model name.
    pricing: dict[str, ModelPricing] = Field(default_factory=dict)

    @field_validator("litellm_route")
    @classmethod
    def _route_ends_with_slash(cls, value: str | None) -> str | None:
        if value is not None and not value.endswith("/"):
            raise ValueError("litellm_route must end with '/'")
        return value

    def to_litellm_model(self, model_name: str) -> str:
        """Translate a catalog-facing model name into the name LiteLLM receives.

        Args:
            model_name: Model name as stored in the catalog and the database.

        Returns:
            The same name when no ``litellm_route`` is set; otherwise the name
            with ``litellm_prefix`` swapped for ``litellm_route``.
        """
        if not self.litellm_route:
            return model_name
        return f"{self.litellm_route}{model_name.removeprefix(self.litellm_prefix)}"


class ProviderServiceEntry(BaseModel):
    """One non-LLM service credential entry in the catalog."""

    key: str
    display_name: str
    credential_fields: list[ProviderCredentialField]


class ProviderCatalog(BaseModel):
    """Parsed provider catalog."""

    providers: list[ProviderCatalogEntry]
    services: list[ProviderServiceEntry] = Field(default_factory=list)


def _catalog_path() -> Path:
    return Path(__file__).with_name("provider_catalog.yaml")


@lru_cache(maxsize=1)
def load_provider_catalog() -> ProviderCatalog:
    """Load the YAML-backed provider catalog once per process."""
    raw = yaml.safe_load(_catalog_path().read_text(encoding="utf-8")) or {}
    return ProviderCatalog.model_validate(raw)


def get_provider_entry(provider_key: str) -> ProviderCatalogEntry:
    """Return one provider entry by key."""
    for provider in load_provider_catalog().providers:
        if provider.key == provider_key:
            return provider
    raise KeyError(f"Unknown provider '{provider_key}'.")


def get_service_entry(service_key: str) -> ProviderServiceEntry:
    """Return one service entry by key."""
    for service in load_provider_catalog().services:
        if service.key == service_key:
            return service
    raise KeyError(f"Unknown service '{service_key}'.")
