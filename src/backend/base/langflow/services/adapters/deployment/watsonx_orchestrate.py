"""Watsonx Orchestrate deployment adapter."""

from __future__ import annotations

import asyncio
import importlib.metadata as md
import io
import json
import re
import secrets
import zipfile
from contextlib import suppress
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from cachetools import func
from fastapi import HTTPException, status
from ibm_watsonx_orchestrate_clients.agents.agent_client import AgentClient, AgentUpsertResponse
from ibm_watsonx_orchestrate_clients.connections.connections_client import (
    ConnectionsClient,
    GetConnectionResponse,
)
from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException, ToolClient
from ibm_watsonx_orchestrate_core.types.connections import (
    ConnectionConfiguration,
    ConnectionEnvironment,
    ConnectionPreference,
    ConnectionSecurityScheme,
    KeyValueConnectionCredentials,
)
from ibm_watsonx_orchestrate_core.types.tools.langflow_tool import LangflowTool, create_langflow_tool
from lfx.services.adapters.deployment.base import BaseDeploymentService
from lfx.services.adapters.deployment.exceptions import (
    AuthSchemeError,
    CredentialResolutionError,
    DeploymentConflictError,
    DeploymentError,
    DeploymentNotFoundError,
    InvalidContentError,
    InvalidDeploymentOperationError,
    InvalidDeploymentTypeError,
)
from lfx.services.adapters.deployment.schema import (
    BaseDeploymentData,
    BaseFlowArtifact,
    ConfigItem,
    DeploymentConfig,
    DeploymentCreate,
    DeploymentCreateResult,
    DeploymentDeleteResult,
    DeploymentDuplicateResult,
    DeploymentGetResult,
    DeploymentListParams,
    DeploymentListResult,
    DeploymentListTypesResult,
    DeploymentStatusResult,
    DeploymentType,
    DeploymentUpdate,
    DeploymentUpdateResult,
    EnvVarKey,
    EnvVarSource,
    EnvVarValueSpec,
    ExecutionCreate,
    ExecutionCreateResult,
    ExecutionStatusResult,
    IdLike,
    ItemResult,
    RedeployResult,
    SnapshotItems,
)
from lfx.services.adapters.registry import register_adapter
from lfx.services.adapters.schema import AdapterType
from lfx.utils.flow_requirements import generate_requirements_from_flow

from langflow.services.adapters.deployment.context import get_current_deployment_provider_id
from langflow.services.auth import utils as auth_utils
from langflow.services.database.models.deployment_provider_account.crud import (
    get_provider_account_by_id,
)
from langflow.services.deps import get_settings_service, get_variable_service
from langflow.utils.version import get_version_info

if TYPE_CHECKING:
    from uuid import UUID

    from ibm_cloud_sdk_core.authenticators import Authenticator
    from lfx.services.settings.service import SettingsService


DEFAULT_LANGFLOW_RUNNER_MODULES = {"lfx", "lfx-nightly"}
DEFAULT_ADAPTER_SNAPSHOT_TYPE = "langflow"
DEFAULT_ADAPTER_DEPLOYMENT_TYPE = "agent"
SUPPORTED_ADAPTER_DEPLOYMENT_TYPES = {DEFAULT_ADAPTER_DEPLOYMENT_TYPE}
CREATE_MAX_RETRIES = 3
ROLLBACK_MAX_RETRIES = 5
RETRY_INITIAL_DELAY_SECONDS = 0.5
RANDOM_PREFIX_LENGTH_RANGE = range(6, 11)

_WXO_SANITIZE_RE = re.compile(r"[^a-zA-Z0-9_]")
_WXO_TRANSLATE = str.maketrans({" ": "_", "-": "_"})


class WxOAuthURL(str, Enum):
    MCSP = "https://iam.platform.saas.ibm.com"
    IBM_IAM = "https://iam.cloud.ibm.com"


@dataclass(slots=True)
class WxOClient:
    instance_url: str
    authenticator: Authenticator
    tool: ToolClient
    connections: ConnectionsClient
    agent: AgentClient


@dataclass(slots=True)
class WxOCredentials:
    instance_url: str
    api_key: str


ERROR_PREFIX = "An error occured while"
ERROR_SUFFIX_IN = "in Watsonx Orchestrate."


class ErrorPrefix(str, Enum):
    CREATE = f"{ERROR_PREFIX} creating a deployment {ERROR_SUFFIX_IN}"
    LIST = f"{ERROR_PREFIX} listing deployments {ERROR_SUFFIX_IN}"
    GET = f"{ERROR_PREFIX} getting a deployment {ERROR_SUFFIX_IN}"
    UPDATE = f"{ERROR_PREFIX} updating a deployment {ERROR_SUFFIX_IN}"
    REDEPLOY = f"{ERROR_PREFIX} redeploying a deployment {ERROR_SUFFIX_IN}"
    CLONE = f"{ERROR_PREFIX} cloning a deployment {ERROR_SUFFIX_IN}"
    DELETE = f"{ERROR_PREFIX} deleting a deployment {ERROR_SUFFIX_IN}"
    HEALTH = f"{ERROR_PREFIX} getting a deployment health {ERROR_SUFFIX_IN}"
    CREATE_CONFIG = f"{ERROR_PREFIX} creating a deployment config {ERROR_SUFFIX_IN}"
    LIST_CONFIGS = f"{ERROR_PREFIX} listing deployment configs {ERROR_SUFFIX_IN}"
    GET_CONFIG = f"{ERROR_PREFIX} getting a deployment config {ERROR_SUFFIX_IN}"
    UPDATE_CONFIG = f"{ERROR_PREFIX} updating a deployment config {ERROR_SUFFIX_IN}"
    DELETE_CONFIG = f"{ERROR_PREFIX} deleting a deployment config {ERROR_SUFFIX_IN}"


# NOTE: this key must match the value of the provider_key column
# in the deployment_provider_account table.
_WATSONX_ORCHESTRATE_DEPLOYMENT_ADAPTER_KEY = "watsonx-orchestrate"


@register_adapter(AdapterType.DEPLOYMENT, _WATSONX_ORCHESTRATE_DEPLOYMENT_ADAPTER_KEY)
class WatsonxOrchestrateDeploymentService(BaseDeploymentService):
    """Deployment adapter for Watsonx Orchestrate.

    Mapping used by this adapter:
    - deployment -> WXO agent bound to exactly one connection app_id and many tools
    - snapshot -> WXO tool (langflow binding) and "immutable" once created
    - config -> WXO connection configuration (+ credentials), keyed by app_id
    """

    name = "deployment_service"
    provider_name = _WATSONX_ORCHESTRATE_DEPLOYMENT_ADAPTER_KEY

    def __init__(self, settings_service: SettingsService | None = None):
        super().__init__()
        if settings_service is None:
            settings_service = get_settings_service()
        if settings_service is None:
            msg = "Settings service is not available."
            raise RuntimeError(msg)
        self.settings_service = settings_service
        # TODO: LRU + TTL hybrid cache
        self._client_managers: dict[str, WxOClient] = {}
        self.set_ready()

    async def create(
        self,
        *,
        user_id: IdLike,
        payload: DeploymentCreate,
        db: Any,
    ) -> DeploymentCreateResult:
        """Create a deployment in Watsonx Orchestrate."""
        # The wxO API does not have an endpoint to create
        # a connection, tool, and agent atomically.
        # We have to make a separate api call for each resource.
        # --
        # If one of these resources is created successfully
        # but the next one fails, then we end up with orphaned resources.
        #     - We thus use a best-effort creation and rollback strategy:
        #       Attempt to create each resource with retries.
        #       If the creation of one resource fails,
        #       then attempt to delete all previously created
        #       resources with retries.
        # --
        # --
        # A common failure is when the name of a resource already exists.
        # This is true for connections, tools, and agents.
        #     - We thus use a best-effort mitigation strategy:
        #       Check if the names of the
        #       connection, tools, and agent already exist.
        #       If any of the names exist, then we
        #       fail early with a DeploymentConflictError.
        #       However, this strategy introduces a
        #       read-before-write race condition,
        #       which we attempt to work around by
        #       generating a random prefix to attach
        #       to the name of each created resource.
        # --
        # --
        deployment_response: AgentUpsertResponse | None = None
        created_config_id: str | None = None
        created_snapshot_ids: list[str] = []
        created_agent_id: str | None = None
        created_tool_ids: list[str] = []
        created_app_id: str | None = None
        clients: WxOClient | None = None
        try:
            deployment_spec: BaseDeploymentData = payload.spec
            normalized_deployment_name = self._validate_wxo_name(deployment_spec.name)
            self._validate_config_create_input(payload.config)

            if deployment_spec.type != DeploymentType.AGENT:
                msg = (
                    f"{ErrorPrefix.CREATE.value}"
                    f"Deployment type '{deployment_spec.type.value}' "
                    "is not supported for watsonx Orchestrate."
                )
                raise InvalidDeploymentTypeError(message=msg)

            clients = await self._get_provider_clients(user_id=user_id, db=db)

            random_length = secrets.choice(RANDOM_PREFIX_LENGTH_RANGE)
            random_prefix = f"lf_{uuid4().hex[:random_length]}_"
            prefixed_deployment_name = f"{random_prefix}{normalized_deployment_name}"

            prefixed_app_id = self._resolve_create_app_id(
                prefixed_deployment_name=prefixed_deployment_name,
                config=payload.config,
            )
            tool_name_prefix = f"{prefixed_deployment_name}_"
            planned_tool_names = self._build_snapshot_tool_names(
                snapshots=payload.snapshot,
                tool_name_prefix=tool_name_prefix,
            )

            # there is a read-before-write race here
            # but locking locally is not enough
            # so we use a random prefix to avoid conflicts
            self._assert_create_resources_available(
                clients=clients,
                deployment_name=prefixed_deployment_name,
                app_id=prefixed_app_id,
                snapshot_tool_names=planned_tool_names,
            )

            try:
                created_app_id = prefixed_app_id
                await self._retry_create(
                    lambda: self._process_config(
                        user_id=user_id,
                        db=db,
                        deployment_name=prefixed_app_id,
                        config=payload.config,
                    )
                )
                created_config_id = (
                    prefixed_app_id if payload.config is not None and payload.config.raw_payload is not None else None
                )

                if payload.snapshot:
                    created_snapshot_ids = await self._retry_create(
                        lambda: self._process_flow_snapshots(
                            user_id=user_id,
                            app_id=prefixed_app_id,
                            snapshots=payload.snapshot,
                            db=db,
                            tool_name_prefix=tool_name_prefix,
                        )
                    )
                    created_tool_ids = list(created_snapshot_ids)
                    if created_tool_ids:
                        connection = self._validate_connection(clients.connections, app_id=prefixed_app_id)
                        self._sync_langflow_tool_connections(
                            clients=clients,
                            tool_ids=created_tool_ids,
                            config_id=prefixed_app_id,
                            connection_id=connection.connection_id,
                        )

                deployment_spec = deployment_spec.model_copy(deep=True)
                deployment_spec.name = prefixed_deployment_name
                deployment_response = await self._retry_create(
                    lambda: self._create_agent_deployment(
                        data=deployment_spec,
                        tool_ids=created_tool_ids,
                        user_id=user_id,
                        db=db,
                    )
                )
                created_agent_id = deployment_response.id
            except Exception:
                await self._rollback_created_resources(
                    clients=clients,
                    agent_id=created_agent_id,
                    tool_ids=created_tool_ids,
                    app_id=created_app_id,
                )
                raise

        except (ClientAPIException, HTTPException) as exc:
            if isinstance(exc, ClientAPIException):
                status_code = exc.response.status_code
                error_detail = self._extract_error_detail(exc.response.text)
            else:
                status_code = exc.status_code
                error_detail = self._extract_error_detail(str(exc.detail))
            if status_code == status.HTTP_409_CONFLICT:
                msg = (
                    f"{ErrorPrefix.CREATE.value}. "
                    "One or more resources already exist. "
                    "Please ensure the names and/or ids of the "
                    "following resources to be unique: "
                    "(1) The deployment specification, "
                    "(2) The deployment configuration, "
                    "(3) The deployment snapshot. "
                    f"error details: {error_detail}"
                )
                raise DeploymentConflictError(message=msg) from None
            if status_code == status.HTTP_422_UNPROCESSABLE_CONTENT:
                msg = (
                    f"{ErrorPrefix.CREATE.value}. "
                    "The deployment request entity is unprocessable. "
                    "Please ensure the request entity is valid and complete. "
                    f"error details: {error_detail}"
                )
                raise InvalidContentError(message=msg) from None
            msg = (
                f"{ErrorPrefix.CREATE.value}. "
                "An unexpected error occurred while "
                "creating a deployment in Watsonx Orchestrate. "
                f"error details: {error_detail}"
            )
            raise DeploymentError(message=msg, error_code="deployment_error") from None
        except (
            DeploymentConflictError,
            DeploymentError,
            InvalidContentError,
            InvalidDeploymentOperationError,
            InvalidDeploymentTypeError,
        ):
            raise
        except Exception as e:
            msg = (
                f"{ErrorPrefix.CREATE.value}. "
                "An unexpected error occurred while "
                "creating a deployment in Watsonx Orchestrate. "
                f"error details: {e}"
            )
            raise DeploymentError(message=msg, error_code="deployment_error") from e

        if deployment_response is None:
            msg = (
                f"{ErrorPrefix.CREATE.value}. "
                "An unexpected error occurred while "
                "creating a deployment in Watsonx Orchestrate. "
                "error details: Deployment response was empty."
            )
            raise DeploymentError(message=msg, error_code="deployment_error")

        return DeploymentCreateResult(
            id=deployment_response.id,
            config_id=created_config_id,
            snapshot_ids=created_snapshot_ids,
            **deployment_spec.model_dump(exclude_unset=True),
        )

    async def list_types(
        self,
        *,
        user_id: IdLike,  # noqa: ARG002 - not used yet, might be, e.g., RBAC
        db: Any,  # noqa: ARG002 - not used
    ) -> DeploymentListTypesResult:
        """List deployment types supported by the provider."""
        return DeploymentListTypesResult(deployment_types=[DeploymentType.AGENT])

    async def list(
        self,
        *,
        user_id: IdLike,
        db: Any,
        params: DeploymentListParams | None = None,
    ) -> DeploymentListResult:
        """List deployments from Watsonx Orchestrate."""
        client_manager = await self._get_provider_clients(user_id=user_id, db=db)
        try:
            deployments: list[ItemResult] = []
            deployment_types = params.deployment_types or [] if params else []
            unsupported_types = [dtype for dtype in deployment_types if dtype is not DeploymentType.AGENT]
            if unsupported_types:
                invalid_values = ", ".join(dtype.value for dtype in unsupported_types)
                msg = f"{ErrorPrefix.LIST.value}watsonx Orchestrate has no such deployment type(s): '{invalid_values}'."
                raise InvalidDeploymentTypeError(message=msg)

            deployments = [
                self._get_deployment_metadata(
                    data=agent,
                    deployment_type=DeploymentType.AGENT,
                    provider_data={
                        "snapshot_ids": self._extract_agent_tool_ids(agent),
                        "mode": self._derive_agent_mode(agent),
                    },
                )
                for agent in client_manager.agent._get(  # noqa: SLF001
                    "/agents",
                    params=params.provider_params if params else None,
                )
            ]
        except (ClientAPIException, HTTPException) as exc:
            if isinstance(exc, ClientAPIException):
                error_detail = self._extract_error_detail(getattr(exc.response, "text", ""))
            else:
                error_detail = self._extract_error_detail(str(exc.detail))
            msg = (
                f"{ErrorPrefix.LIST.value}. "
                "Failed to list deployments from Watsonx Orchestrate. "
                f"error details: {error_detail}"
            )
            raise DeploymentError(message=msg, error_code="deployment_error") from None
        except Exception as exc:  # noqa: BLE001
            msg = (
                f"{ErrorPrefix.LIST.value}. "
                "An unexpected error occurred while listing deployments from Watsonx Orchestrate. "
                f"error details: {exc}"
            )
            raise DeploymentError(message=msg, error_code="deployment_error") from None

        return DeploymentListResult(
            deployments=deployments,
        )

    async def get(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        db: Any,
    ) -> DeploymentGetResult:
        """Get a deployment (agent) from Watsonx Orchestrate."""
        client_manager = await self._get_provider_clients(user_id=user_id, db=db)
        agent = client_manager.agent.get_draft_by_id(deployment_id)
        if not agent:
            msg = f"Deployment '{deployment_id}' not found."
            raise ValueError(msg)
        return self._get_deployment_detail_metadata(
            data=agent,
            deployment_type=DeploymentType.AGENT,
        )

    async def update(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        payload: DeploymentUpdate,
        db: Any,
    ) -> DeploymentUpdateResult:
        """Update deployment metadata, snapshot bindings, and/or connection binding."""
        deployment_id = str(deployment_id).strip()
        if not deployment_id:
            msg = "'deployment_id' must not be empty or whitespace."
            raise ValueError(msg)
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        current = clients.agent.get_draft_by_id(deployment_id)
        if not current:
            msg = f"Deployment '{deployment_id}' not found."
            raise ValueError(msg)

        update_payload: dict[str, Any] = {}
        if payload.spec:
            spec_updates = payload.spec.model_dump(exclude_unset=True)
            if "name" in spec_updates:
                normalized_name = self._validate_wxo_name(spec_updates["name"])
                update_payload["name"] = normalized_name
                update_payload["display_name"] = normalized_name
            if "description" in spec_updates:
                update_payload["description"] = spec_updates["description"]

        current_tool_ids = self._extract_agent_tool_ids(current)
        if payload.snapshot:
            tool_ids_to_remove = set(payload.snapshot.remove or [])
            updated_tool_ids = [tool_id for tool_id in current_tool_ids if tool_id not in tool_ids_to_remove]
            for tool_id in payload.snapshot.add or []:
                if tool_id not in updated_tool_ids:
                    updated_tool_ids.append(tool_id)
            if updated_tool_ids != current_tool_ids:
                update_payload["tools"] = updated_tool_ids

        if payload.config is not None and "config_id" in payload.config.model_fields_set:
            config_id = str(payload.config.config_id) if payload.config.config_id is not None else None
            if config_id is None:
                msg = (
                    "Unbinding deployment configuration/connection via patch is not allowed for "
                    "watsonx Orchestrate deployments."
                )
                raise DeploymentConflictError(message=msg)
            msg = (
                "Replacing deployment configuration/connection via patch is not allowed for "
                "watsonx Orchestrate deployments."
            )
            raise DeploymentConflictError(message=msg)

        if update_payload:
            clients.agent.update(deployment_id, update_payload)

        return DeploymentUpdateResult(id=deployment_id)

    async def redeploy(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        db: Any,
    ) -> RedeployResult:
        """Trigger a deployment redeployment for the agent in draft environment."""
        raise NotImplementedError

    async def duplicate(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        db: Any,
    ) -> DeploymentDuplicateResult:
        """Duplicate an existing deployment."""
        _ = user_id, deployment_id, db
        raise NotImplementedError

    async def undeploy_deployment(
        self,
        *,
        user_id: UUID | str,
        deployment_id: str,
        db: Any,
    ) -> None:
        """Undeploy a deployment."""
        raise NotImplementedError

    async def delete(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        db: Any,
    ) -> DeploymentDeleteResult:
        """Delete only the deployment agent (keep tools/configs reusable)."""
        deployment_id_str = str(deployment_id)
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        try:
            clients.agent.delete(deployment_id_str)
        except ClientAPIException as e:
            status_code = e.response.status_code
            if status_code == status.HTTP_404_NOT_FOUND:
                msg = f"{ErrorPrefix.DELETE.value}deployment id '{deployment_id_str}' not found."
                raise DeploymentNotFoundError(msg) from None
        except Exception:  # noqa: BLE001
            msg = f"An unexpected error occurred while deleting deployment '{deployment_id_str}'."
            raise DeploymentError(msg, error_code="deployment_error") from None

        return DeploymentDeleteResult(id=deployment_id_str)

    async def get_status(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        db: Any,
    ) -> DeploymentStatusResult:
        """Get deployment health directly from WXO release status endpoint."""
        deployment_id_str = str(deployment_id)
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        agent = clients.agent.get_draft_by_id(deployment_id_str)
        if not agent:
            # Fallback for deployments not currently in draft context.
            all_agents = clients.agent.get(ids=[deployment_id_str])
            if not all_agents:
                msg = f"Deployment '{deployment_id_str}' not found."
                raise ValueError(msg)
            agent = all_agents[0]

        environment_id = self._resolve_health_environment_id(clients.agent, deployment_id=deployment_id_str)
        provider_status = self._fetch_agent_release_status(
            clients.agent,
            deployment_id=deployment_id_str,
            environment_id=environment_id,
        )
        normalized_status = self._normalize_release_status(provider_status)

        return DeploymentStatusResult(
            id=deployment_id_str,
            provider_data={
                "status": normalized_status,
                "environment_id": environment_id,
                "mode": self._derive_agent_mode(agent),
                "provider_status": provider_status,
            },
        )

    async def create_execution(
        self,
        *,
        user_id: IdLike,
        payload: ExecutionCreate,
        db: Any,
    ) -> ExecutionCreateResult:
        """Create a provider-agnostic deployment execution."""
        deployment_id = str(payload.deployment_id).strip()
        if not deployment_id:
            msg = "'deployment_id' must not be empty or whitespace."
            raise ValueError(msg)

        clients = await self._get_provider_clients(user_id=user_id, db=db)
        draft_agent = clients.agent.get_draft_by_id(deployment_id)
        if not draft_agent:
            live_agents = clients.agent.get_drafts_by_ids([deployment_id])
            if not live_agents:
                msg = f"Deployment '{deployment_id}' not found."
                raise DeploymentNotFoundError(message=msg)

        provider_data = payload.provider_data if isinstance(payload.provider_data, dict) else {}
        query_suffix = self._build_orchestrate_runs_query(provider_data)
        run_payload = self._build_orchestrate_run_payload(
            provider_data=provider_data,
            deployment_id=deployment_id,
        )

        try:
            provider_result = clients.agent._post(  # noqa: SLF001
                f"/runs{query_suffix}",
                data=run_payload,
            )
        except ClientAPIException as exc:
            status_code = exc.response.status_code
            if status_code == status.HTTP_404_NOT_FOUND:
                msg = f"Deployment '{deployment_id}' was not found in Watsonx Orchestrate."
                raise DeploymentNotFoundError(message=msg) from None
            if status_code == status.HTTP_422_UNPROCESSABLE_CONTENT:
                msg = (
                    "Deployment execution request is unprocessable by Watsonx Orchestrate. "
                    f"{self._extract_error_detail(exc.response.text)}"
                )
                raise InvalidContentError(message=msg) from None

            msg = "An error occurred while creating a deployment execution in Watsonx Orchestrate."
            raise DeploymentError(message=msg, error_code="deployment_error") from None
        except Exception as exc:
            msg = "An unexpected error occurred while creating a deployment execution in Watsonx Orchestrate."
            raise DeploymentError(message=msg, error_code="deployment_error") from exc

        return ExecutionCreateResult(
            execution_id=str(provider_result.get("run_id") or "").strip() or None,
            deployment_id=deployment_id,
            provider_result=provider_result,
        )

    async def get_execution(
        self,
        *,
        user_id: IdLike,
        execution_id: IdLike,
        db: Any,
    ) -> ExecutionStatusResult:
        """Get provider-agnostic deployment execution state/output."""
        run_id = str(execution_id).strip()
        if not run_id:
            msg = "'execution_id' must not be empty or whitespace."
            raise ValueError(msg)

        clients = await self._get_provider_clients(user_id=user_id, db=db)
        provider_result: dict[str, Any] = {"run_id": run_id}

        status_payload = self._fetch_execution_status_payload(
            clients.agent,
            run_id=run_id,
        )
        if status_payload is not None:
            provider_result["status_payload"] = status_payload

        normalized_status = self._normalize_execution_status(status_payload)
        output: str | dict[str, Any] | None = self._extract_execution_output(status_payload)
        if output is None and normalized_status in {"completed", "success", "succeeded"}:
            output = self._fetch_execution_message_output(
                clients.agent,
                provider_input=provider_result,
            )
        provider_result["status"] = normalized_status
        if output is not None:
            provider_result["output"] = output

        resolved_deployment_id = ""
        if isinstance(status_payload, dict):
            resolved_deployment_id = str(
                status_payload.get("agent_id") or status_payload.get("deployment_id") or ""
            ).strip()
        if not resolved_deployment_id:
            msg = "Execution status payload did not include a deployment identifier."
            raise InvalidContentError(message=msg)

        return ExecutionStatusResult(
            execution_id=run_id,
            deployment_id=resolved_deployment_id,
            provider_result=provider_result or None,
        )

    async def materialize_snapshots(
        self,
        *,
        user_id: IdLike,
        raw_payloads: list[BaseFlowArtifact],
        config_id: str | None,
        db: Any,
    ) -> list[str]:
        """Create provider snapshots from flow payloads for internal API orchestration."""
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        random_length = secrets.choice(RANDOM_PREFIX_LENGTH_RANGE)
        tool_name_prefix = f"lf_{uuid4().hex[:random_length]}_"
        connections = self._resolve_snapshot_connections(
            connections_client=clients.connections,
            config_id=config_id,
        )
        return await self._create_and_upload_wxo_flow_tools(
            tool_client=clients.tool,
            flow_payloads=raw_payloads,
            connections=connections,
            app_id=config_id,
            tool_name_prefix=tool_name_prefix,
        )

    async def _create_config(
        self,
        *,
        config: DeploymentConfig,
        user_id: IdLike,
        db: Any,
    ) -> str:
        """Create/update a WXO draft key-value connection config plus runtime credentials."""
        clients = await self._get_provider_clients(user_id=user_id, db=db)

        app_id = self._validate_wxo_name(config.name)

        clients.connections.create(payload={"app_id": app_id})

        wxo_config = ConnectionConfiguration(
            app_id=app_id,
            environment=ConnectionEnvironment.DRAFT,
            preference=ConnectionPreference.TEAM,
            security_scheme=ConnectionSecurityScheme.KEY_VALUE,
        )
        clients.connections.create_config(
            app_id=app_id, payload=wxo_config.model_dump(exclude_unset=True, exclude_none=True)
        )

        runtime_credentials: KeyValueConnectionCredentials = await self._resolve_runtime_credentials(
            environment_variables=config.environment_variables or {},
            user_id=user_id,
            db=db,
        )

        clients.connections.create_credentials(
            app_id=app_id,
            env=ConnectionEnvironment.DRAFT,
            use_app_credentials=False,
            payload={"runtime_credentials": runtime_credentials.model_dump()},
        )

        return app_id

    async def teardown(self) -> None:
        """Teardown provider-specific resources."""
        self._client_managers.clear()

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
        deployment_name: str,
        config: ConfigItem | None,
    ) -> str:
        """Create and bind deployment config using deployment name as app_id."""
        self._validate_config_create_input(config)

        environment_variables = None
        description = ""

        if config and config.raw_payload:
            environment_variables = config.raw_payload.environment_variables
            description = config.raw_payload.description or ""

        config_payload = DeploymentConfig(
            name=deployment_name,
            description=description,
            environment_variables=environment_variables,
        )
        await self._create_config(
            config=config_payload,
            user_id=user_id,
            db=db,
        )

        return deployment_name

    def _validate_config_create_input(self, config: ConfigItem | None) -> None:
        if config and config.reference_id is not None:
            msg = (
                "Config reference binding is not supported for deployment creation in "
                "watsonx Orchestrate. Provide raw config payload or omit config."
            )
            raise InvalidDeploymentOperationError(message=msg)

    def _resolve_create_app_id(
        self,
        *,
        prefixed_deployment_name: str,
        config: ConfigItem | None,
    ) -> str:
        self._validate_config_create_input(config)
        if config is None or config.raw_payload is None:
            return f"{prefixed_deployment_name}_app_id"

        normalized_config_name = self._validate_wxo_name(config.raw_payload.name)
        return f"{prefixed_deployment_name}_{normalized_config_name}_app_id"

    def _assert_create_resources_available(
        self,
        *,
        clients: WxOClient,
        deployment_name: str,
        app_id: str,
        snapshot_tool_names: list[str] | None = None,
    ) -> None:
        """Fail fast when deployment resource names conflict with existing resources."""
        existing_agents = clients.agent.get_draft_by_name(deployment_name)
        if existing_agents:
            msg = f"{ErrorPrefix.CREATE.value}. Deployment '{deployment_name}' already exists."
            raise DeploymentConflictError(message=msg)

        existing_connection = clients.connections.get_draft_by_app_id(app_id=app_id)
        if existing_connection:
            msg = f"{ErrorPrefix.CREATE.value}. Deployment config '{app_id}' already exists."
            raise DeploymentConflictError(message=msg)

        if not snapshot_tool_names:
            return

        seen_tool_names: set[str] = set()
        duplicate_tool_names: set[str] = set()
        for tool_name in snapshot_tool_names:
            if tool_name in seen_tool_names:
                duplicate_tool_names.add(tool_name)
            seen_tool_names.add(tool_name)
        if duplicate_tool_names:
            duplicates = ", ".join(sorted(duplicate_tool_names))
            msg = f"{ErrorPrefix.CREATE.value}. Deployment snapshot name(s) duplicated: {duplicates}."
            raise DeploymentConflictError(message=msg)

        for tool_name in snapshot_tool_names:
            existing_tools = clients.tool.get_draft_by_name(tool_name)
            if existing_tools:
                msg = f"{ErrorPrefix.CREATE.value}. Deployment snapshot '{tool_name}' already exists."
                raise DeploymentConflictError(message=msg)

    async def _process_flow_snapshots(
        self,
        user_id: UUID | str,
        app_id: str | None,
        snapshots: SnapshotItems,
        db: Any,
        tool_name_prefix: str,
    ) -> list[str]:
        """Process flow snapshots."""
        if not tool_name_prefix.strip():
            msg = "Snapshot creation requires a non-empty tool_name_prefix."
            raise InvalidDeploymentOperationError(message=msg)
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        connections = self._resolve_snapshot_connections(
            connections_client=clients.connections,
            config_id=app_id,
        )
        return await self._create_and_upload_wxo_flow_tools(
            tool_client=clients.tool,
            flow_payloads=snapshots.raw_payloads,
            connections=connections,
            app_id=app_id,
            tool_name_prefix=tool_name_prefix,
        )

    async def _get_provider_clients(
        self,
        *,
        user_id: UUID | str,
        db: Any,
    ) -> WxOClient:
        provider_id = self._get_current_provider_id()
        cache_key = str(provider_id)
        if cache_key in self._client_managers:
            return self._client_managers[cache_key]

        credentials: WxOCredentials = await self._resolve_wxo_client_credentials(
            user_id=user_id,
            db=db,
            provider_id=provider_id,
        )

        instance_url: str = credentials.instance_url.rstrip("/")

        authenticator: Authenticator = self.get_authenticator(
            instance_url=instance_url,
            api_key=credentials.api_key,
        )

        self._client_managers[cache_key] = WxOClient(
            instance_url=instance_url,
            authenticator=authenticator,
            tool=ToolClient(base_url=instance_url, authenticator=authenticator),
            connections=ConnectionsClient(base_url=instance_url, authenticator=authenticator),
            agent=AgentClient(base_url=instance_url, authenticator=authenticator),
        )

        return self._client_managers[cache_key]

    async def _resolve_wxo_client_credentials(
        self,
        *,
        user_id: UUID | str,
        db: Any,
        provider_id: UUID,
    ) -> WxOCredentials:
        """Resolve Watsonx Orchestrate client credentials from deployment provider account."""
        try:
            provider_account = await get_provider_account_by_id(
                db,
                provider_id=provider_id,
                user_id=user_id,
            )
            if provider_account is None:
                msg = "Failed to find deployment provider account credentials."
                raise CredentialResolutionError(message=msg)

            provider_key = (provider_account.provider_key or "").strip()
            if provider_key != self.provider_name:
                msg = "Selected deployment provider account is not configured for watsonx-orchestrate."
                raise CredentialResolutionError(message=msg)

            instance_url = (provider_account.backend_url or "").strip()
            api_key = auth_utils.decrypt_api_key((provider_account.api_key or "").strip())
            if not instance_url or not api_key:
                msg = "Watsonx Orchestrate backend URL and API key must be configured."
                raise CredentialResolutionError(message=msg)

        # please ensure that when raising or re-raising an exception,
        # that the message does not leak sensitive information
        except CredentialResolutionError:  # custom exception managed by us , so we re-raise
            raise
        except Exception:  # noqa: BLE001
            msg = "An unexpected error occurred while resolving Watsonx Orchestrate client credentials."
            raise CredentialResolutionError(message=msg) from None

        return WxOCredentials(instance_url=instance_url, api_key=api_key)

    def _get_current_provider_id(self) -> UUID:
        provider_id = get_current_deployment_provider_id()
        if provider_id is None:
            msg = "Deployment account context is not available for adapter resolution."
            raise CredentialResolutionError(message=msg)
        return provider_id

    async def _resolve_runtime_credentials(
        self,
        *,
        user_id: IdLike,
        environment_variables: dict[EnvVarKey, EnvVarValueSpec],
        db: Any,
    ) -> KeyValueConnectionCredentials:
        """Resolve runtime credentials from environment variables."""
        resolved: dict[str, str] = {}
        for credential_key, env_var_value in environment_variables.items():
            resolved[credential_key] = await self._resolve_env_var_value(
                env_var_value,
                user_id=user_id,
                db=db,
            )
        return KeyValueConnectionCredentials(resolved)

    async def _resolve_env_var_value(
        self,
        env_var_value: EnvVarValueSpec,
        *,
        user_id: IdLike,
        db: Any,
    ) -> str:
        if env_var_value.source == EnvVarSource.RAW:
            return env_var_value.value
        return await self._resolve_variable_value(
            env_var_value.value,
            user_id=user_id,
            db=db,
        )

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
            if value is not None:
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

    def _validate_connection(self, connections_client: ConnectionsClient, *, app_id: str) -> GetConnectionResponse:
        connection = connections_client.get_draft_by_app_id(app_id=app_id)
        config = connections_client.get_config(app_id=app_id, env=ConnectionEnvironment.DRAFT)
        if not connection:
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

        return connection

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
            msg = f"{msg_prefix}Exactly one of {resource} id or payload should be present and non-empty and non-null."
            raise ValueError(msg)

    def _build_agent_payload(
        self,
        *,
        data: BaseDeploymentData,
        tool_ids: list[str],
    ) -> dict[str, Any]:
        return {
            "name": data.name,
            "description": str(data.description or "").strip() or f"Langflow deployment {data.name}",
            "tools": tool_ids,
            "style": "default",
            "llm": "groq/openai/gpt-oss-120b",
        }

    def _extract_agent_tool_ids(self, agent: dict[str, Any]) -> list[str]:
        # Shape source:
        # - SDK/API agent payload uses "tools" as list[str] in this adapter flow.
        return [str(tool_id) for tool_id in agent.get("tools", []) if tool_id]

    def _extract_agent_connection_ids(self, agent: dict[str, Any]) -> list[str]:
        # Shape source:
        # - SDK/API agent payload uses "connection_ids" as list[str].
        return [str(connection_id) for connection_id in agent.get("connection_ids", []) if connection_id]

    def _sync_langflow_tool_connections(
        self,
        *,
        clients: WxOClient,
        tool_ids: list[str],
        config_id: str | None,
        connection_id: str | None,
    ) -> None:
        if not tool_ids:
            return

        tools = clients.tool.get_drafts_by_ids(tool_ids)
        tools_by_id = {str(tool.get("id")): tool for tool in tools if isinstance(tool, dict) and tool.get("id")}

        for tool_id in tool_ids:
            tool = tools_by_id.get(tool_id)
            if not tool:
                msg = f"Snapshot '{tool_id}' not found."
                raise ValueError(msg)

            langflow_binding = tool.get("binding", {}).get("langflow", {})
            if not langflow_binding:
                continue

            current_connections = langflow_binding.get("connections")
            if not isinstance(current_connections, dict):
                current_connections = {}

            updated_connections = dict(current_connections)
            if config_id is None:
                # A null config update means "no new connection to add", not "clear existing".
                continue
            if connection_id is not None:
                updated_connections[config_id] = connection_id

            if updated_connections == current_connections:
                # TODO: just send the request?
                continue

            update_payload = self._build_tool_update_payload(tool)
            update_payload.setdefault("binding", {}).setdefault("langflow", {})["connections"] = updated_connections
            clients.tool.update(tool_id, update_payload)

    def _build_tool_update_payload(self, tool: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "description": tool.get("description") or "",
            "permission": tool.get("permission") or "read_only",
        }

        for field in (
            "name",
            "display_name",
            "input_schema",
            "output_schema",
            "binding",
            "tags",
            "is_async",
            "restrictions",
            "bundled_agent_id",
        ):
            if field in tool:
                payload[field] = tool.get(field)

        return payload

    def _get_deployment_metadata(
        self,
        data: dict[str, Any],
        deployment_type: DeploymentType,
        provider_data: dict[str, Any] | None = None,
    ) -> ItemResult:
        result = {
            "id": data.get("id"),
            "type": deployment_type.value,
            "name": data.get("name"),
            "created_at": data.get("created_on"),
            "updated_at": data.get("updated_at"),
        }
        if provider_data:
            result["provider_data"] = provider_data

        return ItemResult(**result)

    def _get_deployment_detail_metadata(
        self,
        data: dict[str, Any],
        deployment_type: DeploymentType,
        provider_data: dict[str, Any] | None = None,
        provider_raw: bool = False,  # noqa: FBT001,FBT002
    ) -> DeploymentGetResult:
        result = {
            "id": data.get("id"),
            "type": deployment_type.value,
            "name": data.get("name"),
            "description": data.get("description"),
        }
        if provider_data:
            result["provider_data"] = provider_data
        if provider_raw:
            result["provider_data"] = data if not provider_data else {**provider_data, "provider_raw": data}

        return DeploymentGetResult(**result)

    def _derive_agent_mode(self, agent: dict[str, Any]) -> str:
        environments = agent.get("environments", [])
        # print(f"environments: {environments}")
        if not isinstance(environments, list) or not environments:
            return "unknown"

        has_draft = False
        has_live = False
        for env in environments:
            if not isinstance(env, dict):
                continue
            env_name = str(env.get("name", "")).strip().lower()
            if env_name == ConnectionEnvironment.DRAFT.value:
                has_draft = True
                continue
            if env_name:
                has_live = True

        if has_draft and has_live:
            return "both"
        if has_live:
            return "live"
        if has_draft:
            return "draft"
        return "unknown"

    def _resolve_health_environment_id(self, agent_client: AgentClient, *, deployment_id: str) -> str:
        environments = agent_client.get_environments_for_agent(deployment_id)
        if not environments:
            msg = f"No environments found for deployment '{deployment_id}'."
            raise ValueError(msg)

        draft_env_id: str | None = None
        for env in environments:
            env_name = str(env.get("name", "")).strip().lower()
            env_id = str(env.get("id", "")).strip()
            if env_name == ConnectionEnvironment.DRAFT.value and env_id:
                draft_env_id = env_id
                break

        if draft_env_id:
            return draft_env_id

        first_env_id = str(environments[0].get("id", "")).strip()
        if first_env_id:
            return first_env_id
        msg = f"Could not resolve environment id for deployment '{deployment_id}'."
        raise ValueError(msg)

    def _fetch_agent_release_status(
        self,
        agent_client: AgentClient,
        *,
        deployment_id: str,
        environment_id: str,
    ) -> dict[str, Any]:
        return agent_client._get(  # noqa: SLF001
            f"/orchestrate/agents/{deployment_id}/releases/status",
            params={"environment_id": environment_id},
        )

    def _normalize_release_status(self, provider_status: dict[str, Any]) -> str:
        status_candidates = [
            provider_status.get("status"),
            provider_status.get("deployment_status"),
            provider_status.get("state"),
        ]
        for candidate in status_candidates:
            normalized = str(candidate or "").strip().lower()
            if normalized:
                return normalized
        return "unknown"

    def _build_orchestrate_runs_query(self, provider_input: dict[str, Any] | None) -> str:
        if not provider_input:
            return ""

        query_segments: list[str] = []
        for key in ("stream", "multiple_content", "stream_timeout"):
            if key not in provider_input or provider_input[key] is None:
                continue
            value = provider_input[key]
            normalized_value = str(value).lower() if isinstance(value, bool) else str(value)
            query_segments.append(f"{key}={normalized_value}")

        if not query_segments:
            return ""
        return f"?{'&'.join(query_segments)}"

    def _build_orchestrate_run_payload(
        self,
        *,
        provider_data: dict[str, Any],
        deployment_id: str,
    ) -> dict[str, Any]:
        message_payload = provider_data.get("message")
        if message_payload is None:
            message_payload = self._resolve_execution_message(provider_data.get("input"))

        payload: dict[str, Any] = {
            "message": message_payload,
            "agent_id": str(provider_data.get("agent_id") or deployment_id),
        }

        for key in (
            "thread_id",
            "llm_params",
            "guardrails",
            "context",
            "additional_parameters",
            "environment_id",
            "version",
            "context_variables",
        ):
            if key in provider_data and provider_data[key] is not None:
                payload[key] = provider_data[key]

        return payload

    def _resolve_execution_message(self, execution_input: str | dict[str, Any] | None) -> dict[str, Any]:
        if isinstance(execution_input, str):
            if not execution_input.strip():
                msg = "Agent execution input message must not be empty."
                raise ValueError(msg)
            return {"role": "user", "content": execution_input}

        if isinstance(execution_input, dict):
            if "role" in execution_input and "content" in execution_input:
                return execution_input

            if "message" in execution_input and isinstance(execution_input["message"], dict):
                return execution_input["message"]

            content = execution_input.get("content")
            if isinstance(content, str) and content.strip():
                return {"role": "user", "content": content}

        msg = (
            "Agent execution requires input content. Provide a non-empty string input "
            "or a message payload with 'role' and 'content'."
        )
        raise ValueError(msg)

    def _fetch_execution_status_payload(
        self,
        agent_client: AgentClient,
        *,
        run_id: str,
    ) -> dict[str, Any] | None:
        try:
            payload = agent_client._get(f"/runs/{run_id}")  # noqa: SLF001
        except ClientAPIException as exc:
            if exc.response.status_code == status.HTTP_404_NOT_FOUND:
                return None
            raise
        return payload if isinstance(payload, dict) else None

    def _normalize_execution_status(
        self,
        status_payload: dict[str, Any] | None,
    ) -> str:
        candidates: list[str] = []
        if status_payload:
            for key in (
                "status",
                "state",
                "run_status",
                "deployment_status",
                "phase",
            ):
                value = status_payload.get(key)
                if value is not None:
                    candidates.append(str(value).strip().lower())

        normalized = next((value for value in candidates if value), "")
        if not normalized:
            return "in_progress"

        completed_statuses = {"completed", "complete", "success", "succeeded", "finished", "done"}
        failed_statuses = {"failed", "error", "errored", "cancelled", "canceled", "timeout"}
        in_progress_statuses = {"queued", "pending", "running", "in_progress", "processing", "accepted", "created"}

        if normalized in completed_statuses:
            return "completed"
        if normalized in failed_statuses:
            return "failed"
        if normalized in in_progress_statuses:
            return "in_progress"

        return normalized

    def _extract_execution_output(self, payload: dict[str, Any] | None) -> str | dict[str, Any] | None:
        if not payload:
            return None
        for key in ("output", "result", "response", "answer"):
            value = payload.get(key)
            if isinstance(value, str):
                if value.strip():
                    return value
                continue
            if isinstance(value, dict):
                extracted = self._extract_text_from_payload(value)
                if isinstance(extracted, str) and extracted.strip():
                    return extracted
                return value
        return self._extract_text_from_payload(payload)

    def _fetch_execution_message_output(
        self,
        agent_client: AgentClient,
        *,
        provider_input: dict[str, Any],
    ) -> str | dict[str, Any] | None:
        thread_id = provider_input.get("thread_id")
        message_id = provider_input.get("message_id")

        message_paths: list[str] = []
        if isinstance(thread_id, str) and thread_id.strip() and isinstance(message_id, str) and message_id.strip():
            message_paths.append(f"/threads/{thread_id}/messages/{message_id}")
        if isinstance(thread_id, str) and thread_id.strip():
            message_paths.append(f"/threads/{thread_id}/messages")
        if isinstance(message_id, str) and message_id.strip():
            message_paths.append(f"/messages/{message_id}")

        for path in message_paths:
            try:
                payload = agent_client._get(path)  # noqa: SLF001
            except ClientAPIException as exc:
                if exc.response.status_code == status.HTTP_404_NOT_FOUND:
                    continue
                raise

            if isinstance(payload, dict):
                output = self._extract_text_from_payload(payload)
                if output:
                    return output
            if isinstance(payload, list):
                for item in reversed(payload):
                    if isinstance(item, dict):
                        output = self._extract_text_from_payload(item)
                        if output:
                            return output

        return None

    def _extract_text_from_payload(self, payload: Any) -> str | dict[str, Any] | None:
        if payload is None:
            return None
        if isinstance(payload, str):
            stripped = payload.strip()
            return stripped or None
        if isinstance(payload, dict):
            for key in ("text", "content", "message", "answer", "output"):
                value = payload.get(key)
                extracted = self._extract_text_from_payload(value)
                if extracted:
                    return extracted
            return None
        if isinstance(payload, list):
            extracted_chunks: list[str] = []
            for item in payload:
                extracted = self._extract_text_from_payload(item)
                if isinstance(extracted, str) and extracted:
                    extracted_chunks.append(extracted)
            if extracted_chunks:
                return "\n".join(extracted_chunks)
            return None
        return None

    def _extract_langflow_artifact_from_zip(self, artifact_zip_bytes: bytes, *, snapshot_id: str) -> dict[str, Any]:
        """Read and parse the Langflow flow JSON from a WXO snapshot artifact zip."""
        try:
            with zipfile.ZipFile(io.BytesIO(artifact_zip_bytes), "r") as zip_artifact:
                json_members = [name for name in zip_artifact.namelist() if name.lower().endswith(".json")]
                if not json_members:
                    msg = f"Snapshot '{snapshot_id}' artifact does not include a flow JSON file."
                    raise ValueError(msg)

                # Snapshot upload currently stores exactly one flow JSON payload.
                flow_json_member = json_members[0]
                flow_json_raw = zip_artifact.read(flow_json_member)
        except zipfile.BadZipFile as exc:
            msg = f"Snapshot '{snapshot_id}' artifact is not a valid zip archive."
            raise ValueError(msg) from exc

        try:
            return json.loads(flow_json_raw.decode("utf-8"))
        except UnicodeDecodeError as exc:
            msg = f"Snapshot '{snapshot_id}' flow artifact is not valid UTF-8 JSON."
            raise ValueError(msg) from exc
        except json.JSONDecodeError as exc:
            msg = f"Snapshot '{snapshot_id}' flow artifact contains invalid JSON."
            raise ValueError(msg) from exc

    def _require_non_empty_string(
        self,
        s: Any,
        *,
        field_name: str,
        error_message: str | None = None,
    ) -> str:
        if isinstance(s, str) and (_value := s.strip()):
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
        lfx_requirement = "lfx>=0.3.0rc3"  # TODO: handle dev environments consistently.
        requirements = generate_requirements_from_flow(
            flow_definition,
            include_lfx=False,
            pin_versions=True,
        )
        requirements = [lfx_requirement, *requirements]
        requirements = self._dedupe_list(requirements)
        requirements_content = "\n".join(requirements) + "\n"
        flow_content = json.dumps(flow_definition, indent=2)

        # print(f"requirements_content: {requirements_content}")

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

    def _resolve_lfx_runner_requirement(self, tool: LangflowTool) -> str:
        tool_requirements = list(getattr(tool, "requirements", []) or [])
        for requirement in tool_requirements:
            requirement_name = re.split(r"[<>=~!\[\s;]", requirement.strip(), maxsplit=1)[0].lower()
            if requirement_name in DEFAULT_LANGFLOW_RUNNER_MODULES:
                return _pin_requirement_name(requirement_name)

        # Prefer whichever runner package is actually installed right now.
        for runner_package in ("lfx-nightly", "lfx"):
            try:
                return _pin_requirement_name(runner_package)
            except md.PackageNotFoundError:
                continue

        return "lfx"

    def _resolve_snapshot_connections(
        self,
        *,
        connections_client: ConnectionsClient,
        config_id: str | None,
    ) -> dict[str, str]:
        connections: dict[str, str] = {}
        if config_id is not None:
            app_id = self._require_non_empty_string(
                config_id,
                field_name="config_id",
                error_message="Snapshot binding requires non-empty 'config_id'.",
            )
            connection = connections_client.get_draft_by_app_id(app_id=app_id)
            if not connection:
                msg = f"Connection '{app_id}' not found."
                raise ValueError(msg)
            connections = {app_id: connection.connection_id}
        return connections

    def _create_wxo_flow_tool(
        self,
        *,
        flow_payload: BaseFlowArtifact,
        connections: dict[str, str],
        app_id: str | None = None,
        tool_name_prefix: str,
    ) -> tuple[dict[str, Any], bytes]:
        """Create a Watsonx Orchestrate flow tool specification.

        Given a flow payload and connections dictionary,
        create a Watsonx Orchestrate flow tool specification
        and the supporting artifacts of the requirements.txt
        and the flow json file.

        Args:
            flow_payload: The flow payload to create the tool specification for.
            connections: The connections dictionary to create the tool specification for.
            app_id: Connection app id used to namespace load_from_db variable references.
            tool_name_prefix: Deterministic prefix for the resulting tool name.

        Returns:
            Tuple[dict[str, Any], bytes]: a tuple containing:
                - tool_payload: The Watsonx Orchestrate flow tool specification.
                - artifacts: The supporting artifacts (the requirements.txt
                    and the flow json file) for the tool.
        """
        flow_definition = flow_payload.model_dump()

        flow_provider_data = flow_definition.pop("provider_data", None)

        if not isinstance(flow_provider_data, dict):
            msg = "Flow payload must include provider_data with a non-empty project_id for Watsonx deployment."
            raise InvalidContentError(message=msg)
        project_id = str(flow_provider_data.get("project_id") or "").strip()
        if not project_id:
            msg = "Flow payload must include provider_data with a non-empty project_id for Watsonx deployment."
            raise InvalidContentError(message=msg)

        flow_definition.update(
            {
                "name": self._normalize_wxo_name(flow_definition.get("name") or ""),
                "id": str(flow_definition.get("id")),
            }
        )

        if app_id is not None:
            flow_definition = self._prefix_flow_global_variable_references(
                flow_definition,
                app_id=app_id,
            )

        # print(f"flow_definition: {flow_definition}")

        # Fallback for flows that don't include last_tested_version in payload
        if not flow_definition.get("last_tested_version"):
            detected_version = (get_version_info() or {}).get("version")
            if not detected_version:
                msg = "Unable to determine running Langflow version for snapshot creation."
                raise ValueError(msg)
            flow_definition["last_tested_version"] = detected_version

        tool: LangflowTool = create_langflow_tool(
            tool_definition=flow_definition,
            connections=connections,
            show_details=False,
        )

        tool_payload = tool.__tool_spec__.model_dump(
            mode="json",
            exclude_unset=True,
            exclude_none=True,
            by_alias=True,
        )

        current_name = str(tool_payload.get("name") or "").strip()

        if current_name:
            normalized_current_name = self._normalize_wxo_name(current_name)
            tool_payload["name"] = f"{tool_name_prefix}{normalized_current_name}"

        (tool_payload.setdefault("binding", {}).setdefault("langflow", {})["project_id"]) = project_id

        artifacts: bytes = self._build_langflow_artifact_bytes(
            tool=tool,
            flow_definition=flow_definition,
        )

        return tool_payload, artifacts

    async def _create_and_upload_wxo_flow_tools(
        self,
        *,
        tool_client: ToolClient,
        flow_payloads: list[BaseFlowArtifact],
        connections: dict[str, str],
        app_id: str | None = None,
        tool_name_prefix: str,
    ) -> list[str]:
        specs = [
            self._create_wxo_flow_tool(
                flow_payload=flow_payload,
                connections=connections,
                app_id=app_id,
                tool_name_prefix=tool_name_prefix,
            )
            for flow_payload in flow_payloads
        ]
        return await asyncio.gather(
            *(
                self._upload_wxo_flow_tool(
                    tool_client=tool_client,
                    tool_payload=tool_payload,
                    artifact_bytes=artifact_bytes,
                )
                for tool_payload, artifact_bytes in specs
            )
        )

    async def _upload_wxo_flow_tool(
        self,
        *,
        tool_client: ToolClient,
        tool_payload: dict[str, Any],
        artifact_bytes: bytes,
    ) -> str:
        tool_response = await asyncio.to_thread(tool_client.create, tool_payload)
        tool_id = self._require_tool_id(tool_response)

        await asyncio.to_thread(
            self._upload_tool_artifact_bytes,
            tool_client,
            tool_id=tool_id,
            artifact_bytes=artifact_bytes,
        )
        return tool_id

    async def _create_langflow_flow_tool(
        self,
        *,
        user_id: UUID | str,
        config_id: str | None = None,
        flow_payload: BaseFlowArtifact,
        db: Any,
    ) -> str:
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        connections = self._resolve_snapshot_connections(
            connections_client=clients.connections,
            config_id=config_id,
        )
        tool_payload, artifact_bytes = self._create_wxo_flow_tool(
            flow_payload=flow_payload,
            connections=connections,
            app_id=config_id,
            tool_name_prefix=f"lf_{uuid4().hex[:6]}_",
        )

        return await self._upload_wxo_flow_tool(
            tool_client=clients.tool,
            tool_payload=tool_payload,
            artifact_bytes=artifact_bytes,
        )

    @staticmethod
    def get_authenticator(instance_url: str, api_key: str) -> None:
        """Set the authenticator for the Watsonx Orchestrate API."""
        if ".cloud.ibm.com" in instance_url:
            from ibm_cloud_sdk_core.authenticators import IAMAuthenticator

            return IAMAuthenticator(apikey=api_key, url=WxOAuthURL.IBM_IAM.value)
        elif ".ibm.com" in instance_url:  # noqa: RET505 - explicitness
            from ibm_cloud_sdk_core.authenticators import MCSPAuthenticator

            return MCSPAuthenticator(apikey=api_key, url=WxOAuthURL.MCSP.value)

        msg = f"Could not determine authentication scheme for instance URL: {instance_url}"
        raise AuthSchemeError(message=msg)

    @staticmethod
    def _extract_error_detail(response_text: str) -> str | dict:
        """Extract a human-readable error detail from a ClientAPIException response.

        The response body may contain a ``detail`` value that is a string, a dict
        with a ``msg`` key, or a list of such dicts.  This helper normalises all
        three shapes into a single value suitable for inclusion in an error message.
        """
        try:
            detail = json.loads(response_text).get("detail")
        except (TypeError, ValueError, json.JSONDecodeError):
            return response_text
        if detail and isinstance(detail, list):
            detail = detail[0]
        if isinstance(detail, dict):
            detail = detail.get("msg") or detail
        return detail

    def _validate_wxo_name(self, name: str) -> str:
        """Normalize and validate a WXO resource name."""
        normalized_name = self._normalize_wxo_name(str(name))
        if not normalized_name:
            msg = "Deployment name must include at least one alphanumeric character."
            raise InvalidContentError(message=msg)
        if not normalized_name[0].isalpha():
            msg = "Deployment name must start with a letter. "
            raise InvalidContentError(message=msg)
        return normalized_name

    def _prefix_flow_global_variable_references(
        self,
        flow_definition: dict[str, Any],
        *,
        app_id: str,
    ) -> dict[str, Any]:
        """Prefix load-from-db global variable names with the WXO app id."""
        normalized_app_id = app_id.strip()
        if not normalized_app_id:
            return flow_definition

        prefix = f"{normalized_app_id}_"

        def _walk(value: Any) -> None:
            if isinstance(value, dict):
                if value.get("load_from_db") is True and isinstance(value.get("value"), str):
                    variable_name = value["value"].strip()
                    if variable_name and not variable_name.startswith(prefix):
                        # TODO: sometimes the user wants to keep a raw value
                        # figure out what the exact conditions for this are
                        value["value"] = f"{prefix}{variable_name}"
                for child in value.values():
                    _walk(child)
                return

            if isinstance(value, list):
                for item in value:
                    _walk(item)

        _walk(flow_definition)
        return flow_definition

    def _normalize_wxo_name(self, s: str) -> str:
        return _WXO_SANITIZE_RE.sub("", s.translate(_WXO_TRANSLATE))

    def _build_snapshot_tool_names(
        self,
        *,
        snapshots: SnapshotItems | None,
        tool_name_prefix: str,
    ) -> list[str]:
        if snapshots is None:
            return []

        tool_names: list[str] = []
        for snapshot in snapshots.raw_payloads:
            normalized_tool_name = self._normalize_wxo_name(str(snapshot.name))
            if not normalized_tool_name:
                msg = "Snapshot name must include at least one alphanumeric character."
                raise InvalidContentError(message=msg)
            tool_names.append(f"{tool_name_prefix}{normalized_tool_name}")
        return tool_names

    async def _retry_with_backoff(
        self,
        operation,
        *,
        max_attempts: int,
        should_retry=None,
    ):
        delay_seconds = RETRY_INITIAL_DELAY_SECONDS
        for attempt in range(1, max_attempts + 1):
            try:
                return await operation()
            except Exception as exc:
                retryable = True if should_retry is None else should_retry(exc)
                if not retryable or attempt == max_attempts:
                    raise
                await asyncio.sleep(delay_seconds)
                delay_seconds *= 2
        msg = "Retry helper exhausted attempts without result."
        raise RuntimeError(msg)

    async def _retry_create(self, operation):
        return await self._retry_with_backoff(
            operation,
            max_attempts=CREATE_MAX_RETRIES,
            should_retry=self._is_retryable_create_exception,
        )

    async def _retry_rollback(self, operation):
        return await self._retry_with_backoff(
            operation,
            max_attempts=ROLLBACK_MAX_RETRIES,
        )

    def _is_retryable_create_exception(self, exc: Exception) -> bool:
        non_retryable_status_codes = {
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_409_CONFLICT,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        }
        if isinstance(exc, ClientAPIException):
            return exc.response.status_code not in non_retryable_status_codes
        if isinstance(exc, HTTPException):
            return exc.status_code not in non_retryable_status_codes
        return not isinstance(
            exc,
            (
                DeploymentConflictError,
                InvalidContentError,
                InvalidDeploymentOperationError,
                InvalidDeploymentTypeError,
            ),
        )

    async def _rollback_created_resources(
        self,
        *,
        clients: WxOClient,
        agent_id: str | None,
        tool_ids: list[str],
        app_id: str | None,
    ) -> None:
        if agent_id:
            with suppress(Exception):
                await self._retry_rollback(lambda: self._delete_agent_if_exists(clients, agent_id=agent_id))
        if tool_ids:
            for tool_id in reversed(tool_ids):
                with suppress(Exception):
                    await self._retry_rollback(
                        lambda tool_id=tool_id: self._delete_tool_if_exists(clients, tool_id=tool_id)
                    )
        if app_id:
            with suppress(Exception):
                await self._retry_rollback(lambda: self._delete_config_if_exists(clients, app_id=app_id))

    async def _delete_agent_if_exists(self, clients: WxOClient, *, agent_id: str) -> None:
        try:
            await asyncio.to_thread(clients.agent.delete, agent_id)
        except ClientAPIException as exc:
            if exc.response.status_code != status.HTTP_404_NOT_FOUND:
                raise

    async def _delete_tool_if_exists(self, clients: WxOClient, *, tool_id: str) -> None:
        try:
            await asyncio.to_thread(clients.tool.delete, tool_id)
        except ClientAPIException as exc:
            if exc.response.status_code != status.HTTP_404_NOT_FOUND:
                raise

    async def _delete_config_if_exists(self, clients: WxOClient, *, app_id: str) -> None:
        try:
            await asyncio.to_thread(clients.connections.delete, app_id)
        except ClientAPIException as exc:
            if exc.response.status_code != status.HTTP_404_NOT_FOUND:
                raise


@func.ttl_cache(maxsize=1, ttl=2)  # only used for lfx
def _pin_requirement_name(package_name: str) -> str:
    version = md.version(package_name)
    return f"{package_name}=={version}"
