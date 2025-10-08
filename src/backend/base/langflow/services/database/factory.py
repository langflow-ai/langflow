from __future__ import annotations

from typing import TYPE_CHECKING

from langflow.services.database.service import DatabaseService
from langflow.services.factory import ServiceFactory

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService


class DatabaseServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(DatabaseService)

    def create(self, settings_service: SettingsService):
        # Here you would have logic to create and configure a DatabaseService
        if not settings_service.settings.database_url:
            msg = "No database URL provided"
            raise ValueError(msg)
        return DatabaseService(settings_service)
