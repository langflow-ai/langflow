"""Deployment service stub for LFX standalone mode."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any

from lfx.services.deployment.base import BaseDeploymentService
from lfx.services.registry import register_service
from lfx.services.schema import ServiceType

if TYPE_CHECKING:
    from uuid import UUID

    from lfx.services.deployment.schema import (
        ConfigCreateRequest,
        ConfigDeleteRequest,
        ConfigDetail,
        ConfigList,
        ConfigListParams,
        ConfigResponse,
        ConfigUpdateRequest,
        DeploymentCreateRequest,
        DeploymentCreateResponse,
        DeploymentDeleteRequest,
        DeploymentDeleteResponse,
        DeploymentExecutionRequest,
        DeploymentExecutionResponse,
        DeploymentExecutionStatusRequest,
        DeploymentItem,
        DeploymentList,
        DeploymentListParams,
        DeploymentRedeployResponse,
        DeploymentStatus,
        DeploymentType,
        DeploymentUpdateRequest,
        DeploymentUpdateResponse,
    )


@register_service(ServiceType.DEPLOYMENT_SERVICE)
class DeploymentService(BaseDeploymentService):
    """Minimal deployment service implementation for LFX.

    Stub that raises NotImplementedError for all operations.
    LFX does not implement a deployment adapter.
    """

    def __init__(self):
        super().__init__()
        self.set_ready()

    @property
    def name(self) -> str:
        return ServiceType.DEPLOYMENT_SERVICE.value

    # -- Deployment lifecycle --

    @abstractmethod
    async def create(
        self, *, user_id: UUID | str, request: DeploymentCreateRequest, db: Any
    ) -> DeploymentCreateResponse:
        raise NotImplementedError

    @abstractmethod
    async def list(
        self, *, user_id: UUID | str, db: Any, params: DeploymentListParams | None = None
    ) -> DeploymentList:
        raise NotImplementedError

    @abstractmethod
    async def get(self, *, user_id: UUID | str, deployment_id: UUID | str, db: Any) -> DeploymentItem:
        raise NotImplementedError

    @abstractmethod
    async def update(
        self, *, user_id: UUID | str, deployment_id: UUID | str, request: DeploymentUpdateRequest, db: Any
    ) -> DeploymentUpdateResponse:
        raise NotImplementedError

    @abstractmethod
    async def delete(
        self, *, user_id: UUID | str, request: DeploymentDeleteRequest, db: Any
    ) -> DeploymentDeleteResponse:
        raise NotImplementedError

    @abstractmethod
    async def get_status(self, *, user_id: UUID | str, deployment_id: str, db: Any) -> DeploymentStatus:
        raise NotImplementedError

    @abstractmethod
    async def redeploy(
        self, *, user_id: UUID | str, deployment_id: str, db: Any
    ) -> DeploymentRedeployResponse:
        raise NotImplementedError

    @abstractmethod
    async def duplicate(
        self, *, user_id: UUID | str, deployment_id: str, deployment_type: DeploymentType, db: Any
    ) -> DeploymentItem:
        raise NotImplementedError

    @abstractmethod
    async def list_types(self, *, user_id: UUID | str, db: Any) -> list[DeploymentType]:
        raise NotImplementedError

    # -- Executions --

    @abstractmethod
    async def create_execution(
        self, *, user_id: UUID | str, request: DeploymentExecutionRequest, db: Any
    ) -> DeploymentExecutionResponse:
        raise NotImplementedError

    @abstractmethod
    async def get_execution(
        self, *, user_id: UUID | str, request: DeploymentExecutionStatusRequest, db: Any
    ) -> DeploymentExecutionResponse:
        raise NotImplementedError

    # -- Configs --

    @abstractmethod
    async def create_config(
        self, *, user_id: UUID | str, request: ConfigCreateRequest, db: Any
    ) -> ConfigResponse:
        raise NotImplementedError

    @abstractmethod
    async def list_configs(
        self, *, user_id: UUID | str, db: Any, params: ConfigListParams | None = None
    ) -> ConfigList:
        raise NotImplementedError

    @abstractmethod
    async def get_config(self, *, user_id: UUID | str, config_id: str, db: Any) -> ConfigDetail:
        raise NotImplementedError

    @abstractmethod
    async def update_config(
        self, *, user_id: UUID | str, request: ConfigUpdateRequest, db: Any
    ) -> ConfigResponse:
        raise NotImplementedError

    @abstractmethod
    async def delete_config(
        self, *, user_id: UUID | str, request: ConfigDeleteRequest, db: Any
    ) -> None:
        raise NotImplementedError

    # -- Teardown --

    @abstractmethod
    async def teardown(self) -> None:
        raise NotImplementedError
