"""Deployment router service factory."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.services.deployment_router.base import BaseDeploymentRouterService  # noqa: TC002
from lfx.services.settings.service import SettingsService  # noqa: TC002

from langflow.services.factory import ServiceFactory

if TYPE_CHECKING:
    from langflow.services.deployment_router.service import DeploymentRouterService


class DeploymentRouterServiceFactory(ServiceFactory):
    """Factory that creates the deployment router service."""

    service_class: type[DeploymentRouterService]

    def __init__(self) -> None:
        from langflow.services.deployment_router.service import DeploymentRouterService

        super().__init__(DeploymentRouterService)

    def create(self, settings_service: SettingsService) -> BaseDeploymentRouterService:
        """Create deployment router service."""
        return self.service_class(settings_service)
