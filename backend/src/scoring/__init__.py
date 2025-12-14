"""Scoring package with lazy access to submodules."""

from importlib import import_module
from typing import Any

__all__ = ["services", "api"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        module = import_module(f"src.scoring.{name}")
        globals()[name] = module
        return module
    raise AttributeError(f"module 'src.scoring' has no attribute '{name}'")
