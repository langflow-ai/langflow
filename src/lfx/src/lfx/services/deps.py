"""Service dependency functions for lfx package."""

from __future__ import annotations

import inspect
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from lfx.log.logger import logger
from lfx.services.schema import ServiceType

if TYPE_CHECKING:
    from lfx.services.interfaces import (
        CacheServiceProtocol,
        ChatServiceProtocol,
        DatabaseServiceProtocol,
        SettingsServiceProtocol,
        StorageServiceProtocol,
        TracingServiceProtocol,
        VariableServiceProtocol,
    )


def get_service(service_type: ServiceType, default=None):
    """Retrieves the service instance for the given service type.

    Args:
        service_type: The type of service to retrieve.
        default: The default ServiceFactory to use if the service is not found.

    Returns:
        The service instance or None if not available.
    """
    from lfx.services.manager import get_service_manager

    service_manager = get_service_manager()

    if not service_manager.are_factories_registered():
        # ! This is a workaround to ensure that the service manager is initialized
        # ! Not optimal, but it works for now

        service_manager.register_factories(service_manager.get_factories())

    if ServiceType.SETTINGS_SERVICE not in service_manager.factories:
        from lfx.services.settings.factory import SettingsServiceFactory

        service_manager.register_factory(service_factory=SettingsServiceFactory())

    try:
        return service_manager.get(service_type, default)
    except Exception:  # noqa: BLE001
        return None


def get_db_service() -> DatabaseServiceProtocol | None:
    """Retrieves the database service instance."""
    from lfx.services.schema import ServiceType

    return get_service(ServiceType.DATABASE_SERVICE)


def get_storage_service() -> StorageServiceProtocol | None:
    """Retrieves the storage service instance."""
    from lfx.services.schema import ServiceType

    return get_service(ServiceType.STORAGE_SERVICE)


def get_settings_service() -> SettingsServiceProtocol | None:
    """Retrieves the settings service instance."""
    from lfx.services.schema import ServiceType

    return get_service(ServiceType.SETTINGS_SERVICE)


def get_variable_service() -> VariableServiceProtocol | None:
    """Retrieves the variable service instance."""
    from lfx.services.schema import ServiceType

    return get_service(ServiceType.VARIABLE_SERVICE)


def get_shared_component_cache_service() -> CacheServiceProtocol | None:
    """Retrieves the shared component cache service instance."""
    from lfx.services.shared_component_cache.factory import SharedComponentCacheServiceFactory

    return get_service(ServiceType.SHARED_COMPONENT_CACHE_SERVICE, SharedComponentCacheServiceFactory())


def get_chat_service() -> ChatServiceProtocol | None:
    """Retrieves the chat service instance."""
    from lfx.services.schema import ServiceType

    return get_service(ServiceType.CHAT_SERVICE)


def get_tracing_service() -> TracingServiceProtocol | None:
    """Retrieves the tracing service instance."""
    from lfx.services.schema import ServiceType

    return get_service(ServiceType.TRACING_SERVICE)


@asynccontextmanager
async def session_scope():
    """Session scope context manager.

    Returns a real session if database service is available, otherwise a NoopSession.
    This ensures code can always call session methods without None checking.
    """
    db_service = get_db_service()
    if db_service is None or inspect.isabstract(type(db_service)):
        from lfx.services.session import NoopSession

        yield NoopSession()
        return

    async with db_service.with_session() as session:
        yield session


def get_session():
    """Get database session.

    Returns a session from the database service if available, otherwise NoopSession.
    """
    msg = "get_session is deprecated, use session_scope instead"
    logger.warning(msg)
    raise NotImplementedError(msg)
