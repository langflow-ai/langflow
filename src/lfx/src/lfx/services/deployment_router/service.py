"""Minimal deployment router service implementation for LFX."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.services.deployment_router.base import BaseDeploymentRouterService
from lfx.services.registry import register_service
from lfx.services.schema import ServiceType

if TYPE_CHECKING:
    from uuid import UUID

    from lfx.services.deployment.schema import DeploymentProviderId
    from lfx.services.interfaces import DeploymentServiceProtocol


@register_service(ServiceType.DEPLOYMENT_ROUTER_SERVICE)
class DeploymentRouterService(BaseDeploymentRouterService):
    """Stub deployment router service for LFX standalone mode."""

    def __init__(self):
        super().__init__()
        self.set_ready()

    @property
    def name(self) -> str:
        return ServiceType.DEPLOYMENT_ROUTER_SERVICE.value

    async def resolve_adapter(
        self,
        *,
        provider_id: DeploymentProviderId,
        user_id: UUID | str,
        db: Any,
    ) -> DeploymentServiceProtocol:
        _ = (provider_id, user_id, db)
        raise NotImplementedError

    def list_adapter_keys(self) -> list[str]:
        raise NotImplementedError
