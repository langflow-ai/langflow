"""Watsonx Orchestrate deployment adapter."""

from __future__ import annotations

import io
import json
import zipfile
from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

from fastapi import status
from fastapi.exceptions import HTTPException
from ibm_watsonx_orchestrate_clients.agents.agent_client import AgentClient, AgentUpsertResponse
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
from lfx.services.deployment.base import BaseDeploymentService
from lfx.services.deployment.exceptions import (
    AuthSchemeError,
    CredentialResolutionError,
    DeploymentConflictError,
    DeploymentError,
    DeploymentNotFoundError,
    DeploymentSupportError,
    InvalidContentError,
    InvalidDeploymentTypeError,
)
from lfx.services.deployment.schema import (
    DEPLOYMENT_CREATE_SCHEMA,
    ArtifactType,
    BaseConfigData,
    BaseDeploymentData,
    BaseFlowArtifact,
    ConfigFormat,
    ConfigItem,
    ConfigItemResult,
    ConfigListResult,
    ConfigResult,
    ConfigUpdate,
    DeploymentCreate,
    DeploymentCreateResult,
    DeploymentDeleteResult,
    DeploymentHealthResult,
    DeploymentItem,
    DeploymentList,
    DeploymentRedeployResult,
    DeploymentType,
    DeploymentUpdate,
    DeploymentUpdateResult,
    EnvVarKey,
    EnvVarValue,
    SnapshotFormat,
    SnapshotItem,
    SnapshotItems,
    SnapshotItemsCreate,
    SnapshotListResult,
    SnapshotResult,
)
from lfx.services.schema import ServiceType

from langflow.services.deps import get_variable_service

if TYPE_CHECKING:
    from uuid import UUID

    from ibm_cloud_sdk_core.authenticators import Authenticator
    from ibm_watsonx_orchestrate_clients.common.credentials import Credentials
    from lfx.services.settings.service import SettingsService


DEFAULT_LANGFLOW_RUNNER_MODULES = {"lfx", "lfx-nightly"}
# TODO: use src/lfx/src/lfx/custom/dependency_analyzer.py instead to get the lfx version.
DEFAULT_LANGFLOW_TOOL_REQUIREMENTS = ["lfx==0.3.0"]
DEFAULT_ADAPTER_SNAPSHOT_TYPE = "langflow"
DEFAULT_ADAPTER_DEPLOYMENT_TYPE = "agent"
SUPPORTED_ADAPTER_DEPLOYMENT_TYPES = {DEFAULT_ADAPTER_DEPLOYMENT_TYPE}


class WxOUserKey(str, Enum):
    INSTANCE_URL = "DEPLOYMENT_SERVICE_BACKEND_WXO_URL"
    API_KEY = "DEPLOYMENT_SERVICE_BACKEND_WXO_API_KEY"


class WxOAuthURL(str, Enum):
    MCSP = "https://iam.platform.saas.ibm.com"
    IBM_IAM = "https://iam.cloud.ibm.com"


@dataclass(slots=True)
class WxOClient:
    tool: ToolClient
    connections: ConnectionsClient
    agent: AgentClient


@dataclass(slots=True)
class WxOCredentials:
    instance_url: str
    api_key: str


ERROR_PREFIX = "An error occured while"
class ErrorPrefix(str, Enum):
    CREATE = f"{ERROR_PREFIX} creating a deployment: "
    LIST = f"{ERROR_PREFIX} listing deployments: "
    GET = f"{ERROR_PREFIX} getting a deployment: "
    UPDATE = f"{ERROR_PREFIX} updating a deployment: "
    REDEPLOY = f"{ERROR_PREFIX} redeploying a deployment: "
    CLONE = f"{ERROR_PREFIX} cloning a deployment: "
    DELETE = f"{ERROR_PREFIX} deleting a deployment: "
    HEALTH = f"{ERROR_PREFIX} getting a deployment health: "
    CREATE_CONFIG = f"{ERROR_PREFIX} creating a deployment config: "
    LIST_CONFIGS = f"{ERROR_PREFIX} listing deployment configs: "
    GET_CONFIG = f"{ERROR_PREFIX} getting a deployment config: "
    UPDATE_CONFIG = f"{ERROR_PREFIX} updating a deployment config: "
    DELETE_CONFIG = f"{ERROR_PREFIX} deleting a deployment config: "


class WatsonxOrchestrateDeploymentService(BaseDeploymentService):
    """Deployment adapter for Watsonx Orchestrate.

    Mapping used by this adapter:
    - deployment -> WXO agent bound to exactly one connection app_id and many tools
    - snapshot -> WXO tool (langflow binding) and immutable once created
    - config -> WXO connection configuration (+ credentials), keyed by app_id
    """

    name = ServiceType.DEPLOYMENT_SERVICE.value
    provider_name = "watsonx-orchestrate"

    def __init__(self, settings_service: SettingsService):
        super().__init__()
        self.settings_service = settings_service
        # TODO: cache clients per tenant, the current approach assumes only one tenant
        self._client_manager: WxOClient | None = None
        self.set_ready()

    async def create_deployment(
        self,
        *,
        user_id: UUID | str,
        deployment: DeploymentCreate,
        db: Any,
    ) -> DeploymentCreateResult:
        """Create a deployment in Watsonx Orchestrate."""
        try:
            app_id = await self._process_config(
                user_id=user_id,
                db=db,
                config=deployment.config,
            )

            tool_ids: list[str] = []

            if deployment.snapshot and deployment.snapshot.artifact_type == ArtifactType.FLOW:
                tool_ids = await self._process_flow_snapshots(
                    user_id=user_id,
                    app_id=app_id,
                    snapshots=deployment.snapshot,
                    db=db,
                )

            deployment_spec: BaseDeploymentData = deployment.spec

            if deployment_spec.type == DeploymentType.AGENT:
                deployment_response: AgentUpsertResponse = (
                    await self._create_agent_deployment(
                        data=deployment_spec,
                        tool_ids=tool_ids,
                        user_id=user_id,
                        db=db,
                    )
                ) # note: tool_ids can be empty here if an incompatible artifact type is provided
            else:
                msg = (
                    f"{ErrorPrefix.CREATE.value}"
                    f"Deployment type '{deployment_spec.type.value}' "
                    "is not supported for watsonx Orchestrate."
                    )
                raise DeploymentSupportError(message=msg)

        except (ClientAPIException, HTTPException) as e:
            status_code = (
                e.response.status_code
                if isinstance(e, ClientAPIException)
                else e.status_code
            )

            if status_code == status.HTTP_409_CONFLICT:
                msg = (
                    f"{ErrorPrefix.CREATE.value}. "
                    "One or more resources already exist. "
                    "Pleasure the names and/or ids of the "
                    "following resources to be unique: "
                    f"(1) The deployment specification, "
                    f"(2) The deployment configuration, "
                    f"(3) The deployment snapshot"
                )
                raise DeploymentConflictError(message=msg) from None

            if status_code == status.HTTP_422_UNPROCESSABLE_CONTENT:
                msg = (
                    f"{ErrorPrefix.CREATE.value}. "
                    "The deployment request entity is unprocessable. "
                    "Please ensure the request entity is valid and complete. "
                    "The expected schema is:\n"
                    f"{DEPLOYMENT_CREATE_SCHEMA}"
                )
                raise InvalidContentError(message=msg) from None

            msg = (
                f"{ErrorPrefix.CREATE.value}. "
                "An unexpected error occurred while "
                "creating a deployment in Watsonx Orchestrate."
            )
            raise DeploymentError(message=msg) from None

        except DeploymentSupportError:
            raise
        except DeploymentError:
            raise
        except Exception: # noqa: BLE001
            msg = (
                f"{ErrorPrefix.CREATE.value}. "
                "An unexpected error occurred while "
                "creating a deployment in Watsonx Orchestrate."
            )
            raise DeploymentError(message=msg) from None

        return DeploymentCreateResult(
            id=deployment_response.id,
            **deployment_spec.model_dump(exclude_unset=True),
        )

    async def list_deployment_types(
        self,
        *,
        user_id: UUID | str, # noqa: ARG002 - not used yet, might be, e.g., RBAC
        db: Any, # noqa: ARG002 - not used
    ) -> list[DeploymentType]:
        """List deployment types supported by the provider."""
        return [DeploymentType.AGENT]

    async def list_deployments(
        self,
        *,
        user_id: UUID | str,
        deployment_type: DeploymentType | None = None,
        db: Any,
    ) -> DeploymentList:
        """List deployments from Watsonx Orchestrate."""
        client_manager = await self._get_provider_clients(user_id=user_id, db=db)
        try:
            # Shape source:
            # - SDK: AgentClient.get() proxies GET /agents?include_hidden=true.
            # - API: list endpoint returns list of agent objects.
            deployments: list[DeploymentItem] = []

            if deployment_type in {DeploymentType.AGENT, None}:
                data = client_manager.agent.get()
                deployments = [
                    self._get_deployment_metadata(
                        data=agent,
                        deployment_type=DeploymentType.AGENT,
                    )
                    for agent in data
                ]
            else:
                msg = (
                    f"{ErrorPrefix.LIST.value}"
                    f"watsonx Orchestrate has no such deployment type '{deployment_type}'."
                )
                raise InvalidDeploymentTypeError(message=msg)
        except (ClientAPIException, HTTPException):
            msg = (
                f"{ErrorPrefix.LIST.value}. "
                "Failed to list deployments from Watsonx Orchestrate."
            )
            raise DeploymentError(message=msg) from None
        except Exception: # noqa: BLE001
            msg = (
                f"{ErrorPrefix.LIST.value}. "
                "An unexpected error occurred while listing deployments from Watsonx Orchestrate."
            )
            raise DeploymentError(message=msg) from None

        return DeploymentList(
            deployments=deployments[:5],
            deployment_type=deployment_type,
        )

    async def get_deployment(
        self,
        *,
        user_id: UUID | str,
        deployment_id: str,
        db: Any,
    ) -> DeploymentItem:
        """Get a deployment (agent) from Watsonx Orchestrate."""
        client_manager = await self._get_provider_clients(user_id=user_id, db=db)
        agent = client_manager.agent.get_draft_by_id(deployment_id)
        if not agent:
            msg = f"Deployment '{deployment_id}' not found."
            raise ValueError(msg)
        return self._get_deployment_metadata(
            data=agent,
            deployment_type=DeploymentType.AGENT,
        )

    async def update_deployment(
        self,
        *,
        user_id: UUID | str,
        update_data: DeploymentUpdate,
        db: Any,
    ) -> DeploymentUpdateResult:
        """Update deployment metadata and/or connection binding."""
        deployment_id = str(update_data.id)
        config_id = (
            str(update_data.config.config_id)
            if update_data.config and update_data.config.config_id is not None
            else None
        )
        snapshot_id = (
            update_data.snapshot.add[0]
            if update_data.snapshot and update_data.snapshot.add
            else None
        )
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

        return DeploymentUpdateResult(id=deployment_id)

    async def redeploy_deployment(
        self,
        deployment_id: str,
        *,
        user_id: UUID | str,
        db: Any,
    ) -> DeploymentRedeployResult:
        """Trigger a deployment release for the agent in draft environment."""
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        environment_id = self._resolve_draft_environment_id(clients.agent, deployment_id)
        deployed = clients.agent.deploy(agent_id=deployment_id, environment_id=environment_id)
        return DeploymentRedeployResult(
            id=deployment_id,
            status="success" if deployed else "failed",
            provider_result={"environment_id": environment_id},
        )

    async def clone_deployment(
        self,
        deployment_id: str,
        *,
        user_id: UUID | str,
        db: Any,
    ) -> DeploymentItem:
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

    async def undeploy_deployment(
        self,
        *,
        user_id: UUID | str,
        deployment_id: str,
        db: Any,
    ) -> None:
        """Undeploy a deployment."""
        raise NotImplementedError
        # clients = await self._get_provider_clients(user_id=user_id, db=db)
        # clients.agent.undeploy(deployment_id)

    async def delete_deployment(
        self,
        *,
        user_id: UUID | str,
        deployment_id: str,
        db: Any,
    ) -> DeploymentDeleteResult:
        """Delete only the deployment agent (keep tools/configs reusable)."""
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        try:
            clients.agent.delete(deployment_id)
        except ClientAPIException as e:
            status_code = e.response.status_code
            if status_code == status.HTTP_404_NOT_FOUND:
                msg = f"{ErrorPrefix.DELETE.value}deployment id '{deployment_id}' not found."
                raise DeploymentNotFoundError(msg) from None
        except Exception: # noqa: BLE001
            msg = f"An unexpected error occurred while deleting deployment '{deployment_id}'."
            raise DeploymentError(msg) from None

        return DeploymentDeleteResult(id=deployment_id)

    async def get_deployment_health(
        self,
        deployment_id: str,
        *,
        user_id: UUID | str,
        db: Any,
    ) -> DeploymentHealthResult:
        """Get deployment health for draft agents from the provider."""
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        agent = clients.agent.get_draft_by_id(deployment_id)
        if not agent:
            msg = f"Deployment '{deployment_id}' not found."
            raise ValueError(msg)

        return DeploymentHealthResult(
            id=deployment_id,
            status="healthy",
            provider_data={
                "exists": True,
                "tool_count": len(self._extract_agent_tool_ids(agent)),
            },
        )

    async def create_deployment_config(
        self,
        *,
        config: BaseConfigData,
        user_id: UUID | str,
        db: Any,
    ) -> ConfigResult:
        """Create/update a WXO draft key-value connection config plus runtime credentials."""
        clients = await self._get_provider_clients(user_id=user_id, db=db)

        app_id = config.name

        clients.connections.create(payload={"app_id": app_id})

        runtime_credentials: KeyValueConnectionCredentials = (
            await self._resolve_runtime_credentials(
                environment_variables=config.environment_variables or {},
                user_id=user_id,
                db=db,
            )
        )

        clients.connections.create_credentials(
            app_id=app_id,
            env=ConnectionEnvironment.DRAFT,
            use_app_credentials=False,
            payload={"runtime_credentials": runtime_credentials.model_dump()},
        )

        return ConfigResult(id=app_id)

    async def list_deployment_configs(
        self,
        *,
        user_id: UUID | str,
        db: Any,
    ) -> ConfigListResult:
        """List deployment configs (represented by WXO app_id)."""
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        # Shape source:
        # - SDK: ConnectionsClient.list() returns list[ListConfigsResponse].
        # - API: /connections/applications?include_details=true -> applications[].
        apps = clients.connections.list()
        results: list[ConfigItemResult] = []
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
                ConfigItemResult(
                    id=app_id,
                    name=app_id,
                    provider_data={
                        "app_id": app_id,
                        "environment": ConnectionEnvironment.DRAFT.value,
                        "preference": config.preference.value,
                        "security_scheme": config.security_scheme.value,
                        "credentials_entered": bool(credentials),
                    },
                )
            )
        return ConfigListResult(configs=results)

    async def get_deployment_config(
        self,
        config_id: str,
        *,
        user_id: UUID | str,
        db: Any,
    ) -> ConfigItemResult:
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
        return ConfigItemResult(
            id=config_id,
            name=config_id,
            provider_data={
                "app_id": config_id,
                "environment": ConnectionEnvironment.DRAFT.value,
                "preference": config.preference.value if getattr(config, "preference", None) else None,
                "security_scheme": config.security_scheme.value if getattr(config, "security_scheme", None) else None,
                "credentials_entered": bool(credentials),
            },
        )

    async def update_deployment_config(
        self,
        *,
        update_data: ConfigUpdate,
        user_id: UUID | str,
        db: Any,
    ) -> ConfigResult:
        """Update an existing draft config by app_id."""
        config_id = str(update_data.id)
        existing = await self.get_deployment_config(config_id, user_id=user_id, db=db)

        environment_variables = update_data.environment_variables or {}
        config = BaseConfigData(
            name=config_id,
            description=update_data.description or "",
            environment_variables=environment_variables,
        )
        await self.create_deployment_config(config=config, user_id=user_id, db=db)
        return ConfigResult(id=config_id, provider_result=existing.provider_data)

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

    async def create_snapshots(
        self,
        *,
        user_id: UUID | str,
        snapshot_items: SnapshotItemsCreate,
        db: Any,
    ) -> SnapshotResult:
        """Create an immutable WXO tool snapshot from a Langflow definition."""
        if len(snapshot_items.value) != 1:
            msg = "create_snapshot expects exactly one flow payload."
            raise ValueError(msg)
        # today, only one snapshot is supported

        if snapshot_items.artifact_type == ArtifactType.FLOW:
            created_snapshot = await self._create_langflow_flow_tool(
                flow_payload=snapshot_items.value[0],
                user_id=user_id,
                db=db,
            )

        return SnapshotResult(ids=[created_snapshot])

    async def list_snapshots(
        self,
        *,
        user_id: UUID | str,
        artifact_type: ArtifactType | None = None,
        db: Any,
    ) -> SnapshotListResult:
        """List WXO tool snapshots."""
        clients = await self._get_provider_clients(user_id=user_id, db=db)

        snapshots: list[SnapshotItem]

        if artifact_type == ArtifactType.FLOW or artifact_type is None:
            # Shape source:`
            # - SDK: ToolClient.get() proxies GET /tools.
            # - API: tools list endpoint returns list of tool objects.
            tools = clients.tool.get()
            snapshots = [ # unfortunately, the API does not support filtering by binding type
                SnapshotItem(
                    id=tool.get("id"),
                    name=tool.get("name"),
                    description=tool.get("description"),
                )
                for tool in tools
                if tool.get("binding", {}).get("langflow", None)
            ]
        else:
            msg = f"Unsupported artifact type: {artifact_type}"
            raise ValueError(msg)

        return SnapshotListResult(
            snapshots=snapshots,
            artifact_type=artifact_type or "all",
        )

    async def get_snapshot(
        self,
        *,
        user_id: UUID | str,
        snapshot_id: str,
        db: Any,
    ) -> SnapshotItem:
        """Get a WXO tool snapshot."""
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        tool = clients.tool.get_draft_by_id(snapshot_id)
        if not tool:
            msg = f"Snapshot '{snapshot_id}' not found."
            raise ValueError(msg)
        return self._map_tool_to_snapshot(tool)

    async def delete_snapshot(
        self,
        *,
        user_id: UUID | str,
        snapshot_id: str,
        db: Any,
    ) -> None:
        """Delete a WXO tool snapshot."""
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        clients.tool.delete(snapshot_id)

    async def teardown(self) -> None:
        """Teardown provider-specific resources."""
        return

    async def _create_agent_deployment(
        self,
        user_id: UUID | str,
        tool_ids: list[str],
        data: BaseDeploymentData,
        db: Any,
    ) -> AgentUpsertResponse:
        """Create an agent deployment."""
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        payload = self._build_agent_payload(
            data=data,
            tool_ids=tool_ids,
        )
        return clients.agent.create(payload)

    def _create_mcp_deployment(self):
        pass

    async def _process_config(
        self,
        user_id: UUID | str,
        db: Any,
        config: ConfigItem | None,
    ) -> str | None:
        """Set the config for the deployment."""
        if config is None:
            return None

        app_id: str | None = None

        if config.format == ConfigFormat.REFERENCE_ID:
            app_id = config.value
        elif config.format == ConfigFormat.RAW_PAYLOAD:
            app_id = config.value.name
            await self.create_deployment_config(
                config=config.value,
                user_id=user_id,
                db=db,
            )

        return app_id

    async def _process_flow_snapshots(
        self,
        user_id: UUID | str,
        app_id: str | None,
        snapshots: SnapshotItems,
        db: Any,
    ) -> list[str]:
        """Process flow snapshots."""
        if len(snapshots.value) > 1:
            msg = "create_snapshot expects exactly one snapshot payload."
            raise ValueError(msg)
        # today, only one snapshot is supported

        tool_ids: list[str]

        snapshot_item = snapshots.value[0]
        # the schema guarantees at least one Snapshot item is present

        if snapshots.format == SnapshotFormat.REFERENCE_ID:
            tool_ids = [snapshot_item]
        elif snapshots.format == SnapshotFormat.RAW_PAYLOAD:
            tool_ids = [
                await self._create_langflow_flow_tool(
                    flow_payload=snapshot_item,
                    config_id=app_id,
                    user_id=user_id,
                    db=db,
                )
            ]

        return tool_ids

    async def _get_provider_clients(
        self,
        *,
        user_id: UUID | str,
        db: Any,
    ) -> WxOClient:
        if self._client_manager is not None:
            return self._client_manager

        credentials: WxOCredentials = await self._resolve_wxo_client_credentials(
            user_id=user_id, db=db
        )

        instance_url: str = credentials.instance_url

        authenticator: Authenticator = self.get_authenticator(
            instance_url=instance_url,
            api_key=credentials.api_key
,
        )

        self._client_manager = WxOClient(
            tool=ToolClient(base_url=instance_url, authenticator=authenticator),
            connections=ConnectionsClient(base_url=instance_url, authenticator=authenticator),
            agent=AgentClient(base_url=instance_url, authenticator=authenticator),
        )

        return self._client_manager

    async def _resolve_wxo_client_credentials(
        self,
        *,
        user_id: UUID | str,
        db: Any,
    ) -> Credentials:
        """Resolve Watsonx Orchestrate client credentials from environment variables."""
        try:
            instance_url = await self._resolve_variable_value(
                WxOUserKey.INSTANCE_URL.value, user_id=user_id, db=db
            )

            api_key = await self._resolve_variable_value(
                WxOUserKey.API_KEY.value, user_id=user_id, db=db
            )

        # please ensure that when raising or re-raising an exception,
        # that the message does not leak sensitive information
        except CredentialResolutionError: # custom exception managed by us , so we re-raise
            raise
        except Exception: # noqa: BLE001
            msg = (
                "An unexpected error occurred while resolving "
                "Watsonx Orchestrate client credentials."
                )
            raise CredentialResolutionError(message=msg) from None

        return WxOCredentials(instance_url=instance_url, api_key=api_key)

    async def _resolve_runtime_credentials(
        self,
        *,
        user_id: UUID | str,
        environment_variables: dict[EnvVarKey, EnvVarValue],
        db: Any,
    ) -> KeyValueConnectionCredentials:
        """Resolve runtime credentials from environment variables."""
        resolved: dict[str, str] = {}
        for credential_key, variable_name in environment_variables.items():
            resolved[credential_key] = (
                await self._resolve_variable_value(
                    variable_name,
                    user_id=user_id,
                    db=db,
                )
            )
        return KeyValueConnectionCredentials(resolved)

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
        msg = (
            "Failed to find a necessary credential for the "
            "watsonX Orchestrate deployment provider. "
            "Please ensure all credentials are provided and valid."
            )
        raise CredentialResolutionError(message=msg)

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
        data: BaseDeploymentData,
        tool_ids: list[str],
    ) -> dict[str, Any]:
        return {
            # Name must start with a letter and contain only alphanumeric characters and underscores
            # WxO will raise an error if the name is not valid. So we won't validate it here.
            "name": data.name,
            "description": data.description,
            "tools": tool_ids,
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
        deployment_type: DeploymentType,
        provider_raw: bool = False, # noqa: FBT001,FBT002
    ) -> DeploymentItem:
        result = {
            "id": data.get("id"),
            "type": deployment_type.value,
            "name": data.get("name"),
            "description": data.get("description"),
        }
        if provider_raw:
            result["provider_data"] = data

        return DeploymentItem(
            **result
        )

    def _map_tool_to_snapshot(self, tool: dict[str, Any]) -> SnapshotItem:
        # snapshot_type is adapter-level terminology, not provider binding type.
        return SnapshotItem(
            id=tool.get("id"),
            name=tool.get("name"),
            description=tool.get("description"),
        )


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

    def _require_tool_id(self, tool_response: dict[str, Any]) -> str:
        tool_id = tool_response.get("id")
        if not tool_id:
            msg = "WXO did not return a tool id for snapshot creation."
            raise ValueError(msg)
        return tool_id

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

    async def _create_langflow_flow_tool(
        self,
        *,
        user_id: UUID | str,
        config_id: str | None = None,
        flow_payload: BaseFlowArtifact,
        db: Any,
    ) -> str:
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        flow_definition = flow_payload.data

        connections: dict[str, str] = {}
        if config_id is not None:
            app_id = self._require_non_empty_string(
                config_id,
                field_name="config_id",
                error_message="Snapshot binding requires non-empty 'config_id'.",
            )
            connection = clients.connections.get_draft_by_app_id(app_id=app_id)
            if not connection:
                msg = f"Connection '{app_id}' not found."
                raise ValueError(msg)
            connections = {app_id: connection.connection_id}

        tool = create_langflow_tool(
            tool_definition=flow_definition,
            connections=connections,
            show_details=False,
        )

        tool_response = clients.tool.create(
            tool.__tool_spec__.model_dump(mode="json", exclude_unset=True, exclude_none=True, by_alias=True)
        )
        tool_id = self._require_tool_id(tool_response)

        artifact = self._build_langflow_artifact_bytes(tool=tool, flow_definition=flow_definition)
        self._upload_tool_artifact_bytes(clients.tool, tool_id=tool_id, artifact_bytes=artifact)

        return tool_id

    @staticmethod
    def _extract_error_detail(response_text: str) -> str | dict:
        """Extract a human-readable error detail from a ClientAPIException response.

        The response body may contain a ``detail`` value that is a string, a dict
        with a ``msg`` key, or a list of such dicts.  This helper normalises all
        three shapes into a single value suitable for inclusion in an error message.
        """
        detail = json.loads(response_text).get("detail")
        if detail and isinstance(detail, list):
            detail = detail[0]
        if isinstance(detail, dict):
            detail = detail.get("msg") or detail
        return detail

    @staticmethod
    def get_authenticator(instance_url: str, api_key: str) -> None:
        """Set the authenticator for the Watsonx Orchestrate API."""
        if ".cloud.ibm.com" in instance_url:
            from ibm_cloud_sdk_core.authenticators import IAMAuthenticator

            return IAMAuthenticator(apikey=api_key, url=WxOAuthURL.IBM_IAM.value)
        elif ".ibm.com" in instance_url: # noqa: RET505 - explicitness
            from ibm_cloud_sdk_core.authenticators import MCSPAuthenticator

            return MCSPAuthenticator(apikey=api_key, url=WxOAuthURL.MCSP.value)

        msg = f"Could not determine authentication scheme for instance URL: {instance_url}"
        raise AuthSchemeError(message=msg)
