from typing import TYPE_CHECKING

from langflow_base.services.factory import ServiceFactory
from langflow_base.services.store.service import StoreService

if TYPE_CHECKING:
    from langflow_base.services.settings.service import SettingsService


class StoreServiceFactory(ServiceFactory):
    def __init__(self):
        super().__init__(StoreService)

    def create(self, settings_service: "SettingsService"):
        return StoreService(settings_service)
