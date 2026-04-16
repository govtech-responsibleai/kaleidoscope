"""
Unit tests for the extension loader fault isolation.
"""

import sys
from types import ModuleType

import pytest

from src.common.config import get_settings
from src.common.connectors.registry import get_registered_types
from src.extensions import load_extensions


@pytest.fixture
def restore_extensions_setting():
    """Save and restore the kaleidoscope_extensions setting."""
    settings = get_settings()
    original = settings.kaleidoscope_extensions
    yield settings
    settings.kaleidoscope_extensions = original


@pytest.mark.unit
class TestExtensionLoaderFaultIsolation:
    """A broken extension must not prevent app startup."""

    def test_missing_extension_module_does_not_raise(self, restore_extensions_setting):
        """An extension that cannot be imported is logged and skipped."""
        restore_extensions_setting.kaleidoscope_extensions = "definitely_not_a_real_extension"
        types_before = set(get_registered_types())

        load_extensions()

        assert set(get_registered_types()) == types_before

    def test_extension_register_raises_does_not_propagate(self, restore_extensions_setting):
        """An extension whose register() raises is logged and skipped."""
        def _broken_register():
            raise RuntimeError("boom")

        broken_module = ModuleType("src.extensions.broken_register_ext")
        broken_module.register = _broken_register  # type: ignore[attr-defined]
        sys.modules["src.extensions.broken_register_ext"] = broken_module
        try:
            restore_extensions_setting.kaleidoscope_extensions = "broken_register_ext"
            types_before = set(get_registered_types())

            load_extensions()

            assert set(get_registered_types()) == types_before
        finally:
            sys.modules.pop("src.extensions.broken_register_ext", None)

    def test_one_broken_extension_does_not_block_a_working_one(self, restore_extensions_setting):
        """Mixed list: working extension loads even when a sibling is broken."""
        loaded = {"called": False}

        def _good_register():
            loaded["called"] = True

        good_module = ModuleType("src.extensions.good_ext")
        good_module.register = _good_register  # type: ignore[attr-defined]
        sys.modules["src.extensions.good_ext"] = good_module
        try:
            restore_extensions_setting.kaleidoscope_extensions = "missing_ext, good_ext"

            load_extensions()

            assert loaded["called"] is True
        finally:
            sys.modules.pop("src.extensions.good_ext", None)
