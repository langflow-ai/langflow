"""Watsonx Orchestrate deployment adapter."""

from __future__ import annotations

import io
import json
import time
import zipfile
from typing import TYPE_CHECKING, Any

import requests
from lfx.log.logger import logger
from lfx.services.deployment.base import BaseDeploymentService
from lfx.services.deployment.exceptions import AuthenticationError, DeploymentError
from lfx.services.schema import ServiceType

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService

HTTP_NOT_FOUND = 404
DOC_CONNECTIONS_OVERVIEW = "https://developer.watson-orchestrate.ibm.com/connections/overview"
DOC_CONNECTIONS_BUILD = "https://developer.watson-orchestrate.ibm.com/connections/build_connections"
DOC_CONNECTIONS_ASSOCIATE = "https://developer.watson-orchestrate.ibm.com/connections/using_connections"
DOC_WXO_BUILD_AGENTS = (
    "https://www.ibm.com/docs/en/watsonx/watson-orchestrate/base?topic=building-customizing-agents"
)
DOC_WXO_BUILD_TOOLS = "https://www.ibm.com/docs/en/watsonx/watson-orchestrate/base?topic=building-tools"
LANGFLOW_CHAT_INPUT_LABEL = "ChatInput"
LANGFLOW_CHAT_OUTPUT_LABEL = "ChatOutput"


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
        self.authenticator: WxOAuthenticator | None = None
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
        self._require_configured_client()
        if snapshot and not snapshot_id:
            created_snapshot = await self.create_snapshot(data=snapshot, snapshot_type=deployment_type)
            snapshot_id = created_snapshot["id"]
        if config and not config_id:
            created_config = await self.create_deployment_config(data=config)
            config_id = created_config["config_id"]
        if not snapshot_id:
            msg = "Deployment requires a snapshot_id or snapshot payload."
            raise DeploymentError(msg, error_code="missing_snapshot")

        if not config_id:
            msg = "Deployment requires a config_id or config payload."
            raise DeploymentError(msg, error_code="missing_config")

        # Source of truth:
        # - Agent-builder docs: DOC_WXO_BUILD_AGENTS
        # - ADK contract cross-check: agent_builder/agents/types.py BaseAgentSpec
        agent_payload = (config or {}).get("agent", {})
        deployment_name = agent_payload.get("name")
        deployment_description = agent_payload.get("description")
        if not deployment_name or not deployment_description:
            msg = "Deployment config must include config.agent.name and config.agent.description."
            raise DeploymentError(msg, error_code="missing_agent_spec")

        config_obj = await self.get_deployment_config(config_id)
        app_id = config_obj["app_id"]
        connection = self._request("GET", "/connections/applications", params={"app_id": app_id})
        connection_id = connection.get("connection_id")
        if not connection_id:
            msg = f"Connection app_id '{app_id}' resolved but no connection_id was returned."
            raise DeploymentError(msg, error_code="connection_not_found")

        # Endpoint reference:
        # - Documentation context: DOC_WXO_BUILD_AGENTS
        # - ADK implementation: client/agents/agent_client.py -> AgentClient.create -> POST /agents
        create_payload = {
            "name": deployment_name,
            "description": deployment_description,
            "tools": [snapshot_id],
        }
        created = self._request("POST", "/agents", json_payload=create_payload)
        deployment_id = created.get("id")
        if not deployment_id:
            msg = "WXO did not return an agent id for deployment creation."
            raise DeploymentError(msg, error_code="deployment_create_failed")

        self._request(
            "PATCH",
            f"/agents/{deployment_id}",
            json_payload={"connection_ids": [connection_id]},
        )
        return await self.get_deployment(deployment_id)

    async def list_deployments(self, deployment_type: str | None = None) -> list[dict[str, Any]]:
        self._require_configured_client()
        agents = self._request("GET", "/agents", params={"include_hidden": "true"})
        if not isinstance(agents, list):
            return []
        deployments: list[dict[str, Any]] = []
        for agent in agents:
            deployment_id = agent.get("id")
            if not deployment_id:
                continue
            deployment = await self.get_deployment(deployment_id)
            if deployment_type and deployment.get("deployment_type") != deployment_type:
                continue
            deployments.append(deployment)
        return deployments

    async def get_deployment(self, deployment_id: str) -> dict[str, Any]:
        self._require_configured_client()
        agent = self._request("GET", f"/agents/{deployment_id}")
        tool_ids = list(agent.get("tools") or [])
        snapshots: list[dict[str, Any]] = []
        app_ids: set[str] = set()

        for tool_id in tool_ids:
            tool = await self.get_snapshot(tool_id)
            snapshots.append(tool)
            for connection_id in tool.get("connection_ids", []):
                app_id = self._resolve_app_id_from_connection_id(connection_id)
                if app_id:
                    app_ids.add(app_id)

        return {
            "id": deployment_id,
            "name": agent.get("name"),
            "description": agent.get("description"),
            "deployment_type": agent.get("deployment_type"),
            "snapshot_ids": [snapshot.get("id") for snapshot in snapshots],
            "snapshots": snapshots,
            "connection_app_ids": sorted(app_ids),
            "agent": {
                "id": agent.get("id"),
                "name": agent.get("name"),
                "description": agent.get("description"),
            },
        }

    async def update_deployment(
        self,
        deployment_id: str,
        *,
        snapshot_id: str | None = None,
        config_id: str | None = None,
    ) -> dict[str, Any]:
        self._require_configured_client()
        if snapshot_id:
            agent = self._request("GET", f"/agents/{deployment_id}")
            existing_tools = list(agent.get("tools") or [])
            if snapshot_id not in existing_tools:
                existing_tools.append(snapshot_id)
                self._request(
                    "PATCH",
                    f"/agents/{deployment_id}",
                    json_payload={"tools": existing_tools},
                )

        if config_id:
            config_obj = await self.get_deployment_config(config_id)
            app_id = config_obj["app_id"]
            connection = self._request("GET", "/connections/applications", params={"app_id": app_id})
            connection_id = connection.get("connection_id")
            if connection_id:
                self._request(
                    "PATCH",
                    f"/agents/{deployment_id}",
                    json_payload={"connection_ids": [connection_id]},
                )

        return await self.get_deployment(deployment_id)

    async def redeploy_deployment(self, deployment_id: str) -> dict[str, Any]:
        self._require_configured_client()
        environments = self._request("GET", f"/agents/{deployment_id}/environment")
        results = []
        for environment in environments or []:
            env_id = environment.get("id") or environment.get("environment_id")
            env_name = (environment.get("name") or "").lower()
            if not env_id or env_name == "draft":
                continue

            self._request(
                "POST",
                f"/agents/{deployment_id}/releases",
                json_payload={"environment_id": env_id},
            )
            status = self._poll_release_status(deployment_id, env_id)
            results.append(
                {
                    "environment_id": env_id,
                    "environment_name": environment.get("name"),
                    "success": status,
                }
            )
        return {"id": deployment_id, "status": "redeployed", "results": results}

    async def clone_deployment(self, deployment_id: str) -> dict[str, Any]:
        self._require_configured_client()
        current = await self.get_deployment(deployment_id)
        source_agent = current["agent"]
        clone_payload = {
            "name": f"{source_agent.get('name')}_clone_{int(time.time())}",
            "description": source_agent.get("description") or "Cloned deployment",
            "tools": list(current.get("snapshot_ids") or []),
        }
        created = self._request("POST", "/agents", json_payload=clone_payload)
        clone_id = created.get("id")
        if not clone_id:
            msg = "WXO did not return a cloned deployment id."
            raise DeploymentError(msg, error_code="clone_failed")

        connection_ids = []
        for app_id in current.get("connection_app_ids", []):
            connection = self._request("GET", "/connections/applications", params={"app_id": app_id})
            connection_id = connection.get("connection_id")
            if connection_id:
                connection_ids.append(connection_id)
        if connection_ids:
            self._request(
                "PATCH",
                f"/agents/{clone_id}",
                json_payload={"connection_ids": connection_ids[:1]},
            )
        return await self.get_deployment(clone_id)

    async def delete_deployment(self, deployment_id: str) -> None:
        self._require_configured_client()
        self._request("DELETE", f"/agents/{deployment_id}")

    async def get_deployment_health(self, deployment_id: str) -> dict[str, Any]:
        self._require_configured_client()
        status = self._request("GET", f"/agents/{deployment_id}/releases/status")
        environments = self._request("GET", f"/agents/{deployment_id}/environment")
        return {
            "id": deployment_id,
            "status": status.get("deployment_status", "unknown"),
            "raw_status": status,
            "environments": environments,
        }

    async def create_deployment_config(self, *, data: dict) -> dict[str, Any]:
        self._require_configured_client()
        app_id = data.get("app_id")
        if not app_id:
            msg = "Deployment config requires 'app_id'."
            raise DeploymentError(msg, error_code="missing_app_id")

        environment = str(data.get("environment") or data.get("env") or "draft").lower()
        preference = data.get("preference") or data.get("type") or "team"
        security_scheme = data.get("security_scheme") or "key_value_creds"
        auth_type = data.get("auth_type")
        sso = bool(data.get("sso", False))
        server_url = data.get("server_url")

        existing_conn = self._request("GET", "/connections/applications", params={"app_id": app_id}, allow_404=True)
        if not existing_conn:
            self._request("POST", "/connections/applications", json_payload={"app_id": app_id})

        configuration_payload = {
            "app_id": app_id,
            "environment": environment,
            "preference": preference,
            "security_scheme": security_scheme,
            "auth_type": auth_type,
            "sso": sso,
            "server_url": server_url,
        }
        configuration_payload = {key: value for key, value in configuration_payload.items() if value is not None}

        current_config = self._request(
            "GET",
            f"/connections/applications/{app_id}/configurations/{environment}",
            allow_404=True,
        )
        if current_config:
            self._request(
                "PATCH",
                f"/connections/applications/{app_id}/configurations/{environment}",
                json_payload=configuration_payload,
            )
        else:
            self._request(
                "POST",
                f"/connections/applications/{app_id}/configurations",
                json_payload=configuration_payload,
            )

        credentials_payload = data.get("credentials_payload")
        credentials_dict = data.get("credentials")
        use_app_credentials = bool(data.get("use_app_credentials", False))
        if credentials_payload is None and credentials_dict is not None:
            payload_key = "app_credentials" if use_app_credentials else "runtime_credentials"
            credentials_payload = {payload_key: credentials_dict}
        if credentials_payload is not None:
            credential_suffix = "credentials" if use_app_credentials else "runtime_credentials"
            credentials_path = f"/connections/applications/{app_id}/configs/{environment}/{credential_suffix}"
            existing_credentials = self._request(
                "GET",
                "/connections/applications/runtime_credentials",
                params={"app_id": app_id, "env": environment},
                allow_404=True,
            )
            method = "PATCH" if existing_credentials else "POST"
            self._request(method, credentials_path, json_payload=credentials_payload)

        refreshed = self._request("GET", f"/connections/applications/{app_id}/configurations/{environment}")
        return self._format_deployment_config(app_id, refreshed, environment)

    async def list_deployment_configs(self) -> list[dict[str, Any]]:
        self._require_configured_client()
        # Endpoint reference:
        # - Documentation context: DOC_CONNECTIONS_BUILD and DOC_CONNECTIONS_OVERVIEW
        # - ADK implementation: client/connections/connections_client.py -> list()
        #   GET /connections/applications?include_details=true
        applications = self._request("GET", "/connections/applications", params={"include_details": "true"})
        entries = applications.get("applications", []) if isinstance(applications, dict) else []
        # Do not fan out into N additional calls; rely on provider list response directly.
        return [self._format_list_config_entry(entry) for entry in entries if isinstance(entry, dict)]

    async def get_deployment_config(self, config_id: str) -> dict[str, Any]:
        self._require_configured_client()
        app_id, environment, config = self._find_config_by_id(config_id)
        if not config:
            msg = f"No deployment config found for config_id '{config_id}'."
            raise DeploymentError(msg, error_code="config_not_found")
        return self._format_deployment_config(app_id, config, environment)

    async def update_deployment_config(
        self,
        config_id: str,
        *,
        data: dict | None = None,
    ) -> dict[str, Any]:
        self._require_configured_client()
        if data is None:
            return await self.get_deployment_config(config_id)

        app_id, environment, config = self._find_config_by_id(config_id)
        if not config:
            msg = f"No deployment config found for config_id '{config_id}'."
            raise DeploymentError(msg, error_code="config_not_found")

        payload = dict(config)
        payload.update({key: value for key, value in data.items() if value is not None})
        self._request(
            "PATCH",
            f"/connections/applications/{app_id}/configurations/{environment}",
            json_payload=payload,
        )
        if "credentials_payload" in data:
            credential_path = f"/connections/applications/{app_id}/configs/{environment}/runtime_credentials"
            self._request("PATCH", credential_path, json_payload=data["credentials_payload"])
        refreshed = self._request("GET", f"/connections/applications/{app_id}/configurations/{environment}")
        return self._format_deployment_config(app_id, refreshed, environment)

    async def delete_deployment_config(self, config_id: str) -> None:
        self._require_configured_client()
        app_id, environment, config = self._find_config_by_id(config_id)
        if not config:
            msg = f"No deployment config found for config_id '{config_id}'."
            raise DeploymentError(msg, error_code="config_not_found")
        self._request(
            "DELETE",
            f"/connections/applications/{app_id}/configurations/{environment}",
            allow_404=True,
        )

    async def get_provider_config_schema(self) -> dict:
        # Do not synthesize a schema that can drift from provider reality.
        # Instead, return authoritative references used by this adapter.
        return {
            "provider": "watsonx_orchestrate",
            "schema_source": {
                "documentation": [
                    DOC_CONNECTIONS_BUILD,
                    DOC_CONNECTIONS_OVERVIEW,
                    DOC_CONNECTIONS_ASSOCIATE,
                    DOC_WXO_BUILD_AGENTS,
                    DOC_WXO_BUILD_TOOLS,
                ],
                "adk_references": {
                    "connection_configuration_type": "ibm_watsonx_orchestrate/agent_builder/connections/types.py",
                    "connections_client_endpoints": "ibm_watsonx_orchestrate/client/connections/connections_client.py",
                    "agent_spec_requirements": "ibm_watsonx_orchestrate/agent_builder/agents/types.py",
                    "tool_client_endpoints": "ibm_watsonx_orchestrate/client/tools/tool_client.py",
                },
            },
            "notes": "Use provider docs/ADK as source of truth for field constraints.",
        }

    async def create_snapshot(self, *, data: dict, snapshot_type: str) -> dict[str, Any]:
        self._require_configured_client()
        flow_definition = data.get("flow_definition") or data.get("snapshot") or data
        if not isinstance(flow_definition, dict):
            msg = "Snapshot payload must include a flow definition object."
            raise DeploymentError(msg, error_code="invalid_snapshot_payload")

        self._validate_langflow_tool_definition(flow_definition)
        tool_name = flow_definition.get("name")

        existing_by_name = self._request("GET", "/tools", params={"names": tool_name}, allow_404=True) or []
        if existing_by_name:
            msg = f"Snapshot '{tool_name}' already exists and snapshots are immutable."
            raise DeploymentError(msg, error_code="snapshot_already_exists")

        connection_app_id = data.get("connection_app_id")
        connections_binding = {}
        if connection_app_id:
            connection = self._request("GET", "/connections/applications", params={"app_id": connection_app_id})
            connection_id = connection.get("connection_id")
            if not connection_id:
                msg = f"No connection found for app_id '{connection_app_id}'."
                raise DeploymentError(msg, error_code="connection_not_found")
            connections_binding[connection_app_id] = connection_id

        tool_spec = {
            "name": tool_name,
            "description": flow_definition.get("description"),
            "permission": "read_only",
            "input_schema": self._langflow_input_schema(flow_definition),
            "output_schema": self._langflow_output_schema(flow_definition),
            "binding": {
                "langflow": {
                    "langflow_id": flow_definition.get("id"),
                    "langflow_version": flow_definition.get("last_tested_version"),
                    "connections": connections_binding or None,
                }
            },
        }
        created = self._request("POST", "/tools", json_payload=tool_spec)
        tool_id = created.get("id")
        if not tool_id:
            msg = "WXO did not return a snapshot/tool id."
            raise DeploymentError(msg, error_code="snapshot_create_failed")

        artifact_bytes = self._build_langflow_artifact(tool_name=tool_name, flow_definition=flow_definition)
        self._upload_tool_artifact(tool_id, artifact_bytes)
        snapshot = await self.get_snapshot(tool_id)
        snapshot["snapshot_type"] = snapshot_type
        return snapshot

    async def list_snapshots(self, snapshot_type: str | None = None) -> list[dict[str, Any]]:
        self._require_configured_client()
        tools = self._request("GET", "/tools")
        snapshots: list[dict[str, Any]] = []
        for tool in tools or []:
            binding = tool.get("binding") or {}
            if "langflow" not in binding:
                continue
            snapshots.append(
                {
                    "id": tool.get("id"),
                    "name": tool.get("name"),
                    "description": tool.get("description"),
                    "snapshot_type": snapshot_type or "langflow_tool",
                    "binding": {"langflow": binding.get("langflow")},
                    "connection_ids": self._extract_connection_ids(tool),
                }
            )
        return snapshots

    async def get_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        self._require_configured_client()
        tool = self._request("GET", f"/tools/{snapshot_id}", allow_404=True)
        if not tool:
            by_name = self._request("GET", "/tools", params={"names": snapshot_id}, allow_404=True) or []
            tool = by_name[0] if by_name else None
        if not tool:
            msg = f"No snapshot/tool found for identifier '{snapshot_id}'."
            raise DeploymentError(msg, error_code="snapshot_not_found")
        binding = tool.get("binding") or {}
        return {
            "id": tool.get("id"),
            "name": tool.get("name"),
            "description": tool.get("description"),
            "snapshot_type": "langflow_tool",
            "binding": {"langflow": binding.get("langflow")},
            "connection_ids": self._extract_connection_ids(tool),
        }

    async def delete_snapshot(self, snapshot_id: str) -> None:
        self._require_configured_client()
        tool = self._request("GET", f"/tools/{snapshot_id}", allow_404=True)
        if not tool:
            by_name = self._request("GET", "/tools", params={"names": snapshot_id}, allow_404=True) or []
            tool = by_name[0] if by_name else None
        if not tool:
            msg = f"No snapshot/tool found for identifier '{snapshot_id}'."
            raise DeploymentError(msg, error_code="snapshot_not_found")
        self._request("DELETE", f"/tools/{tool.get('id')}")

    def _get_headers(self) -> dict[str, str]:
        """Get the headers for the Watsonx Orchestrate API."""
        self._require_configured_client()
        return {"Authorization": f"Bearer {self.authenticator.get_token()}"}

    async def teardown(self) -> None:
        """Teardown provider-specific resources."""
        self.authenticator = None

    def _set_authenticator(self, instance_url: str, api_key: str, authorization_url: str) -> None:
        """Set runtime auth state for Watsonx Orchestrate API calls."""
        self.authenticator = WxOAuthenticator(instance_url, api_key, authorization_url)

    def _require_configured_client(self) -> None:
        if not self.authenticator:
            msg = "WXO adapter is not configured. Call _set_authenticator(...) before using deployment operations."
            raise AuthenticationError(message=msg, error_code="not_configured")

    def _base_url(self) -> str:
        self._require_configured_client()
        # Base path differs by runtime environment.
        # Source of truth:
        # - ADK implementation:
        #   ibm_watsonx_orchestrate/client/connections/connections_client.py
        #   uses /api/v1/orchestrate for local dev URLs and /v1/orchestrate otherwise.
        # - Documentation context:
        #   https://developer.watson-orchestrate.ibm.com/developer_edition/wxOde_overview
        if self._is_local_dev_url(self.authenticator.instance_url):
            return f"{self.authenticator.instance_url}/api/v1/orchestrate"
        return f"{self.authenticator.instance_url}/v1/orchestrate"

    @staticmethod
    def _is_local_dev_url(url: str) -> bool:
        """Mirror ADK local-dev URL detection semantics."""
        return url.startswith(
            (
                "http://localhost",
                "http://127.0.0.1",
                "http://[::1]",
                "http://0.0.0.0",
            )
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_payload: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        allow_404: bool = False,
    ) -> Any:
        url = f"{self._base_url()}{path}"
        response = requests.request(
            method,
            url,
            headers=self._get_headers(),
            params=params,
            json=json_payload,
            files=files,
            timeout=60,
        )
        if allow_404 and response.status_code == HTTP_NOT_FOUND:
            return None
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            message = f"WXO request failed: {method} {path} [{response.status_code}]"
            raise DeploymentError(message=message, error_code="provider_request_failed") from exc
        if not response.text:
            return {}
        try:
            return response.json()
        except ValueError:
            return response.text

    def _poll_release_status(self, deployment_id: str, environment_id: str) -> bool:
        for _ in range(10):
            status = self._request(
                "GET",
                f"/agents/{deployment_id}/releases/status",
                params={"environment_id": environment_id},
                allow_404=True,
            )
            deployment_status = (status or {}).get("deployment_status")
            if deployment_status == "success":
                return True
            if deployment_status == "failed":
                return False
            time.sleep(2)
        return None

    def _find_config_by_id(self, config_id: str) -> tuple[str, str, dict | None]:
        applications = self._request("GET", "/connections/applications", params={"include_details": "true"})
        entries = applications.get("applications", []) if isinstance(applications, dict) else []
        app_ids = {entry.get("app_id") for entry in entries if entry.get("app_id")}
        for app_id in app_ids:
            for environment in ("draft", "live"):
                config = self._request(
                    "GET",
                    f"/connections/applications/{app_id}/configurations/{environment}",
                    allow_404=True,
                )
                if config and config.get("config_id") == config_id:
                    return app_id, environment, config
        return "", "draft", None

    def _resolve_app_id_from_connection_id(self, connection_id: str) -> str | None:
        details = self._request(
            "GET",
            "/connections/applications",
            params={"connection_id": connection_id},
            allow_404=True,
        )
        if not details:
            return None
        return details.get("app_id")

    def _format_deployment_config(self, app_id: str, config: dict[str, Any], environment: str) -> dict[str, Any]:
        runtime_credentials = self._request(
            "GET",
            "/connections/applications/runtime_credentials",
            params={"app_id": app_id, "env": environment},
            allow_404=True,
        )
        return {
            "config_id": config.get("config_id"),
            "app_id": app_id,
            "environment": environment,
            "preference": config.get("preference"),
            "security_scheme": config.get("security_scheme"),
            "auth_type": config.get("auth_type"),
            "server_url": config.get("server_url"),
            "sso": config.get("sso", False),
            "credentials": runtime_credentials,
        }

    @staticmethod
    def _format_list_config_entry(entry: dict[str, Any]) -> dict[str, Any]:
        """Normalize provider list response without extra API calls.

        Source of truth:
        - Documentation context: DOC_CONNECTIONS_OVERVIEW
        - ADK contract cross-check:
          ibm_watsonx_orchestrate/client/connections/connections_client.py -> ListConfigsResponse
        """
        return {
            "config_id": entry.get("config_id"),
            "app_id": entry.get("app_id"),
            "environment": entry.get("environment"),
            "preference": entry.get("preference"),
            "security_scheme": entry.get("security_scheme"),
            "auth_type": entry.get("auth_type"),
            "credentials_entered": entry.get("credentials_entered"),
            "connection_id": entry.get("connection_id"),
        }

    @staticmethod
    def _extract_connection_ids(tool: dict[str, Any]) -> list[str]:
        binding = tool.get("binding") or {}
        langflow = binding.get("langflow") or {}
        connections = langflow.get("connections") or {}
        return [connection_id for connection_id in connections.values() if connection_id]

    @staticmethod
    def _build_langflow_artifact(*, tool_name: str, flow_definition: dict[str, Any]) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_artifact:
            zip_artifact.writestr(f"{tool_name}.json", json.dumps(flow_definition, indent=2))
            zip_artifact.writestr("requirements.txt", "\n")
            zip_artifact.writestr("bundle-format", "2.0.0\n")
        return buffer.getvalue()

    def _upload_tool_artifact(self, tool_id: str, artifact_bytes: bytes) -> dict[str, Any]:
        file_obj = io.BytesIO(artifact_bytes)
        return self._request(
            "POST",
            f"/tools/{tool_id}/upload",
            files={
                "file": (f"{tool_id}.zip", file_obj, "application/zip", {"Expires": "0"}),
            },
        )

    @staticmethod
    def _extract_langflow_nodes(flow_definition: dict[str, Any], node_type: str) -> list[dict[str, Any]]:
        nodes = flow_definition.get("data", {}).get("nodes", [])
        if not isinstance(nodes, list):
            return []
        return [node for node in nodes if node.get("data", {}).get("type") == node_type]

    def _langflow_input_schema(self, flow_definition: dict[str, Any]) -> dict[str, Any]:
        """Build input schema from ChatInput nodes in flow definition.

        Source of truth:
        - Documentation context: DOC_WXO_BUILD_TOOLS
        - ADK contract cross-check:
          ibm_watsonx_orchestrate/agent_builder/tools/langflow_tool.py -> langflow_input_schema()
        """
        chat_input_nodes = self._extract_langflow_nodes(flow_definition, LANGFLOW_CHAT_INPUT_LABEL)
        if len(chat_input_nodes) < 1:
            msg = f"No '{LANGFLOW_CHAT_INPUT_LABEL}' node found in flow definition."
            raise DeploymentError(msg, error_code="invalid_snapshot_payload")
        if len(chat_input_nodes) > 1:
            msg = f"Too many '{LANGFLOW_CHAT_INPUT_LABEL}' nodes found in flow definition."
            raise DeploymentError(msg, error_code="invalid_snapshot_payload")

        description = chat_input_nodes[0].get("data", {}).get("node", {}).get("description", "")
        return {
            "type": "object",
            "properties": {
                "input": {
                    "type": "string",
                    "description": description,
                }
            },
            "required": ["input"],
        }

    def _langflow_output_schema(self, flow_definition: dict[str, Any]) -> dict[str, Any]:
        """Build output schema from ChatOutput nodes in flow definition.

        Source of truth:
        - Documentation context: DOC_WXO_BUILD_TOOLS
        - ADK contract cross-check:
          ibm_watsonx_orchestrate/agent_builder/tools/langflow_tool.py -> langflow_output_schema()
        """
        chat_output_nodes = self._extract_langflow_nodes(flow_definition, LANGFLOW_CHAT_OUTPUT_LABEL)
        if len(chat_output_nodes) < 1:
            msg = f"No '{LANGFLOW_CHAT_OUTPUT_LABEL}' node found in flow definition."
            raise DeploymentError(msg, error_code="invalid_snapshot_payload")
        if len(chat_output_nodes) > 1:
            description = ""
        else:
            description = chat_output_nodes[0].get("data", {}).get("node", {}).get("description", "")
        return {
            "type": "string",
            "description": description,
        }

    def _validate_langflow_tool_definition(self, flow_definition: dict[str, Any]) -> None:
        """Validate required fields for WXO langflow tool import.

        Source of truth:
        - Documentation context: DOC_WXO_BUILD_TOOLS
        - ADK contract cross-check:
          ibm_watsonx_orchestrate/agent_builder/tools/langflow_tool.py -> create_langflow_tool()
        """
        if not flow_definition.get("name"):
            msg = "Flow definition requires a non-empty 'name'."
            raise DeploymentError(msg, error_code="invalid_snapshot_payload")
        if not flow_definition.get("description"):
            msg = "Flow definition requires a non-empty 'description'."
            raise DeploymentError(msg, error_code="invalid_snapshot_payload")
        if not flow_definition.get("last_tested_version"):
            msg = "Flow definition requires 'last_tested_version'."
            raise DeploymentError(msg, error_code="invalid_snapshot_payload")


class WxOAuthenticator:
    """Authenticator for Watsonx Orchestrate."""

    def __init__(self, instance_url: str, api_key: str, authorization_url: str):
        self._validate_settings(instance_url, api_key, authorization_url)

        self.instance_url = instance_url.rstrip("/")
        self.authenticator = None

        try:
            self.set_authenticator(instance_url, api_key, authorization_url)
        except Exception:  # noqa: BLE001 don't expose sensitive data in exception details
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

