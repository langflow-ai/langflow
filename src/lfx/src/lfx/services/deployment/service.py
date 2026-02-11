"""Deployment service base class."""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from lfx.services.deployment.base import BaseDeploymentService
from lfx.services.registry import register_service
from lfx.services.schema import ServiceType


@register_service(ServiceType.DEPLOYMENT_SERVICE)
class DeploymentService(BaseDeploymentService):
    """Minimal deployment service implementation for LFX.

    This is a stub that exposes
    crud operations of deployment
    resources in the deployment adapter,
    such as snapshots and configs.
    LFX does not implement a deployment adapter.
    """

    def __init__(self):
        """Initialize the deployment service."""
        super().__init__()
        self.set_ready()

    @property
    def name(self) -> str:
        """Service name identifier.

        Returns:
            str: The service name.
        """
        return ServiceType.DEPLOYMENT_SERVICE.value

    @abstractmethod
    async def create_deployment(
        self,
        *,
        snapshot_id: str | None = None,
        config_id: str | None = None,
        snapshot: dict | None = None,
        config: dict | None = None,
        deployment_type: str,
    ) -> dict[str, Any]:
        """Create a new deployment in the provider."""
        raise NotImplementedError

    @abstractmethod
    async def list_deployments(
        self,
        deployment_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """List deployments visible to this adapter."""
        raise NotImplementedError

    @abstractmethod
    async def get_deployment(self, deployment_id: str) -> dict[str, Any]:
        """Return deployment metadata by provider ID."""
        raise NotImplementedError

    @abstractmethod
    async def update_deployment(
        self,
        deployment_id: str,
        *,
        snapshot_id: str | None = None,
        config_id: str | None = None,
    ) -> dict[str, Any]:
        """Update deployment inputs and apply changes in the provider."""
        raise NotImplementedError

    @abstractmethod
    async def redeploy_deployment(self, deployment_id: str) -> dict[str, Any]:
        """Re-apply current deployment inputs without changing them."""
        raise NotImplementedError

    @abstractmethod
    async def clone_deployment(self, deployment_id: str) -> dict[str, Any]:
        """Create a new deployment using the same inputs as the source."""
        raise NotImplementedError

    @abstractmethod
    async def delete_deployment(self, deployment_id: str) -> None:
        """Delete the deployment from the provider."""
        raise NotImplementedError

    @abstractmethod
    async def get_deployment_health(self, deployment_id: str) -> dict[str, Any]:
        """Return provider-reported health/status for the deployment."""
        raise NotImplementedError

    @abstractmethod
    async def create_deployment_config(
        self,
        *,
        data: dict,
    ) -> dict[str, Any]:
        """Create a provider-scoped deployment configuration."""
        raise NotImplementedError

    @abstractmethod
    async def list_deployment_configs(self) -> list[dict[str, Any]]:
        """List deployment configurations for this provider."""
        raise NotImplementedError

    @abstractmethod
    async def get_deployment_config(self, config_id: str) -> dict[str, Any]:
        """Return deployment configuration by provider ID."""
        raise NotImplementedError

    @abstractmethod
    async def update_deployment_config(
        self,
        config_id: str,
        *,
        data: dict | None = None,
    ) -> dict[str, Any]:
        """Update a deployment configuration's JSON data."""
        raise NotImplementedError

    @abstractmethod
    async def delete_deployment_config(self, config_id: str) -> None:
        """Delete a deployment configuration from the provider."""
        raise NotImplementedError

    @abstractmethod
    async def create_snapshot(self, *, data: dict, snapshot_type: str) -> dict[str, Any]:
        """Create a provider snapshot (deployed or not)."""
        raise NotImplementedError

    @abstractmethod
    async def list_snapshots(self, snapshot_type: str | None = None) -> list[dict[str, Any]]:
        """List provider snapshots (deployed or not)."""
        raise NotImplementedError

    @abstractmethod
    async def get_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        """Return snapshot metadata by provider ID."""
        raise NotImplementedError


    @abstractmethod
    async def delete_snapshot(self, snapshot_id: str) -> None:
        """Delete a provider snapshot."""
        raise NotImplementedError


    @abstractmethod
    async def teardown(self) -> None:
        """Teardown the deployment service."""
        raise NotImplementedError
