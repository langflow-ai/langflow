from langflow.services import ServiceType, service_manager
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from langflow.services.database.manager import DatabaseManager
    from langflow.services.settings.manager import SettingsManager


def get_settings_manager() -> "SettingsManager":
    return service_manager.get(ServiceType.SETTINGS_MANAGER)


def get_db_manager() -> "DatabaseManager":
    return service_manager.get(ServiceType.DATABASE_MANAGER)


def get_session():
    db_manager = service_manager.get(ServiceType.DATABASE_MANAGER)
    yield from db_manager.get_session()


def get_cache_manager():
    return service_manager.get(ServiceType.CACHE_MANAGER)


def get_session_manager():
    return service_manager.get(ServiceType.SESSION_MANAGER)
