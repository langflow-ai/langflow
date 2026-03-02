"""Deployment service base class."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.log.logger import logger
from lfx.services.deployment.base import BaseDeploymentService

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from lfx.services.deployment.schema import (
        DeploymentCreate,
        DeploymentCreateResult,
        DeploymentDeleteResult,
        DeploymentDuplicateResult,
        DeploymentGetResult,
        DeploymentListParams,
        DeploymentListResult,
        DeploymentListTypesResult,
        DeploymentStatusResult,
        DeploymentUpdate,
        DeploymentUpdateResult,
        ExecutionCreate,
        ExecutionCreateResult,
        ExecutionStatusResult,
        RedeployResult,
    )


# @register_service(ServiceType.DEPLOYMENT_SERVICE)
# do not register this service yet. Only define the
# protocol.
class DeploymentService(BaseDeploymentService):
    """Minimal deployment service implementation for LFX.

    This is a stub that exposes crud operations for deployments.
    LFX does not implement a deployment adapter.
    """

    name = "deployment_service"

    def __init__(self):
        """Initialize the deployment service."""
        super().__init__()
        self.set_ready()

    async def create(
        self,
        *,
        user_id: UUID | str,
        payload: DeploymentCreate,
        db: AsyncSession,
    ) -> DeploymentCreateResult:
        """Create a new deployment in the provider."""
        raise NotImplementedError

    async def list_types(
        self,
        *,
        user_id: UUID | str,
        db: AsyncSession,
    ) -> DeploymentListTypesResult:
        """List deployment types supported by the provider."""
        raise NotImplementedError

    async def list(
        self,
        *,
        user_id: UUID | str,
        params: DeploymentListParams | None = None,
        db: AsyncSession,
    ) -> DeploymentListResult:
        """List deployments visible to this adapter."""
        raise NotImplementedError

    async def get(
        self,
        *,
        user_id: UUID | str,
        deployment_id: UUID | str,
        db: AsyncSession,
    ) -> DeploymentGetResult:
        """Return deployment metadata by provider ID."""
        raise NotImplementedError

    async def update(
        self,
        *,
        user_id: UUID | str,
        deployment_id: UUID | str,
        payload: DeploymentUpdate,
        db: AsyncSession,
    ) -> DeploymentUpdateResult:
        """Update deployment inputs and apply changes in the provider."""
        raise NotImplementedError

    async def redeploy(
        self,
        *,
        user_id: UUID | str,
        deployment_id: UUID | str,
        db: AsyncSession,
    ) -> RedeployResult:
        """Re-apply current deployment inputs without changing them."""
        raise NotImplementedError

    async def duplicate(
        self,
        *,
        user_id: UUID | str,
        deployment_id: UUID | str,
        db: AsyncSession,
    ) -> DeploymentDuplicateResult:
        """Create a new deployment using the same inputs as the source."""
        raise NotImplementedError

    async def delete(
        self,
        *,
        user_id: UUID | str,
        deployment_id: UUID | str,
        db: AsyncSession,
    ) -> DeploymentDeleteResult:
        """Delete the deployment from the provider."""
        raise NotImplementedError

    async def get_status(
        self,
        *,
        user_id: UUID | str,
        deployment_id: UUID | str,
        db: AsyncSession,
    ) -> DeploymentStatusResult:
        """Return provider-reported health/status for the deployment."""
        raise NotImplementedError

    async def create_execution(
        self,
        *,
        user_id: UUID | str,
        payload: ExecutionCreate,
        db: AsyncSession,
    ) -> ExecutionCreateResult:
        """Run a provider-agnostic deployment execution."""
        raise NotImplementedError

    async def get_execution(
        self,
        *,
        user_id: UUID | str,
        execution_id: UUID | str,
        db: AsyncSession,
    ) -> ExecutionStatusResult:
        """Get provider-agnostic deployment execution state/output."""
        raise NotImplementedError

    async def teardown(self) -> None:
        logger.debug("Deployment service teardown")
