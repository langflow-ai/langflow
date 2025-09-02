"""Langflow ServiceManager that extends lfx's ServiceManager with enhanced features.

This maintains backward compatibility while using lfx as the foundation.
"""

from __future__ import annotations

# Import the enhanced manager that extends lfx
from langflow.services.enhanced_manager import NoFactoryRegisteredError, ServiceManager

__all__ = ["NoFactoryRegisteredError", "ServiceManager"]


def initialize_settings_service() -> None:
    """Initialize the settings manager."""
    from lfx.services.manager import get_service_manager
    from lfx.services.settings import factory as settings_factory

    get_service_manager().register_factory(settings_factory.SettingsServiceFactory())


def initialize_session_service() -> None:
    """Initialize the session manager."""
    from lfx.services.manager import get_service_manager

    from langflow.services.cache import factory as cache_factory
    from langflow.services.session import factory as session_service_factory

    initialize_settings_service()

    get_service_manager().register_factory(cache_factory.CacheServiceFactory())

    get_service_manager().register_factory(session_service_factory.SessionServiceFactory())
