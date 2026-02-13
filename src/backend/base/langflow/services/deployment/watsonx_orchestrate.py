"""Watsonx Orchestrate deployment adapter."""

from __future__ import annotations

import io
import json
import zipfile
from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import fastapi
from ibm_watsonx_orchestrate_clients.agents.agent_client import AgentClient
from ibm_watsonx_orchestrate_clients.common.client import Client
from ibm_watsonx_orchestrate_clients.common.credentials import Credentials
from ibm_watsonx_orchestrate_clients.connections.connections_client import ConnectionsClient
from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException, ToolClient
from ibm_watsonx_orchestrate_core.types.connections import (
    ConnectionConfiguration,
    ConnectionEnvironment,
    ConnectionPreference,
    ConnectionSecurityScheme,
    KeyValueConnectionCredentials,
)
from ibm_watsonx_orchestrate_core.types.tools.langflow_tool import create_langflow_tool
from lfx.services.deployment.base import BaseDeploymentService, DeploymentType
from lfx.services.deployment.exceptions import DeploymentConflictError, DeploymentError, UnprocessableContentError
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
DEFAULT_ADAPTER_DEPLOYMENT_TYPE = "agent"
SUPPORTED_ADAPTER_DEPLOYMENT_TYPES = {DEFAULT_ADAPTER_DEPLOYMENT_TYPE}


@dataclass(slots=True)
class _ProviderClients:
    tool: ToolClient
    connections: ConnectionsClient
    agent: AgentClient


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
        # TODO: cache clients per tenant, the current approach assumes only one tenant
        self.clients = None
        self.set_ready()

    async def create_deployment(
        self,
        *,
        snapshot_ids: list[str] | None = None,
        config_id: str | None = None,
        snapshots: list[dict] | None = None,
        config: dict | None = None,
        deployment_name: str,
        deployment_type: str,
        user_id: UUID | str,
        db: Any,
    ) -> dict[str, Any]:
        """Create a deployment in Watsonx Orchestrate."""
        err_msg_prefix = "An error occured while creating a deployment: "
        try:
            self._require_exclusive_resource(
                resource="snapshot",
                _id=snapshot_ids,
                payload=snapshots,
                msg_prefix=err_msg_prefix,
            )
            self._require_exclusive_resource(
                resource="config",
                _id=config_id,
                payload=config,
                msg_prefix=err_msg_prefix,
            )

            if deployment_type == DeploymentType.AGENT:
                pass

            app_id: str

            if config_id:
                app_id = self._require_non_empty_string(
                    s=config_id,
                    field_name="config_id",
                    error_message=(
                        "An error occured in create_deployment: "
                        "Please provide a valid config_id with non-whitespace characters."
                        ),
                )
            elif config:
                new_app_id = config.get("app_id", None)
                if not (new_app_id and (_app_id := new_app_id.strip())):
                    msg = (
                        f"{err_msg_prefix}"
                        "The provided config object does not contain a valid 'app_id'."
                        "Please ensure the config object contains an 'app_id' field "
                        "and ensure it consists of alphanumeric characters."
                    )
                    raise ValueError(msg)
                app_id = _app_id
                await self.create_deployment_config(data=config, user_id=user_id, db=db)

            tool_ids: list[str]

            if snapshot_ids:
                tool_ids = (
                    self._dedupe_list(
                        [
                            _id
                            for sid in snapshot_ids
                            if sid and (_id:=sid.strip())
                        ]
                    )
                )
            elif snapshots:
                tool_ids = self._dedupe_list(
                    [
                        await self._create_snapshot(
                            snapshot_data=snapshot_data,
                            config_id=app_id,
                            user_id=user_id,
                            db=db,
                            )
                        for snapshot_data in snapshots
                        if isinstance(snapshot_data, dict)
                    ]
                )
            if not tool_ids:
                msg = (
                    f"{err_msg_prefix}"
                    "create_deployment requires a list of valid snapshot ids or a list of valid snapshots. "
                    "A valid snapshot id is a non-empty string with non-whitespace characters. "
                    "A valid snapshot is a JSON whose contents are Langflow flow data."
                )
                raise UnprocessableContentError(msg)

            clients = await self._get_provider_clients(user_id=user_id, db=db)

            # connection = clients.connections.get_draft_by_app_id(app_id=app_id)
            # if not connection:
            #     msg = f"{err_msg_prefix}Connection '{app_id}' not found."
            #     raise ValueError(msg)
            # self._validate_connection(clients.connections, app_id=app_id)
            # connection_id = connection.connection_id

            payload = self._build_agent_payload(
                deployment_name=deployment_name,
                deployment_type=deployment_type,
                app_id=app_id,
                # connection_id=connection_id,
                tool_ids=tool_ids,
            )


            created = clients.agent.create(payload)

            # clients.agent.connect_connections(created.id, [connection_id])

            # agent = clients.agent.get_draft_by_id(created.id)

        except ClientAPIException as e:
            detail = e.response.json().get("detail", [{}])[0].get("msg", None) or e.response.text
            msg = f"{err_msg_prefix}{detail}"
            if e.response.status_code == fastapi.status.HTTP_409_CONFLICT:
                raise DeploymentConflictError(message=msg) from e
            if e.response.status_code == fastapi.status.HTTP_422_UNPROCESSABLE_CONTENT:
                raise UnprocessableContentError(message=msg) from e
            raise DeploymentError(message=msg) from e
        except Exception as e:
            msg = f"{err_msg_prefix} {e!s}"
            raise DeploymentError(message=msg) from e

        return {
            "deployment_id": created.id,
            "deployment_name": deployment_name,
            "deployment_type": deployment_type,
        }

    async def list_deployments(
        self,
        deployment_type: str | None = None,
        *,
        user_id: UUID | str,
        db: Any,
    ) -> list[dict[str, Any]]:
        """List deployments (agents) from Watsonx Orchestrate."""
        normalized_type = self._normalize_deployment_type(deployment_type) if deployment_type else None
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        # Shape source:
        # - SDK: AgentClient.get() proxies GET /agents?include_hidden=true.
        # - API: list endpoint returns list of agent objects.
        data = clients.agent.get()
        deployments = [
            self._get_deployment_metadata(
                data=agent,
                deployment_type=DEFAULT_ADAPTER_DEPLOYMENT_TYPE,
            )
            for agent in data
        ]
        if normalized_type is None:
            return deployments
        return [deployment for deployment in deployments if deployment.get("deployment_type") == normalized_type]

    async def get_deployment(
        self,
        deployment_id: str,
        *,
        user_id: UUID | str,
        db: Any,
    ) -> dict[str, Any]:
        """Get a deployment (agent) from Watsonx Orchestrate."""
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        agent = clients.agent.get_draft_by_id(deployment_id)
        if not agent:
            msg = f"Deployment '{deployment_id}' not found."
            raise ValueError(msg)
        return self._get_deployment_metadata(
            data=agent,
            deployment_type=DEFAULT_ADAPTER_DEPLOYMENT_TYPE,
        )

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
        current = clients.agent.get_draft_by_id(deployment_id)
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
            connection = clients.connections.get_draft_by_app_id(app_id=config_id)
            if not connection:
                msg = f"Connection '{config_id}' not found."
                raise ValueError(msg)
            self._validate_connection(clients.connections, app_id=config_id)
            update_payload["connection_ids"] = [connection.connection_id]

        if update_payload:
            clients.agent.update(deployment_id, update_payload)

        return await self.get_deployment(deployment_id, user_id=user_id, db=db)

    async def redeploy_deployment(
        self,
        deployment_id: str,
        *,
        user_id: UUID | str,
        db: Any,
    ) -> dict[str, Any]:
        """Trigger a deployment release for the agent in draft environment."""
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        environment_id = self._resolve_draft_environment_id(clients.agent, deployment_id)
        deployed = clients.agent.deploy(agent_id=deployment_id, environment_id=environment_id)
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
        current = clients.agent.get_draft_by_id(deployment_id)
        if not current:
            msg = f"Deployment '{deployment_id}' not found."
            raise ValueError(msg)

        payload = self._build_agent_clone_payload(current)
        created = clients.agent.create(payload)
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
        clients.agent.delete(deployment_id)

    async def get_deployment_health(
        self,
        deployment_id: str,
        *,
        user_id: UUID | str,
        db: Any,
    ) -> dict[str, Any]:
        """Get deployment health for draft agents from the provider."""
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        agent = clients.agent.get_draft_by_id(deployment_id)
        if not agent:
            msg = f"Deployment '{deployment_id}' not found."
            raise ValueError(msg)

        return {
            "deployment_id": deployment_id,
            "exists": True,
            "tool_count": len(self._extract_agent_tool_ids(agent)),
        }

    async def create_deployment_config(
        self,
        *,
        data: dict,
        user_id: UUID | str,
        db: Any,
    ) -> dict[str, Any]:
        """Create/update a WXO draft key-value connection config plus runtime credentials."""
        app_id = self._require_non_empty_string(
            data.get("app_id"),
            field_name="app_id",
            error_message="Deployment config requires a non-empty 'app_id' (also used as config_id).",
        )
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        connection = clients.connections.get_draft_by_app_id(app_id=app_id)
        if not connection:
            clients.connections.create(payload={"app_id": app_id})
            connection = clients.connections.get_draft_by_app_id(app_id=app_id)
            if not connection:
                msg = f"Failed to create or resolve WXO connection app '{app_id}'."
                raise ValueError(msg)
        self._upsert_draft_kv_config(clients.connections, app_id=app_id)

        runtime_credentials = await self._resolve_runtime_credentials(data, user_id=user_id, db=db)
        self._upsert_runtime_credentials(
            clients.connections,
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
        # Shape source:
        # - SDK: ConnectionsClient.list() returns list[ListConfigsResponse].
        # - API: /connections/applications?include_details=true -> applications[].
        apps = clients.connections.list()
        results: list[dict[str, Any]] = []
        for app in apps:
            app_id = app.app_id
            config = clients.connections.get_config(app_id=app_id, env=ConnectionEnvironment.DRAFT)
            if not config:
                continue
            credentials = clients.connections.get_credentials(
                app_id=app_id,
                env=ConnectionEnvironment.DRAFT,
                use_app_credentials=False,
            )
            results.append(
                {
                    "config_id": app_id,
                    "app_id": app_id,
                    "environment": ConnectionEnvironment.DRAFT.value,
                    "preference": config.preference.value,
                    "security_scheme": config.security_scheme.value,
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
        config = clients.connections.get_config(app_id=config_id, env=ConnectionEnvironment.DRAFT)
        if not config:
            msg = f"Deployment config '{config_id}' not found in draft environment."
            raise ValueError(msg)
        credentials = clients.connections.get_credentials(
            app_id=config_id,
            env=ConnectionEnvironment.DRAFT,
            use_app_credentials=False,
        )
        return {
            "config_id": config_id,
            "app_id": config_id,
            "environment": ConnectionEnvironment.DRAFT.value,
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
        """Update an existing draft config by app_id."""
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
        clients.connections.delete(config_id)

    async def create_snapshot(
        self,
        *,
        data: dict,
        snapshot_type: str,
        user_id: UUID | str,
        db: Any,
    ) -> dict[str, Any]:
        """Create an immutable WXO tool snapshot from a Langflow definition."""
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        flow_definition = self._require_flow_definition(data)
        app_id = self._require_non_empty_string(
            data.get("config_id"),
            field_name="config_id",
            error_message="Snapshot creation requires non-empty 'config_id' to bind tool connections.",
        )

        connection = clients.connections.get_draft_by_app_id(app_id=app_id)
        if not connection:
            msg = f"Connection '{app_id}' not found."
            raise ValueError(msg)
        tool = create_langflow_tool(
            tool_definition=flow_definition,
            connections={app_id: connection.connection_id},
            show_details=False,
        )

        existing = clients.tool.get_draft_by_name(tool.__tool_spec__.name)
        if existing:
            msg = (
                f"Snapshot/tool '{tool.__tool_spec__.name}' already exists. "
                "Snapshots are immutable; create a new snapshot with a new name."
            )
            raise ValueError(msg)

        created = clients.tool.create(
            tool.__tool_spec__.model_dump(mode="json", exclude_unset=True, exclude_none=True, by_alias=True)
        )
        tool_id = created.get("id")
        if not tool_id:
            msg = "WXO did not return a tool id for snapshot creation."
            raise ValueError(msg)

        artifact = self._build_langflow_artifact_bytes(tool=tool, flow_definition=flow_definition)
        self._upload_tool_artifact_bytes(clients.tool, tool_id=tool_id, artifact_bytes=artifact)
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
        # Shape source:
        # - SDK: ToolClient.get() proxies GET /tools.
        # - API: tools list endpoint returns list of tool objects.
        tools = clients.tool.get()
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
        tool = clients.tool.get_draft_by_id(snapshot_id)
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
        clients.tool.delete(snapshot_id)

    async def teardown(self) -> None:
        """Teardown provider-specific resources."""
        return

    def _create_agent_deployment(
        self, deployment_name: str, 
        deployment_type: DeploymentType,
        app_id: str,
        tool_ids: list[str],
        user_id: UUID | str,
        db: Any,
    ) -> dict[str, Any]:
        """Create an agent deployment."""
        pass

    async def _get_provider_clients(
        self,
        *,
        user_id: UUID | str,
        db: Any,
    ) -> _ProviderClients:
        if self.clients is not None:
            return self.clients
        creds_dict = await self._resolve_wxo_client_credentials(user_id=user_id, db=db)
        credentials = Credentials(
            url=creds_dict["instance_url"],
            api_key=creds_dict["api_key"],
            iam_url=creds_dict.get("iam_url"),
            auth_type=creds_dict.get("auth_type") or DEFAULT_WXO_AUTH_TYPE,
        )
        client = Client(credentials)
        self.clients = _ProviderClients(
            tool=ToolClient(base_url=credentials.url, api_key=client.token),
            connections=ConnectionsClient(base_url=credentials.url, api_key=client.token),
            agent=AgentClient(base_url=credentials.url, api_key=client.token),
        )
        return self.clients

    async def _resolve_wxo_client_credentials(
        self,
        *,
        user_id: UUID | str,
        db: Any,
    ) -> dict[str, str]:
        """Resolve Watsonx Orchestrate client credentials from environment variables."""
        return {
            "instance_url": await self._resolve_variable_value(
               DEFAULT_WXO_INSTANCE_URL_VARIABLE, user_id=user_id, db=db
            ),
            "api_key": await self._resolve_variable_value(
                DEFAULT_WXO_API_KEY_VARIABLE, user_id=user_id, db=db),
            "iam_url": await self._resolve_variable_value(
                DEFAULT_WXO_AWS_IAM_URL_VARIABLE, user_id=user_id, db=db, optional=True
            ),
            "auth_type": await self._resolve_variable_value(
                DEFAULT_WXO_AUTH_TYPE_VARIABLE,
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
            for item in env_vars:
                try:
                    normalized = self._require_non_empty_string(
                        item,
                        field_name="environment_variables[]",
                    )
                    mapping[normalized] = normalized
                except ValueError:
                    continue
        elif isinstance(env_vars, dict):
            normalized = {}
            for key, value in env_vars.items():
                try:
                    normalized_key = self._require_non_empty_string(
                        key,
                        field_name="environment_variables.key",
                    )
                except ValueError:
                    continue
                try:
                    normalized_value = self._require_non_empty_string(
                        value,
                        field_name="environment_variables.value",
                        error_message=(
                            f"Invalid environment variable mapping for '{key}'. "
                            "Expected a non-empty variable name."
                        ),
                    )
                except ValueError as exc:
                    msg = f"Invalid environment variable mapping for '{key}'. Expected a non-empty variable name."
                    raise ValueError(msg) from exc
                normalized[normalized_key] = normalized_value
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

    def _validate_connection(self, connections_client: ConnectionsClient, *, app_id: str) -> None:
        config = connections_client.get_config(app_id=app_id, env=ConnectionEnvironment.DRAFT)
        if not config:
            msg = f"Connection '{app_id}' is missing draft config. Deployments require draft mode."
            raise ValueError(msg)
        if config.security_scheme != ConnectionSecurityScheme.KEY_VALUE:
            msg = f"Connection '{app_id}' must use key-value credentials for Langflow flows."
            raise ValueError(msg)
        runtime_credentials = connections_client.get_credentials(
            app_id=app_id,
            env=ConnectionEnvironment.DRAFT,
            use_app_credentials=False,
        )
        if not runtime_credentials:
            msg = f"Connection '{app_id}' is missing draft runtime credentials."
            raise ValueError(msg)

    def _upsert_draft_kv_config(self, connections_client: ConnectionsClient, *, app_id: str) -> None:
        config = ConnectionConfiguration(
            app_id=app_id,
            environment=ConnectionEnvironment.DRAFT,
            preference=ConnectionPreference.TEAM,
            security_scheme=ConnectionSecurityScheme.KEY_VALUE,
        )
        existing = connections_client.get_config(app_id=app_id, env=ConnectionEnvironment.DRAFT)
        if existing:
            connections_client.update_config(
                app_id=app_id,
                env=ConnectionEnvironment.DRAFT,
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
            env=ConnectionEnvironment.DRAFT,
            use_app_credentials=False,
        )
        payload = {"runtime_credentials": credentials.model_dump()}
        if existing:
            connections_client.update_credentials(
                app_id=app_id,
                env=ConnectionEnvironment.DRAFT,
                use_app_credentials=False,
                payload=payload,
            )
            return
        connections_client.create_credentials(
            app_id=app_id,
            env=ConnectionEnvironment.DRAFT,
            use_app_credentials=False,
            payload=payload,
        )

    def _require_exclusive_resource(
        self,
        *,
        resource: str,
        _id: str | list[str] | None,
        payload: dict[str, Any] | None,
        msg_prefix: str = "",
    ) -> None:
        """Require exactly one of the resource id or payload to be present and non-empty and non-null."""
        if (not _id) == (not payload):
            msg = (
                f"{msg_prefix}Exactly one of {resource} id or payload should be present and non-empty and non-null."
            )
            raise ValueError(msg)

    def _build_agent_payload(
        self,
        *,
        deployment_name: str,
        deployment_type: str,
        app_id: str,
        # connection_id: str,
        tool_ids: list[str],
    ) -> dict[str, Any]:
        return {
            # Name must start with a letter and contain only alphanumeric characters and underscores
            # WxO will raise an error if the name is not valid. So we won't validate it here.
            "name": deployment_name,
            "description": f"Langflow deployment ({deployment_type}) using connection '{app_id}'",
            "tools": tool_ids,
            # "connection_ids": [connection_id],
            "style": "default",
            "llm": "groq/openai/gpt-oss-120b",
        }

    def _build_agent_clone_payload(self, current: dict[str, Any]) -> dict[str, Any]:
        payload = deepcopy(current) # TODO: deepcopy is not necessary here
        payload.pop("id", None)
        payload.pop("created_at", None)
        payload.pop("updated_at", None)
        # TODO: handle unique naming if "<name>_clone" already exists.
        payload["name"] = f"{payload.get('name', 'agent')}_clone"
        return payload

    def _extract_agent_tool_ids(self, agent: dict[str, Any]) -> list[str]:
        # Shape source:
        # - SDK/API agent payload uses "tools" as list[str] in this adapter flow.
        return agent["tools"]

    def _extract_agent_connection_ids(self, agent: dict[str, Any]) -> list[str]:
        # Shape source:
        # - SDK/API agent payload uses "connection_ids" as list[str].
        return agent["connection_ids"]

    def _resolve_draft_environment_id(self, agent_client: AgentClient, deployment_id: str) -> str:
        # Shape source:
        # - SDK: AgentClient.get_environments_for_agent() -> GET /agents/{agent_id}/environment
        # - API: Agent Release Environments "List All Environments Of An Agent"
        #   response is a list of objects with required "id" and "name".
        environments = agent_client.get_environments_for_agent(deployment_id)
        for env in environments:
            if env["name"] == ConnectionEnvironment.DRAFT.value:
                return env["id"]
        msg = f"No draft environment found for deployment '{deployment_id}'."
        raise ValueError(msg)

    def _get_deployment_metadata(
        self,
        data: dict[str, Any],
        deployment_type: str,
        provider_raw: bool = False, # noqa: FBT001,FBT002
    ) -> dict[str, Any]:
        result = {
            "deployment_id": data["id"],
            "name": data["name"],
            "description": data["description"],
            "deployment_type": deployment_type,
        }
        if provider_raw:
            result["provider_raw"] = data
        return result


    def _map_tool_to_snapshot(self, tool: dict[str, Any]) -> dict[str, Any]:
        # snapshot_type is adapter-level terminology, not provider binding type.
        snapshot_type = DEFAULT_ADAPTER_SNAPSHOT_TYPE
        return {
            "snapshot_id": tool["id"],
            "name": tool["name"],
            "description": tool["description"],
            "snapshot_type": snapshot_type,
            "immutable": True,
            "provider_raw": tool,
        }

    def _require_flow_definition(self, data: dict[str, Any]) -> dict[str, Any]:
        flow_definition = data.get("flow_definition") or data.get("tool_definition")
        # TODO: validate the flow_definition is a pydantic flow schema.
        if not isinstance(flow_definition, dict):
            msg = "Snapshot data must include 'flow_definition' (Langflow JSON dict)."
            raise TypeError(msg)
        return flow_definition

    def _require_non_empty_string(
        self,
        s: Any,
        *,
        field_name: str,
        error_message: str | None = None,
    ) -> str:
        if isinstance(s, str) and (_value:=s.strip()):
            return _value
        msg = error_message or f"Expected non-empty string for '{field_name}'."
        raise ValueError(msg)

    def _build_langflow_artifact_bytes(
        self,
        *,
        tool,
        flow_definition: dict[str, Any],
        flow_filename: str | None = None,
    ) -> bytes:
        filename = flow_filename or f"{tool.__tool_spec__.name}.json"
        requirements = list(getattr(tool, "requirements", []) or [])
        requirements = self._dedupe_list(requirements)

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

    def _dedupe_list(self, requirements: list[str]) -> list[str]:
        seen = set()
        result = []
        for requirement in requirements:
            if requirement not in seen:
                result.append(requirement)
                seen.add(requirement)
        return result

    async def _create_snapshot(
        self,
        *,
        snapshot_data: dict[str, Any],
        config_id: str,
        user_id: UUID | str,
        db: Any,
    ) -> str:
        data = dict(snapshot_data)
        snapshot_type = str(data.pop("snapshot_type", DEFAULT_ADAPTER_SNAPSHOT_TYPE))
        data.setdefault("config_id", config_id)
        created_snapshot = await self.create_snapshot(
            data=data,
            snapshot_type=snapshot_type,
            user_id=user_id,
            db=db,
        )
        created_snapshot_id = created_snapshot.get("snapshot_id")
        if not created_snapshot_id:
            msg = "Failed to resolve snapshot_id from created snapshot object."
            raise ValueError(msg)
        return str(created_snapshot_id)
