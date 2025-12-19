"""Service dependency functions for lfx package."""

from __future__ import annotations

from contextlib import asynccontextmanager, suppress
from http import HTTPStatus
from typing import TYPE_CHECKING

from fastapi import HTTPException
from sqlalchemy.exc import InvalidRequestError

from lfx.log.logger import logger
from lfx.services.schema import ServiceType

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncSession

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


def get_db_service() -> DatabaseServiceProtocol:
    """Retrieves the database service instance.

    Returns a NoopDatabaseService if no real database service is available,
    ensuring that session_scope() always has a valid database service to work with.
    """
    from lfx.services.database.service import NoopDatabaseService
    from lfx.services.schema import ServiceType

    db_service = get_service(ServiceType.DATABASE_SERVICE)
    if db_service is None:
        # Return noop database service when no real database service is available
        # This allows lfx to work in standalone mode without requiring database setup
        return NoopDatabaseService()
    return db_service


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


async def get_session():
    msg = "get_session is deprecated, use session_scope instead"
    logger.warning(msg)
    raise NotImplementedError(msg)


async def injectable_session_scope():
    async with session_scope() as session:
        yield session


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for managing an async session scope with auto-commit for write operations.

    This is used with `async with session_scope() as session:` for direct session management.
    It ensures that the session is properly committed if no exceptions occur,
    and rolled back if an exception is raised.
    Use session_scope_readonly() for read-only operations to avoid unnecessary commits and locks.

    Yields:
        AsyncSession: The async session object.

    Raises:
        Exception: If an error occurs during the session scope.
    """
    db_service = get_db_service()
    async with db_service._with_session() as session:  # noqa: SLF001
        try:
            yield session
            await session.commit()
        except Exception as e:
            # Log at appropriate level based on error type
            if isinstance(e, HTTPException):
                if HTTPStatus.BAD_REQUEST.value <= e.status_code < HTTPStatus.INTERNAL_SERVER_ERROR.value:
                    # Client errors (4xx) - log at info level
                    await logger.ainfo(f"Client error during session scope: {e.status_code}: {e.detail}")
                else:
                    # Server errors (5xx) or other - log at error level
                    await logger.aexception("An error occurred during the session scope.", exception=e)
            else:
                # Non-HTTP exceptions - log at error level
                await logger.aexception("An error occurred during the session scope.", exception=e)

            # Only rollback if session is still in a valid state
            if session.is_active:
                with suppress(InvalidRequestError):
                    # Session was already rolled back by SQLAlchemy
                    await session.rollback()
            raise
        # No explicit close needed - _with_session() handles it


async def injectable_session_scope_readonly():
    async with session_scope_readonly() as session:
        yield session


@asynccontextmanager
async def session_scope_readonly() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for managing a read-only async session scope.

    This is used with `async with session_scope_readonly() as session:` for direct session management
    when only reading data. No auto-commit or rollback - the session is simply closed after use.

    Yields:
        AsyncSession: The async session object.
    """
    db_service = get_db_service()
    async with db_service._with_session() as session:  # noqa: SLF001
        yield session
        # No commit - read-only
        # No clean up - client is responsible (plus, read only sessions are not committed)
        # No explicit close needed - _with_session() handles it
