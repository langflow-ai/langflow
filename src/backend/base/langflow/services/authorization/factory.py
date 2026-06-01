"""Authorization service factory."""

from __future__ import annotations

from typing import TYPE_CHECKING

from langflow.services.factory import ServiceFactory
from langflow.services.schema import ServiceType

if TYPE_CHECKING:
    from lfx.services.authorization.base import BaseAuthorizationService
    from lfx.services.settings.service import SettingsService

    from langflow.services.authorization.service import LangflowAuthorizationService


class AuthorizationServiceFactory(ServiceFactory):
    """Factory that creates the Langflow authorization service."""

    name = ServiceType.AUTHORIZATION_SERVICE.value

    service_class: type[LangflowAuthorizationService]

    def __init__(self) -> None:
        """Bind the factory to the LangflowAuthorizationService implementation."""
        from langflow.services.authorization.service import LangflowAuthorizationService

        super().__init__(LangflowAuthorizationService)

    def create(self, settings_service: SettingsService) -> BaseAuthorizationService:
        """Build a LangflowAuthorizationService using the injected settings service."""
        return self.service_class(settings_service)
