from langflow.services.task.manager import TaskService
from langflow.services.factory import ServiceFactory


class TaskServiceFactory(ServiceFactory):
    def __init__(self):
        super().__init__(TaskService)

    def create(self):
        # Here you would have logic to create and configure a TaskService
        return TaskService()
