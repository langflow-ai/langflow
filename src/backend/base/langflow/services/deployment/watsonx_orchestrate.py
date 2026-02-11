"""Watsonx Orchestrate deployment adapter."""

from __future__ import annotations

import io
import json
import zipfile
from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ibm_watsonx_orchestrate_clients.agents.agent_client import AgentClient
from ibm_watsonx_orchestrate_clients.common.client import Client
from ibm_watsonx_orchestrate_clients.common.credentials import Credentials
from ibm_watsonx_orchestrate_clients.connections.connections_client import ConnectionsClient
from ibm_watsonx_orchestrate_clients.tools.tool_client import ToolClient
from ibm_watsonx_orchestrate_core.types.connections import (
    ConnectionConfiguration,
    ConnectionEnvironment,
    ConnectionPreference,
    ConnectionSecurityScheme,
    KeyValueConnectionCredentials,
)
from ibm_watsonx_orchestrate_core.types.tools.langflow_tool import create_langflow_tool
from lfx.services.deployment.base import BaseDeploymentService
from lfx.services.schema import ServiceType

from langflow.services.deps import get_variable_service

if TYPE_CHECKING:
    from uuid import UUID

    from lfx.services.settings.service import SettingsService


DEFAULT_WXO_INSTANCE_URL_VARIABLE = "WXO_INSTANCE_URL"
DEFAULT_WXO_API_KEY_VARIABLE = "WXO_API_KEY"
DEFAULT_WXO_AWS_IAM_URL_VARIABLE = "WXO_AWS_IAM_URL"
DEFAULT_WXO_AUTH_TYPE_VARIABLE = "WXO_AUTH_TYPE"
DEFAULT_WXO_AUTH_TYPE = "mcsp" # TODO: derive the auth type from the wxo instance url and/or iam url

DEFAULT_LANGFLOW_RUNNER_MODULES = {"lfx", "lfx-nightly"}
# TODO: use src/lfx/src/lfx/custom/dependency_analyzer.py instead to get the lfx version.
DEFAULT_LANGFLOW_TOOL_REQUIREMENTS = ["lfx==0.3.0"]
DEFAULT_ADAPTER_SNAPSHOT_TYPE = "langflow"


@dataclass(slots=True)
class _ProviderClients:
    tool_client: ToolClient
    connections_client: ConnectionsClient
    agent_client: AgentClient


class WatsonxOrchestrateDeploymentService(BaseDeploymentService):
    """Deployment adapter for Watsonx Orchestrate.

    Mapping used by this adapter:
    - deployment -> WXO agent bound to exactly one connection app_id and many tools
    - snapshot -> WXO tool (langflow binding) and immutable once created
    - config -> WXO connection configuration (+ credentials), keyed by app_id
    """

    name = ServiceType.DEPLOYMENT_SERVICE.value

    def __init__(self, settings_service: SettingsService):
        super().__init__()
        self.settings_service = settings_service
        # Cache provider clients per user to avoid re-instantiation on every method call.
        self._provider_clients_cache: dict[str, _ProviderClients] = {}
        self.set_ready()

    async def create_deployment(
        self,
        *,
        snapshot_id: str | None = None,
        config_id: str | None = None,
        snapshot: dict | None = None,
        config: dict | None = None,
        deployment_type: str,
        user_id: UUID | str,
        db: Any,
    ) -> dict[str, Any]:
        """Create a deployment (agent) in Watsonx Orchestrate."""
        self._validate_exclusive_inputs(
            resource_name="snapshot",
            resource_id=snapshot_id,
            resource_object=snapshot,
        )
        self._validate_exclusive_inputs(
            resource_name="config",
            resource_id=config_id,
            resource_object=config,
        )

        clients = await self._get_provider_clients(user_id=user_id, db=db, data=config or snapshot)
        app_id = await self._resolve_config_id_for_deployment(
            config_id=config_id,
            config=config,
            user_id=user_id,
            db=db,
        )
        tool_ids = await self._resolve_snapshot_ids_for_deployment(
            snapshot_id=snapshot_id,
            snapshot=snapshot,
            config_id=app_id,
            user_id=user_id,
            db=db,
        )
        if not tool_ids:
            msg = "create_deployment requires at least one snapshot_id/tool id."
            raise ValueError(msg)

        connection = self._ensure_connection_exists(clients.connections_client, app_id=app_id)
        self._validate_live_connection(clients.connections_client, app_id=app_id)
        connection_id = connection.connection_id
        payload = self._build_agent_payload(
            deployment_type=deployment_type,
            app_id=app_id,
            connection_id=connection_id,
            tool_ids=tool_ids,
            source_data=snapshot or {},
        )

        created = clients.agent_client.create(payload)
        if not created.id:
            msg = "WXO did not return an agent id."
            raise ValueError(msg)

        clients.agent_client.connect_connections(created.id, [connection_id])
        return await self.get_deployment(created.id, user_id=user_id, db=db)

    async def list_deployments(
        self,
        deployment_type: str | None = None,
        *,
        user_id: UUID | str,
        db: Any,
    ) -> list[dict[str, Any]]:
        """List deployments (agents) from Watsonx Orchestrate."""
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        data = clients.agent_client.get()
        if not isinstance(data, list):
            data = [data]

        deployments = [self._map_agent_to_deployment(agent) for agent in data]
        if deployment_type is None:
            return deployments
        return [deployment for deployment in deployments if deployment.get("deployment_type") == deployment_type]

    async def get_deployment(
        self,
        deployment_id: str,
        *,
        user_id: UUID | str,
        db: Any,
    ) -> dict[str, Any]:
        """Get a deployment (agent) from Watsonx Orchestrate."""
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        agent = clients.agent_client.get_draft_by_id(deployment_id)
        if not agent:
            msg = f"Deployment '{deployment_id}' not found."
            raise ValueError(msg)
        return self._map_agent_to_deployment(agent)

    async def update_deployment(
        self,
        deployment_id: str,
        *,
        snapshot_id: str | None = None,
        config_id: str | None = None,
        user_id: UUID | str,
        db: Any,
    ) -> dict[str, Any]:
        """Update deployment metadata and/or connection binding."""
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        current = clients.agent_client.get_draft_by_id(deployment_id)
        if not current:
            msg = f"Deployment '{deployment_id}' not found."
            raise ValueError(msg)

        update_payload: dict[str, Any] = {}
        current_tool_ids = self._extract_agent_tool_ids(current)
        if snapshot_id and current_tool_ids and snapshot_id not in set(current_tool_ids):
            msg = (
                "Snapshots are immutable in this adapter. "
                "Updating deployment snapshots is not allowed; create a new deployment with the new snapshot instead."
            )
            raise ValueError(msg)

        if config_id:
            connection = self._ensure_connection_exists(clients.connections_client, app_id=config_id)
            self._validate_live_connection(clients.connections_client, app_id=config_id)
            update_payload["connection_ids"] = [connection.connection_id]

        if update_payload:
            clients.agent_client.update(deployment_id, update_payload)

        return await self.get_deployment(deployment_id, user_id=user_id, db=db)

    async def redeploy_deployment(
        self,
        deployment_id: str,
        *,
        user_id: UUID | str,
        db: Any,
    ) -> dict[str, Any]:
        """Trigger a deployment release for the agent in a live environment."""
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        environment_id = self._resolve_live_environment_id(clients.agent_client, deployment_id)
        deployed = clients.agent_client.deploy(agent_id=deployment_id, environment_id=environment_id)
        return {
            "deployment_id": deployment_id,
            "environment_id": environment_id,
            "status": "success" if deployed else "failed",
        }

    async def clone_deployment(
        self,
        deployment_id: str,
        *,
        user_id: UUID | str,
        db: Any,
    ) -> dict[str, Any]:
        """Clone an existing deployment by creating a new agent."""
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        current = clients.agent_client.get_draft_by_id(deployment_id)
        if not current:
            msg = f"Deployment '{deployment_id}' not found."
            raise ValueError(msg)

        payload = self._build_agent_clone_payload(current)
        created = clients.agent_client.create(payload)
        if not created.id:
            msg = "WXO did not return an agent id for clone operation."
            raise ValueError(msg)
        return await self.get_deployment(created.id, user_id=user_id, db=db)

    async def delete_deployment(
        self,
        deployment_id: str,
        *,
        user_id: UUID | str,
        db: Any,
    ) -> None:
        """Delete only the deployment agent (keep tools/configs reusable)."""
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        clients.agent_client.delete(deployment_id)

    async def get_deployment_health(
        self,
        deployment_id: str,
        *,
        user_id: UUID | str,
        db: Any,
    ) -> dict[str, Any]:
        """Get deployment health from the provider."""
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        agent = clients.agent_client.get_draft_by_id(deployment_id)
        if not agent:
            msg = f"Deployment '{deployment_id}' not found."
            raise ValueError(msg)

        health: dict[str, Any] = {
            "deployment_id": deployment_id,
            "exists": True,
            "tool_count": len(self._extract_agent_tool_ids(agent)),
        }
        try:
            environment_id = self._resolve_live_environment_id(clients.agent_client, deployment_id)
            status = clients.agent_client._get(  # noqa: SLF001
                f"{clients.agent_client.base_endpoint}/{deployment_id}/releases/status?environment_id={environment_id}"
            )
            health["release_status"] = status
        except Exception as exc:  # noqa: BLE001
            health["release_status"] = {"status": "unknown", "reason": str(exc)}
        return health

    async def create_deployment_config(
        self,
        *,
        data: dict,
        user_id: UUID | str,
        db: Any,
    ) -> dict[str, Any]:
        """Create/update a WXO live key-value connection config plus runtime credentials."""
        app_id = self._require_app_id(data)
        clients = await self._get_provider_clients(data=data, user_id=user_id, db=db)
        self._ensure_connection_exists(clients.connections_client, app_id=app_id)
        self._upsert_live_kv_config(clients.connections_client, app_id=app_id)

        runtime_credentials = await self._resolve_runtime_credentials(data, user_id=user_id, db=db)
        self._upsert_runtime_credentials(
            clients.connections_client,
            app_id=app_id,
            runtime_credentials=runtime_credentials,
        )
        return await self.get_deployment_config(app_id, user_id=user_id, db=db)

    async def list_deployment_configs(
        self,
        *,
        user_id: UUID | str,
        db: Any,
    ) -> list[dict[str, Any]]:
        """List deployment configs (represented by WXO app_id)."""
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        apps = clients.connections_client.list()
        results: list[dict[str, Any]] = []
        for app in apps:
            app_id = getattr(app, "app_id", None)
            if not app_id:
                continue
            config = clients.connections_client.get_config(app_id=app_id, env=ConnectionEnvironment.LIVE)
            if not config:
                continue
            credentials = clients.connections_client.get_credentials(
                app_id=app_id,
                env=ConnectionEnvironment.LIVE,
                use_app_credentials=False,
            )
            results.append(
                {
                    "config_id": app_id,
                    "app_id": app_id,
                    "environment": ConnectionEnvironment.LIVE.value,
                    "preference": config.preference.value if getattr(config, "preference", None) else None,
                    "security_scheme": (
                        config.security_scheme.value if getattr(config, "security_scheme", None) else None
                    ),
                    "credentials_entered": bool(credentials),
                }
            )
        return results

    async def get_deployment_config(
        self,
        config_id: str,
        *,
        user_id: UUID | str,
        db: Any,
    ) -> dict[str, Any]:
        """Get deployment config by app_id (adapter config_id)."""
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        config = clients.connections_client.get_config(app_id=config_id, env=ConnectionEnvironment.LIVE)
        if not config:
            msg = f"Deployment config '{config_id}' not found in live environment."
            raise ValueError(msg)
        credentials = clients.connections_client.get_credentials(
            app_id=config_id,
            env=ConnectionEnvironment.LIVE,
            use_app_credentials=False,
        )
        return {
            "config_id": config_id,
            "app_id": config_id,
            "environment": ConnectionEnvironment.LIVE.value,
            "preference": config.preference.value if getattr(config, "preference", None) else None,
            "security_scheme": config.security_scheme.value if getattr(config, "security_scheme", None) else None,
            "credentials_entered": bool(credentials),
        }

    async def update_deployment_config(
        self,
        config_id: str,
        *,
        data: dict | None = None,
        user_id: UUID | str,
        db: Any,
    ) -> dict[str, Any]:
        """Update an existing live config by app_id."""
        payload = dict(data or {})
        payload["app_id"] = config_id
        return await self.create_deployment_config(data=payload, user_id=user_id, db=db)

    async def delete_deployment_config(
        self,
        config_id: str,
        *,
        user_id: UUID | str,
        db: Any,
    ) -> None:
        """Delete provider config by removing the underlying connection app."""
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        clients.connections_client.delete(config_id)

    async def create_snapshot(
        self,
        *,
        data: dict,
        snapshot_type: str,
        user_id: UUID | str,
        db: Any,
    ) -> dict[str, Any]:
        """Create an immutable WXO tool snapshot from a Langflow definition."""
        clients = await self._get_provider_clients(data=data, user_id=user_id, db=db)
        flow_definition = self._require_flow_definition(data)
        app_id = data.get("config_id") or data.get("app_id")
        if not app_id:
            msg = "Snapshot creation requires config_id/app_id to bind tool connections."
            raise ValueError(msg)

        connection = self._ensure_connection_exists(clients.connections_client, app_id=app_id)
        tool = create_langflow_tool(
            tool_definition=flow_definition,
            connections={app_id: connection.connection_id},
            show_details=False,
        )

        existing = clients.tool_client.get_draft_by_name(tool.__tool_spec__.name)
        if existing:
            msg = (
                f"Snapshot/tool '{tool.__tool_spec__.name}' already exists. "
                "Snapshots are immutable; create a new snapshot with a new name."
            )
            raise ValueError(msg)

        created = clients.tool_client.create(
            tool.__tool_spec__.model_dump(mode="json", exclude_unset=True, exclude_none=True, by_alias=True)
        )
        tool_id = created.get("id")
        if not tool_id:
            msg = "WXO did not return a tool id for snapshot creation."
            raise ValueError(msg)

        artifact = self._build_langflow_artifact_bytes(tool=tool, flow_definition=flow_definition)
        self._upload_tool_artifact_bytes(clients.tool_client, tool_id=tool_id, artifact_bytes=artifact)
        snapshot = await self.get_snapshot(tool_id, user_id=user_id, db=db)
        snapshot["snapshot_type"] = snapshot_type or DEFAULT_ADAPTER_SNAPSHOT_TYPE
        return snapshot

    async def list_snapshots(
        self,
        snapshot_type: str | None = None,
        *,
        user_id: UUID | str,
        db: Any,
    ) -> list[dict[str, Any]]:
        """List WXO tool snapshots."""
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        tools = clients.tool_client.get()
        if isinstance(tools, dict):
            tools = [tools]
        snapshots = [self._map_tool_to_snapshot(item) for item in tools]
        if snapshot_type is None:
            return snapshots
        return [snapshot for snapshot in snapshots if snapshot.get("snapshot_type") == snapshot_type]

    async def get_snapshot(
        self,
        snapshot_id: str,
        *,
        user_id: UUID | str,
        db: Any,
    ) -> dict[str, Any]:
        """Get a WXO tool snapshot."""
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        tool = clients.tool_client.get_draft_by_id(snapshot_id)
        if not tool:
            msg = f"Snapshot '{snapshot_id}' not found."
            raise ValueError(msg)
        return self._map_tool_to_snapshot(tool)

    async def delete_snapshot(
        self,
        snapshot_id: str,
        *,
        user_id: UUID | str,
        db: Any,
    ) -> None:
        """Delete a WXO tool snapshot."""
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        clients.tool_client.delete(snapshot_id)

    async def teardown(self) -> None:
        """Teardown provider-specific resources."""
        self._provider_clients_cache.clear()

    async def _get_provider_clients(
        self,
        *,
        user_id: UUID | str,
        db: Any,
        data: dict[str, Any] | None = None,
    ) -> _ProviderClients:
        cache_key = self._build_client_cache_key(user_id=user_id, data=data)
        if cache_key in self._provider_clients_cache:
            return self._provider_clients_cache[cache_key]

        creds_dict = await self._resolve_wxo_client_credentials(user_id=user_id, db=db, data=data)
        credentials = Credentials(
            url=creds_dict["instance_url"],
            api_key=creds_dict["api_key"],
            iam_url=creds_dict.get("iam_url"),
            auth_type=creds_dict.get("auth_type") or DEFAULT_WXO_AUTH_TYPE,
        )
        client = Client(credentials)
        clients = _ProviderClients(
            tool_client=ToolClient(base_url=credentials.url, api_key=client.token),
            connections_client=ConnectionsClient(base_url=credentials.url, api_key=client.token),
            agent_client=AgentClient(base_url=credentials.url, api_key=client.token),
        )
        self._provider_clients_cache[cache_key] = clients
        return clients

    def _build_client_cache_key(
        self,
        *,
        user_id: UUID | str,
        data: dict[str, Any] | None = None,
    ) -> str:
        if data and isinstance(data.get("wxo_client_cache_key"), str) and data["wxo_client_cache_key"]:
            return data["wxo_client_cache_key"]
        return str(user_id)

    async def _resolve_wxo_client_credentials(
        self,
        *,
        user_id: UUID | str,
        db: Any,
        data: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        names = {
            "instance_url": DEFAULT_WXO_INSTANCE_URL_VARIABLE,
            "api_key": DEFAULT_WXO_API_KEY_VARIABLE,
            "iam_url": DEFAULT_WXO_AWS_IAM_URL_VARIABLE,
            "auth_type": DEFAULT_WXO_AUTH_TYPE_VARIABLE,
        }
        overrides = (data or {}).get("wxo_credentials", {})
        if isinstance(overrides, dict):
            names["instance_url"] = overrides.get("instance_url_variable", names["instance_url"])
            names["api_key"] = overrides.get("api_key_variable", names["api_key"])
            names["iam_url"] = overrides.get("iam_url_variable", names["iam_url"])
            names["auth_type"] = overrides.get("auth_type_variable", names["auth_type"])

        return {
            "instance_url": await self._resolve_variable_value(
                names["instance_url"], user_id=user_id, db=db
            ),
            "api_key": await self._resolve_variable_value(names["api_key"], user_id=user_id, db=db),
            "iam_url": await self._resolve_variable_value(
                names["iam_url"], user_id=user_id, db=db, optional=True
            ),
            "auth_type": await self._resolve_variable_value(
                names["auth_type"],
                user_id=user_id,
                db=db,
                optional=True,
                default_value=DEFAULT_WXO_AUTH_TYPE,
            ),
        }

    async def _resolve_runtime_credentials(
        self,
        data: dict[str, Any],
        *,
        user_id: UUID | str,
        db: Any,
    ) -> dict[str, str]:
        env_vars = data.get("environment_variables")
        if env_vars is None:
            msg = "Deployment config data must include 'environment_variables'."
            raise ValueError(msg)

        mapping: dict[str, str] = {}
        if isinstance(env_vars, list):
            mapping = {name: name for name in env_vars if isinstance(name, str) and name}
        elif isinstance(env_vars, dict):
            normalized = {}
            for key, value in env_vars.items():
                if not isinstance(key, str) or not key:
                    continue
                if not isinstance(value, str) or not value:
                    msg = f"Invalid environment variable mapping for '{key}'. Expected a non-empty variable name."
                    raise ValueError(msg)
                normalized[key] = value
            mapping = normalized
        else:
            msg = "'environment_variables' must be either a list[str] or dict[str, str]."
            raise TypeError(msg)

        if not mapping:
            msg = "'environment_variables' cannot be empty."
            raise ValueError(msg)

        resolved: dict[str, str] = {}
        for credential_key, variable_name in mapping.items():
            resolved[credential_key] = await self._resolve_variable_value(
                variable_name,
                user_id=user_id,
                db=db,
            )
        return resolved

    async def _resolve_variable_value(
        self,
        variable_name: str,
        *,
        user_id: UUID | str,
        db: Any,
        optional: bool = False,
        default_value: str | None = None,
    ) -> str:
        variable_service = get_variable_service()
        if variable_service is None:
            msg = "Variable service is not available."
            raise ValueError(msg)
        try:
            value = await variable_service.get_variable(
                user_id=user_id,
                name=variable_name,
                field="value",
                session=db,
            )
            if value:
                return value
        except Exception:
            if not optional:
                raise
        if optional:
            return default_value or ""
        msg = f"Required variable '{variable_name}' is not set."
        raise ValueError(msg)

    def _ensure_connection_exists(self, connections_client: ConnectionsClient, *, app_id: str):
        connection = connections_client.get_draft_by_app_id(app_id=app_id)
        if connection:
            return connection
        connections_client.create(payload={"app_id": app_id})
        connection = connections_client.get_draft_by_app_id(app_id=app_id)
        if not connection:
            msg = f"Failed to create or resolve WXO connection app '{app_id}'."
            raise ValueError(msg)
        return connection

    def _validate_live_connection(self, connections_client: ConnectionsClient, *, app_id: str) -> None:
        config = connections_client.get_config(app_id=app_id, env=ConnectionEnvironment.LIVE)
        if not config:
            msg = f"Connection '{app_id}' is missing live config. Deployments require live mode."
            raise ValueError(msg)
        if config.security_scheme != ConnectionSecurityScheme.KEY_VALUE:
            msg = f"Connection '{app_id}' must use key-value credentials for Langflow flows."
            raise ValueError(msg)
        runtime_credentials = connections_client.get_credentials(
            app_id=app_id,
            env=ConnectionEnvironment.LIVE,
            use_app_credentials=False,
        )
        if not runtime_credentials:
            msg = f"Connection '{app_id}' is missing live runtime credentials."
            raise ValueError(msg)

    def _upsert_live_kv_config(self, connections_client: ConnectionsClient, *, app_id: str) -> None:
        config = ConnectionConfiguration(
            app_id=app_id,
            environment=ConnectionEnvironment.LIVE,
            preference=ConnectionPreference.TEAM,
            security_scheme=ConnectionSecurityScheme.KEY_VALUE,
        )
        existing = connections_client.get_config(app_id=app_id, env=ConnectionEnvironment.LIVE)
        if existing:
            connections_client.update_config(
                app_id=app_id,
                env=ConnectionEnvironment.LIVE,
                payload=config.model_dump(exclude_none=True),
            )
            return
        connections_client.create_config(app_id=app_id, payload=config.model_dump(exclude_none=True))

    def _upsert_runtime_credentials(
        self,
        connections_client: ConnectionsClient,
        *,
        app_id: str,
        runtime_credentials: dict[str, str],
    ) -> None:
        credentials = KeyValueConnectionCredentials(runtime_credentials)
        existing = connections_client.get_credentials(
            app_id=app_id,
            env=ConnectionEnvironment.LIVE,
            use_app_credentials=False,
        )
        payload = {"runtime_credentials": credentials.model_dump()}
        if existing:
            connections_client.update_credentials(
                app_id=app_id,
                env=ConnectionEnvironment.LIVE,
                use_app_credentials=False,
                payload=payload,
            )
            return
        connections_client.create_credentials(
            app_id=app_id,
            env=ConnectionEnvironment.LIVE,
            use_app_credentials=False,
            payload=payload,
        )

    def _resolve_tool_ids(self, *, snapshot_id: str | None, snapshot: dict | None) -> list[str]:
        if snapshot_id:
            return [snapshot_id]
        if not snapshot:
            return []
        if isinstance(snapshot.get("snapshot_ids"), list):
            return [item for item in snapshot["snapshot_ids"] if isinstance(item, str) and item]
        if isinstance(snapshot.get("tool_ids"), list):
            return [item for item in snapshot["tool_ids"] if isinstance(item, str) and item]
        if isinstance(snapshot.get("id"), str):
            return [snapshot["id"]]
        return []

    async def _resolve_config_id_for_deployment(
        self,
        *,
        config_id: str | None,
        config: dict[str, Any] | None,
        user_id: UUID | str,
        db: Any,
    ) -> str:
        if config_id:
            return config_id

        if config is None:
            msg = "create_deployment requires either 'config_id' or a fresh 'config' object."
            raise ValueError(msg)

        if isinstance(config.get("config_id"), str) and config["config_id"]:
            return config["config_id"]
        if isinstance(config.get("app_id"), str) and config["app_id"] and "environment_variables" not in config:
            return config["app_id"]

        created_config = await self.create_deployment_config(data=config, user_id=user_id, db=db)
        created_config_id = created_config.get("config_id")
        if not created_config_id:
            msg = "Failed to resolve config_id from created config object."
            raise ValueError(msg)
        return str(created_config_id)

    async def _resolve_snapshot_ids_for_deployment(
        self,
        *,
        snapshot_id: str | None,
        snapshot: dict[str, Any] | None,
        config_id: str,
        user_id: UUID | str,
        db: Any,
    ) -> list[str]:
        if snapshot_id:
            return [snapshot_id]

        if snapshot is None:
            msg = "create_deployment requires either 'snapshot_id' or a fresh 'snapshot' object."
            raise ValueError(msg)

        existing_ids = self._resolve_tool_ids(snapshot_id=None, snapshot=snapshot)
        if existing_ids:
            return existing_ids

        snapshot_data = dict(snapshot)
        snapshot_type = str(snapshot_data.pop("snapshot_type", DEFAULT_ADAPTER_SNAPSHOT_TYPE))
        snapshot_data.setdefault("app_id", config_id)
        created_snapshot = await self.create_snapshot(
            data=snapshot_data,
            snapshot_type=snapshot_type,
            user_id=user_id,
            db=db,
        )
        created_snapshot_id = created_snapshot.get("snapshot_id")
        if not created_snapshot_id:
            msg = "Failed to resolve snapshot_id from created snapshot object."
            raise ValueError(msg)
        return [str(created_snapshot_id)]

    def _validate_exclusive_inputs(
        self,
        *,
        resource_name: str,
        resource_id: str | None,
        resource_object: dict[str, Any] | None,
    ) -> None:
        if resource_id and resource_object is not None:
            msg = f"Only one of '{resource_name}_id' or '{resource_name}' should be present."
            raise ValueError(msg)

    def _build_agent_payload(
        self,
        *,
        deployment_type: str,
        app_id: str,
        connection_id: str,
        tool_ids: list[str],
        source_data: dict[str, Any],
    ) -> dict[str, Any]:
        name = source_data.get("agent_name") or source_data.get("name")
        if not name:
            default_tool = tool_ids[0][:8] if tool_ids else "tool"
            name = f"langflow_{deployment_type}_{app_id}_{default_tool}"
        payload = {
            "name": name,
            "description": source_data.get(
                "agent_description",
                f"Langflow deployment ({deployment_type}) using connection '{app_id}'",
            ),
            "tools": tool_ids,
            "connection_ids": [connection_id],
        }
        extra = source_data.get("agent_payload", {})
        if isinstance(extra, dict):
            payload.update(extra)
        return payload

    def _build_agent_clone_payload(self, current: dict[str, Any]) -> dict[str, Any]:
        payload = deepcopy(current)
        payload.pop("id", None)
        payload.pop("created_at", None)
        payload.pop("updated_at", None)
        payload["name"] = f"{payload.get('name', 'agent')}_clone"
        return payload

    def _extract_agent_tool_ids(self, agent: dict[str, Any]) -> list[str]:
        tools = agent.get("tools", [])
        tool_ids: list[str] = []
        for item in tools:
            if isinstance(item, str):
                tool_ids.append(item)
            elif isinstance(item, dict) and item.get("id"):
                tool_ids.append(str(item["id"]))
        return tool_ids

    def _extract_agent_connection_ids(self, agent: dict[str, Any]) -> list[str]:
        connections = agent.get("connection_ids", [])
        return [item for item in connections if isinstance(item, str)]

    def _resolve_live_environment_id(self, agent_client: AgentClient, deployment_id: str) -> str:
        environments = agent_client.get_environments_for_agent(deployment_id)
        if isinstance(environments, dict):
            envs = environments.get("environments", []) or environments.get("data", []) or []
        elif isinstance(environments, list):
            envs = environments
        else:
            envs = []

        for env in envs:
            if not isinstance(env, dict):
                continue
            name = str(env.get("name", "")).lower()
            label = str(env.get("label", "")).lower()
            mode = str(env.get("environment", "")).lower()
            if "live" in {name, label, mode}:
                env_id = env.get("id") or env.get("environment_id")
                if env_id:
                    return str(env_id)
        if envs and isinstance(envs[0], dict):
            env_id = envs[0].get("id") or envs[0].get("environment_id")
            if env_id:
                return str(env_id)
        msg = f"No deployable environment found for deployment '{deployment_id}'."
        raise ValueError(msg)

    def _map_agent_to_deployment(self, agent: dict[str, Any]) -> dict[str, Any]:
        tool_ids = self._extract_agent_tool_ids(agent)
        return {
            "deployment_id": agent.get("id"),
            "name": agent.get("name"),
            "description": agent.get("description"),
            "snapshot_ids": tool_ids,
            "config_ids": self._extract_agent_connection_ids(agent),
            "deployment_type": "wxo_agent",
            "provider_raw": agent,
        }

    def _map_tool_to_snapshot(self, tool: dict[str, Any]) -> dict[str, Any]:
        # snapshot_type is adapter-level terminology, not provider binding type.
        snapshot_type = DEFAULT_ADAPTER_SNAPSHOT_TYPE
        return {
            "snapshot_id": tool.get("id"),
            "name": tool.get("name"),
            "description": tool.get("description"),
            "snapshot_type": snapshot_type,
            "immutable": True,
            "provider_raw": tool,
        }

    def _require_flow_definition(self, data: dict[str, Any]) -> dict[str, Any]:
        flow_definition = data.get("flow_definition") or data.get("tool_definition")
        if not isinstance(flow_definition, dict):
            msg = "Snapshot data must include 'flow_definition' (Langflow JSON dict)."
            raise TypeError(msg)
        return flow_definition

    def _require_app_id(self, data: dict[str, Any]) -> str:
        app_id = data.get("app_id") or data.get("config_id")
        if not isinstance(app_id, str) or not app_id.strip():
            msg = "Deployment config requires a non-empty 'app_id' (also used as config_id)."
            raise ValueError(msg)
        return app_id

    def _build_langflow_artifact_bytes(
        self,
        *,
        tool,
        flow_definition: dict[str, Any],
        flow_filename: str | None = None,
    ) -> bytes:
        filename = flow_filename or f"{tool.__tool_spec__.name}.json"
        requirements = list(getattr(tool, "requirements", []) or [])
        requirements = self._dedupe_requirements(requirements)

        runner_overridden = False
        for requirement in requirements:
            module_name = (
                requirement.strip()
                .split("==")[0]
                .split("=")[0]
                .split(">=")[0]
                .split("<=")[0]
                .split("~=")[0]
                .lower()
            )
            if module_name and not module_name.startswith("#") and module_name in DEFAULT_LANGFLOW_RUNNER_MODULES:
                runner_overridden = True
                break

        if not runner_overridden:
            requirements = DEFAULT_LANGFLOW_TOOL_REQUIREMENTS + list(requirements)

        requirements_content = "\n".join(requirements) + "\n"
        flow_content = json.dumps(flow_definition, indent=2)

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_tool_artifacts:
            zip_tool_artifacts.writestr(filename, flow_content)
            zip_tool_artifacts.writestr("requirements.txt", requirements_content)
            zip_tool_artifacts.writestr("bundle-format", "2.0.0\n")
        return buffer.getvalue()

    def _upload_tool_artifact_bytes(
        self,
        tool_client: ToolClient,
        *,
        tool_id: str,
        artifact_bytes: bytes,
    ) -> dict[str, Any]:
        file_obj = io.BytesIO(artifact_bytes)
        return tool_client._post(  # noqa: SLF001
            f"/tools/{tool_id}/upload",
            files={"file": (f"{tool_id}.zip", file_obj, "application/zip", {"Expires": "0"})},
        )

    def _dedupe_requirements(self, requirements: list[str]) -> list[str]:
        seen = set()
        result = []
        for requirement in requirements:
            if requirement not in seen:
                result.append(requirement)
                seen.add(requirement)
        return result



