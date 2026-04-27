"""Pydantic models for provider setup and valid-model APIs."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ProviderCredentialFieldResponse(BaseModel):
    """Credential field metadata plus configured-state details."""

    key: str
    label: str
    env_var: str
    required: bool
    is_configured: bool
    masked_value: Optional[str] = None


class ProviderModelOption(BaseModel):
    """A provider-backed model option surfaced to the frontend."""

    value: str
    label: str
    provider_key: str
    provider_name: str
    logo_path: str


class ProviderSetupEntryResponse(BaseModel):
    """One provider's effective setup state for the current user."""

    key: str
    display_name: str
    logo_path: str
    description: Optional[str] = None
    source: Literal["shared", "personal", "personal_override", "none"]
    is_valid: bool
    is_read_only: bool
    default_model: str
    common_models: list[str] = Field(default_factory=list)
    embedding_models: list[str] = Field(default_factory=list)
    credential_fields: list[ProviderCredentialFieldResponse] = Field(default_factory=list)


class ServiceCredentialSetupResponse(BaseModel):
    """Merged setup state for one non-provider service credential."""

    key: str
    display_name: str
    source: Literal["shared", "personal", "personal_override", "none"]
    is_valid: bool
    is_read_only: bool
    credential_fields: list[ProviderCredentialFieldResponse] = Field(default_factory=list)


class ProviderServiceDefaultsResponse(BaseModel):
    """Effective defaults derived from the current valid provider list."""

    generation_default_model: Optional[str] = None
    embedding_default_model: Optional[str] = None
    judge_default_models: list[str] = Field(default_factory=list)
    web_search_enabled: bool = False


class ProviderCatalogResponse(BaseModel):
    """Catalog-only provider metadata."""

    providers: list[ProviderSetupEntryResponse]
    services: list[ServiceCredentialSetupResponse]


class ProviderSetupResponse(ProviderCatalogResponse):
    """Merged provider setup response used by the setup page."""

    valid_models: list[ProviderModelOption] = Field(default_factory=list)
    valid_embedding_models: list[ProviderModelOption] = Field(default_factory=list)
    defaults: ProviderServiceDefaultsResponse


class ProviderCredentialUpsertRequest(BaseModel):
    """Payload for saving a personal provider credential set."""

    credentials: dict[str, str] = Field(default_factory=dict)


class ServiceCredentialUpsertRequest(BaseModel):
    """Payload for saving a personal service credential set."""

    credentials: dict[str, str] = Field(default_factory=dict)
