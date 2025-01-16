from typing_extensions import override

from langflow.services.factory import ServiceFactory
from langflow.services.settings.service import SettingsService
from langflow.services.state.service import InMemoryStateService


class StateServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(InMemoryStateService)

    @override
    def create(self, settings_service: SettingsService):
        return InMemoryStateService(
            settings_service,
        )
