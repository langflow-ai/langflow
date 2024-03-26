from typing import TYPE_CHECKING

from langflow.services.credentials.service import CredentialService
from langflow.services.factory import ServiceFactory

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class CredentialServiceFactory(ServiceFactory):
    def __init__(self):
        super().__init__(CredentialService)

    def create(self, settings_service: "SettingsService"):
        return CredentialService(settings_service)
