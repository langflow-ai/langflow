from langflow.services import ServiceType, service_manager
from typing import TYPE_CHECKING, Generator


if TYPE_CHECKING:
    from langflow.services.database.manager import DatabaseManager
    from langflow.services.settings.manager import SettingsManager
    from langflow.services.chat.manager import ChatManager
    from sqlmodel import Session


def get_settings_manager() -> "SettingsManager":
    return service_manager.get(ServiceType.SETTINGS_MANAGER)


def get_db_manager() -> "DatabaseManager":
    return service_manager.get(ServiceType.DATABASE_MANAGER)


def get_session() -> Generator["Session", None, None]:
    db_manager = service_manager.get(ServiceType.DATABASE_MANAGER)
    yield from db_manager.get_session()


def get_chat_manager() -> "ChatManager":
    return service_manager.get(ServiceType.CHAT_MANAGER)
