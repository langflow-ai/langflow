"""Watsonx Orchestrate deployment adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.services.deployment.base import BaseDeploymentService
from lfx.services.schema import ServiceType

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService


class WatsonxOrchestrateDeploymentService(BaseDeploymentService):
    """Deployment adapter for Watsonx Orchestrate.

    Mapping used by this adapter:
    - deployment -> WXO agent bound to exactly one connection app_id and many tools
    - snapshot -> WXO tool (langflow binding) and immutable once created
    - config -> WXO connection configuration (+ credentials) identified by provider config_id
    """

    name = ServiceType.DEPLOYMENT_SERVICE.value

    def __init__(self, settings_service: SettingsService):
        super().__init__()
        self.settings_service = settings_service
        self.set_ready()

    async def create_deployment(
        self,
        *,
        snapshot_id: str | None = None,
        config_id: str | None = None,
        snapshot: dict | None = None,
        config: dict | None = None,
        deployment_type: str,
    ) -> dict[str, Any]:
        """Create a deployment in Watsonx Orchestrate."""
        raise NotImplementedError

    async def list_deployments(self, deployment_type: str | None = None) -> list[dict[str, Any]]:
        """List deployments from Watsonx Orchestrate."""
        raise NotImplementedError

    async def get_deployment(self, deployment_id: str) -> dict[str, Any]:
        """Get a deployment from Watsonx Orchestrate."""
        raise NotImplementedError

    async def update_deployment(
        self,
        deployment_id: str,
        *,
        snapshot_id: str | None = None,
        config_id: str | None = None,
    ) -> dict[str, Any]:
        """Update a deployment in Watsonx Orchestrate."""
        raise NotImplementedError

    async def redeploy_deployment(self, deployment_id: str) -> dict[str, Any]:
        """Redeploy a deployment from Watsonx Orchestrate."""
        raise NotImplementedError

    async def clone_deployment(self, deployment_id: str) -> dict[str, Any]:
        """Clone a deployment from Watsonx Orchestrate."""
        raise NotImplementedError

    async def delete_deployment(self, deployment_id: str) -> None:
        """Delete a deployment from Watsonx Orchestrate."""
        raise NotImplementedError

    async def get_deployment_health(self, deployment_id: str) -> dict[str, Any]:
        """Get the health of a deployment from Watsonx Orchestrate."""
        raise NotImplementedError

    async def create_deployment_config(self, *, data: dict) -> dict[str, Any]:
        """Create a deployment configuration in Watsonx Orchestrate."""
        raise NotImplementedError

    async def list_deployment_configs(self) -> list[dict[str, Any]]:
        """List deployment configurations from Watsonx Orchestrate."""
        raise NotImplementedError

    async def get_deployment_config(self, config_id: str) -> dict[str, Any]:
        """Get a deployment configuration from Watsonx Orchestrate."""
        raise NotImplementedError

    async def update_deployment_config(
        self,
        config_id: str,
        *,
        data: dict | None = None,
    ) -> dict[str, Any]:
        """Update a deployment configuration in Watsonx Orchestrate."""
        raise NotImplementedError

    async def delete_deployment_config(self, config_id: str) -> None:
        """Delete a deployment configuration from Watsonx Orchestrate."""
        raise NotImplementedError

    async def create_snapshot(self, *, data: dict, snapshot_type: str) -> dict[str, Any]:
        """Create a snapshot/tool in Watsonx Orchestrate."""
        raise NotImplementedError

    async def list_snapshots(self, snapshot_type: str | None = None) -> list[dict[str, Any]]:
        """List snapshots/tools from Watsonx Orchestrate."""
        raise NotImplementedError

    async def get_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        """Get a snapshot/tool from Watsonx Orchestrate."""
        raise NotImplementedError

    async def delete_snapshot(self, snapshot_id: str) -> None:
        """Delete a snapshot/tool from Watsonx Orchestrate."""
        raise NotImplementedError

    async def teardown(self) -> None:
        """Teardown provider-specific resources."""
        raise NotImplementedError



