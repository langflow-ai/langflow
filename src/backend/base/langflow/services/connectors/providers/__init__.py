"""Connector providers."""

from typing import Any

from langflow.services.connectors.base import BaseConnector

from .google_drive import GoogleDriveConnector

# Registry of available connectors
CONNECTOR_REGISTRY: dict[str, type[BaseConnector]] = {
    "google_drive": GoogleDriveConnector,
}


def get_connector_class(connector_type: str) -> type[BaseConnector] | None:
    """Get connector class by type.

    Args:
        connector_type: Type of connector

    Returns:
        Connector class or None if not found
    """
    return CONNECTOR_REGISTRY.get(connector_type)


def create_connector(connector_type: str, config: dict[str, Any]) -> BaseConnector | None:
    """Create a connector instance.

    Args:
        connector_type: Type of connector
        config: Connector configuration

    Returns:
        Connector instance or None if type not found
    """
    connector_class = get_connector_class(connector_type)
    if connector_class:
        return connector_class(config)
    return None


__all__ = [
    "CONNECTOR_REGISTRY",
    "GoogleDriveConnector",
    "create_connector",
    "get_connector_class",
]
