from typing import TYPE_CHECKING

from langflow.services.factory import ServiceFactory
from langflow.services.task_orchestration.service import TaskOrchestrationService

if TYPE_CHECKING:
    from langflow.services.database.service import DatabaseService
    from langflow.services.event_bus.service import EventBusService
    from langflow.services.settings.service import SettingsService


class TaskOrchestrationServiceFactory(ServiceFactory):
    def __init__(self):
        super().__init__(TaskOrchestrationService)

    def create(
        self,
        settings_service: "SettingsService",
        database_service: "DatabaseService",
        event_bus_service: "EventBusService",
    ):
        return TaskOrchestrationService(settings_service, database_service, event_bus_service)
