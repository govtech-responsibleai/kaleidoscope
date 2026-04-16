"""
Connector registry — maps endpoint_type to the right connector class.

Built-in connectors (e.g. http) are registered on import.
Extensions register additional connectors at app startup via
``register_connector()``.
"""

import copy
import logging
from typing import Dict, List, Type

from src.common.connectors.base import TargetConnector
from src.common.connectors.http_auth import resolve_http_auth_config

logger = logging.getLogger(__name__)

_registry: Dict[str, Type[TargetConnector]] = {}


def register_connector(name: str, cls: Type[TargetConnector]) -> None:
    """Register a connector type.

    Called by built-in modules (on import) and by extensions (at startup).

    Args:
        name: The endpoint_type string (e.g. "http", "aibots").
        cls: A TargetConnector subclass.
    """
    _registry[name] = cls
    logger.info(f"Registered connector: {name}")


def get_connector(target, db=None) -> TargetConnector:
    """Instantiate the appropriate connector for a target.

    Args:
        target: A Target ORM instance (or any object with endpoint_type,
                api_endpoint, and endpoint_config attributes).

    Returns:
        A TargetConnector ready to send messages.

    Raises:
        ValueError: If endpoint_type is missing, unsupported, or
                    api_endpoint is not set.
    """
    endpoint_type = target.endpoint_type
    endpoint_url = target.api_endpoint
    config = copy.deepcopy(target.endpoint_config or {})

    if not endpoint_type:
        raise ValueError(f"Target {target.id} has no endpoint_type configured")

    if not endpoint_url:
        raise ValueError(f"Target {target.id} has no api_endpoint configured")

    cls = _registry.get(endpoint_type)
    if cls is None:
        raise ValueError(
            f"Target {target.id} has unsupported endpoint_type '{endpoint_type}'. "
            f"Registered types: {list(_registry)}"
        )

    if endpoint_type == "http":
        config = resolve_http_auth_config(
            config,
            target_id=getattr(target, "id", None),
            db=db,
        )

    return cls(endpoint_url, config)


def get_registered_types() -> List[str]:
    """Return names of all registered connector types."""
    return list(_registry.keys())


def validate_connector_config(endpoint_type: str, config: dict) -> None:
    """Delegate config validation to the connector's validate_config classmethod.

    Args:
        endpoint_type: The endpoint type string.
        config: The endpoint_config dict to validate.

    Raises:
        ValueError: If the connector's validate_config rejects the config.
    """
    cls = _registry.get(endpoint_type)
    if cls is None:
        raise ValueError(
            f"Unsupported endpoint_type '{endpoint_type}'. "
            f"Registered types: {list(_registry)}"
        )
    cls.validate_config(config)


# ---- Auto-register built-in connectors ----

from src.common.connectors.http import HttpConnector  # noqa: E402

register_connector("http", HttpConnector)
