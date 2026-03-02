"""Deployment service base class."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.log.logger import logger
from lfx.services.deployment.base import BaseDeploymentService

if TYPE_CHECKING:
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
        IdLike,
        RedeployResult,
    )

_NOT_IMPLEMENTED_MSG = (
    "DeploymentService.{method}() is not implemented. "
    "Register a concrete deployment adapter to enable deployment operations."
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

    async def create(
        self,
        *,
        user_id: IdLike,
        payload: DeploymentCreate,
        db: AsyncSession,
    ) -> DeploymentCreateResult:
        """Create a new deployment in the provider."""
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG.format(method="create"))

    async def list_types(
        self,
        *,
        user_id: IdLike,
        db: AsyncSession,
    ) -> DeploymentListTypesResult:
        """List deployment types supported by the provider."""
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG.format(method="list_types"))

    async def list(
        self,
        *,
        user_id: IdLike,
        params: DeploymentListParams | None = None,
        db: AsyncSession,
    ) -> DeploymentListResult:
        """List deployments visible to this adapter."""
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG.format(method="list"))

    async def get(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        db: AsyncSession,
    ) -> DeploymentGetResult:
        """Return deployment metadata by provider ID."""
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG.format(method="get"))

    async def update(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        payload: DeploymentUpdate,
        db: AsyncSession,
    ) -> DeploymentUpdateResult:
        """Update deployment inputs and apply changes in the provider."""
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG.format(method="update"))

    async def redeploy(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        db: AsyncSession,
    ) -> RedeployResult:
        """Re-apply current deployment inputs without changing them."""
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG.format(method="redeploy"))

    async def duplicate(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        db: AsyncSession,
    ) -> DeploymentDuplicateResult:
        """Create a new deployment using the same inputs as the source."""
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG.format(method="duplicate"))

    async def delete(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        db: AsyncSession,
    ) -> DeploymentDeleteResult:
        """Delete the deployment from the provider."""
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG.format(method="delete"))

    async def get_status(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        db: AsyncSession,
    ) -> DeploymentStatusResult:
        """Return provider-reported health/status for the deployment."""
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG.format(method="get_status"))

    async def create_execution(
        self,
        *,
        user_id: IdLike,
        payload: ExecutionCreate,
        db: AsyncSession,
    ) -> ExecutionCreateResult:
        """Run a provider-agnostic deployment execution."""
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG.format(method="create_execution"))

    async def get_execution(
        self,
        *,
        user_id: IdLike,
        execution_id: IdLike,
        db: AsyncSession,
    ) -> ExecutionStatusResult:
        """Get provider-agnostic deployment execution state/output."""
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG.format(method="get_execution"))

    async def teardown(self) -> None:
        logger.debug("Deployment service teardown")
