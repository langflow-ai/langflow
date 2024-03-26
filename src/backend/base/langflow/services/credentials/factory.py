from typing import TYPE_CHECKING

from langflow.services.credentials.service import VariableService
from langflow.services.factory import ServiceFactory

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class VariableServiceFactory(ServiceFactory):
    def __init__(self):
        super().__init__(VariableService)

    def create(self, settings_service: "SettingsService"):
        return VariableService(settings_service)
