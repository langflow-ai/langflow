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
        user_id: IdLike,  # noqa: ARG002
        payload: DeploymentCreate,  # noqa: ARG002
        db: AsyncSession,  # noqa: ARG002
    ) -> DeploymentCreateResult:
        """Create a new deployment in the provider."""
        raise DeploymentNotConfiguredError(method="create")

    async def list_types(
        self,
        *,
        user_id: IdLike,  # noqa: ARG002
        db: AsyncSession,  # noqa: ARG002
    ) -> DeploymentListTypesResult:
        """List deployment types supported by the provider."""
        raise DeploymentNotConfiguredError(method="list_types")

    async def list(
        self,
        *,
        user_id: IdLike,  # noqa: ARG002
        params: DeploymentListParams | None = None,  # noqa: ARG002
        db: AsyncSession,  # noqa: ARG002
    ) -> DeploymentListResult:
        """List deployments visible to this adapter."""
        raise DeploymentNotConfiguredError(method="list")

    async def get(
        self,
        *,
        user_id: IdLike,  # noqa: ARG002
        deployment_id: IdLike,  # noqa: ARG002
        db: AsyncSession,  # noqa: ARG002
    ) -> DeploymentGetResult:
        """Return deployment metadata by provider ID."""
        raise DeploymentNotConfiguredError(method="get")

    async def update(
        self,
        *,
        user_id: IdLike,  # noqa: ARG002
        deployment_id: IdLike,  # noqa: ARG002
        payload: DeploymentUpdate,  # noqa: ARG002
        db: AsyncSession,  # noqa: ARG002
    ) -> DeploymentUpdateResult:
        """Update deployment inputs and apply changes in the provider."""
        raise DeploymentNotConfiguredError(method="update")

    async def redeploy(
        self,
        *,
        user_id: IdLike,  # noqa: ARG002
        deployment_id: IdLike,  # noqa: ARG002
        db: AsyncSession,  # noqa: ARG002
    ) -> RedeployResult:
        """Re-apply current deployment inputs without changing them."""
        raise DeploymentNotConfiguredError(method="redeploy")

    async def duplicate(
        self,
        *,
        user_id: IdLike,  # noqa: ARG002
        deployment_id: IdLike,  # noqa: ARG002
        db: AsyncSession,  # noqa: ARG002
    ) -> DeploymentDuplicateResult:
        """Create a new deployment using the same inputs as the source."""
        raise DeploymentNotConfiguredError(method="duplicate")

    async def delete(
        self,
        *,
        user_id: IdLike,  # noqa: ARG002
        deployment_id: IdLike,  # noqa: ARG002
        db: AsyncSession,  # noqa: ARG002
    ) -> DeploymentDeleteResult:
        """Delete the deployment from the provider."""
        raise DeploymentNotConfiguredError(method="delete")

    async def get_status(
        self,
        *,
        user_id: IdLike,  # noqa: ARG002
        deployment_id: IdLike,  # noqa: ARG002
        db: AsyncSession,  # noqa: ARG002
    ) -> DeploymentStatusResult:
        """Return provider-reported health/status for the deployment."""
        raise DeploymentNotConfiguredError(method="get_status")

    async def create_execution(
        self,
        *,
        user_id: IdLike,  # noqa: ARG002
        payload: ExecutionCreate,  # noqa: ARG002
        db: AsyncSession,  # noqa: ARG002
    ) -> ExecutionCreateResult:
        """Run a provider-agnostic deployment execution."""
        raise DeploymentNotConfiguredError(method="create_execution")

    async def get_execution(
        self,
        *,
        user_id: IdLike,  # noqa: ARG002
        execution_id: IdLike,  # noqa: ARG002
        db: AsyncSession,  # noqa: ARG002
    ) -> ExecutionStatusResult:
        """Get provider-agnostic deployment execution state/output."""
        raise DeploymentNotConfiguredError(method="get_execution")

    async def teardown(self) -> None:
        logger.debug("Deployment service teardown")
