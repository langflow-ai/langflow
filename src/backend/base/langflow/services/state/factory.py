from typing import TYPE_CHECKING

from langflow.services.factory import ServiceFactory
from langflow.services.state.service import InMemoryStateService

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class StateServiceFactory(ServiceFactory):
    def __init__(self):
        super().__init__()

    def create(self, settings_service: SettingsService):
        return InMemoryStateService(
            settings_service,
        )
