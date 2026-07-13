from lfx.services.settings.service import SettingsService
from typing_extensions import override

from langflow_services.factory import ServiceFactory
from langflow_services.task.service import TaskService


class TaskServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(TaskService)

    @override
    def create(self, settings_service: SettingsService):
        return TaskService(settings_service)
