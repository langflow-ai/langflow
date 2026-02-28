"""Deployment service base class."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any

from lfx.services.base import Service

if TYPE_CHECKING:
    from uuid import UUID

    from lfx.services.deployment.schema import (
        ArtifactType,
        BaseConfigData,
        ConfigItemResult,
        ConfigListFilterOptions,
        ConfigListResult,
        ConfigResult,
        ConfigUpdate,
        DeploymentCreate,
        DeploymentCreateResult,
        DeploymentDeleteResult,
        DeploymentDetailItem,
        DeploymentExecution,
        DeploymentExecutionResult,
        DeploymentExecutionStatus,
        DeploymentItem,
        DeploymentList,
        DeploymentListParams,
        DeploymentRedeploymentResult,
        DeploymentStatusResult,
        DeploymentType,
        DeploymentUpdate,
        DeploymentUpdateResult,
        SnapshotGetResult,
        SnapshotItemsCreate,
        SnapshotListFilterOptions,
        SnapshotListResult,
        SnapshotResult,
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
    ) -> DeploymentCreateResult:
        """Create a new deployment in the provider."""

    @abstractmethod
    async def list_deployment_types(
        self,
        *,
        user_id: UUID | str,
        db: Any,
    ) -> list[DeploymentType]:
        """List deployment types supported by the provider."""
        ...

    @abstractmethod
    async def list_deployments(
        self,
        *,
        user_id: UUID | str,
        db: Any,
        params: DeploymentListParams | None = None,
    ) -> DeploymentList:
        """List deployments visible to this adapter."""

    @abstractmethod
    async def get_deployment(
        self,
        *,
        user_id: UUID | str,
        deployment_id: UUID | str,
        db: Any,
    ) -> DeploymentDetailItem:
        """Return deployment metadata by provider ID."""

    @abstractmethod
    async def update_deployment(
        self,
        *,
        user_id: UUID | str,
        deployment_id: UUID | str,
        update_data: DeploymentUpdate,
        db: Any,
    ) -> DeploymentUpdateResult:
        """Update deployment inputs and apply changes in the provider."""

    @abstractmethod
    async def redeploy_deployment(
        self,
        *,
        user_id: UUID | str,
        deployment_id: str,
        db: Any,
    ) -> DeploymentRedeploymentResult:
        """Re-apply current deployment inputs without changing them."""

    @abstractmethod
    async def duplicate_deployment(
        self,
        *,
        user_id: UUID | str,
        deployment_id: str,
        deployment_type: DeploymentType,
        db: Any,
    ) -> DeploymentItem:
        """Create a new deployment using the same inputs as the source."""

    @abstractmethod
    async def delete_deployment(
        self,
        *,
        user_id: UUID | str,
        deployment_id: str,
        db: Any,
    ) -> DeploymentDeleteResult:
        """Delete the deployment from the provider."""

    @abstractmethod
    async def get_deployment_status(
        self,
        *,
        user_id: UUID | str,
        deployment_id: str,
        db: Any,
    ) -> DeploymentStatusResult:
        """Return provider-reported health/status for the deployment."""

    @abstractmethod
    async def create_execution(
        self,
        *,
        user_id: UUID | str,
        execution: DeploymentExecution,
        db: Any,
    ) -> DeploymentExecutionResult:
        """Run a provider-agnostic deployment execution."""

    @abstractmethod
    async def get_execution(
        self,
        *,
        user_id: UUID | str,
        execution_status: DeploymentExecutionStatus,
        db: Any,
    ) -> DeploymentExecutionResult:
        """Get provider-agnostic deployment execution state/output."""

    @abstractmethod
    async def create_deployment_config(
        self,
        *,
        config: BaseConfigData,
        user_id: UUID | str,
        db: Any,
    ) -> ConfigResult:
        """Create a provider-scoped deployment configuration."""

    @abstractmethod
    async def list_deployment_configs(
        self,
        *,
        user_id: UUID | str,
        db: Any,
        filter_options: ConfigListFilterOptions | None = None,
    ) -> ConfigListResult:
        """List deployment configurations for this provider."""

    @abstractmethod
    async def get_deployment_config(
        self,
        *,
        user_id: UUID | str,
        config_id: str,
        db: Any,
    ) -> ConfigItemResult:
        """Return deployment configuration by provider ID."""

    @abstractmethod
    async def update_deployment_config(
        self,
        *,
        config_id: str,
        update_data: ConfigUpdate,
        user_id: UUID | str,
        db: Any,
    ) -> ConfigResult:
        """Update a deployment configuration's JSON data."""

    @abstractmethod
    async def delete_deployment_config(
        self,
        *,
        user_id: UUID | str,
        config_id: str,
        db: Any,
    ) -> None:
        """Delete a deployment configuration from the provider."""

    @abstractmethod
    async def create_snapshots(
        self,
        *,
        user_id: UUID | str,
        snapshot_items: SnapshotItemsCreate,
        db: Any,
    ) -> SnapshotResult:
        """Create a provider snapshot (deployed or not)."""

    @abstractmethod
    async def list_snapshots(
        self,
        *,
        user_id: UUID | str,
        artifact_type: ArtifactType | None = None,
        db: Any,
        filter_options: SnapshotListFilterOptions | None = None,
    ) -> SnapshotListResult:
        """List provider snapshots (deployed or not)."""

    @abstractmethod
    async def get_snapshot(
        self,
        *,
        user_id: UUID | str,
        snapshot_id: str,
        db: Any,
    ) -> SnapshotGetResult:
        """Return snapshot payload by provider ID."""

    @abstractmethod
    async def delete_snapshot(
        self,
        *,
        user_id: UUID | str,
        snapshot_id: str,
        db: Any,
    ) -> None:
        """Delete a provider snapshot."""

    @abstractmethod
    async def teardown(self) -> None:
        """Teardown the deployment service."""
