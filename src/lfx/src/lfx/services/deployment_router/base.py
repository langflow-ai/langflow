"""Deployment router service base class."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from lfx.services.base import Service

if TYPE_CHECKING:
    from lfx.services.deployment.schema import DeploymentProviderId
    from lfx.services.interfaces import DeploymentServiceProtocol


class BaseDeploymentRouterService(Service):
    """Abstract base class for deployment router services.

    Routers resolve provider/account context into a concrete deployment adapter.
    """

    @abstractmethod
    def __init__(self):
        super().__init__()

    @property
    @abstractmethod
    def name(self) -> str:
        return "deployment_router_service"

    @abstractmethod
    def resolve_adapter(
        self,
        *,
        provider_id: DeploymentProviderId,
    ) -> DeploymentServiceProtocol:
        """Resolve and return the deployment adapter for provider_id."""

    @abstractmethod
    def list_adapter_keys(self) -> list[str]:
        """List registered deployment adapter keys."""
