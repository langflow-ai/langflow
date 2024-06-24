from typing import TYPE_CHECKING

from langflow.services.factory import ServiceFactory
from langflow.services.variable.service import DatabaseVariableService, VariableService

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class VariableServiceFactory(ServiceFactory):
    def __init__(self):
        super().__init__(VariableService)

    def create(self, settings_service: "SettingsService"):
        # here you would have logic to create and configure a VariableService
        # based on the settings_service

        if settings_service.settings.variable_store == "kubernetes":
            # Keep it here to avoid import errors
            from langflow.services.variable.kubernetes import KubernetesSecretService

            return KubernetesSecretService(settings_service)
        else:
            return DatabaseVariableService(settings_service)
