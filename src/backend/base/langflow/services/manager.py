"""Langflow ServiceManager that extends lfx's ServiceManager with enhanced features.

This maintains backward compatibility while using lfx as the foundation.
"""

from __future__ import annotations

# Import the enhanced manager that extends lfx
from langflow.services.enhanced_manager import NoFactoryRegisteredError, ServiceManager

# Create the service manager instance
service_manager = ServiceManager()

# Re-export the classes and exceptions for backward compatibility
__all__ = ["NoFactoryRegisteredError", "ServiceManager", "service_manager"]


def initialize_settings_service() -> None:
    """Initialize the settings manager."""
    from langflow.services.settings import factory as settings_factory

    service_manager.register_factory(settings_factory.SettingsServiceFactory())


def initialize_session_service() -> None:
    """Initialize the session manager."""
    from langflow.services.cache import factory as cache_factory
    from langflow.services.session import factory as session_service_factory

    initialize_settings_service()

    service_manager.register_factory(cache_factory.CacheServiceFactory())

    service_manager.register_factory(session_service_factory.SessionServiceFactory())
