"""
Cost tracking utilities for LLM API calls.

Works in conjunction with Arize Phoenix instrumentation for comprehensive tracking.
Note: Phoenix automatically tracks all LiteLLM calls when instrumented.
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class CostTracker:
    """
    Tracks cumulative costs and token usage for a specific job or operation.

    This provides in-memory tracking for immediate feedback, while Phoenix
    provides persistent tracking and analytics across all API calls.
    """

    def __init__(self, job_id: Optional[int] = None):
        """
        Initialize cost tracker.

        Args:
            job_id: Optional job ID for tracking costs per job
        """
        self.job_id = job_id
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0
        self.total_cost = 0.0
        self.calls = []

    def add_call(self, response: Dict) -> None:
        """
        Add an LLM call response to the tracker.

        Args:
            response: Response dict from LLMClient.generate()
                Expected keys: prompt_tokens, completion_tokens, total_tokens, cost
        """
        self.total_prompt_tokens += response.get("prompt_tokens", 0)
        self.total_completion_tokens += response.get("completion_tokens", 0)
        self.total_tokens += response.get("total_tokens", 0)
        self.total_cost += response.get("cost", 0.0)

        self.calls.append({
            "model": response.get("model"),
            "prompt_tokens": response.get("prompt_tokens", 0),
            "completion_tokens": response.get("completion_tokens", 0),
            "total_tokens": response.get("total_tokens", 0),
            "cost": response.get("cost", 0.0),
        })

    def add_batch(self, responses: List[Dict]) -> None:
        """
        Add multiple LLM call responses to the tracker.

        Args:
            responses: List of response dicts from LLMClient
        """
        for response in responses:
            self.add_call(response)

    def get_summary(self) -> Dict:
        """
        Get summary of tracked costs and usage.

        Returns:
            Dict with:
                - total_calls: Number of API calls
                - prompt_tokens: Total prompt tokens
                - completion_tokens: Total completion tokens
                - total_tokens: Total tokens used
                - total_cost: Total cost in USD
        """
        return {
            "total_calls": len(self.calls),
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "total_cost": round(self.total_cost, 6),
        }

    def log_summary(self, prefix: str = "") -> None:
        """
        Log a summary of costs and usage.

        Args:
            prefix: Optional prefix for log message
        """
        summary = self.get_summary()
        msg = f"💰 Cost Summary"
        if prefix:
            msg = f"{prefix} - {msg}"
        if self.job_id:
            msg += f" [Job {self.job_id}]"

        logger.info(
            f"{msg}: {summary['total_calls']} calls, "
            f"{summary['total_tokens']} tokens, "
            f"${summary['total_cost']:.6f}"
        )

    def reset(self) -> None:
        """Reset the tracker."""
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0
        self.total_cost = 0.0
        self.calls = []
