from langflow.services import ServiceType, service_manager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langflow.services.settings.manager import SettingsManager


def get_settings_manager() -> "SettingsManager":
    return service_manager.get(ServiceType.SETTINGS_MANAGER)


def get_db_manager():
    return service_manager.get(ServiceType.DATABASE_MANAGER)


def get_session():
    db_manager = service_manager.get(ServiceType.DATABASE_MANAGER)
    yield from db_manager.get_session()
