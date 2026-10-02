"""Factory for the trigger persistence service."""

from typing_extensions import override

from langflow.services.factory import ServiceFactory
from langflow.services.schema import ServiceType
from langflow.services.triggers.service import TriggerService


class TriggerServiceFactory(ServiceFactory):
    name = ServiceType.TRIGGER_SERVICE.value

    def __init__(self) -> None:
        super().__init__(TriggerService)

    @override
    def create(self) -> TriggerService:
        return self.service_class()
