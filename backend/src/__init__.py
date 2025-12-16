"""Top-level Kaleidoscope backend package with lazy submodule loading."""

from importlib import import_module
from typing import Any

__all__ = ["scoring", "query_generation", "common"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        module = import_module(f"src.{name}")
        globals()[name] = module
        return module
    raise AttributeError(f"module 'src' has no attribute '{name}'")
