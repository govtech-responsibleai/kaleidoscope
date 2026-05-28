"""Demo target seeding for first-time Google sign-ins."""

import json
import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from src.common.connectors.http_auth import prepare_http_config_for_storage, persist_http_auth_secret
from src.common.config import get_settings
from src.common.database.models import Target
from src.common.database.repositories.target_repo import TargetRepository
from src.rubric.services.system_rubrics import bootstrap_target_rubrics_and_judges

logger = logging.getLogger(__name__)


def _parse_json_object(value: Optional[str], setting_name: str) -> Optional[dict[str, Any]]:
    """Parse an optional JSON object setting."""
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        logger.warning("%s must be valid JSON; skipping demo target seeding", setting_name)
        return None
    if not isinstance(parsed, dict):
        logger.warning("%s must be a JSON object; skipping demo target seeding", setting_name)
        return None
    return parsed


def _extract_managed_auth(headers: dict[str, Any]) -> tuple[dict[str, str], Optional[dict[str, str]]]:
    """Move supported auth headers into managed HTTP auth config."""
    safe_headers: dict[str, str] = {}
    auth_config: Optional[dict[str, str]] = None

    for key, value in headers.items():
        header_name = str(key)
        header_value = str(value)
        normalized = header_name.lower()
        if normalized == "x-api-key" and auth_config is None:
            auth_config = {"preset": "x-api-key", "secret_value": header_value}
            continue
        if normalized == "api-key" and auth_config is None:
            auth_config = {"preset": "api-key", "secret_value": header_value}
            continue
        if normalized == "authorization" and header_value.lower().startswith("bearer ") and auth_config is None:
            auth_config = {"preset": "bearer", "secret_value": header_value[7:].strip()}
            continue
        safe_headers[header_name] = header_value

    return safe_headers, auth_config


def seed_demo_target(db: Session, user_id: int) -> Optional[Target]:
    """Create the configured demo HTTP target for a new user.

    Args:
        db: Database session.
        user_id: Owner user ID.

    Returns:
        The created target, or None when seeding is disabled/skipped.
    """
    settings = get_settings()
    if not settings.demo_target_endpoint:
        return None
    if not settings.demo_target_response_path:
        logger.warning("DEMO_TARGET_RESPONSE_PATH is required when DEMO_TARGET_ENDPOINT is set; skipping demo target seeding")
        return None

    headers = _parse_json_object(settings.demo_target_headers, "DEMO_TARGET_HEADERS")
    if settings.demo_target_headers and headers is None:
        return None

    body_template = _parse_json_object(settings.demo_target_body_template, "DEMO_TARGET_BODY_TEMPLATE")
    if settings.demo_target_body_template and body_template is None:
        return None

    endpoint_config: dict[str, Any] = {
        "response_content_path": settings.demo_target_response_path,
    }
    if settings.demo_target_retrieved_context_path:
        endpoint_config["retrieved_context_path"] = settings.demo_target_retrieved_context_path
    if headers:
        safe_headers, auth_config = _extract_managed_auth(headers)
        if safe_headers:
            endpoint_config["headers"] = safe_headers
        if auth_config:
            endpoint_config["auth"] = auth_config
    if body_template:
        endpoint_config["body_template"] = body_template

    endpoint_config, pending_secret_value, should_keep_secret = prepare_http_config_for_storage(
        endpoint_config,
        has_existing_secret=False,
    )

    target = TargetRepository.create(
        db,
        {
            "user_id": user_id,
            "name": settings.demo_target_name or "Demo Chatbot",
            "agency": settings.demo_target_agency or None,
            "purpose": settings.demo_target_purpose or None,
            "target_users": settings.demo_target_target_users or None,
            "api_endpoint": settings.demo_target_endpoint,
            "endpoint_type": "http",
            "endpoint_config": endpoint_config,
        },
    )
    bootstrap_target_rubrics_and_judges(db, int(target.id))  # type: ignore[arg-type]
    persist_http_auth_secret(
        db,
        int(target.id),  # type: ignore[arg-type]
        secret_value=pending_secret_value,
        should_keep_secret=should_keep_secret,
    )
    db.commit()
    db.refresh(target)
    return target
