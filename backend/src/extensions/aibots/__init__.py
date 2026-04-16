"""
AIBots extension for Kaleidoscope.

Enable by setting KALEIDOSCOPE_EXTENSIONS=aibots in the environment.
"""


def register():
    """Register the AIBots connector with the connector registry."""
    from src.common.connectors.registry import register_connector
    from src.extensions.aibots.connector import AibotsConnector

    register_connector("aibots", AibotsConnector)
