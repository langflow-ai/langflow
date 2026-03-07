"""Slim WatsonxOrchestrateDeploymentService that delegates to submodules."""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import HTTPException, status
from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException
from lfx.services.adapters.deployment.base import BaseDeploymentService
from lfx.services.adapters.deployment.exceptions import (
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
    ExecutionCreate,
    ExecutionCreateResult,
    ExecutionStatusResult,
    IdLike,
    ProviderPayload,
    RedeployResult,
)

from langflow.services.adapters.deployment.watsonx_orchestrate.client import get_provider_clients
from langflow.services.adapters.deployment.watsonx_orchestrate.constants import (
    _WATSONX_ORCHESTRATE_DEPLOYMENT_ADAPTER_KEY,
    RANDOM_PREFIX_LENGTH_RANGE,
    SUPPORTED_ADAPTER_DEPLOYMENT_TYPES,
    ErrorPrefix,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.core.config import (
    assert_create_resources_available,
    process_config,
    resolve_create_app_id,
    validate_config_create_input,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.core.execution import (
    build_orchestrate_run_payload,
    build_orchestrate_runs_query,
    extract_execution_output,
    fetch_execution_message_output,
    fetch_execution_status_payload,
    normalize_execution_status,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.core.retry import (
    retry_create,
    rollback_created_resources,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.core.status import (
    derive_agent_mode,
    fetch_agent_release_status,
    get_deployment_detail_metadata,
    get_deployment_metadata,
    normalize_release_status,
    resolve_health_environment_id,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.core.tools import (
    build_snapshot_tool_names,
    create_and_upload_wxo_flow_tools,
    process_raw_flows_with_app_id,
    resolve_snapshot_connections,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.utils import (
    build_agent_payload,
    extract_agent_tool_ids,
    extract_error_detail,
    validate_wxo_name,
)
from langflow.services.deps import get_settings_service

if TYPE_CHECKING:
    from uuid import UUID

    from ibm_watsonx_orchestrate_clients.agents.agent_client import AgentUpsertResponse
    from lfx.services.settings.service import SettingsService

    from langflow.services.adapters.deployment.watsonx_orchestrate.types import WxOClient


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

    async def _get_provider_clients(self, *, user_id: UUID | str, db: Any) -> WxOClient:
        return await get_provider_clients(
            user_id=user_id,
            db=db,
            provider_name=self.provider_name,
            client_cache=self._client_managers,
        )

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
        created_agent_id: str | None = None
        created_tool_ids: list[str] = []
        created_app_id: str | None = None
        clients: WxOClient | None = None
        try:
            deployment_spec: BaseDeploymentData = payload.spec
            normalized_deployment_name = validate_wxo_name(deployment_spec.name)
            validate_config_create_input(payload.config)

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

            prefixed_app_id = resolve_create_app_id(
                prefixed_deployment_name=prefixed_deployment_name,
                config=payload.config,
            )

            planned_tool_names = build_snapshot_tool_names(
                snapshots=payload.snapshot,
                tool_name_prefix=random_prefix,
            )

            # there is a read-before-write race here
            # but locking locally is not enough
            # so we use a random prefix to avoid conflicts
            assert_create_resources_available(
                clients=clients,
                deployment_name=prefixed_deployment_name,
                app_id=prefixed_app_id,
                snapshot_tool_names=planned_tool_names,
            )

            try:
                created_app_id = prefixed_app_id
                await retry_create(
                    lambda: process_config(
                        user_id=user_id,
                        db=db,
                        deployment_name=prefixed_app_id,
                        config=payload.config,
                        provider_name=self.provider_name,
                        client_cache=self._client_managers,
                    )
                )

                if payload.snapshot and payload.snapshot.raw_payloads:
                    created_tool_ids = await retry_create(
                        lambda: process_raw_flows_with_app_id(
                            user_id=user_id,
                            app_id=prefixed_app_id,
                            flows=payload.snapshot.raw_payloads,
                            db=db,
                            tool_name_prefix=random_prefix,
                            provider_name=self.provider_name,
                            client_cache=self._client_managers,
                        )
                    )

                derived_spec = deployment_spec.model_copy(deep=True)
                if derived_spec.provider_spec is None:
                    derived_spec.provider_spec = {}
                derived_spec.provider_spec.update(
                    {
                        "name": prefixed_deployment_name,
                        "display_name": derived_spec.name,
                    }
                )
                deployment_response = await retry_create(
                    lambda: self._create_agent_deployment(
                        data=derived_spec,
                        tool_ids=created_tool_ids,
                        user_id=user_id,
                        db=db,
                    )
                )
                created_agent_id = deployment_response.id
            except Exception:
                await rollback_created_resources(
                    clients=clients,
                    agent_id=created_agent_id,
                    tool_ids=created_tool_ids,
                    app_id=created_app_id,
                )
                raise

        except (ClientAPIException, HTTPException) as exc:
            if isinstance(exc, ClientAPIException):
                status_code = exc.response.status_code
                error_detail = extract_error_detail(exc.response.text)
            else:
                status_code = exc.status_code
                error_detail = extract_error_detail(str(exc.detail))
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

        derived_spec.name = deployment_spec.name  # restore the original name

        return DeploymentCreateResult(
            id=deployment_response.id,
            config_id=created_app_id,
            snapshot_ids=created_tool_ids,
            **derived_spec.model_dump(exclude_unset=True),
        )

    async def list_types(
        self,
        *,
        user_id: IdLike,  # noqa: ARG002
        db: Any,  # noqa: ARG002
    ) -> DeploymentListTypesResult:
        """List deployment types supported by the provider."""
        return DeploymentListTypesResult(deployment_types=list(SUPPORTED_ADAPTER_DEPLOYMENT_TYPES))

    async def list(
        self,
        *,
        user_id: IdLike,
        db: Any,
        params: DeploymentListParams | None = None,
    ) -> DeploymentListResult:
        """List deployments from Watsonx Orchestrate."""
        client_manager = await self._get_provider_clients(user_id=user_id, db=db)
        deployments: list = []
        try:
            # validate deployment types
            deployment_types: list[DeploymentType] = []
            invalid_deployment_types: list[DeploymentType] = []

            if params and params.deployment_types:
                deployment_types = params.deployment_types
                invalid_deployment_types = set(deployment_types).difference(SUPPORTED_ADAPTER_DEPLOYMENT_TYPES)

            if invalid_deployment_types:
                invalid_values = ", ".join([dtype.value for dtype in invalid_deployment_types])
                msg = f"{ErrorPrefix.LIST.value}watsonx Orchestrate has no such deployment type(s): '{invalid_values}'."
                raise InvalidDeploymentTypeError(message=msg)

            query_params: ProviderPayload = {}

            if params.provider_params:
                query_params = params.provider_params

            if params.deployment_ids and "ids" not in query_params:
                query_params["ids"] = [str(_id) for _id in params.deployment_ids]

            # if different deployment types
            # are distinct resources in wxo
            # then we should probably raise an error if
            # the ids query parameter is not empty
            # this is not a problem today, but might be in the future

            deployments = [
                get_deployment_metadata(
                    data=agent,
                    deployment_type=DeploymentType.AGENT,
                    provider_data={
                        "snapshot_ids": extract_agent_tool_ids(agent),
                        "mode": derive_agent_mode(agent),
                    },
                )
                for agent in client_manager.agent._get(  # noqa: SLF001
                    "/agents",
                    params=query_params or None,
                )
            ]
        except (ClientAPIException, HTTPException) as exc:
            if isinstance(exc, ClientAPIException):
                error_detail = extract_error_detail(getattr(exc.response, "text", ""))
            else:
                error_detail = extract_error_detail(str(exc.detail))
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
        return get_deployment_detail_metadata(
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
                normalized_name = validate_wxo_name(spec_updates["name"])
                update_payload["name"] = normalized_name
                update_payload["display_name"] = spec_updates["name"]
            if "description" in spec_updates:
                update_payload["description"] = spec_updates["description"]

        current_tool_ids = extract_agent_tool_ids(current)
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

        environment_id = resolve_health_environment_id(clients.agent, deployment_id=deployment_id_str)
        provider_status = fetch_agent_release_status(
            clients.agent,
            deployment_id=deployment_id_str,
            environment_id=environment_id,
        )
        normalized_status = normalize_release_status(provider_status)

        return DeploymentStatusResult(
            id=deployment_id_str,
            provider_data={
                "status": normalized_status,
                "environment_id": environment_id,
                "mode": derive_agent_mode(agent),
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
        query_suffix = build_orchestrate_runs_query(provider_data)
        run_payload = build_orchestrate_run_payload(
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
                    f"{extract_error_detail(exc.response.text)}"
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

        status_payload = fetch_execution_status_payload(
            clients.agent,
            run_id=run_id,
        )
        if status_payload is not None:
            provider_result["status_payload"] = status_payload

        normalized_status = normalize_execution_status(status_payload)
        output: str | dict[str, Any] | None = extract_execution_output(status_payload)
        if output is None and normalized_status in {"completed", "success", "succeeded"}:
            output = fetch_execution_message_output(
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
        connections = resolve_snapshot_connections(
            connections_client=clients.connections,
            config_id=config_id,
        )
        return await create_and_upload_wxo_flow_tools(
            tool_client=clients.tool,
            flow_payloads=raw_payloads,
            connections=connections,
            app_id=config_id,
            tool_name_prefix=tool_name_prefix,
        )

    async def _process_config(
        self,
        user_id: Any,
        db: Any,
        deployment_name: str,
        config: Any,
    ) -> str:
        """Create and bind deployment config using deployment name as app_id."""
        return await process_config(
            user_id=user_id,
            db=db,
            deployment_name=deployment_name,
            config=config,
            provider_name=self.provider_name,
            client_cache=self._client_managers,
        )

    async def _create_agent_deployment(
        self,
        user_id: UUID | str,
        tool_ids: list[str],
        data: BaseDeploymentData,
        db: Any,
    ) -> AgentUpsertResponse:
        """Create an agent deployment."""
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        payload = build_agent_payload(
            data=data,
            tool_ids=tool_ids,
        )
        return clients.agent.create(payload)

    async def teardown(self) -> None:
        """Teardown provider-specific resources."""
        self._client_managers.clear()
