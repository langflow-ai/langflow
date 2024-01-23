from typing import TYPE_CHECKING, Generator

from langflow.services import ServiceType, service_manager

if TYPE_CHECKING:
    from langflow.services.cache.service import BaseCacheService
    from langflow.services.chat.service import ChatService
    from langflow.services.credentials.service import CredentialService
    from langflow.services.database.service import DatabaseService
    from langflow.services.plugins.service import PluginService
    from langflow.services.session.service import SessionService
    from langflow.services.settings.service import SettingsService
    from langflow.services.store.service import StoreService
    from langflow.services.task.service import TaskService
    from sqlmodel import Session


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


def get_cache_service() -> "BaseCacheService":
    return service_manager.get(ServiceType.CACHE_SERVICE)  # type: ignore


def get_session_service() -> "SessionService":
    return service_manager.get(ServiceType.SESSION_SERVICE)  # type: ignore


def get_task_service() -> "TaskService":
    return service_manager.get(ServiceType.TASK_SERVICE)  # type: ignore


def get_chat_service() -> "ChatService":
    return service_manager.get(ServiceType.CHAT_SERVICE)  # type: ignore


def get_store_service() -> "StoreService":
    return service_manager.get(ServiceType.STORE_SERVICE)  # type: ignore
