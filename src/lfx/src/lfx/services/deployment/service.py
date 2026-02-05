"""Deployment service base class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from lfx.services.base import Service
from lfx.services.interfaces import DeploymentServiceProtocol


class DeploymentService(Service, DeploymentServiceProtocol, ABC):
    """Abstract base class for deployment provider services."""

    name = "deployment_service"

    @abstractmethod
    async def create_deployment(
        self,
        *,
        user_id: str,
        project_id: str,
        snapshot_id: str,
        config_id: str | None = None,
        tag: str | None = None,
    ) -> dict[str, Any]:
        """Create a new deployment in the provider and track it in Langflow.

        Must create the deployment in the provider and return the resulting
        Langflow-tracked deployment record, including any provider-assigned IDs
        or URLs recorded by Langflow.
        """
        raise NotImplementedError

    @abstractmethod
    async def list_deployments(
        self,
        *,
        flow_id: str | None = None,
        config_id: str | None = None,
        snapshot_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """List Langflow-tracked deployments visible to this adapter.

        Must return Langflow-tracked records (not live provider truth). Optional
        filters constrain results by related flow, config, or snapshot.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_deployment(self, deployment_id: str) -> dict[str, Any]:
        """Return the Langflow-tracked deployment record by ID.

        Must return Langflow-tracked metadata and may diverge from live provider
        state.
        """
        raise NotImplementedError

    @abstractmethod
    async def update_deployment(
        self,
        deployment_id: str,
        *,
        snapshot_id: str | None = None,
        config_id: str | None = None,
        tag: str | None = None,
    ) -> dict[str, Any]:
        """Update deployment inputs and apply changes in the provider.

        Any provided snapshot/config/tag replaces the existing value. Must
        apply the change in the provider and return the updated Langflow-tracked
        deployment record after the provider update is applied.
        """
        raise NotImplementedError

    @abstractmethod
    async def redeploy_deployment(self, deployment_id: str) -> dict[str, Any]:
        """Re-apply current deployment inputs without changing them.

        Intended to trigger a provider-side restart/rebuild using existing
        snapshot/config/tag values. Must return the resulting Langflow-tracked
        deployment record after the provider action completes.
        """
        raise NotImplementedError

    @abstractmethod
    async def clone_deployment(self, deployment_id: str) -> dict[str, Any]:
        """Create a new deployment using the same inputs as the source.

        Uses the source deployment's snapshot/config/tag to create a new
        deployment identity. Must return the new Langflow-tracked deployment
        record.
        """
        raise NotImplementedError

    @abstractmethod
    async def delete_deployment(self, deployment_id: str) -> None:
        """Delete the deployment from the provider and Langflow tracking."""
        raise NotImplementedError

    @abstractmethod
    async def get_deployment_health(self, deployment_id: str) -> dict[str, Any]:
        """Return provider-reported health/status for the deployment.

        Must return provider-truth health/status, not a cached value.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_live_deployment(self, deployment_id: str) -> dict[str, Any]:
        """Fetch live provider-truth state for this deployment.

        Must return authoritative provider state (no Langflow caching), used
        for drift detection against Langflow-tracked state.
        """
        raise NotImplementedError

    @abstractmethod
    async def list_live_deployments(self) -> list[dict[str, Any]]:
        """List live provider-truth deployments visible to this adapter.

        Must return provider-truth data (no Langflow caching).
        """
        raise NotImplementedError

    @abstractmethod
    async def create_deployment_config(
        self,
        *,
        user_id: str,
        data: dict,
    ) -> dict[str, Any]:
        """Create a provider-scoped deployment configuration.

        The data payload is provider-specific JSON config. Must return the
        newly created Langflow-tracked config record.
        """
        raise NotImplementedError

    @abstractmethod
    async def list_deployment_configs(self) -> list[dict[str, Any]]:
        """List Langflow-tracked deployment configurations for this provider."""
        raise NotImplementedError

    @abstractmethod
    async def get_deployment_config(self, config_id: str) -> dict[str, Any]:
        """Return a Langflow-tracked deployment configuration by ID."""
        raise NotImplementedError

    @abstractmethod
    async def update_deployment_config(
        self,
        config_id: str,
        *,
        data: dict | None = None,
    ) -> dict[str, Any]:
        """Update a deployment configuration's JSON data.

        Must return the updated Langflow-tracked config record.
        """
        raise NotImplementedError

    @abstractmethod
    async def clone_deployment_config(self, config_id: str) -> dict[str, Any]:
        """Create a new Langflow-tracked config using the same data as the source."""
        raise NotImplementedError

    @abstractmethod
    async def export_deployment_config(self, config_id: str) -> dict:
        """Return a portable JSON export of the Langflow-tracked configuration."""
        raise NotImplementedError

    @abstractmethod
    async def import_deployment_config(
        self,
        *,
        user_id: str,
        data: dict,
    ) -> dict[str, Any]:
        """Create a Langflow-tracked configuration from an exported JSON payload."""
        raise NotImplementedError

    @abstractmethod
    async def delete_deployment_config(self, config_id: str) -> None:
        """Delete a deployment configuration from Langflow tracking."""
        raise NotImplementedError

    @abstractmethod
    async def get_provider_config_schema(self) -> dict:
        """Return provider-specific configuration schema and defaults.

        Must return provider-truth schema/defaults used by UI or validation.
        """
        raise NotImplementedError


    @abstractmethod
    async def teardown(self) -> None:
        raise NotImplementedError
