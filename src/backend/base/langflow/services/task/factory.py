from typing_extensions import override

from langflow.services.factory import ServiceFactory
from langflow.services.settings.service import SettingsService
from langflow.services.task.service import TaskService


class TaskServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(TaskService)

    def create(self, settings_service: SettingsService) -> TaskService:
        """Create a new TaskService instance with the required dependencies."""
        return TaskService(settings_service=settings_service)
