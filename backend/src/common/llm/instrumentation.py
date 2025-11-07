"""
Phoenix instrumentation for automatic LLM tracking.

Sets up Arize Phoenix to automatically track all LiteLLM calls
with token counts, costs, and traces.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def setup_phoenix_instrumentation(project_name: str = "kaleidoscope-api") -> Optional[str]:
    """
    Setup Arize Phoenix instrumentation for automatic LLM tracking.

    This should be called once at API startup. It will automatically track:
    - All LiteLLM API calls
    - Token counts (prompt, completion, total)
    - Costs per call
    - Request/response traces

    Args:
        project_name: Name for the Phoenix project

    Returns:
        Phoenix dashboard URL if successful, None otherwise

    Environment Variables Required:
        - PHOENIX_COLLECTOR_ENDPOINT: Phoenix collector endpoint
        - PHOENIX_API_KEY: Phoenix API key (optional for local)
    """
    try:
        from phoenix.otel import register as register_phoenix
        from openinference.instrumentation.litellm import LiteLLMInstrumentor

        endpoint = os.getenv("PHOENIX_COLLECTOR_ENDPOINT")
        if not endpoint:
            logger.warning(
                "PHOENIX_COLLECTOR_ENDPOINT not set. Skipping Phoenix instrumentation. "
                "LLM calls will still work but won't be tracked."
            )
            return None

        # Configure Phoenix tracer
        tracer_provider = register_phoenix(
            project_name=project_name,
            endpoint=f"{endpoint}/v1/traces" if not endpoint.endswith("/v1/traces") else endpoint,
            auto_instrument=True,
        )

        # Instrument LiteLLM for automatic tracking
        LiteLLMInstrumentor().instrument(tracer_provider=tracer_provider)

        logger.info(
            f"🔍 Phoenix instrumentation enabled for project '{project_name}'"
        )
        logger.info(f"📊 View traces at: {endpoint}")

        return endpoint

    except ImportError as e:
        logger.warning(
            f"Phoenix dependencies not installed: {e}. "
            "Install with: pip install arize-phoenix openinference-instrumentation-litellm"
        )
        return None
    except Exception as e:
        logger.error(f"Failed to setup Phoenix instrumentation: {e}")
        return None


def disable_phoenix_instrumentation():
    """
    Disable Phoenix instrumentation.

    Useful for testing or when you want to temporarily disable tracking.
    """
    try:
        from openinference.instrumentation.litellm import LiteLLMInstrumentor

        LiteLLMInstrumentor().uninstrument()
        logger.info("Phoenix instrumentation disabled")
    except Exception as e:
        logger.warning(f"Failed to disable Phoenix instrumentation: {e}")
