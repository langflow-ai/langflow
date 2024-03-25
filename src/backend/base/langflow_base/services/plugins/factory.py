from typing import TYPE_CHECKING

from langflow_base.services.factory import ServiceFactory
from langflow_base.services.plugins.service import PluginService

if TYPE_CHECKING:
    from langflow_base.services.settings.service import SettingsService


class PluginServiceFactory(ServiceFactory):
    def __init__(self):
        super().__init__(PluginService)

    def create(self, settings_service: "SettingsService"):
        service = PluginService(settings_service)
        return service
