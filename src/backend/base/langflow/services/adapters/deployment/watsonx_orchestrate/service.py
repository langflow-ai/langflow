"""Slim WatsonxOrchestrateDeploymentService that delegates to submodules."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException
from lfx.services.adapters.deployment.base import BaseDeploymentService
from lfx.services.adapters.deployment.exceptions import (
    AuthenticationError,
    AuthorizationError,
    DeploymentConflictError,
    DeploymentError,
    DeploymentNotFoundError,
    DeploymentSupportError,
    InvalidContentError,
    InvalidDeploymentOperationError,
    InvalidDeploymentTypeError,
    OperationNotSupportedError,
)
from lfx.services.adapters.deployment.payloads import DeploymentPayloadSchemas
from lfx.services.adapters.deployment.schema import (
    BaseDeploymentData,
    ConfigListItem,
    ConfigListParams,
    ConfigListResult,
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
    RedeployResult,
    SnapshotItem,
    SnapshotListParams,
    SnapshotListResult,
    _normalize_and_validate_id,
)
from lfx.services.adapters.payload import AdapterPayloadValidationError, PayloadSlot

from langflow.services.adapters.deployment.watsonx_orchestrate.client import get_provider_clients
from langflow.services.adapters.deployment.watsonx_orchestrate.constants import (
    PROVIDER_SPEC_RESOURCE_NAME_PREFIX_KEY,
    SUPPORTED_ADAPTER_DEPLOYMENT_TYPES,
    ErrorPrefix,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.core.config import (
    process_config,
    resolve_create_app_id,
    validate_config_create_input,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.core.execution import (
    create_agent_run,
    get_agent_run,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.core.retry import (
    retry_create,
    rollback_created_resources,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.core.status import (
    derive_agent_environment,
    get_deployment_detail_metadata,
    get_deployment_metadata,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.core.tools import (
    build_snapshot_tool_names,
    process_raw_flows_with_app_id,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.payloads import (
    WatsonxDeploymentUpdatePayload,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.update_helpers import (
    apply_provider_update_plan_with_rollback,
    build_provider_update_plan,
    build_update_payload_from_spec,
    validate_provider_update_request_sections,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.utils import (
    _require_single_deployment_id,
    build_agent_payload,
    dedupe_list,
    extract_agent_tool_ids,
    extract_error_detail,
    raise_as_deployment_error,
    resolve_resource_name_prefix,
    validate_wxo_name,
)
from langflow.services.deps import get_settings_service

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Any

    from ibm_watsonx_orchestrate_clients.agents.agent_client import AgentUpsertResponse
    from lfx.services.settings.service import SettingsService
    from sqlalchemy.ext.asyncio import AsyncSession

    from langflow.services.adapters.deployment.watsonx_orchestrate.types import WxOClient


class WatsonxOrchestrateDeploymentService(BaseDeploymentService):
    """Deployment adapter for Watsonx Orchestrate."""

    name = "deployment_service"
    payload_schemas = DeploymentPayloadSchemas(
        deployment_update=PayloadSlot(WatsonxDeploymentUpdatePayload),
    )

    def __init__(self, settings_service: SettingsService | None = None):
        super().__init__()
        if settings_service is None:
            settings_service = get_settings_service()
        if settings_service is None:
            msg = "Settings service is not available."
            raise RuntimeError(msg)
        self.settings_service = settings_service
        self.set_ready()

    async def _get_provider_clients(self, *, user_id: IdLike, db: AsyncSession) -> WxOClient:
        """Resolve provider clients through a service-level seam.

        A dedicated method keeps call sites patchable in unit/e2e tests and
        centralizes provider-client resolution behavior for this service.
        """
        return await get_provider_clients(user_id=user_id, db=db)

    async def create(
        self,
        *,
        user_id: IdLike,
        payload: DeploymentCreate,
        db: AsyncSession,
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
        # The caller must supply a resource name prefix via
        # provider_spec["resource_name_prefix"].
        # Every created resource (connection, tool, agent) is
        # prefixed with this value, which prevents name collisions
        # and supports idempotent retries (re-use the same prefix
        # across attempts). We recommend using a random prefix.
        # --
        logger.info("Creating wxO deployment for user_id=%s", user_id)
        agent_create_response: AgentUpsertResponse | None = None
        created_tool_ids: list[str] = []
        created_app_id: str | None = None
        clients: WxOClient | None = None
        derived_spec: BaseDeploymentData | None = None
        try:
            deployment_spec: BaseDeploymentData = payload.spec
            normalized_deployment_name = validate_wxo_name(deployment_spec.name)
            validate_config_create_input(payload.config)

            if deployment_spec.type != DeploymentType.AGENT:
                msg = (
                    f"{ErrorPrefix.CREATE.value}"
                    f"Deployment type '{deployment_spec.type.value}' "
                    "is not supported by watsonx Orchestrate."
                )
                raise DeploymentSupportError(message=msg)

            caller_prefix = (deployment_spec.provider_spec or {}).get(PROVIDER_SPEC_RESOURCE_NAME_PREFIX_KEY)
            if not caller_prefix:
                msg = (
                    f"{ErrorPrefix.CREATE.value} provider_spec must include '{PROVIDER_SPEC_RESOURCE_NAME_PREFIX_KEY}'."
                )
                raise InvalidContentError(message=msg)

            clients = await self._get_provider_clients(user_id=user_id, db=db)

            resource_prefix = resolve_resource_name_prefix(
                caller_prefix=caller_prefix,
            )
            prefixed_deployment_name = f"{resource_prefix}{normalized_deployment_name}"

            tool_names = build_snapshot_tool_names(
                snapshots=payload.snapshot,
                tool_name_prefix=resource_prefix,
            )
            if len(tool_names) != len(set(tool_names)):
                msg = (
                    f"{ErrorPrefix.CREATE.value} "
                    "Duplicate snapshot names detected in the request. "
                    "Each snapshot must have a unique name."
                )
                raise DeploymentConflictError(message=msg)

            prefixed_app_id = resolve_create_app_id(
                prefixed_deployment_name=prefixed_deployment_name,
                config=payload.config,
            )

            try:
                created_app_id = await retry_create(
                    process_config,
                    clients=clients,
                    user_id=user_id,
                    db=db,
                    deployment_name=prefixed_app_id,
                    config=payload.config,
                )

                if payload.snapshot and (flow_payloads := payload.snapshot.raw_payloads):
                    created_tool_ids = await retry_create(
                        process_raw_flows_with_app_id,
                        clients=clients,
                        app_id=prefixed_app_id,
                        flows=flow_payloads,
                        tool_name_prefix=resource_prefix,
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

                agent_create_response = await retry_create(
                    self._create_agent_deployment,
                    clients=clients,
                    data=derived_spec,
                    tool_ids=created_tool_ids,
                )
            except Exception:
                logger.warning(
                    "wxO create failed; rolling back agent_id=%s, tool_ids=%s, app_id=%s",
                    agent_create_response.id if agent_create_response else None,
                    created_tool_ids,
                    created_app_id,
                )
                await rollback_created_resources(
                    clients=clients,
                    agent_id=agent_create_response.id if agent_create_response else None,
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
            is_conflict = status_code == status.HTTP_409_CONFLICT or "already exists" in error_detail.lower()
            if is_conflict:
                msg = (
                    f"{ErrorPrefix.CREATE.value} "
                    "One or more resources already exist. "
                    "Please ensure the names and/or ids of the "
                    "following resources to be unique: "
                    "(1) The deployment specification, "
                    "(2) The deployment configuration, "
                    "(3) The deployment snapshot. "
                    f"error details: {error_detail}"
                )
                raise DeploymentConflictError(message=msg) from exc
            if status_code == status.HTTP_422_UNPROCESSABLE_CONTENT:
                msg = (
                    f"{ErrorPrefix.CREATE.value} "
                    "The deployment request entity is unprocessable. "
                    "Please ensure the request entity is valid and complete. "
                    f"error details: {error_detail}"
                )
                raise InvalidContentError(message=msg) from exc
            msg = f"{ErrorPrefix.CREATE.value} error details: {error_detail}"
            raise DeploymentError(message=msg, error_code="deployment_error") from exc
        except (
            AuthenticationError,
            DeploymentConflictError,
            InvalidContentError,
            InvalidDeploymentOperationError,
            InvalidDeploymentTypeError,
            DeploymentSupportError,
        ):
            raise
        except Exception as exc:
            logger.exception("Unexpected error during wxO deployment creation")
            msg = f"{ErrorPrefix.CREATE.value} Please check server logs for details."
            raise DeploymentError(message=msg, error_code="deployment_error") from exc

        if agent_create_response is None or derived_spec is None:
            msg = f"{ErrorPrefix.CREATE.value} Deployment response was empty."
            raise DeploymentError(message=msg, error_code="deployment_error")

        derived_spec.name = deployment_spec.name  # restore the original name

        return DeploymentCreateResult(
            id=agent_create_response.id,
            config_id=created_app_id,
            snapshot_ids=created_tool_ids,
            **derived_spec.model_dump(exclude_unset=True),
        )

    async def list_types(
        self,
        *,
        user_id: IdLike,  # noqa: ARG002
        db: AsyncSession,  # noqa: ARG002
    ) -> DeploymentListTypesResult:
        """List deployment types supported by the provider."""
        return DeploymentListTypesResult(deployment_types=list(SUPPORTED_ADAPTER_DEPLOYMENT_TYPES))

    async def list(
        self,
        *,
        user_id: IdLike,
        db: AsyncSession,
        params: DeploymentListParams | None = None,
    ) -> DeploymentListResult:
        """List deployments from Watsonx Orchestrate."""
        client_manager = await self._get_provider_clients(user_id=user_id, db=db)
        deployments: list = []
        try:
            deployment_types: set[DeploymentType] = set()
            invalid_deployment_types: set[DeploymentType] = set()

            if params and params.deployment_types:
                deployment_types = set(params.deployment_types)
                invalid_deployment_types = deployment_types.difference(SUPPORTED_ADAPTER_DEPLOYMENT_TYPES)

            if invalid_deployment_types:
                invalid_values = ", ".join([dtype.value for dtype in invalid_deployment_types])
                msg = (
                    f"{ErrorPrefix.LIST.value} watsonx Orchestrate has no such deployment type(s): '{invalid_values}'."
                )
                raise InvalidDeploymentTypeError(message=msg)

            query_params: dict[str, Any] = {}

            if params and params.provider_params:
                query_params = params.provider_params

            if params and params.deployment_ids and "ids" not in query_params:
                query_params["ids"] = [str(_id) for _id in params.deployment_ids]

            # if different deployment types
            # are distinct resources in wxO
            # then we should probably raise an error if
            # the ids query parameter is not empty or null
            # this is not a problem today, but might be in the future

            raw_agents = await asyncio.to_thread(
                client_manager.get_agents_raw,
                params=query_params or None,
            )
            deployments = [
                get_deployment_metadata(
                    data=agent,
                    deployment_type=DeploymentType.AGENT,
                    provider_data={
                        "snapshot_ids": extract_agent_tool_ids(agent),
                        "environment": derive_agent_environment(agent),
                    },
                )
                for agent in raw_agents
            ]
        except Exception as exc:  # noqa: BLE001
            raise_as_deployment_error(
                exc,
                error_prefix=ErrorPrefix.LIST,
                log_msg="Unexpected error while listing wxO deployments",
                pass_through=(AuthenticationError, AuthorizationError, InvalidDeploymentTypeError),
            )

        return DeploymentListResult(
            deployments=deployments,
        )

    async def get(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        deployment_type: DeploymentType | None = None,  # noqa: ARG002
        db: AsyncSession,
    ) -> DeploymentGetResult:
        """Get a deployment (agent) from Watsonx Orchestrate."""
        client_manager = await self._get_provider_clients(user_id=user_id, db=db)
        try:
            agent = await asyncio.to_thread(client_manager.agent.get_draft_by_id, deployment_id)
        except Exception as exc:  # noqa: BLE001
            raise_as_deployment_error(
                exc,
                error_prefix=ErrorPrefix.GET,
                log_msg="Unexpected error fetching wxO deployment",
                pass_through=(AuthenticationError, AuthorizationError, DeploymentNotFoundError),
            )
        if not agent:
            msg = f"Deployment '{deployment_id}' not found."
            raise DeploymentNotFoundError(msg)
        return get_deployment_detail_metadata(
            data=agent,
            deployment_type=DeploymentType.AGENT,
        )

    async def update(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        deployment_type: DeploymentType | None = None,  # noqa: ARG002
        payload: DeploymentUpdate,
        db: AsyncSession,
    ) -> DeploymentUpdateResult:
        """Update deployment metadata and provider-driven tool/config operations."""
        try:
            clients = await self._get_provider_clients(user_id=user_id, db=db)
            agent_id = _normalize_and_validate_id(str(deployment_id), field_name="deployment_id")

            agent = await asyncio.to_thread(clients.agent.get_draft_by_id, agent_id)

            if not agent:
                msg = f"Deployment '{agent_id}' not found."
                raise DeploymentNotFoundError(msg)

            # base agent payload to build for final update call
            update_payload: dict[str, Any] = build_update_payload_from_spec(payload.spec)

            validate_provider_update_request_sections(payload)
            if payload.provider_data is None:
                if not update_payload:
                    msg = "provider_data is required when update operations do not include spec changes."
                    raise InvalidContentError(message=msg)
                await retry_create(
                    asyncio.to_thread,
                    clients.agent.update,
                    agent_id,
                    update_payload,
                )
                return DeploymentUpdateResult(id=deployment_id, snapshot_ids=[])

            try:
                provider_update = self.payload_schemas.deployment_update.parse(payload.provider_data)
            except AdapterPayloadValidationError as exc:
                first_error = exc.error.errors()[0] if exc.error.errors() else {}
                msg = str(first_error.get("msg") or exc)
                raise InvalidContentError(message=msg) from None

            provider_plan = build_provider_update_plan(
                agent=agent,
                provider_update=provider_update,
            )

            added_snapshot_ids: list[str] = await apply_provider_update_plan_with_rollback(
                clients=clients,
                user_id=user_id,
                db=db,
                agent_id=agent_id,
                agent=agent,
                update_payload=update_payload,
                plan=provider_plan,
            )

            return DeploymentUpdateResult(
                id=deployment_id,
                snapshot_ids=added_snapshot_ids,
            )

        except (ClientAPIException, HTTPException) as exc:
            raise_as_deployment_error(
                exc,
                error_prefix=ErrorPrefix.UPDATE,
                log_msg="Unexpected provider error during wxO deployment update",
            )
        except (
            AuthenticationError,
            AuthorizationError,
            DeploymentNotFoundError,
            InvalidContentError,
            InvalidDeploymentOperationError,
            DeploymentConflictError,
        ):
            raise
        except Exception as exc:
            logger.exception("Unexpected error during wxO deployment update")
            msg = f"{ErrorPrefix.UPDATE.value} Please check server logs for details."
            raise DeploymentError(message=msg, error_code="deployment_error") from exc

    async def redeploy(
        self,
        *,
        user_id: IdLike,  # noqa: ARG002
        deployment_id: IdLike,  # noqa: ARG002
        deployment_type: DeploymentType | None = None,  # noqa: ARG002
        db: AsyncSession,  # noqa: ARG002
    ) -> RedeployResult:
        """Trigger a deployment redeployment for the agent in draft environment."""
        msg = "Redeployment is not supported by the watsonx Orchestrate adapter."
        raise OperationNotSupportedError(message=msg)

    async def duplicate(
        self,
        *,
        user_id: IdLike,  # noqa: ARG002
        deployment_id: IdLike,  # noqa: ARG002
        deployment_type: DeploymentType | None = None,  # noqa: ARG002
        db: AsyncSession,  # noqa: ARG002
    ) -> DeploymentDuplicateResult:
        """Duplicate an existing deployment."""
        msg = "Deployment duplication is not supported by the watsonx Orchestrate adapter."
        raise OperationNotSupportedError(message=msg)

    async def delete(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        deployment_type: DeploymentType | None = None,  # noqa: ARG002
        db: AsyncSession,
    ) -> DeploymentDeleteResult:
        """Delete only the deployment agent (keep tools/configs reusable)."""
        logger.info("Deleting wxO deployment deployment_id=%s", deployment_id)
        agent_id = _normalize_and_validate_id(str(deployment_id), field_name="deployment_id")
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        try:
            await asyncio.to_thread(clients.agent.delete, agent_id)
        except ClientAPIException as e:
            status_code = e.response.status_code
            if status_code == status.HTTP_404_NOT_FOUND:
                msg = f"{ErrorPrefix.DELETE.value} deployment id '{agent_id}' not found."
                raise DeploymentNotFoundError(msg) from e
            msg = f"{ErrorPrefix.DELETE.value} error details: {extract_error_detail(e.response.text)}"
            raise DeploymentError(msg, error_code="deployment_error") from e
        except (AuthenticationError, AuthorizationError, DeploymentNotFoundError):
            raise
        except Exception as exc:
            logger.exception("Unexpected error while deleting wxO deployment %s", agent_id)
            msg = f"{ErrorPrefix.DELETE.value} Please check server logs for details."
            raise DeploymentError(msg, error_code="deployment_error") from exc

        return DeploymentDeleteResult(id=agent_id)

    # TODO: get status normally if its a live agent
    # if its draft, use the current 'exists' or raise not found logic
    async def get_status(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        deployment_type: DeploymentType | None = None,  # noqa: ARG002
        db: AsyncSession,
    ) -> DeploymentStatusResult:
        """Get deployment status from wxO agent metadata.

        Note: wxO does not expose a dedicated health endpoint for draft Agents. Status is
        inferred from agent existence and environment metadata -- "connected"
        means the agent draft was found, not that it is healthy at runtime.
        """
        agent_id = _normalize_and_validate_id(str(deployment_id), field_name="deployment_id")

        clients = await self._get_provider_clients(user_id=user_id, db=db)

        try:
            agent = await asyncio.to_thread(clients.agent.get_draft_by_id, agent_id)
        except Exception as exc:  # noqa: BLE001
            raise_as_deployment_error(
                exc,
                error_prefix=ErrorPrefix.HEALTH,
                log_msg="Unexpected error fetching wxO deployment status",
            )

        if not agent or isinstance(agent, str):  # the adk returns a string if not found
            raise DeploymentNotFoundError(deployment_id=agent_id)

        return DeploymentStatusResult(
            id=agent_id,
            provider_data={
                "status": "connected",
                "environment": derive_agent_environment(agent),
            },
        )

    async def create_execution(
        self,
        *,
        user_id: IdLike,
        deployment_type: DeploymentType | None = None,  # noqa: ARG002
        payload: ExecutionCreate,
        db: AsyncSession,
    ) -> ExecutionCreateResult:
        """Create a provider-agnostic deployment execution."""
        agent_id = _normalize_and_validate_id(str(payload.deployment_id), field_name="deployment_id")

        clients = await self._get_provider_clients(user_id=user_id, db=db)

        provider_data: dict = payload.provider_data or {}

        try:
            agent_run_result = await create_agent_run(
                clients,
                provider_data=provider_data,
                deployment_id=agent_id,
            )
        except Exception as exc:  # noqa: BLE001
            raise_as_deployment_error(
                exc,
                error_prefix=ErrorPrefix.CREATE_EXECUTION,
                log_msg="Unexpected error creating wxO deployment execution",
                pass_through=(AuthenticationError, AuthorizationError, DeploymentNotFoundError, InvalidContentError),
            )

        return ExecutionCreateResult(
            execution_id=agent_run_result.get("run_id"),
            deployment_id=agent_id,
            provider_result=agent_run_result,
        )

    async def get_execution(
        self,
        *,
        user_id: IdLike,
        execution_id: IdLike,
        deployment_type: DeploymentType | None = None,  # noqa: ARG002
        db: AsyncSession,
    ) -> ExecutionStatusResult:
        """Get provider-agnostic deployment execution state/output."""
        run_id = _normalize_and_validate_id(str(execution_id), field_name="execution_id")

        clients = await self._get_provider_clients(user_id=user_id, db=db)

        try:
            agent_run_result = await get_agent_run(
                clients,
                run_id=run_id,
            )
        except Exception as exc:  # noqa: BLE001
            raise_as_deployment_error(
                exc,
                error_prefix=ErrorPrefix.GET_EXECUTION,
                log_msg="Unexpected error fetching wxO deployment execution",
                pass_through=(AuthenticationError, AuthorizationError, DeploymentNotFoundError, InvalidContentError),
            )

        return ExecutionStatusResult(
            execution_id=run_id,
            deployment_id=agent_run_result.get("agent_id"),
            provider_result=agent_run_result,
        )

    async def list_configs(
        self,
        *,
        user_id: IdLike,
        params: ConfigListParams | None = None,
        db: AsyncSession,
    ) -> ConfigListResult:
        """List configs visible to this adapter."""
        agent_id = _require_single_deployment_id(params, resource_label="config")
        clients = await self._get_provider_clients(user_id=user_id, db=db)

        try:
            agent = await asyncio.to_thread(clients.agent.get_draft_by_id, agent_id)
        except Exception as exc:  # noqa: BLE001
            raise_as_deployment_error(
                exc,
                error_prefix=ErrorPrefix.LIST_CONFIGS,
                log_msg="Unexpected error while listing wxO deployment configs",
            )

        if not agent:
            msg = f"Deployment '{agent_id}' not found."
            raise DeploymentNotFoundError(msg)

        tool_ids = agent.get("tools", []) if isinstance(agent, dict) else []
        tool_ids = dedupe_list(tool_ids)

        if not tool_ids:
            return ConfigListResult(
                configs=[],
                provider_result={"deployment_id": agent_id, "tool_ids": []},
            )

        tools: list[dict]

        try:
            tools = await asyncio.to_thread(clients.tool.get_drafts_by_ids, tool_ids)
        except Exception as exc:  # noqa: BLE001
            raise_as_deployment_error(
                exc,
                error_prefix=ErrorPrefix.LIST_CONFIGS,
                log_msg="Unexpected error while listing wxO tools for config extraction",
            )

        app_ids: set[str] = set()
        for tool in tools or []:
            if not isinstance(tool, dict):
                continue
            connections: dict = tool.get("binding", {}).get("langflow", {}).get("connections", {})
            if not connections:
                continue
            app_ids.update(connections.keys())

        return ConfigListResult(
            configs=[ConfigListItem(id=app_id, name=app_id) for app_id in app_ids],
            provider_result={"deployment_id": agent_id},
        )

    async def list_snapshots(
        self,
        *,
        user_id: IdLike,
        params: SnapshotListParams | None = None,
        db: AsyncSession,
    ) -> SnapshotListResult:
        """List snapshots visible to this adapter."""
        agent_id = _require_single_deployment_id(params, resource_label="snapshot")
        clients = await self._get_provider_clients(user_id=user_id, db=db)

        try:
            agent = await asyncio.to_thread(clients.agent.get_draft_by_id, agent_id)
        except Exception as exc:  # noqa: BLE001
            raise_as_deployment_error(
                exc,
                error_prefix=ErrorPrefix.LIST,
                log_msg="Unexpected error while listing wxO deployment snapshots",
            )

        if not agent or not isinstance(agent, dict):
            msg = f"Deployment '{agent_id}' not found."
            raise DeploymentNotFoundError(msg)

        tools: list[dict] = []
        requested_tool_ids = dedupe_list(agent.get("tools", []))
        if requested_tool_ids:
            try:
                tools = await asyncio.to_thread(clients.tool.get_drafts_by_ids, requested_tool_ids)
            except Exception as exc:  # noqa: BLE001
                raise_as_deployment_error(
                    exc,
                    error_prefix=ErrorPrefix.LIST,
                    log_msg="Unexpected error while listing wxO tools for snapshot extraction",
                )

        snapshots = [
            SnapshotItem(
                id=tool["id"],
                name=tool.get("name") or tool["id"],
            )
            for tool in (tools or [])
            if tool.get("id")
        ]
        if not snapshots and requested_tool_ids:
            snapshots = [SnapshotItem(id=tool_id, name=tool_id) for tool_id in requested_tool_ids]

        return SnapshotListResult(
            snapshots=snapshots,
            provider_result={"deployment_id": agent_id},
        )

    async def _create_agent_deployment(
        self,
        *,
        clients: WxOClient,
        tool_ids: Sequence[str],
        data: BaseDeploymentData,
    ) -> AgentUpsertResponse:
        """Create an agent deployment."""
        payload = build_agent_payload(
            data=data,
            tool_ids=tool_ids,
        )
        return await asyncio.to_thread(clients.agent.create, payload)

    async def teardown(self) -> None:
        """Teardown provider-specific resources."""
