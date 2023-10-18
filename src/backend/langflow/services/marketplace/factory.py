from typing import TYPE_CHECKING
from langflow.services.marketplace.service import MarketplaceService
from langflow.services.factory import ServiceFactory

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class MarketplaceServiceFactory(ServiceFactory):
    def __init__(self):
        super().__init__(MarketplaceService)

    def create(self, settings_service: "SettingsService"):
        return MarketplaceService(settings_service)
