"""Shared helpers for encrypting and masking sensitive user-managed secrets."""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from src.common.config import get_settings


def _fernet() -> Fernet:
    digest = hashlib.sha256(get_settings().jwt_secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(secret: str) -> str:
    """Encrypt one sensitive string for database storage."""
    return _fernet().encrypt(secret.encode("utf-8")).decode("utf-8")


def decrypt_secret(token: str) -> str:
    """Decrypt one sensitive string from database storage."""
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:  # pragma: no cover - corruption/rotation edge case
        raise ValueError("Stored secret could not be decrypted.") from exc


def encrypt_json_secret(value: dict[str, Any]) -> str:
    """Encrypt a JSON payload for compact credential storage."""
    return encrypt_secret(json.dumps(value))


def decrypt_json_secret(token: str) -> dict[str, Any]:
    """Decrypt a JSON payload used for provider credentials."""
    raw = decrypt_secret(token)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:  # pragma: no cover - corruption edge case
        raise ValueError("Stored secret payload is not valid JSON.") from exc
    if not isinstance(data, dict):
        raise ValueError("Stored secret payload must be a JSON object.")
    return data


def mask_secret(secret: str) -> str:
    """Mask a secret while leaving a short tail visible for user confirmation."""
    tail = secret[-4:] if len(secret) >= 4 else secret
    return f"{'•' * max(4, len(secret) - len(tail))}{tail}"
