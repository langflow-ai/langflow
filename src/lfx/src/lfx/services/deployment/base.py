"""Deployment service base class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from lfx.services.base import Service

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


class BaseDeploymentService(Service, ABC):
    """Abstract base class for deployment provider services.

    Defines the minimal interface that all deployment service implementations
    must provide, whether minimal (LFX) or full-featured (Langflow).

    Note:
        ``db`` parameters are intentionally typed as ``Any`` to avoid coupling
        deployment adapters to a specific session implementation.
    """

    @abstractmethod
    async def create(
        self,
        *,
        user_id: UUID | str,
        payload: DeploymentCreate,
        db: Any,
    ) -> DeploymentCreateResult:
        """Create a new deployment in the provider."""

    @abstractmethod
    async def list_types(
        self,
        *,
        user_id: UUID | str,
        db: Any,
    ) -> DeploymentListTypesResult:
        """List deployment types supported by the provider."""

    @abstractmethod
    async def list(
        self,
        *,
        user_id: UUID | str,
        params: DeploymentListParams | None = None,
        db: Any,
    ) -> DeploymentListResult:
        """List deployments visible to this adapter."""

    @abstractmethod
    async def get(
        self,
        *,
        user_id: UUID | str,
        deployment_id: UUID | str,
        db: Any,
    ) -> DeploymentGetResult:
        """Return deployment metadata by provider ID."""

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

    @abstractmethod
    async def redeploy(
        self,
        *,
        user_id: UUID | str,
        deployment_id: UUID | str,
        db: Any,
    ) -> RedeployResult:
        """Re-apply current deployment inputs without changing them."""

    @abstractmethod
    async def duplicate(
        self,
        *,
        user_id: UUID | str,
        deployment_id: UUID | str,
        db: Any,
    ) -> DeploymentDuplicateResult:
        """Create a new deployment using the same inputs as the source."""

    @abstractmethod
    async def delete(
        self,
        *,
        user_id: UUID | str,
        deployment_id: UUID | str,
        db: Any,
    ) -> DeploymentDeleteResult:
        """Delete the deployment from the provider."""

    @abstractmethod
    async def get_status(
        self,
        *,
        user_id: UUID | str,
        deployment_id: UUID | str,
        db: Any,
    ) -> DeploymentStatusResult:
        """Return provider-reported health/status for the deployment."""

    @abstractmethod
    async def create_execution(
        self,
        *,
        user_id: UUID | str,
        payload: ExecutionCreate,
        db: Any,
    ) -> ExecutionCreateResult:
        """Run a provider-agnostic deployment execution."""

    @abstractmethod
    async def get_execution(
        self,
        *,
        user_id: UUID | str,
        execution_id: UUID | str,
        db: Any,
    ) -> ExecutionStatusResult:
        """Get provider-agnostic deployment execution state/output."""
