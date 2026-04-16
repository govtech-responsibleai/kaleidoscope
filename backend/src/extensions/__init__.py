"""
Extension loader for Kaleidoscope.

Extensions are optional modules that add connector types (and potentially
other capabilities) to Kaleidoscope. They are enabled via the
``KALEIDOSCOPE_EXTENSIONS`` environment variable.

Each extension lives under ``src/extensions/<name>/`` and must expose a
``register()`` function that is called at app startup.
"""

import importlib
import logging

logger = logging.getLogger(__name__)


def load_extensions() -> None:
    """Load all extensions listed in KALEIDOSCOPE_EXTENSIONS.

    Reads the comma-separated setting, imports each extension module,
    and calls its ``register()`` function. Logs and skips extensions
    that fail to load.
    """
    from src.common.config import get_settings

    raw = get_settings().kaleidoscope_extensions
    ext_names = [e.strip() for e in raw.split(",") if e.strip()]

    if not ext_names:
        logger.debug("No extensions configured")
        return

    for name in ext_names:
        try:
            module = importlib.import_module(f"src.extensions.{name}")
            module.register()
            logger.info(f"Loaded extension: {name}")
        except Exception:
            logger.exception(f"Failed to load extension '{name}'")
