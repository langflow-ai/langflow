from contextlib import contextmanager
from typing import TYPE_CHECKING, Generator

from langflow.services import ServiceType, service_manager

if TYPE_CHECKING:
    from sqlmodel import Session

    from langflow.services.cache.service import CacheService
    from langflow.services.chat.service import ChatService
    from langflow.services.database.service import DatabaseService
    from langflow.services.monitor.service import MonitorService
    from langflow.services.plugins.service import PluginService
    from langflow.services.session.service import SessionService
    from langflow.services.settings.service import SettingsService
    from langflow.services.socket.service import SocketIOService
    from langflow.services.state.service import StateService
    from langflow.services.storage.service import StorageService
    from langflow.services.store.service import StoreService
    from langflow.services.task.service import TaskService
    from langflow.services.variable.service import VariableService


def get_service(service_type: ServiceType):
    """
    Retrieves the service instance for the given service type.

    Args:
        service_type (ServiceType): The type of service to retrieve.

    Returns:
        Any: The service instance.

    """
    return service_manager.get(service_type)  # type: ignore


def get_state_service() -> "StateService":
    """
    Retrieves the StateService instance from the service manager.

    Returns:
        The StateService instance.
    """
    return service_manager.get(ServiceType.STATE_SERVICE)  # type: ignore


def get_socket_service() -> "SocketIOService":
    """
    Get the SocketIOService instance from the service manager.

    Returns:
        SocketIOService: The SocketIOService instance.
    """
    return service_manager.get(ServiceType.SOCKETIO_SERVICE)  # type: ignore


def get_storage_service() -> "StorageService":
    """
    Retrieves the storage service instance.

    Returns:
        The storage service instance.
    """
    return service_manager.get(ServiceType.STORAGE_SERVICE)  # type: ignore


def get_variable_service() -> "VariableService":
    """
    Retrieves the VariableService instance from the service manager.

    Returns:
        The VariableService instance.

    """
    return service_manager.get(ServiceType.VARIABLE_SERVICE)  # type: ignore


def get_plugins_service() -> "PluginService":
    """
    Get the PluginService instance from the service manager.

    Returns:
        PluginService: The PluginService instance.
    """
    return service_manager.get(ServiceType.PLUGIN_SERVICE)  # type: ignore


def get_settings_service() -> "SettingsService":
    """
    Retrieves the SettingsService instance.

    If the service is not yet initialized, it will be initialized before returning.

    Returns:
        The SettingsService instance.

    Raises:
        ValueError: If the service cannot be retrieved or initialized.
    """
    try:
        return service_manager.get(ServiceType.SETTINGS_SERVICE)  # type: ignore
    except ValueError:
        # initialize settings service
        from langflow.services.manager import initialize_settings_service

        initialize_settings_service()
        return service_manager.get(ServiceType.SETTINGS_SERVICE)  # type: ignore


def get_db_service() -> "DatabaseService":
    """
    Retrieves the DatabaseService instance from the service manager.

    Returns:
        The DatabaseService instance.

    """
    return service_manager.get(ServiceType.DATABASE_SERVICE)  # type: ignore


def get_session() -> Generator["Session", None, None]:
    """
    Retrieves a session from the database service.

    Yields:
        Session: A session object.

    """
    db_service = get_db_service()
    yield from db_service.get_session()


@contextmanager
def session_scope():
    """
    Context manager for managing a session scope.

    This context manager is used to manage a session scope for database operations.
    It ensures that the session is properly committed if no exceptions occur,
    and rolled back if an exception is raised.

    Yields:
        session: The session object.

    Raises:
        Exception: If an error occurs during the session scope.

    """
    session = next(get_session())
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()


def get_cache_service() -> "CacheService":
    """
    Retrieves the cache service from the service manager.

    Returns:
        The cache service instance.
    """
    return service_manager.get(ServiceType.CACHE_SERVICE)  # type: ignore


def get_session_service() -> "SessionService":
    """
    Retrieves the session service from the service manager.

    Returns:
        The session service instance.
    """
    return service_manager.get(ServiceType.SESSION_SERVICE)  # type: ignore


def get_monitor_service() -> "MonitorService":
    """
    Retrieves the MonitorService instance from the service manager.

    Returns:
        MonitorService: The MonitorService instance.
    """
    return service_manager.get(ServiceType.MONITOR_SERVICE)  # type: ignore


def get_task_service() -> "TaskService":
    """
    Retrieves the TaskService instance from the service manager.

    Returns:
        The TaskService instance.

    """
    return service_manager.get(ServiceType.TASK_SERVICE)  # type: ignore


def get_chat_service() -> "ChatService":
    """
    Get the chat service instance.

    Returns:
        ChatService: The chat service instance.
    """
    return service_manager.get(ServiceType.CHAT_SERVICE)  # type: ignore


def get_store_service() -> "StoreService":
    """
    Retrieves the StoreService instance from the service manager.

    Returns:
        StoreService: The StoreService instance.
    """
    return service_manager.get(ServiceType.STORE_SERVICE)  # type: ignore
