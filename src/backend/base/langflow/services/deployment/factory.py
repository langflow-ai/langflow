"""Deployment service factory.

Builds the Langflow deployment adapter implementation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.services.deployment.base import BaseDeploymentService  # noqa: TC002
from lfx.services.settings.service import SettingsService  # noqa: TC002

from langflow.services.factory import ServiceFactory

if TYPE_CHECKING:
    from langflow.services.deployment.watsonx_orchestrate import WatsonxOrchestrateDeploymentService


class DeploymentServiceFactory(ServiceFactory):
    """Factory that creates a deployment adapter implementation."""

    service_class: type[WatsonxOrchestrateDeploymentService]

    def __init__(self) -> None:
        from langflow.services.deployment.watsonx_orchestrate import WatsonxOrchestrateDeploymentService

        super().__init__(WatsonxOrchestrateDeploymentService)

    def create(self, settings_service: SettingsService) -> BaseDeploymentService:
        """Create deployment adapter service.

        Args:
            settings_service: Settings service instance.

        Returns:
            Deployment adapter implementing `BaseDeploymentService`.
        """
        return self.service_class(settings_service)
