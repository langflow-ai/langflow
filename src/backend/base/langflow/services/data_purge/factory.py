"""Factory for data purge service."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing_extensions import override

from langflow.services.factory import ServiceFactory
from langflow.services.data_purge.service import DataPurgeService

if TYPE_CHECKING:
    from langflow.services.database.service import DatabaseService
    from langflow.services.settings.service import SettingsService


class DataPurgeServiceFactory(ServiceFactory):
    def __init__(self):
        super().__init__(DataPurgeService)

    @override
    def create(self, database_service: DatabaseService, settings_service: SettingsService):
        return DataPurgeService(database_service, settings_service)