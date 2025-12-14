"""Expose scoring service modules lazily for patching in tests."""

from importlib import import_module
from typing import Any

__all__ = ["claim_processor", "judge_scoring", "metrics_service", "qa_job_processor"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        module = import_module(f"src.scoring.services.{name}")
        globals()[name] = module
        return module
    raise AttributeError(f"module 'src.scoring.services' has no attribute '{name}'")
