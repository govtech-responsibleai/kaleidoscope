"""Managed HTTP auth helpers for target connectors."""

from __future__ import annotations

import copy
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from src.common.database.repositories import TargetHttpAuthSecretRepository
from src.common.secrets import decrypt_secret, encrypt_secret, mask_secret

HTTP_AUTH_PRESETS: dict[str, dict[str, str]] = {
    "bearer": {"header_name": "Authorization", "prefix": "Bearer "},
    "x-api-key": {"header_name": "x-api-key", "prefix": ""},
    "api-key": {"header_name": "api-key", "prefix": ""},
}
def encrypt_http_auth_secret(secret: str) -> str:
    return encrypt_secret(secret)


def decrypt_http_auth_secret(token: str) -> str:
    return decrypt_secret(token)


def mask_http_auth_secret(secret: str) -> str:
    return mask_secret(secret)


def normalize_http_auth_preset(preset: Any) -> str:
    value = str(preset or "").strip().lower()
    if value not in HTTP_AUTH_PRESETS:
        raise ValueError("Choose a supported auth preset.")
    return value


def _build_auth_header(preset: str, secret: str) -> tuple[str, str]:
    preset_config = HTTP_AUTH_PRESETS[preset]
    return preset_config["header_name"], f"{preset_config['prefix']}{secret}"


def prepare_http_config_for_storage(config: Optional[Dict[str, Any]], has_existing_secret: bool) -> tuple[Dict[str, Any], Optional[str], bool]:
    """Strip transient auth fields and return safe config for persistence."""
    next_config = copy.deepcopy(config or {})
    auth = next_config.get("auth")

    if not isinstance(auth, dict):
        next_config.pop("auth", None)
        return next_config, None, has_existing_secret

    if auth.get("clear_secret"):
        next_config.pop("auth", None)
        return next_config, None, False

    preset = normalize_http_auth_preset(auth.get("preset"))
    secret_value = str(auth.get("secret_value") or "").strip()

    if secret_value:
        next_config["auth"] = {
            "preset": preset,
            "is_configured": True,
            "masked_value": mask_http_auth_secret(secret_value),
        }
        return next_config, secret_value, True

    if has_existing_secret:
        masked_value = str(auth.get("masked_value") or "").strip()
        if not masked_value:
            raise ValueError("Managed auth is configured but its masked value is missing.")
        next_config["auth"] = {
            "preset": preset,
            "is_configured": True,
            "masked_value": masked_value,
        }
        return next_config, None, True

    raise ValueError("Enter an auth value or remove the auth configuration.")


def persist_http_auth_secret(
    db: Session,
    target_id: int,
    *,
    secret_value: Optional[str],
    should_keep_secret: bool,
) -> None:
    """Persist or clear a target-scoped managed HTTP auth secret."""
    if secret_value:
        TargetHttpAuthSecretRepository.upsert(db, target_id, encrypt_http_auth_secret(secret_value))
        return
    if not should_keep_secret:
        TargetHttpAuthSecretRepository.delete_by_target_id(db, target_id)


def resolve_http_auth_config(
    config: Optional[Dict[str, Any]],
    *,
    target_id: Optional[int] = None,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Resolve transient or stored managed auth into concrete HTTP headers."""
    next_config = copy.deepcopy(config or {})
    auth = next_config.pop("auth", None)
    if not isinstance(auth, dict):
        return next_config

    preset = normalize_http_auth_preset(auth.get("preset"))
    secret_value = str(auth.get("secret_value") or "").strip()

    if not secret_value and auth.get("is_configured"):
        if target_id is None or db is None:
            raise ValueError("Managed auth is configured but no target context was provided.")
        secret_row = TargetHttpAuthSecretRepository.get_by_target_id(db, target_id)
        if not secret_row:
            raise ValueError("Managed auth is configured but no saved secret was found for this target.")
        secret_value = decrypt_http_auth_secret(secret_row.encrypted_secret)

    if not secret_value:
        return next_config

    header_name, header_value = _build_auth_header(preset, secret_value)
    headers = dict(next_config.get("headers", {}))
    headers[header_name] = header_value
    next_config["headers"] = headers
    return next_config
