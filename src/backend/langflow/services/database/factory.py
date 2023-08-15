from typing import TYPE_CHECKING
from langflow.services.database.manager import DatabaseManager
from langflow.services.factory import ServiceFactory

if TYPE_CHECKING:
    from langflow.services.settings.manager import SettingsManager


class DatabaseManagerFactory(ServiceFactory):
    def __init__(self):
        super().__init__(DatabaseManager)

    def create(self, settings_service: "SettingsManager"):
        # Here you would have logic to create and configure a DatabaseManager
        if not settings_service.settings.DATABASE_URL:
            raise ValueError("No database URL provided")
        return DatabaseManager(settings_service.settings.DATABASE_URL)
