from contextlib import contextmanager
from typing import TYPE_CHECKING, Generator

from langflow_base.services import ServiceType, service_manager

if TYPE_CHECKING:
    from sqlmodel import Session

    from langflow_base.services.cache.service import BaseCacheService
    from langflow_base.services.chat.service import ChatService
    from langflow_base.services.credentials.service import CredentialService
    from langflow_base.services.database.service import DatabaseService
    from langflow_base.services.session.service import SessionService
    from langflow_base.services.settings.service import SettingsService
    from langflow_base.services.store.service import StoreService
    from langflow_base.services.task.service import TaskService


def get_credential_service() -> "CredentialService":
    return service_manager.get(ServiceType.CREDENTIAL_SERVICE)  # type: ignore


def get_plugins_service() -> "PluginService":
    return service_manager.get(ServiceType.PLUGIN_SERVICE)  # type: ignore


def get_settings_service() -> "SettingsService":
    try:
        return service_manager.get(ServiceType.SETTINGS_SERVICE)  # type: ignore
    except ValueError:
        # initialize settings service
        from langflow_base.services.manager import initialize_settings_service

        initialize_settings_service()
        return service_manager.get(ServiceType.SETTINGS_SERVICE)  # type: ignore


def get_db_service() -> "DatabaseService":
    return service_manager.get(ServiceType.DATABASE_SERVICE)  # type: ignore


def get_session() -> Generator["Session", None, None]:
    db_service = get_db_service()
    yield from db_service.get_session()


@contextmanager
def session_scope():
    session = next(get_session())
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()


def get_cache_service() -> "BaseCacheService":
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
