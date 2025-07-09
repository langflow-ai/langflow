from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from langflow.services.factory import ServiceFactory
from langflow.services.oauth.service import OAuthService
from langflow.services.schema import ServiceType

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class OAuthServiceFactory(ServiceFactory):
    dependencies = [ServiceType.SETTINGS_SERVICE]

    def __init__(self) -> None:
        super().__init__(OAuthService)

    @override
    def create(self, settings_service: SettingsService):
        return OAuthService(settings_service)
