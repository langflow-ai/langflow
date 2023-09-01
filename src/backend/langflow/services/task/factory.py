from langflow.services.task.manager import TaskManager
from langflow.services.factory import ServiceFactory


class TaskManagerFactory(ServiceFactory):
    def __init__(self):
        super().__init__(TaskManager)

    def create(self):
        # Here you would have logic to create and configure a TaskManager
        return TaskManager()
