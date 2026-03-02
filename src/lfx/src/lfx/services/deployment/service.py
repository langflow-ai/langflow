"""Deployment service base class."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any

from lfx.services.deployment.base import BaseDeploymentService

if TYPE_CHECKING:
    from uuid import UUID

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
        # for now, return a string. Later, define ServiceType.DEPLOYMENT_SERVICE.
        return "deployment_service"

    @abstractmethod
    async def create(
        self,
        *,
        user_id: UUID | str,
        payload: DeploymentCreate,
        db: Any,
    ) -> DeploymentCreateResult:
        """Create a new deployment in the provider."""
        raise NotImplementedError

    @abstractmethod
    async def list_types(
        self,
        *,
        user_id: UUID | str,
        db: Any,
    ) -> DeploymentListTypesResult:
        """List deployment types supported by the provider."""
        raise NotImplementedError

    @abstractmethod
    async def list(
        self,
        *,
        user_id: UUID | str,
        params: DeploymentListParams | None = None,
        db: Any,
    ) -> DeploymentListResult:
        """List deployments visible to this adapter."""
        raise NotImplementedError

    @abstractmethod
    async def get(
        self,
        *,
        user_id: UUID | str,
        deployment_id: UUID | str,
        db: Any,
    ) -> DeploymentGetResult:
        """Return deployment metadata by provider ID."""
        raise NotImplementedError

    @abstractmethod
    async def update(
        self,
        *,
        user_id: UUID | str,
        deployment_id: UUID | str,
        payload: DeploymentUpdate,
        db: Any,
    ) -> DeploymentUpdateResult:
        """Update deployment inputs and apply changes in the provider."""
        raise NotImplementedError

    @abstractmethod
    async def redeploy(
        self,
        *,
        user_id: UUID | str,
        deployment_id: UUID | str,
        db: Any,
    ) -> RedeployResult:
        """Re-apply current deployment inputs without changing them."""
        raise NotImplementedError

    @abstractmethod
    async def duplicate(
        self,
        *,
        user_id: UUID | str,
        deployment_id: UUID | str,
        db: Any,
    ) -> DeploymentDuplicateResult:
        """Create a new deployment using the same inputs as the source."""
        raise NotImplementedError

    @abstractmethod
    async def delete(
        self,
        *,
        user_id: UUID | str,
        deployment_id: UUID | str,
        db: Any,
    ) -> DeploymentDeleteResult:
        """Delete the deployment from the provider."""
        raise NotImplementedError

    @abstractmethod
    async def get_status(
        self,
        *,
        user_id: UUID | str,
        deployment_id: UUID | str,
        db: Any,
    ) -> DeploymentStatusResult:
        """Return provider-reported health/status for the deployment."""
        raise NotImplementedError

    @abstractmethod
    async def create_execution(
        self,
        *,
        user_id: UUID | str,
        payload: ExecutionCreate,
        db: Any,
    ) -> ExecutionCreateResult:
        """Run a provider-agnostic deployment execution."""
        raise NotImplementedError

    @abstractmethod
    async def get_execution(
        self,
        *,
        user_id: UUID | str,
        execution_id: UUID | str,
        db: Any,
    ) -> ExecutionStatusResult:
        """Get provider-agnostic deployment execution state/output."""
        raise NotImplementedError

    @abstractmethod
    async def teardown(self) -> None:
        """Teardown the deployment service."""
        raise NotImplementedError
