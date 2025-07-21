"""Service dependency functions for lfx package."""

from __future__ import annotations

from contextlib import asynccontextmanager


def get_service(service_type, default=None):
    """Retrieves the service instance for the given service type.

    Args:
        service_type (ServiceType): The type of service to retrieve.
        default (ServiceFactory, optional): The default ServiceFactory to use if the service is not found.
            Defaults to None.

    Returns:
        Any: The service instance.
    """
    from lfx.services.manager import service_manager

    return service_manager.get(service_type, default)


def get_db_service():
    """Retrieves the database service instance."""
    from lfx.services.schema import ServiceType

    try:
        return get_service(ServiceType.DATABASE_SERVICE)
    except Exception:  # noqa: BLE001
        # Return a stub if no real service is available
        return _StubDatabaseService()


def get_storage_service():
    """Retrieves the storage service instance."""
    from lfx.services.schema import ServiceType

    try:
        return get_service(ServiceType.STORAGE_SERVICE)
    except Exception:  # noqa: BLE001
        # Return a stub if no real service is available
        return _StubStorageService()


def get_settings_service():
    """Retrieves the settings service instance."""
    from lfx.services.schema import ServiceType

    try:
        return get_service(ServiceType.SETTINGS_SERVICE)
    except Exception:  # noqa: BLE001
        # Return a stub if no real service is available
        return _StubSettingsService()


def get_variable_service():
    """Retrieves the variable service instance."""
    from lfx.services.schema import ServiceType

    try:
        return get_service(ServiceType.VARIABLE_SERVICE)
    except Exception:  # noqa: BLE001
        # Return a stub if no real service is available
        return _StubVariableService()


def get_shared_component_cache_service():
    """Retrieves the shared component cache service instance."""
    from lfx.services.schema import ServiceType

    try:
        return get_service(ServiceType.CACHE_SERVICE)
    except Exception:  # noqa: BLE001
        # Return a stub if no real service is available
        return _StubCacheService()


def get_chat_service():
    """Retrieves the chat service instance."""
    from lfx.services.schema import ServiceType

    try:
        return get_service(ServiceType.CHAT_SERVICE)
    except Exception:  # noqa: BLE001
        # Return a stub if no real service is available
        return _StubChatService()


def get_tracing_service():
    """Retrieves the tracing service instance."""
    from lfx.services.schema import ServiceType

    try:
        return get_service(ServiceType.TRACING_SERVICE)
    except Exception:  # noqa: BLE001
        # Return a stub if no real service is available
        return _StubTracingService()


@asynccontextmanager
async def session_scope():
    """Session scope context manager."""
    # This is a stub implementation
    yield None


# Stub service implementations for when real services aren't available
class _StubDatabaseService:
    def get_session(self):
        return None


class _StubStorageService:
    def save(self, *args, **kwargs):  # noqa: ARG002
        return "stub://saved"

    def get_file(self, *args, **kwargs):  # noqa: ARG002
        return None


class _StubSettingsService:
    def __init__(self):
        self.settings = _StubSettings()

    def get(self, key, default=None):
        return getattr(self.settings, key, default)


class _StubSettings:
    def __init__(self):
        self.vertex_builds_storage_enabled = False
        self.lazy_load_components = False
        self.max_text_length = 2000
        self.max_items_length = 1000


class _StubVariableService:
    def get_variable(self, *args, **kwargs):  # noqa: ARG002
        return None

    def set_variable(self, *args, **kwargs):
        pass


class _StubCacheService:
    def get(self, *args, **kwargs):  # noqa: ARG002
        return None

    def set(self, *args, **kwargs):
        pass


class _StubChatService:
    pass


class _StubTracingService:
    def log(self, *args, **kwargs):
        pass
