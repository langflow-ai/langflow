"""Deployment service base class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from lfx.services.base import Service

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
    from lfx.services.interfaces import DeploymentServiceProtocol


class BaseDeploymentService(Service, ABC):
    """Abstract base class for deployment provider services.

    Defines the minimal interface that all deployment service implementations
    must provide, whether minimal (LFX) or full-featured (Langflow).

    Note:
        ``db`` parameters are typed as ``AsyncSession`` to align with current
        LFX dependency injection and service protocols.
    """

    @abstractmethod
    async def create(
        self,
        *,
        user_id: IdLike,
        payload: DeploymentCreate,
        db: AsyncSession,
    ) -> DeploymentCreateResult:
        """Create a new deployment in the provider."""

    @abstractmethod
    async def list_types(
        self,
        *,
        user_id: IdLike,
        db: AsyncSession,
    ) -> DeploymentListTypesResult:
        """List deployment types supported by the provider."""

    @abstractmethod
    async def list(
        self,
        *,
        user_id: IdLike,
        params: DeploymentListParams | None = None,
        db: AsyncSession,
    ) -> DeploymentListResult:
        """List deployments visible to this adapter."""

    @abstractmethod
    async def get(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        db: AsyncSession,
    ) -> DeploymentGetResult:
        """Return deployment metadata by provider ID."""

    @abstractmethod
    async def update(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        payload: DeploymentUpdate,
        db: AsyncSession,
    ) -> DeploymentUpdateResult:
        """Update deployment inputs and apply changes in the provider."""

    @abstractmethod
    async def redeploy(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        db: AsyncSession,
    ) -> RedeployResult:
        """Re-apply current deployment inputs without changing them."""

    @abstractmethod
    async def duplicate(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        db: AsyncSession,
    ) -> DeploymentDuplicateResult:
        """Create a new deployment using the same inputs as the source."""

    @abstractmethod
    async def delete(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        db: AsyncSession,
    ) -> DeploymentDeleteResult:
        """Delete the deployment from the provider."""

    @abstractmethod
    async def get_status(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        db: AsyncSession,
    ) -> DeploymentStatusResult:
        """Return provider-reported health/status for the deployment."""

    @abstractmethod
    async def create_execution(
        self,
        *,
        user_id: IdLike,
        payload: ExecutionCreate,
        db: AsyncSession,
    ) -> ExecutionCreateResult:
        """Run a provider-agnostic deployment execution."""

    @abstractmethod
    async def get_execution(
        self,
        *,
        user_id: IdLike,
        execution_id: IdLike,
        db: AsyncSession,
    ) -> ExecutionStatusResult:
        """Get provider-agnostic deployment execution state/output."""


if TYPE_CHECKING:
    # Static assertion: keep ABC API in sync with the consumer protocol.
    _: type[DeploymentServiceProtocol] = BaseDeploymentService
