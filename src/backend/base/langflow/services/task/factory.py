from typing import TYPE_CHECKING

from langflow.services.factory import ServiceFactory
from langflow.services.task.service import TaskService

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class TaskServiceFactory(ServiceFactory):
    def __init__(self):
        super().__init__(TaskService)

    def create(self, settings_service: "SettingsService"):
        # Here you would have logic to create and configure a TaskService
        return TaskService(settings_service)
