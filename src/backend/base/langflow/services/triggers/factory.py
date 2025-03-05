from typing import TYPE_CHECKING

from langflow.services.factory import ServiceFactory
from langflow.services.triggers.service import TriggerService

if TYPE_CHECKING:
    from langflow.services.task_orchestration.service import TaskOrchestrationService


class TriggerServiceFactory(ServiceFactory):
    """Factory for creating TriggerService instances."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        super().__init__(TriggerService)

    def create(self, task_orchestration_service: "TaskOrchestrationService"):
        """Create a new TriggerService instance.

        Args:
            task_orchestration_service: The task orchestration service to use

        Returns:
            A new TriggerService instance
        """
        return TriggerService(task_orchestration_service)
