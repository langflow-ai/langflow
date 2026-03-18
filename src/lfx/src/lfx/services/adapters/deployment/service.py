# ruff: noqa: ARG002
"""Default (no-op) deployment service implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.log.logger import logger
from lfx.services.adapters.deployment.base import BaseDeploymentService
from lfx.services.adapters.deployment.exceptions import DeploymentNotConfiguredError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from lfx.services.adapters.deployment.schema import (
        ConfigListParams,
        ConfigListResult,
        DeploymentCreate,
        DeploymentCreateResult,
        DeploymentDeleteResult,
        DeploymentDuplicateResult,
        DeploymentGetResult,
        DeploymentListParams,
        DeploymentListResult,
        DeploymentListTypesResult,
        DeploymentStatusResult,
        DeploymentType,
        DeploymentUpdate,
        DeploymentUpdateResult,
        ExecutionCreate,
        ExecutionCreateResult,
        ExecutionStatusResult,
        IdLike,
        RedeployResult,
        SnapshotListParams,
        SnapshotListResult,
    )


# No adapter key registered -- this stub exists so the protocol and ABC are
# testable.  Concrete adapters (e.g. in Langflow) subclass BaseDeploymentService
# and register under meaningful keys like "local" or "remote".
class DeploymentService(BaseDeploymentService):
    """Null deployment service for LFX.

    All operations raise :class:`DeploymentNotConfiguredError` because LFX does
    not ship a deployment adapter.  Concrete adapters (e.g. in Langflow) should
    subclass :class:`BaseDeploymentService` to provide real behaviour.
    """

    name = "deployment_service"

    async def create(
        self,
        *,
        user_id: IdLike,
        payload: DeploymentCreate,
        db: AsyncSession,
    ) -> DeploymentCreateResult:
        """Create a new deployment in the provider."""
        raise DeploymentNotConfiguredError(method="create")

    async def list_types(
        self,
        *,
        user_id: IdLike,
        db: AsyncSession,
    ) -> DeploymentListTypesResult:
        """List deployment types supported by the provider."""
        raise DeploymentNotConfiguredError(method="list_types")

    async def list(
        self,
        *,
        user_id: IdLike,
        params: DeploymentListParams | None = None,
        db: AsyncSession,
    ) -> DeploymentListResult:
        """List deployments visible to this adapter."""
        raise DeploymentNotConfiguredError(method="list")

    async def get(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        deployment_type: DeploymentType | None = None,
        db: AsyncSession,
    ) -> DeploymentGetResult:
        """Return deployment metadata by provider ID."""
        raise DeploymentNotConfiguredError(method="get")

    async def update(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        deployment_type: DeploymentType | None = None,
        payload: DeploymentUpdate,
        db: AsyncSession,
    ) -> DeploymentUpdateResult:
        """Update deployment inputs and apply changes in the provider."""
        raise DeploymentNotConfiguredError(method="update")

    async def redeploy(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        deployment_type: DeploymentType | None = None,
        db: AsyncSession,
    ) -> RedeployResult:
        """Re-apply current deployment inputs without changing them."""
        raise DeploymentNotConfiguredError(method="redeploy")

    async def duplicate(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        deployment_type: DeploymentType | None = None,
        db: AsyncSession,
    ) -> DeploymentDuplicateResult:
        """Create a new deployment using the same inputs as the source."""
        raise DeploymentNotConfiguredError(method="duplicate")

    async def delete(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        deployment_type: DeploymentType | None = None,
        db: AsyncSession,
    ) -> DeploymentDeleteResult:
        """Delete the deployment from the provider."""
        raise DeploymentNotConfiguredError(method="delete")

    async def get_status(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        deployment_type: DeploymentType | None = None,
        db: AsyncSession,
    ) -> DeploymentStatusResult:
        """Return provider-reported health/status for the deployment."""
        raise DeploymentNotConfiguredError(method="get_status")

    async def create_execution(
        self,
        *,
        user_id: IdLike,
        payload: ExecutionCreate,
        db: AsyncSession,
    ) -> ExecutionCreateResult:
        """Run a provider-agnostic deployment execution."""
        raise DeploymentNotConfiguredError(method="create_execution")

    async def get_execution(
        self,
        *,
        user_id: IdLike,
        execution_id: IdLike,
        deployment_type: DeploymentType | None = None,
        db: AsyncSession,
    ) -> ExecutionStatusResult:
        """Get provider-agnostic deployment execution state/output."""
        raise DeploymentNotConfiguredError(method="get_execution")

    async def list_configs(
        self,
        *,
        user_id: IdLike,
        params: ConfigListParams | None = None,
        db: AsyncSession,
    ) -> ConfigListResult:
        """List configs visible to this adapter."""
        raise DeploymentNotConfiguredError(method="list_configs")

    async def list_snapshots(
        self,
        *,
        user_id: IdLike,
        params: SnapshotListParams | None = None,
        db: AsyncSession,
    ) -> SnapshotListResult:
        """List snapshots visible to this adapter."""
        raise DeploymentNotConfiguredError(method="list_snapshots")

    async def teardown(self) -> None:
        logger.debug("Deployment service teardown")
