"""Backend-owned provider catalog loader and typed access helpers."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class ProviderCredentialField(BaseModel):
    """One credential field required or accepted by a provider."""

    key: str
    label: str
    env_var: str
    required: bool = True


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
