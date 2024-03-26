from contextlib import contextmanager
from typing import TYPE_CHECKING, Generator

from langflow.services import ServiceType, service_manager

if TYPE_CHECKING:
    from sqlmodel import Session

    from langflow.services.cache.service import CacheService
    from langflow.services.chat.service import ChatService
    from langflow.services.credentials.service import CredentialService
    from langflow.services.database.service import DatabaseService
    from langflow.services.monitor.service import MonitorService
    from langflow.services.plugins.service import PluginService
    from langflow.services.session.service import SessionService
    from langflow.services.settings.service import SettingsService
    from langflow.services.socket.service import SocketIOService
    from langflow.services.storage.service import StorageService
    from langflow.services.store.service import StoreService
    from langflow.services.task.service import TaskService


def get_socket_service() -> "SocketIOService":
    return service_manager.get(ServiceType.SOCKETIO_SERVICE)  # type: ignore


def get_storage_service() -> "StorageService":
    return service_manager.get(ServiceType.STORAGE_SERVICE)  # type: ignore


def get_credential_service() -> "CredentialService":
    return service_manager.get(ServiceType.CREDENTIAL_SERVICE)  # type: ignore


def get_plugins_service() -> "PluginService":
    return service_manager.get(ServiceType.PLUGIN_SERVICE)  # type: ignore


def get_settings_service() -> "SettingsService":
    try:
        return service_manager.get(ServiceType.SETTINGS_SERVICE)  # type: ignore
    except ValueError:
        # initialize settings service
        from langflow.services.manager import initialize_settings_service

        initialize_settings_service()
        return service_manager.get(ServiceType.SETTINGS_SERVICE)  # type: ignore


def get_db_service() -> "DatabaseService":
    return service_manager.get(ServiceType.DATABASE_SERVICE)  # type: ignore


def get_session() -> Generator["Session", None, None]:
    db_service = get_db_service()
    yield from db_service.get_session()


@contextmanager
def session_scope():
    """
    Context manager for managing a session scope.

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
    return service_manager.get(ServiceType.CACHE_SERVICE)  # type: ignore


def get_session_service() -> "SessionService":
    return service_manager.get(ServiceType.SESSION_SERVICE)  # type: ignore


def get_monitor_service() -> "MonitorService":
    return service_manager.get(ServiceType.MONITOR_SERVICE)  # type: ignore


def get_task_service() -> "TaskService":
    return service_manager.get(ServiceType.TASK_SERVICE)  # type: ignore


def get_chat_service() -> "ChatService":
    return service_manager.get(ServiceType.CHAT_SERVICE)  # type: ignore


def get_store_service() -> "StoreService":
    return service_manager.get(ServiceType.STORE_SERVICE)  # type: ignore
