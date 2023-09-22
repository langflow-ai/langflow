from langflow.services import ServiceType, service_service
from typing import TYPE_CHECKING, Generator


if TYPE_CHECKING:
    from langflow.services.database.manager import DatabaseService
    from langflow.services.settings.manager import SettingsService
    from langflow.services.cache.manager import BaseCacheService
    from langflow.services.session.manager import SessionService
    from langflow.services.task.manager import TaskService
    from langflow.services.chat.manager import ChatService
    from sqlmodel import Session


def get_settings_service() -> "SettingsService":
    try:
        return service_service.get(ServiceType.SETTINGS_MANAGER)
    except ValueError:
        # initialize settings service
        from langflow.services.manager import initialize_settings_service

        initialize_settings_service()
        return service_service.get(ServiceType.SETTINGS_MANAGER)


def get_db_service() -> "DatabaseService":
    return service_service.get(ServiceType.DATABASE_MANAGER)


def get_session() -> Generator["Session", None, None]:
    db_service = service_service.get(ServiceType.DATABASE_MANAGER)
    yield from db_service.get_session()


def get_cache_service() -> "BaseCacheService":
    return service_service.get(ServiceType.CACHE_MANAGER)


def get_session_service() -> "SessionService":
    return service_service.get(ServiceType.SESSION_MANAGER)


def get_task_service() -> "TaskService":
    return service_service.get(ServiceType.TASK_MANAGER)


def get_chat_service() -> "ChatService":
    return service_service.get(ServiceType.CHAT_MANAGER)
