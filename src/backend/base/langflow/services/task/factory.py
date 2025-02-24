from typing_extensions import override

from langflow.services.deps import get_service
from langflow.services.factory import ServiceFactory
from langflow.services.schema import ServiceType
from langflow.services.task.service import TaskService


class TaskServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(TaskService)

    @override
    def create(self):
        # Get the settings service instance
        settings_service = get_service(ServiceType.SETTINGS_SERVICE)
        # Create and return a TaskService instance with the settings service
        return TaskService(settings_service)
