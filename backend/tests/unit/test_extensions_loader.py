"""
Unit tests for configured extension loading.
"""

import sys
from types import ModuleType

import pytest

from src.common.config import get_settings
from src.extensions import load_extensions


@pytest.fixture
def restore_extensions_setting():
    """Save and restore the kaleidoscope_extensions setting."""
    settings = get_settings()
    original = settings.kaleidoscope_extensions
    yield settings
    settings.kaleidoscope_extensions = original


@pytest.mark.unit
class TestExtensionLoader:
    """Configured extension load failures should block startup."""

    def test_missing_extension_module_raises(self, restore_extensions_setting):
        """A configured extension that cannot be imported should fail startup."""
        restore_extensions_setting.kaleidoscope_extensions = "definitely_not_a_real_extension"
        with pytest.raises(RuntimeError, match="definitely_not_a_real_extension"):
            load_extensions()

    def test_extension_register_raises(self, restore_extensions_setting):
        """A configured extension whose register() fails should block startup."""
        def _broken_register():
            raise RuntimeError("boom")

        broken_module = ModuleType("src.extensions.broken_register_ext")
        broken_module.register = _broken_register  # type: ignore[attr-defined]
        sys.modules["src.extensions.broken_register_ext"] = broken_module
        try:
            restore_extensions_setting.kaleidoscope_extensions = "broken_register_ext"
            with pytest.raises(RuntimeError, match="broken_register_ext"):
                load_extensions()
        finally:
            sys.modules.pop("src.extensions.broken_register_ext", None)

    def test_no_extensions_is_noop(self, restore_extensions_setting):
        """Empty extension setting should not raise."""
        restore_extensions_setting.kaleidoscope_extensions = ""
        load_extensions()

    def test_working_extension_registers(self, restore_extensions_setting):
        """A valid configured extension should still load successfully."""
        loaded = {"called": False}

        def _good_register():
            loaded["called"] = True

        good_module = ModuleType("src.extensions.good_ext")
        good_module.register = _good_register  # type: ignore[attr-defined]
        sys.modules["src.extensions.good_ext"] = good_module
        try:
            restore_extensions_setting.kaleidoscope_extensions = "good_ext"

            load_extensions()

            assert loaded["called"] is True
        finally:
            sys.modules.pop("src.extensions.good_ext", None)
