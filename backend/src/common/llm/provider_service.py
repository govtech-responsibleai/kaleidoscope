"""Provider catalog + credential resolution helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field as dc_field
from typing import Any, Literal, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from src.common.config import get_settings
from src.common.database.repositories.target_repo import TargetRepository
from src.common.database.repositories.user_provider_credential_repo import UserProviderCredentialRepository
from src.common.database.repositories.user_service_credential_repo import UserServiceCredentialRepository
from src.common.llm.provider_catalog import (
    ProviderCatalogEntry,
    ProviderCredentialField,
    ProviderServiceEntry,
    get_provider_entry,
    get_service_entry,
    load_provider_catalog,
)
from src.common.models.provider_setup import (
    ProviderCatalogResponse,
    ProviderCredentialFieldResponse,
    ProviderModelOption,
    ProviderServiceDefaultsResponse,
    ProviderSetupEntryResponse,
    ProviderSetupResponse,
    ServiceCredentialSetupResponse,
)
from src.common.secrets import decrypt_json_secret, encrypt_json_secret, mask_secret

ENV_VAR_TO_SETTING_ATTR = {
    "OPENAI_API_KEY": "openai_api_key",
    "AZURE_API_KEY": "azure_api_key",
    "AZURE_API_BASE": "azure_api_base",
    "ANTHROPIC_API_KEY": "anthropic_api_key",
    "GEMINI_API_KEY": "gemini_api_key",
    "AWS_BEARER_TOKEN_BEDROCK": "aws_bearer_token_bedrock",
    "OPENROUTER_API_KEY": "openrouter_api_key",
    "OPENROUTER_API_BASE": "openrouter_api_base",
    "FIREWORKS_AI_API_KEY": "fireworks_ai_api_key",
    "SERPER_API_KEY": "serper_api_key",
}


@dataclass
class ResolvedProvider:
    """Effective resolved provider state after merging shared + personal creds."""

    catalog: ProviderCatalogEntry
    source: Literal["shared", "personal", "personal_override", "none"]
    credentials: dict[str, str]
    is_valid: bool
    shared_values: dict[str, str] = dc_field(default_factory=dict)
    personal_values: dict[str, str] = dc_field(default_factory=dict)


@dataclass
class ResolvedService:
    """Effective resolved service state after merging shared + personal creds."""

    catalog: ProviderServiceEntry
    source: Literal["shared", "personal", "personal_override", "none"]
    credentials: dict[str, str]
    is_valid: bool
    shared_values: dict[str, str] = dc_field(default_factory=dict)
    personal_values: dict[str, str] = dc_field(default_factory=dict)


@dataclass
class ProviderRuntimeConfig:
    """Per-model provider config ready to pass into LiteLLM."""

    provider_key: str
    model_name: str
    litellm_kwargs: dict[str, Any]


def _normalize_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _field_values_from_settings(fields: list[ProviderCredentialField]) -> dict[str, str]:
    settings = get_settings()
    resolved: dict[str, str] = {}
    for field in fields:
        setting_attr = ENV_VAR_TO_SETTING_ATTR.get(field.env_var)
        if not setting_attr:
            continue
        value = _normalize_value(getattr(settings, setting_attr, None))
        if value:
            resolved[field.key] = value
    return resolved


def _field_values_from_encrypted_payload(payload: Optional[str]) -> dict[str, str]:
    if not payload:
        return {}
    try:
        decrypted = decrypt_json_secret(payload)
    except ValueError:
        logger.warning("Stored credential could not be decrypted (key rotation?). Falling back to env vars.")
        return {}
    resolved: dict[str, str] = {}
    for key, value in decrypted.items():
        normalized = _normalize_value(value)
        if normalized:
            resolved[str(key)] = normalized
    return resolved


def _has_required_fields(fields: list[ProviderCredentialField], values: dict[str, str]) -> bool:
    return all(values.get(field.key) for field in fields if field.required)


def _merge_field_statuses(
    fields: list[ProviderCredentialField],
    *,
    shared_values: dict[str, str],
    personal_values: dict[str, str],
) -> list[ProviderCredentialFieldResponse]:
    source_values = personal_values or shared_values
    return [
        ProviderCredentialFieldResponse(
            key=field.key,
            label=field.label,
            env_var=field.env_var,
            required=field.required,
            is_configured=bool(source_values.get(field.key)),
            masked_value=mask_secret(source_values[field.key]) if source_values.get(field.key) else None,
        )
        for field in fields
    ]


def _resolve_source(shared_values: dict[str, str], personal_values: dict[str, str]) -> Literal["shared", "personal", "personal_override", "none"]:
    if personal_values and shared_values:
        return "personal_override"
    if personal_values:
        return "personal"
    if shared_values:
        return "shared"
    return "none"


def _model_label(model_name: str) -> str:
    return model_name.split("/", 1)[-1]


def _provider_to_model_options(provider: ProviderCatalogEntry, models: list[str]) -> list[ProviderModelOption]:
    return [
        ProviderModelOption(
            value=model,
            label=_model_label(model),
            provider_key=provider.key,
            provider_name=provider.display_name,
            logo_path=provider.logo_path,
        )
        for model in models
    ]



def list_resolved_providers(db: Session, user_id: int) -> list[ResolvedProvider]:
    """Return providers merged from shared env vars and personal credentials."""
    personal_rows = {
        row.provider_key: row
        for row in UserProviderCredentialRepository.list_by_user(db, user_id)
    }
    resolved: list[ResolvedProvider] = []
    for provider in load_provider_catalog().providers:
        shared_values = _field_values_from_settings(provider.credential_fields)
        row = personal_rows.get(provider.key)
        personal_values = _field_values_from_encrypted_payload(
            str(row.encrypted_credentials) if row is not None else None
        )
        effective_values = personal_values or shared_values
        resolved.append(
            ResolvedProvider(
                catalog=provider,
                source=_resolve_source(shared_values, personal_values),
                credentials=effective_values,
                is_valid=_has_required_fields(provider.credential_fields, effective_values),
                shared_values=shared_values,
                personal_values=personal_values,
            )
        )
    return resolved


def list_resolved_services(db: Session, user_id: int) -> list[ResolvedService]:
    """Return service credentials merged from shared env vars and personal credentials."""
    personal_rows = {
        row.service_key: row
        for row in UserServiceCredentialRepository.list_by_user(db, user_id)
    }
    resolved: list[ResolvedService] = []
    for service in load_provider_catalog().services:
        row = personal_rows.get(service.key)
        shared_values = _field_values_from_settings(service.credential_fields)
        personal_values = _field_values_from_encrypted_payload(
            str(row.encrypted_credentials) if row is not None else None
        )
        effective_values = personal_values or shared_values
        resolved.append(
            ResolvedService(
                catalog=service,
                source=_resolve_source(shared_values, personal_values),
                credentials=effective_values,
                is_valid=_has_required_fields(service.credential_fields, effective_values),
                shared_values=shared_values,
                personal_values=personal_values,
            )
        )
    return resolved


def build_provider_catalog_response(
    db: Session,
    user_id: int,
    resolved_providers: Optional[list[ResolvedProvider]] = None,
    resolved_services: Optional[list[ResolvedService]] = None,
) -> ProviderCatalogResponse:
    """Return provider catalog metadata plus merged credential states."""
    providers = resolved_providers if resolved_providers is not None else list_resolved_providers(db, user_id)
    services = resolved_services if resolved_services is not None else list_resolved_services(db, user_id)

    provider_entries: list[ProviderSetupEntryResponse] = [
        ProviderSetupEntryResponse(
            key=provider.catalog.key,
            display_name=provider.catalog.display_name,
            logo_path=provider.catalog.logo_path,
            description=provider.catalog.description,
            source=provider.source,
            is_valid=provider.is_valid,
            is_read_only=provider.source == "shared",
            default_model=provider.catalog.default_model,
            common_models=provider.catalog.common_models,
            embedding_models=provider.catalog.embedding_models,
            credential_fields=_merge_field_statuses(
                provider.catalog.credential_fields,
                shared_values=provider.shared_values,
                personal_values=provider.personal_values,
            ),
        )
        for provider in providers
    ]

    service_entries: list[ServiceCredentialSetupResponse] = [
        ServiceCredentialSetupResponse(
            key=service.catalog.key,
            display_name=service.catalog.display_name,
            source=service.source,
            is_valid=service.is_valid,
            is_read_only=service.source == "shared",
            credential_fields=_merge_field_statuses(
                service.catalog.credential_fields,
                shared_values=service.shared_values,
                personal_values=service.personal_values,
            ),
        )
        for service in services
    ]

    return ProviderCatalogResponse(providers=provider_entries, services=service_entries)


def get_valid_model_options(
    db: Session,
    user_id: int,
    resolved: Optional[list[ResolvedProvider]] = None,
) -> list[ProviderModelOption]:
    """Return valid generation models for the user in catalog order."""
    providers = resolved if resolved is not None else list_resolved_providers(db, user_id)
    models: list[ProviderModelOption] = []
    for provider in providers:
        if not provider.is_valid:
            continue
        ordered_models = list(dict.fromkeys(
            [provider.catalog.default_model, *provider.catalog.common_models]
        ))
        models.extend(_provider_to_model_options(provider.catalog, ordered_models))
    return models


def get_valid_embedding_model_options(
    db: Session,
    user_id: int,
    resolved: Optional[list[ResolvedProvider]] = None,
) -> list[ProviderModelOption]:
    """Return valid embedding models for the user in catalog order."""
    providers = resolved if resolved is not None else list_resolved_providers(db, user_id)
    models: list[ProviderModelOption] = []
    for provider in providers:
        if not provider.is_valid or not provider.catalog.embedding_models:
            continue
        models.extend(_provider_to_model_options(provider.catalog, provider.catalog.embedding_models))
    return models


def build_provider_setup_response(db: Session, user_id: int) -> ProviderSetupResponse:
    """Return full provider setup state for the current user."""
    resolved_providers = list_resolved_providers(db, user_id)
    resolved_services = list_resolved_services(db, user_id)
    catalog_response = build_provider_catalog_response(
        db, user_id,
        resolved_providers=resolved_providers,
        resolved_services=resolved_services,
    )
    valid_models = get_valid_model_options(db, user_id, resolved=resolved_providers)
    valid_embedding_models = get_valid_embedding_model_options(db, user_id, resolved=resolved_providers)
    defaults = ProviderServiceDefaultsResponse(
        generation_default_model=valid_models[0].value if valid_models else None,
        embedding_default_model=valid_embedding_models[0].value if valid_embedding_models else None,
        judge_default_models=[model.value for model in valid_models[:3]],
        web_search_enabled=any(service.key == "serper" and service.is_valid for service in catalog_response.services),
    )
    return ProviderSetupResponse(
        providers=catalog_response.providers,
        services=catalog_response.services,
        valid_models=valid_models,
        valid_embedding_models=valid_embedding_models,
        defaults=defaults,
    )


def validate_model_for_user(db: Session, user_id: int, model_name: str) -> bool:
    """Return whether the given model is in the current user's valid model list."""
    return any(option.value == model_name for option in get_valid_model_options(db, user_id))


def require_valid_model_for_user(db: Session, user_id: int, model_name: str) -> None:
    """Raise a setup error when a chosen model is not currently valid."""
    if not validate_model_for_user(db, user_id, model_name):
        raise ValueError("Selected model is not configured for this user.")


def get_default_generation_model(db: Session, user_id: int) -> Optional[str]:
    """Return the first valid generation model for the user."""
    models = get_valid_model_options(db, user_id)
    return models[0].value if models else None


def get_default_embedding_model(db: Session, user_id: int) -> Optional[str]:
    """Return the first valid embedding model for the user."""
    models = get_valid_embedding_model_options(db, user_id)
    return models[0].value if models else None


def require_default_generation_model(db: Session, user_id: int) -> str:
    """Return the first valid generation model or raise a user-facing setup error."""
    model = get_default_generation_model(db, user_id)
    if not model:
        raise ValueError("No model set up. Add a valid provider before continuing.")
    return model


def require_default_embedding_model(db: Session, user_id: int) -> str:
    """Return the first valid embedding model or raise a user-facing setup error."""
    model = get_default_embedding_model(db, user_id)
    if not model:
        raise ValueError("No embedding model set up. Add a provider with embeddings before generating questions.")
    return model


def require_user_has_valid_provider(db: Session, user_id: int) -> None:
    """Ensure the user has at least one valid provider configured."""
    if not get_valid_model_options(db, user_id):
        raise ValueError("No model set up. Add a valid provider before creating a target.")


def resolve_serper_api_key(db: Session, user_id: int) -> Optional[str]:
    """Return the effective Serper key for the user, if any."""
    services = list_resolved_services(db, user_id)
    serper = next((service for service in services if service.catalog.key == "serper"), None)
    if not serper or not serper.is_valid:
        return None
    field = serper.catalog.credential_fields[0]
    return serper.credentials.get(field.key)


def _provider_from_model(model_name: str) -> ProviderCatalogEntry:
    for provider in load_provider_catalog().providers:
        if model_name.startswith(provider.litellm_prefix):
            return provider
    raise ValueError(f"Model '{model_name}' is not a supported provider model.")


def _provider_kwargs(provider_key: str, credentials: dict[str, str]) -> dict[str, Any]:
    if provider_key == "azure":
        kwargs: dict[str, Any] = {"api_key": credentials["AZURE_API_KEY"]}
        if credentials.get("AZURE_API_BASE"):
            kwargs["api_base"] = credentials["AZURE_API_BASE"]
        return kwargs
    if provider_key == "bedrock":
        return {"aws_bearer_token_bedrock": credentials["AWS_BEARER_TOKEN_BEDROCK"]}
    if provider_key == "openrouter":
        kwargs = {"api_key": credentials["OPENROUTER_API_KEY"]}
        if credentials.get("OPENROUTER_API_BASE"):
            kwargs["api_base"] = credentials["OPENROUTER_API_BASE"]
        return kwargs
    if provider_key == "openai":
        return {"api_key": credentials["OPENAI_API_KEY"]}
    if provider_key == "anthropic":
        return {"api_key": credentials["ANTHROPIC_API_KEY"]}
    if provider_key == "gemini":
        return {"api_key": credentials["GEMINI_API_KEY"]}
    if provider_key == "fireworks":
        return {"api_key": credentials["FIREWORKS_AI_API_KEY"]}
    return {}


def resolve_model_runtime_config(db: Session, user_id: int, model_name: str) -> ProviderRuntimeConfig:
    """Resolve provider-specific LiteLLM kwargs for a model and user."""
    provider = _provider_from_model(model_name)
    resolved = next(
        (item for item in list_resolved_providers(db, user_id) if item.catalog.key == provider.key),
        None,
    )
    if not resolved or not resolved.is_valid:
        raise ValueError(f"Provider '{provider.display_name}' is not configured for this user.")
    return ProviderRuntimeConfig(
        provider_key=provider.key,
        model_name=model_name,
        litellm_kwargs=_provider_kwargs(provider.key, resolved.credentials),
    )


def resolve_model_runtime_config_for_target(
    db: Session,
    target_id: int,
    model_name: str,
) -> ProviderRuntimeConfig:
    """Resolve provider-specific LiteLLM kwargs using the owning target's user."""
    target = TargetRepository.get_by_id(db, target_id)
    if not target or target.user_id is None:
        raise ValueError("Target owner could not be resolved for provider credentials.")
    return resolve_model_runtime_config(db, int(target.user_id), model_name)


def store_provider_credentials(
    db: Session,
    user_id: int,
    provider_key: str,
    credentials: dict[str, str],
) -> None:
    """Store a personal provider credential set after validating required fields."""
    provider = get_provider_entry(provider_key)
    normalized = {
        key: value.strip()
        for key, value in credentials.items()
        if isinstance(value, str) and value.strip()
    }
    if not _has_required_fields(provider.credential_fields, normalized):
        raise ValueError("Missing one or more required credential fields.")
    UserProviderCredentialRepository.upsert(
        db,
        user_id,
        provider_key,
        encrypt_json_secret(normalized),
    )


def delete_provider_credentials(db: Session, user_id: int, provider_key: str) -> None:
    """Delete one personal provider credential set."""
    get_provider_entry(provider_key)
    UserProviderCredentialRepository.delete_by_user_and_provider(db, user_id, provider_key)


def store_service_credentials(
    db: Session,
    user_id: int,
    service_key: str,
    credentials: dict[str, str],
) -> None:
    """Store one personal service credential set after validating required fields."""
    service = get_service_entry(service_key)
    normalized = {
        key: value.strip()
        for key, value in credentials.items()
        if isinstance(value, str) and value.strip()
    }
    if not _has_required_fields(service.credential_fields, normalized):
        raise ValueError("Missing one or more required credential fields.")
    UserServiceCredentialRepository.upsert(
        db,
        user_id,
        service_key,
        encrypt_json_secret(normalized),
    )


def delete_service_credentials(db: Session, user_id: int, service_key: str) -> None:
    """Delete one personal service credential set."""
    get_service_entry(service_key)
    UserServiceCredentialRepository.delete_by_user_and_service(db, user_id, service_key)
