"""Slim WatsonxOrchestrateDeploymentService that delegates to submodules."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from cachetools import TTLCache
from fastapi import HTTPException, status
from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException
from lfx.services.adapters.deployment.base import BaseDeploymentService
from lfx.services.adapters.deployment.exceptions import (
    DeploymentConflictError,
    DeploymentError,
    DeploymentNotFoundError,
    DeploymentServiceError,
    DeploymentSupportError,
    InvalidContentError,
    InvalidDeploymentOperationError,
    InvalidDeploymentTypeError,
)
from lfx.services.adapters.deployment.schema import (
    BaseDeploymentData,
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
    _normalize_and_validate_id,
)

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
from langflow.services.adapters.deployment.watsonx_orchestrate.utils import (
    build_agent_payload,
    extract_agent_tool_ids,
    extract_error_detail,
    resolve_resource_name_prefix,
    validate_wxo_name,
)
from langflow.services.deps import get_settings_service

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from uuid import UUID

    from ibm_watsonx_orchestrate_clients.agents.agent_client import AgentUpsertResponse
    from lfx.services.settings.service import SettingsService

    from langflow.services.adapters.deployment.watsonx_orchestrate.types import WxOClient


class WatsonxOrchestrateDeploymentService(BaseDeploymentService):
    """Deployment adapter for Watsonx Orchestrate.

    Mapping used by this adapter:
    - deployment -> wxO agent bound to exactly one connection app_id and many tools
    - snapshot -> wxO tool (langflow binding) and "immutable" once created
    - config -> wxO connection configuration (+ credentials), keyed by app_id
    """

    name = "deployment_service"

    def __init__(self, settings_service: SettingsService | None = None):
        super().__init__()
        if settings_service is None:
            settings_service = get_settings_service()
        if settings_service is None:
            msg = "Settings service is not available."
            raise RuntimeError(msg)
        self.settings_service = settings_service
        self._client_managers: TTLCache = TTLCache(maxsize=128, ttl=3600)
        self.set_ready()

    async def _get_provider_clients(self, *, user_id: UUID | str, db: Any) -> WxOClient:
        return await get_provider_clients(
            user_id=user_id,
            db=db,
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
                    lambda: process_config(
                        user_id=user_id,
                        db=db,
                        deployment_name=prefixed_app_id,
                        config=payload.config,
                        client_cache=self._client_managers,
                    )
                )

                if payload.snapshot and (flow_payloads := payload.snapshot.raw_payloads):
                    created_tool_ids = await retry_create(
                        lambda: process_raw_flows_with_app_id(
                            user_id=user_id,
                            app_id=prefixed_app_id,
                            flows=flow_payloads,
                            db=db,
                            tool_name_prefix=resource_prefix,
                            client_cache=self._client_managers,
                        )
                    )

                derived_spec: BaseDeploymentData = deployment_spec.model_copy(deep=True)

                if derived_spec.provider_spec is None:
                    derived_spec.provider_spec = {}

                derived_spec.provider_spec.update(
                    {
                        "name": prefixed_deployment_name,
                        "display_name": derived_spec.name,
                    }
                )

                agent_create_response = await retry_create(
                    lambda: self._create_agent_deployment(
                        data=derived_spec,
                        tool_ids=created_tool_ids,
                        user_id=user_id,
                        db=db,
                    )
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
                raise DeploymentConflictError(message=msg) from None
            if status_code == status.HTTP_422_UNPROCESSABLE_CONTENT:
                msg = (
                    f"{ErrorPrefix.CREATE.value} "
                    "The deployment request entity is unprocessable. "
                    "Please ensure the request entity is valid and complete. "
                    f"error details: {error_detail}"
                )
                raise InvalidContentError(message=msg) from None
            msg = f"{ErrorPrefix.CREATE.value} error details: {error_detail}"
            raise DeploymentError(message=msg, error_code="deployment_error") from None
        except DeploymentServiceError:
            raise
        except Exception:
            logger.exception("Unexpected error during wxO deployment creation")
            msg = f"{ErrorPrefix.CREATE.value} Please check server logs for details."
            raise DeploymentError(message=msg, error_code="deployment_error") from None

        if agent_create_response is None:
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
            deployment_types: set[DeploymentType] = set()
            invalid_deployment_types: set[DeploymentType] = set()

            if params and params.deployment_types:
                deployment_types = set(params.deployment_types)
                invalid_deployment_types = deployment_types.difference(SUPPORTED_ADAPTER_DEPLOYMENT_TYPES)

            if invalid_deployment_types:
                invalid_values = ", ".join([dtype.value for dtype in invalid_deployment_types])
                msg = f"{ErrorPrefix.LIST.value}watsonx Orchestrate has no such deployment type(s): '{invalid_values}'."
                raise InvalidDeploymentTypeError(message=msg)

            query_params: ProviderPayload = {}

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
        except DeploymentServiceError:
            raise
        except (ClientAPIException, HTTPException) as exc:
            if isinstance(exc, ClientAPIException):
                error_detail = extract_error_detail(getattr(exc.response, "text", ""))
            else:
                error_detail = extract_error_detail(str(exc.detail))
            msg = f"{ErrorPrefix.LIST.value} error details: {error_detail}"
            raise DeploymentError(message=msg, error_code="deployment_error") from None
        except Exception:
            logger.exception("Unexpected error while listing wxO deployments")
            msg = f"{ErrorPrefix.LIST.value} Please check server logs for details."
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
        agent = await asyncio.to_thread(client_manager.agent.get_draft_by_id, deployment_id)
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
        payload: DeploymentUpdate,
        db: Any,
    ) -> DeploymentUpdateResult:
        """Update deployment metadata, snapshot bindings, and/or connection binding."""
        clients = await self._get_provider_clients(user_id=user_id, db=db)

        agent_id = _normalize_and_validate_id(str(deployment_id), field_name="deployment_id")
        agent = await asyncio.to_thread(clients.agent.get_draft_by_id, agent_id)

        if not agent:
            msg = f"Deployment '{agent_id}' not found."
            raise DeploymentNotFoundError(msg)

        config = payload.config

        if config and "config_id" in config.model_fields_set:
            msg = (
                "Replacing or unbinding deployment "
                "configuration/connection via patch "
                "is not allowed for watsonx Orchestrate "
                "deployments in Langflow. "
                "Please do not set the config_id field."
            )
            raise InvalidDeploymentOperationError(message=msg)

        update_payload: dict[str, Any] = {}

        if payload.spec:
            spec_updates = payload.spec.model_dump(exclude_unset=True)
            if "name" in spec_updates:
                update_payload.update(
                    {
                        "name": validate_wxo_name(spec_updates["name"]),
                        "display_name": spec_updates["name"],
                    }
                )
            if "description" in spec_updates:
                update_payload["description"] = spec_updates["description"]

        if payload.snapshot:
            msg = "Updating snapshot bindings is not supported by watsonx Orchestrate."
            raise InvalidDeploymentOperationError(message=msg)

        if update_payload:
            await asyncio.to_thread(clients.agent.update, agent_id, update_payload)

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
        user_id: IdLike,
        deployment_id: IdLike,
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
        logger.info("Deleting wxO deployment deployment_id=%s", deployment_id)
        agent_id = _normalize_and_validate_id(str(deployment_id), field_name="deployment_id")
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        try:
            await asyncio.to_thread(clients.agent.delete, agent_id)
        except ClientAPIException as e:
            status_code = e.response.status_code
            if status_code == status.HTTP_404_NOT_FOUND:
                msg = f"{ErrorPrefix.DELETE.value} deployment id '{agent_id}' not found."
                raise DeploymentNotFoundError(msg) from None
            msg = f"{ErrorPrefix.DELETE.value} error details: {extract_error_detail(e.response.text)}"
            raise DeploymentError(msg, error_code="deployment_error") from None
        except DeploymentServiceError:
            raise
        except Exception:
            logger.exception("Unexpected error while deleting wxO deployment %s", agent_id)
            msg = f"An unexpected error occurred while deleting deployment '{agent_id}'."
            raise DeploymentError(msg, error_code="deployment_error") from None

        return DeploymentDeleteResult(id=agent_id)

    async def get_status(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        db: Any,
    ) -> DeploymentStatusResult:
        """Get deployment health directly from wxO release status endpoint."""
        agent_id = _normalize_and_validate_id(str(deployment_id), field_name="deployment_id")

        clients = await self._get_provider_clients(user_id=user_id, db=db)

        status_data: dict[str, Any] = {}

        try:
            agent = await asyncio.to_thread(clients.agent.get_draft_by_id, agent_id)
            if agent:
                status_data = {
                    "status": "connected",
                    "environment": derive_agent_environment(agent),
                }
        except DeploymentServiceError:
            raise
        except (ClientAPIException, HTTPException) as exc:
            if isinstance(exc, ClientAPIException):
                error_detail = extract_error_detail(getattr(exc.response, "text", ""))
            else:
                error_detail = extract_error_detail(str(exc.detail))
            msg = f"{ErrorPrefix.HEALTH.value} error details: {error_detail}"
            raise DeploymentError(message=msg, error_code="deployment_error") from None
        except Exception:
            logger.exception("Unexpected error fetching wxO deployment status")
            msg = f"{ErrorPrefix.HEALTH.value} Please check server logs for details."
            raise DeploymentError(message=msg, error_code="deployment_error") from None

        return DeploymentStatusResult(
            id=agent_id,
            provider_data=status_data
            or {
                "status": "not found",
                "environment": "unknown",
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
        agent_id = _normalize_and_validate_id(str(payload.deployment_id), field_name="deployment_id")

        clients = await self._get_provider_clients(user_id=user_id, db=db)

        provider_data: dict = payload.provider_data or {}

        try:
            agent_run_result = await create_agent_run(
                clients,
                provider_data=provider_data,
                deployment_id=agent_id,
            )
        except DeploymentServiceError:
            raise
        except (ClientAPIException, HTTPException) as exc:
            if isinstance(exc, ClientAPIException):
                error_detail = extract_error_detail(getattr(exc.response, "text", ""))
            else:
                error_detail = extract_error_detail(str(exc.detail))
            msg = f"{ErrorPrefix.CREATE_EXECUTION.value} error details: {error_detail}"
            raise DeploymentError(message=msg, error_code="deployment_error") from None
        except Exception as exc:
            logger.exception("Unexpected error creating wxO deployment execution")
            msg = "An unexpected error occurred while creating a deployment execution in Watsonx Orchestrate."
            raise DeploymentError(message=msg, error_code="deployment_error") from exc

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
        db: Any,
    ) -> ExecutionStatusResult:
        """Get provider-agnostic deployment execution state/output."""
        run_id = _normalize_and_validate_id(str(execution_id), field_name="execution_id")

        clients = await self._get_provider_clients(user_id=user_id, db=db)

        agent_run_result = await get_agent_run(
            clients,
            run_id=run_id,
        )

        return ExecutionStatusResult(
            execution_id=run_id,
            deployment_id=agent_run_result.get("agent_id"),
            provider_result=agent_run_result,
        )

    async def _create_agent_deployment(
        self,
        *,
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
        return await asyncio.to_thread(clients.agent.create, payload)

    async def teardown(self) -> None:
        """Teardown provider-specific resources."""
        self._client_managers.clear()
