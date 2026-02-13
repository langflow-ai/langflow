"""Deployment service base class."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any

from lfx.services.base import Service
from lfx.services.deployment.schema import BaseConfigData

if TYPE_CHECKING:
    from uuid import UUID

    from lfx.services.deployment.schema import (
        ConfigUpdate,
        DeploymentCreate,
        DeploymentType,
        DeploymentUpdate,
        SnapshotPayload,
        SnapshotType,
    )


class BaseDeploymentService(Service):
    """Abstract base class for deployment provider services.

    Defines the minimal interface that all deployment service implementations
    must provide, whether minimal (LFX) or full-featured (Langflow).
    """
    @abstractmethod
    def __init__(self):
        """Initialize the deployment service."""
        super().__init__()

    @property
    @abstractmethod
    def name(self) -> str:
        """Service name identifier.

        Returns:
            str: The service name.
        """
        return "deployment_service"

    @abstractmethod
    async def create_deployment(
        self,
        *,
        user_id: UUID | str,
        deployment: DeploymentCreate,
        db: Any,
    ) -> dict[str, Any]:
        """Create a new deployment in the provider."""

    @abstractmethod
    async def list_deployments(
        self,
        *,
        user_id: UUID | str,
        deployment_type: DeploymentType | None = None,
        db: Any,
    ) -> list[dict[str, Any]]:
        """List deployments visible to this adapter."""

    @abstractmethod
    async def get_deployment(
        self,
        *,
        user_id: UUID | str,
        deployment_id: UUID | str,
        db: Any,
    ) -> dict[str, Any]:
        """Return deployment metadata by provider ID."""


    @abstractmethod
    async def update_deployment(
        self,
        *,
        user_id: UUID | str,
        update_data: DeploymentUpdate,
        db: Any,
    ) -> dict[str, Any]:
        """Update deployment inputs and apply changes in the provider."""

    @abstractmethod
    async def redeploy_deployment(
        self,
        *,
        user_id: UUID | str,
        deployment_id: str,
        db: Any,
    ) -> dict[str, Any]:
        """Re-apply current deployment inputs without changing them."""

    @abstractmethod
    async def clone_deployment(
        self,
        *,
        user_id: UUID | str,
        deployment_id: str,
        db: Any,
    ) -> dict[str, Any]:
        """Create a new deployment using the same inputs as the source."""

    @abstractmethod
    async def delete_deployment(
        self,
        *,
        user_id: UUID | str,
        deployment_id: str,
        db: Any,
    ) -> None:
        """Delete the deployment from the provider."""

    @abstractmethod
    async def get_deployment_health(
        self,
        *,
        user_id: UUID | str,
        deployment_id: str,
        db: Any,
    ) -> dict[str, Any]:
        """Return provider-reported health/status for the deployment."""

    @abstractmethod
    async def create_deployment_config(
        self,
        *,
        config: BaseConfigData,
        user_id: UUID | str,
        db: Any,
    ) -> dict[str, Any]:
        """Create a provider-scoped deployment configuration."""

    @abstractmethod
    async def list_deployment_configs(
        self,
        *,
        user_id: UUID | str,
        db: Any,
    ) -> list[dict[str, Any]]:
        """List deployment configurations for this provider."""

    @abstractmethod
    async def get_deployment_config(
        self,
        config_id: str,
        *,
        user_id: UUID | str,
        db: Any,
    ) -> dict[str, Any]:
        """Return deployment configuration by provider ID."""

    @abstractmethod
    async def update_deployment_config(
        self,
        *,
        update_data: ConfigUpdate,
        user_id: UUID | str,
        db: Any,
    ) -> dict[str, Any]:
        """Update a deployment configuration's JSON data."""

    @abstractmethod
    async def delete_deployment_config(
        self,
        config_id: str,
        *,
        user_id: UUID | str,
        db: Any,
    ) -> None:
        """Delete a deployment configuration from the provider."""

    @abstractmethod
    async def create_snapshot(
        self,
        *,
        user_id: UUID | str,
        snapshot: SnapshotPayload,
        db: Any,
    ) -> dict[str, Any]:
        """Create a provider snapshot (deployed or not)."""

    @abstractmethod
    async def list_snapshots(
        self,
        *,
        user_id: UUID | str,
        snapshot_type: SnapshotType | None = None,
        db: Any,
    ) -> list[dict[str, Any]]:
        """List provider snapshots (deployed or not)."""

    @abstractmethod
    async def get_snapshot(
        self,
        *,
        user_id: UUID | str,
        snapshot_id: str,
        db: Any,
    ) -> dict[str, Any]:
        """Return snapshot metadata by provider ID."""\

    @abstractmethod
    async def delete_snapshot(
        self,
        snapshot_id: str,
        *,
        user_id: UUID | str,
        db: Any,
    ) -> None:
        """Delete a provider snapshot."""

    @abstractmethod
    async def teardown(self) -> None:
        """Teardown the deployment service."""
