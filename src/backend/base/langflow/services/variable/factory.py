from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from langflow.services.factory import ServiceFactory
from langflow.services.variable.service import DatabaseVariableService, VariableService

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class VariableServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(VariableService)

    @override
    def create(self, settings_service: SettingsService):
        # here you would have logic to create and configure a VariableService
        # based on the settings_service

        if settings_service.settings.variable_store == "kubernetes":
            # Keep it here to avoid import errors
            from langflow.services.variable.kubernetes import KubernetesSecretService

            return KubernetesSecretService(settings_service)
        return DatabaseVariableService(settings_service)
