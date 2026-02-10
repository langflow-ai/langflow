"""Watsonx Orchestrate deployment adapter scaffold."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger
from lfx.services.deployment.base import BaseDeploymentService
from lfx.services.deployment.exceptions import AuthenticationError
from lfx.services.schema import ServiceType

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService


class WatsonxOrchestrateDeploymentService(BaseDeploymentService):
    """Deployment adapter scaffold for Watsonx Orchestrate.

    This class intentionally implements the full adapter surface with explicit
    placeholders so concrete API wiring can be added incrementally.
    """

    name = ServiceType.DEPLOYMENT_SERVICE.value

    def __init__(self, settings_service: SettingsService):
        super().__init__()
        self.settings_service = settings_service
        self.set_ready()

    def _not_implemented(self, operation: str) -> NotImplementedError:
        return NotImplementedError(f"Operation '{operation}' is not implemented for Watsonx Orchestrate yet.")

    async def create_deployment(
        self,
        *,
        snapshot_id: str | None = None,
        config_id: str | None = None,
        snapshot: dict | None = None,
        config: dict | None = None,
        deployment_type: str,
    ) -> dict[str, Any]:
        raise self._not_implemented("create_deployment")

    async def list_deployments(self, deployment_type: str | None = None) -> list[dict[str, Any]]:
        raise self._not_implemented("list_deployments")

    async def get_deployment(self, deployment_id: str) -> dict[str, Any]:
        raise self._not_implemented("get_deployment")

    async def update_deployment(
        self,
        deployment_id: str,
        *,
        snapshot_id: str | None = None,
        config_id: str | None = None,
    ) -> dict[str, Any]:
        raise self._not_implemented("update_deployment")

    async def redeploy_deployment(self, deployment_id: str) -> dict[str, Any]:
        raise self._not_implemented("redeploy_deployment")

    async def clone_deployment(self, deployment_id: str) -> dict[str, Any]:
        raise self._not_implemented("clone_deployment")

    async def delete_deployment(self, deployment_id: str) -> None:
        raise self._not_implemented("delete_deployment")

    async def get_deployment_health(self, deployment_id: str) -> dict[str, Any]:
        raise self._not_implemented("get_deployment_health")

    async def create_deployment_config(self, *, data: dict) -> dict[str, Any]:
        raise self._not_implemented("create_deployment_config")

    async def list_deployment_configs(self) -> list[dict[str, Any]]:
        raise self._not_implemented("list_deployment_configs")

    async def get_deployment_config(self, config_id: str) -> dict[str, Any]:
        raise self._not_implemented("get_deployment_config")

    async def update_deployment_config(
        self,
        config_id: str,
        *,
        data: dict | None = None,
    ) -> dict[str, Any]:
        raise self._not_implemented("update_deployment_config")

    async def delete_deployment_config(self, config_id: str) -> None:
        raise self._not_implemented("delete_deployment_config")

    async def get_provider_config_schema(self) -> dict:
        raise self._not_implemented("get_provider_config_schema")

    async def create_snapshot(self, *, data: dict, snapshot_type: str) -> dict[str, Any]:
        raise self._not_implemented("create_snapshot")

    async def list_snapshots(self, snapshot_type: str | None = None) -> list[dict[str, Any]]:
        raise self._not_implemented("list_snapshots")

    async def get_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        raise self._not_implemented("get_snapshot")

    async def delete_snapshot(self, snapshot_id: str) -> None:
        raise self._not_implemented("delete_snapshot")

    def _get_headers(self) -> dict[str, str]:
        """Get the headers for the Watsonx Orchestrate API."""
        return {"Authorization": f"Bearer {self.authenticator.get_token()}"}

    async def teardown(self) -> None:
        """Teardown provider-specific resources."""

    def _set_authenticator(self, instance_url: str, api_key: str, authorization_url: str) -> None:
        """Set the authenticator for the Watsonx Orchestrate API."""
        self.authenticator = WxOAuthenticator(instance_url, api_key, authorization_url)


class WxOAuthenticator:
    """Authenticator for Watsonx Orchestrate."""
    def __init__(self, instance_url: str, api_key: str, authorization_url: str):
        self.validate_settings(instance_url, api_key, authorization_url)

        self.authenticator = None

        try:
            self.set_authenticator(instance_url, api_key, authorization_url)
        except Exception: # noqa: BLE001 don't expose sensitive data in exception details
            # if we reach this block, authentication failed
            msg = "Authentication failed for the provided watsonx instance. Please provide valid credentials."
            self._handle_invalid_credentials(msg, "invalid_credentials")

        if not self.authenticator:
            # if we reach this block, authentication was not attemped
            # because the instance url did not match any supported type
            msg = "Authentication not implemented for the provided watsonx instance"
            self._handle_invalid_credentials(msg, "unsupported_instance_type")

    def get_token(self) -> str:
        """Authenticate with Watsonx Orchestrate."""
        return self.authenticator.token_manager.get_token()

    @staticmethod
    def _validate_settings(instance_url: str, api_key: str, authorization_url: str) -> None:
        """Validate the settings for Watsonx Orchestrate."""
        if not instance_url:
            msg = "Please provide a Watsonx instance URL"
            raise ValueError(msg)
        if not api_key:
            msg = "Please provide a Watsonx API key"
            raise ValueError(msg)
        if not authorization_url:
            msg = "Please provide a Watsonx Authorization URL"
            raise ValueError(msg)

    @staticmethod
    def _handle_invalid_credentials(message: str, error_code: str) -> None:
        """Handle invalid credentials."""
        logger.error(message)
        raise AuthenticationError(message=message, error_code=error_code)

    def set_authenticator(self, instance_url: str, api_key: str, authorization_url: str) -> None:
        """Set the authenticator for the Watsonx Orchestrate API."""
        if ".cloud.ibm.com" in instance_url:
            from ibm_cloud_sdk_core.authenticators import IAMAuthenticator

            self.authenticator = IAMAuthenticator(apikey=api_key, url=authorization_url)
        elif ".ibm.com" in instance_url:
            from ibm_cloud_sdk_core.authenticators import MCSPAuthenticator

            self.authenticator = MCSPAuthenticator(apikey=api_key, url=authorization_url)

