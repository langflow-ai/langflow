from typing import TYPE_CHECKING

from langflow.services.factory import ServiceFactory
from langflow.services.task_orchestration.service import TaskOrchestrationService

if TYPE_CHECKING:
    from langflow.services.database.service import DatabaseService
    from langflow.services.settings.service import SettingsService


class TaskOrchestrationServiceFactory(ServiceFactory):
    def __init__(self):
        super().__init__(TaskOrchestrationService)

    def create(self, settings_service: "SettingsService", database_service: "DatabaseService"):
        return TaskOrchestrationService(settings_service, database_service)
