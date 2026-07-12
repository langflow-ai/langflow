from lfx.services.settings.service import SettingsService
from typing_extensions import override

from services.factory import ServiceFactory
from services.task.service import TaskService


class TaskServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(TaskService)

    @override
    def create(self, settings_service: SettingsService):
        return TaskService(settings_service)
