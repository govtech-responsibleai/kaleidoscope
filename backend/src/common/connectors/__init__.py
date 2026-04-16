"""
Target connectors for Kaleidoscope.

Usage:
    from src.common.connectors import get_connector

    connector = get_connector(target)
    response = await connector.send_message("What is MediShield?")
    print(response.content)
"""

from src.common.connectors.base import ConnectorResponse, TargetConnector
from src.common.connectors.registry import get_connector

__all__ = ["ConnectorResponse", "TargetConnector", "get_connector"]
