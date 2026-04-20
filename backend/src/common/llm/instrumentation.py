"""
Langfuse instrumentation for automatic LLM tracking.

Sets up Langfuse via LiteLLM's OTEL callback to automatically track all
LiteLLM calls with token counts, costs, and traces.

Requires langfuse>=3.0.0 and litellm>=1.83.8.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def setup_langfuse_instrumentation(project_name: str = "kaleidoscope-api") -> Optional[str]:
    """
    Setup Langfuse instrumentation for automatic LLM tracking via LiteLLM's
    OTEL callback.

    This should be called once at API startup. It will automatically track:
    - All LiteLLM API calls
    - Token counts (prompt, completion, total)
    - Costs per call
    - Request/response traces

    Args:
        project_name: Ignored (kept for call-site compatibility). Langfuse uses
                      projects configured via the dashboard.

    Returns:
        Langfuse host URL if enabled, None otherwise.

    Environment Variables Required:
        LANGFUSE_PUBLIC_KEY  - Langfuse public key
        LANGFUSE_SECRET_KEY  - Langfuse secret key
        LANGFUSE_BASE_URL    - (optional) self-hosted URL, defaults to Langfuse cloud
    """
    from src.common.config import get_settings
    settings = get_settings()

    public_key = settings.langfuse_public_key
    secret_key = settings.langfuse_secret_key

    if not public_key or not secret_key:
        logger.warning(
            "LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY not set. "
            "Skipping Langfuse instrumentation. "
            "LLM calls will still work but won't be tracked."
        )
        return None

    try:
        # Verify langfuse is installed before enabling the callback.
        # If we set litellm.callbacks = ["langfuse_otel"] when the package
        # is missing, LiteLLM's async callback queue crashes on the first LLM
        # call, producing confusing "Queue bound to different event loop" errors.
        import langfuse  # noqa: F401 — import check only

        import litellm

        # Expose keys as env vars so LiteLLM's langfuse_otel callback can read them
        os.environ["LANGFUSE_PUBLIC_KEY"] = public_key
        os.environ["LANGFUSE_SECRET_KEY"] = secret_key
        if settings.langfuse_base_url:
            # Set both env vars that LiteLLM/Langfuse may check
            os.environ["LANGFUSE_HOST"] = settings.langfuse_base_url
            os.environ["LANGFUSE_OTEL_HOST"] = settings.langfuse_base_url

        # The OTEL HTTP exporter defaults to certifi's CA bundle, which doesn't
        # include the Cloudflare inspection CA that self-hosted instances sit behind.
        # Point it to the system bundle (populated by the Dockerfile's update-ca-certificates).
        system_ca_bundle = "/etc/ssl/certs/ca-certificates.crt"
        if os.path.exists(system_ca_bundle):
            os.environ.setdefault("OTEL_EXPORTER_OTLP_CERTIFICATE", system_ca_bundle)
            os.environ.setdefault("REQUESTS_CA_BUNDLE", system_ca_bundle)

        # Register Langfuse OTEL as a LiteLLM callback.
        # "langfuse_otel" is the correct callback name for langfuse 3.x+.
        # The legacy "langfuse" callback only works with langfuse 2.x.
        litellm.callbacks = ["langfuse_otel"]

        host = settings.langfuse_base_url or "https://cloud.langfuse.com"
        logger.info("Langfuse instrumentation enabled (OTEL)")
        logger.info(f"View traces at: {host}")
        return host

    except ImportError as e:
        logger.warning(
            f"Langfuse package not installed ({e}). "
            "Skipping Langfuse instrumentation. "
            "Rebuild the container with: docker-compose up --build"
        )
        return None
    except Exception as e:
        logger.error(f"Failed to setup Langfuse instrumentation: {e}")
        return None


def disable_langfuse_instrumentation() -> None:
    """Disable Langfuse instrumentation by clearing LiteLLM callbacks."""
    try:
        import litellm
        litellm.callbacks = [c for c in (litellm.callbacks or []) if c != "langfuse_otel"]
        logger.info("Langfuse instrumentation disabled")
    except Exception as e:
        logger.warning(f"Failed to disable Langfuse instrumentation: {e}")
