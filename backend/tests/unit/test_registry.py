"""
Unit tests for the connector registry.
"""

import pytest
from unittest.mock import Mock

from src.common.connectors.base import TargetConnector, ConnectorResponse
from src.common.connectors.registry import (
    _registry,
    get_connector,
    get_registered_types,
    register_connector,
    validate_connector_config,
)


class FakeConnector(TargetConnector):
    """Stub connector for registry tests."""

    @classmethod
    def validate_config(cls, config: dict) -> None:
        if not config.get("token"):
            raise ValueError("token is required")

    async def send_message(self, prompt: str) -> ConnectorResponse:
        return ConnectorResponse(content="fake", raw_response={})


@pytest.mark.unit
class TestRegistry:
    """Tests for connector registration and lookup."""

    def test_http_registered_by_default(self):
        """The built-in http connector is registered on import."""
        assert "http" in get_registered_types()

    def test_register_custom_connector(self):
        """register_connector adds a new type."""
        register_connector("fake", FakeConnector)
        assert "fake" in get_registered_types()
        assert _registry["fake"] is FakeConnector
        # Cleanup
        _registry.pop("fake", None)

    def test_get_connector_success(self):
        """get_connector returns a connector instance for a registered type."""
        register_connector("fake", FakeConnector)
        target = Mock()
        target.id = 1
        target.endpoint_type = "fake"
        target.api_endpoint = "https://api.test.com"
        target.endpoint_config = {"token": "abc"}

        connector = get_connector(target)
        assert isinstance(connector, FakeConnector)
        assert connector.endpoint_url == "https://api.test.com"
        # Cleanup
        _registry.pop("fake", None)

    def test_get_connector_unknown_type(self):
        """get_connector raises ValueError for unregistered types."""
        target = Mock()
        target.id = 99
        target.endpoint_type = "nonexistent"
        target.api_endpoint = "https://api.test.com"
        target.endpoint_config = {}

        with pytest.raises(ValueError, match="unsupported endpoint_type 'nonexistent'"):
            get_connector(target)

    def test_get_connector_no_endpoint_type(self):
        """get_connector raises if endpoint_type is missing."""
        target = Mock()
        target.id = 1
        target.endpoint_type = None
        target.api_endpoint = "https://api.test.com"
        target.endpoint_config = {}

        with pytest.raises(ValueError, match="no endpoint_type configured"):
            get_connector(target)

    def test_get_connector_no_api_endpoint(self):
        """get_connector raises if api_endpoint is missing."""
        target = Mock()
        target.id = 1
        target.endpoint_type = "http"
        target.api_endpoint = None
        target.endpoint_config = {}

        with pytest.raises(ValueError, match="no api_endpoint configured"):
            get_connector(target)

    def test_validate_connector_config_delegates(self):
        """validate_connector_config calls the connector's validate_config."""
        register_connector("fake", FakeConnector)

        # Should pass
        validate_connector_config("fake", {"token": "abc"})

        # Should raise
        with pytest.raises(ValueError, match="token is required"):
            validate_connector_config("fake", {})

        # Cleanup
        _registry.pop("fake", None)

    def test_validate_connector_config_unknown_type_noop(self):
        """validate_connector_config is a no-op for unregistered types."""
        validate_connector_config("unknown_type", {"anything": True})
