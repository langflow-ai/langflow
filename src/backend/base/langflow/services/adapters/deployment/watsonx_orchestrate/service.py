"""Slim WatsonxOrchestrateDeploymentService that delegates to submodules."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from ibm_cloud_sdk_core import ApiException
from ibm_watsonx_orchestrate_clients.connections.connections_client import ListConfigsResponse
from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException
from lfx.services.adapters.deployment.base import BaseDeploymentService
from lfx.services.adapters.deployment.exceptions import (
    AuthenticationError,
    AuthorizationError,
    AuthSchemeError,
    DeploymentConflictError,
    DeploymentError,
    DeploymentNotFoundError,
    DeploymentSupportError,
    InvalidContentError,
    InvalidDeploymentOperationError,
    InvalidDeploymentTypeError,
    OperationNotSupportedError,
    ResourceNotFoundError,
    raise_for_status_and_detail,
)
from lfx.services.adapters.deployment.schema import (
    BaseDeploymentData,
    BaseFlowArtifact,
    ConfigListItem,
    ConfigListParams,
    ConfigListResult,
    DeploymentCreate,
    DeploymentCreateResult,
    DeploymentDeleteResult,
    DeploymentDuplicateResult,
    DeploymentGetResult,
    DeploymentListLlmsResult,
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
    SnapshotUpdateResult,
    VerifyCredentials,
    VerifyCredentialsResult,
    _normalize_and_validate_id,
)
from lfx.services.adapters.payload import AdapterPayloadMissingError, AdapterPayloadValidationError

from langflow.services.adapters.deployment.watsonx_orchestrate.client import get_authenticator, get_provider_clients
from langflow.services.adapters.deployment.watsonx_orchestrate.constants import (
    SUPPORTED_ADAPTER_DEPLOYMENT_TYPES,
    ErrorPrefix,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.core.create import (
    apply_provider_create_plan_with_rollback,
    build_provider_create_plan,
    validate_provider_create_request_sections,
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
    build_langflow_artifact_bytes,
    extract_langflow_connections_binding,
    upload_tool_artifact_bytes,
    verify_tools_by_ids,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.core.update import (
    apply_provider_update_plan_with_rollback,
    build_provider_update_plan,
    build_update_payload_from_spec,
    validate_provider_update_request_sections,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.payloads import (
    PAYLOAD_SCHEMAS,
    WatsonxDeploymentCreatePayload,
    WatsonxDeploymentCreateResultData,
    WatsonxDeploymentLlmListResultData,
    WatsonxDeploymentUpdatePayload,
    WatsonxDeploymentUpdateResultData,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.utils import (
    _require_single_deployment_id,
    dedupe_list,
    extract_agent_tool_ids,
    extract_error_detail,
    raise_as_deployment_error,
)
from langflow.services.deps import get_settings_service

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Any

    from lfx.services.settings.service import SettingsService
    from sqlalchemy.ext.asyncio import AsyncSession

    from langflow.services.adapters.deployment.watsonx_orchestrate.types import WxOClient


class WatsonxOrchestrateDeploymentService(BaseDeploymentService):
    """Deployment adapter for Watsonx Orchestrate."""

    name = "deployment_service"
    payload_schemas = PAYLOAD_SCHEMAS

    def __init__(self, settings_service: SettingsService | None = None):
        super().__init__()
        if settings_service is None:
            settings_service = get_settings_service()
        if settings_service is None:
            msg = "Settings service is not available."
            raise RuntimeError(msg)
        self.settings_service = settings_service
        self.set_ready()

    @staticmethod
    def _build_config_list_item(
        *,
        connection_id: str,
        app_id: str,
        config_type: str | None = None,
    ) -> ConfigListItem:
        """Build a normalized config list item from resolved identifiers."""
        provider_data = {"type": config_type} if config_type else None
        return ConfigListItem(
            id=connection_id,
            name=app_id,
            provider_data=provider_data,
        )

    @staticmethod
    def _normalize_optional_text(value: object | None) -> str | None:
        """Normalize SDK scalar/enum/tuple values to optional text.

        Guards against two quirks in the upstream SDK model definitions:

        * **Tuple defaults** - Several ``ListConfigsResponse`` fields are
          declared with trailing commas (e.g. ``security_scheme: ... = None,``)
          which makes the Python default ``(None,)`` instead of ``None``.
          Pydantic coerces this away when the field *is* supplied, but we
          unwrap single-element tuples defensively in case a future SDK
          version or edge case surfaces the raw default.
        * **str-Enum coercion** - ``ConnectionSecurityScheme(str, Enum)``
          inherits from ``str``, yet ``str()`` returns the class-qualified
          name (``"ConnectionSecurityScheme.KEY_VALUE"``) in Python 3.11+.
          Extracting ``.value`` yields the raw string we need.
        """
        if isinstance(value, tuple):
            if len(value) == 1:
                value = value[0]
            else:
                logger.debug("_normalize_optional_text: ignoring multi-element tuple: %s", value)
                return None
        if hasattr(value, "value"):
            value = value.value
        normalized = str(value or "").strip()
        return normalized or None

    async def _get_provider_clients(self, *, user_id: IdLike, db: AsyncSession) -> WxOClient:
        """Resolve provider clients through a service-level seam.

        A dedicated method keeps call sites patchable in unit/e2e tests and
        centralizes provider-client resolution behavior for this service.
        """
        return await get_provider_clients(user_id=user_id, db=db)

    def _parse_provider_payload(
        self,
        *,
        slot,
        slot_name: str,
        provider_data: object,
        error_prefix: ErrorPrefix,
    ):
        if slot is None:
            msg = f"{error_prefix.value} Required slot '{slot_name}' is not configured."
            raise DeploymentError(message=msg, error_code="deployment_error")

        try:
            return slot.parse(provider_data)
        except (AdapterPayloadMissingError, AdapterPayloadValidationError) as exc:
            msg = exc.format_first_error() if isinstance(exc, AdapterPayloadValidationError) else str(exc)
            raise InvalidContentError(message=msg) from None

    def _validate_snapshot_item_provider_data(self, raw: dict[str, object]) -> dict[str, object]:
        """Validate per-item snapshot provider_data via configured slot."""
        snapshot_item_slot = self.payload_schemas.snapshot_item_data
        if snapshot_item_slot is None:
            msg = f"{ErrorPrefix.LIST.value} Required slot 'snapshot_item_data' is not configured."
            raise DeploymentError(message=msg, error_code="deployment_error")

        try:
            return snapshot_item_slot.apply(raw)
        except (AdapterPayloadMissingError, AdapterPayloadValidationError) as exc:
            detail = exc.format_first_error() if isinstance(exc, AdapterPayloadValidationError) else str(exc)
            raise InvalidContentError(message=detail) from None

    async def create(
        self,
        *,
        user_id: IdLike,
        payload: DeploymentCreate,
        db: AsyncSession,
    ) -> DeploymentCreateResult:
        """Create a deployment in Watsonx Orchestrate."""
        logger.info("Creating wxO deployment for user_id=%s", user_id)
        try:
            deployment_spec: BaseDeploymentData = payload.spec
            # TODO: clean up ambiguity between spec vs config.
            if deployment_spec.type != DeploymentType.AGENT:
                msg = (
                    f"{ErrorPrefix.CREATE.value}"
                    f"Deployment type '{deployment_spec.type.value}' "
                    "is not supported by watsonx Orchestrate."
                )
                raise DeploymentSupportError(message=msg)

            validate_provider_create_request_sections(payload)
            deployment_create_slot = self.payload_schemas.deployment_create

            provider_create: WatsonxDeploymentCreatePayload = self._parse_provider_payload(
                slot=deployment_create_slot,
                slot_name="deployment_create",
                provider_data=payload.provider_data,
                error_prefix=ErrorPrefix.CREATE,
            )

            clients = await self._get_provider_clients(user_id=user_id, db=db)
            provider_plan = build_provider_create_plan(
                deployment_name=deployment_spec.name,
                provider_create=provider_create,
            )
            apply_result = await apply_provider_create_plan_with_rollback(
                clients=clients,
                user_id=user_id,
                db=db,
                deployment_spec=deployment_spec,
                plan=provider_plan,
            )
        except (
            AuthenticationError,
            DeploymentConflictError,
            InvalidContentError,
            InvalidDeploymentOperationError,
            InvalidDeploymentTypeError,
            DeploymentSupportError,
        ):
            raise
        except (ClientAPIException, HTTPException) as exc:
            raise_as_deployment_error(
                exc,
                error_prefix=ErrorPrefix.CREATE,
                log_msg="Unexpected provider error during wxO deployment create",
            )
        except Exception as exc:
            logger.exception("Unexpected error during wxO deployment creation")
            msg = f"{ErrorPrefix.CREATE.value} Please check server logs for details."
            raise DeploymentError(message=msg, error_code="deployment_error") from exc

        create_result_payload = WatsonxDeploymentCreateResultData(
            app_ids=apply_result.app_ids,
            tools_with_refs=apply_result.tools_with_refs,
            tool_app_bindings=apply_result.tool_app_bindings,
        )
        create_result_slot = self.payload_schemas.deployment_create_result
        if create_result_slot is None:
            msg = f"{ErrorPrefix.CREATE.value} Required slot 'deployment_create_result' is not configured."
            raise DeploymentError(message=msg, error_code="deployment_error")

        return DeploymentCreateResult[WatsonxDeploymentCreateResultData](
            id=apply_result.agent_id,
            provider_result=create_result_slot.parse(create_result_payload),
        )

    async def rollback_create_result(
        self,
        *,
        user_id: IdLike,
        deployment_id: IdLike,
        provider_result: object,
        db: AsyncSession,
    ) -> None:
        """Best-effort cleanup for create-time side resources after a DB failure."""
        result_data = WatsonxDeploymentCreateResultData.model_validate(provider_result)
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        tool_ids = dedupe_list([binding.tool_id for binding in result_data.tools_with_refs])
        await rollback_created_resources(
            clients=clients,
            agent_id=_normalize_and_validate_id(str(deployment_id), field_name="deployment_id"),
            tool_ids=tool_ids,
            app_ids=result_data.app_ids,
        )

    async def list_types(
        self,
        *,
        user_id: IdLike,  # noqa: ARG002
        db: AsyncSession,  # noqa: ARG002
    ) -> DeploymentListTypesResult:
        """List deployment types supported by the provider."""
        return DeploymentListTypesResult(deployment_types=list(SUPPORTED_ADAPTER_DEPLOYMENT_TYPES))

    async def list_llms(
        self,
        *,
        user_id: IdLike,
        db: AsyncSession,
    ) -> DeploymentListLlmsResult:
        """List provider-available LLM model names."""
        client_manager = await self._get_provider_clients(user_id=user_id, db=db)
        try:
            raw_models = await asyncio.to_thread(client_manager.get_models_raw)
            parsed_models: WatsonxDeploymentLlmListResultData = self._parse_provider_payload(
                slot=self.payload_schemas.deployment_llm_list_result,
                slot_name="deployment_llm_list_result",
                provider_data={"models": raw_models},
                error_prefix=ErrorPrefix.LIST_LLMS,
            )
            return DeploymentListLlmsResult(
                provider_result=parsed_models.model_dump(exclude_none=True),
            )
        except Exception as exc:  # noqa: BLE001
            raise_as_deployment_error(
                exc,
                error_prefix=ErrorPrefix.LIST_LLMS,
                log_msg="Unexpected error while listing wxO deployment LLMs",
                pass_through=(InvalidContentError),
            )

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
                        "tool_ids": extract_agent_tool_ids(agent),
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
            provider_data={
                **({"llm": agent["llm"]} if isinstance(agent, dict) and agent.get("llm") else {}),
            }
            or None,
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

            validate_provider_update_request_sections(payload)
            provider_update: WatsonxDeploymentUpdatePayload | None = None
            if payload.provider_data is not None:
                provider_update = self._parse_provider_payload(
                    slot=self.payload_schemas.deployment_update,
                    slot_name="deployment_update",
                    provider_data=payload.provider_data,
                    error_prefix=ErrorPrefix.UPDATE,
                )
            # base agent payload to build for final update call
            update_payload: dict[str, Any] = build_update_payload_from_spec(
                payload.spec,
                llm=provider_update.llm if provider_update is not None else None,
            )

            if payload.provider_data is None or not (provider_update is not None and provider_update.has_tool_work):
                if not update_payload:
                    msg = "provider_data is required when update operations do not include spec changes."
                    raise InvalidContentError(message=msg)
                await retry_create(
                    asyncio.to_thread,
                    clients.agent.update,
                    agent_id,
                    update_payload,
                )
                return DeploymentUpdateResult[WatsonxDeploymentUpdateResultData](
                    id=deployment_id, provider_result=WatsonxDeploymentUpdateResultData()
                )

            provider_plan = build_provider_update_plan(
                agent=agent,
                provider_update=provider_update,
            )

            apply_result = await apply_provider_update_plan_with_rollback(
                clients=clients,
                user_id=user_id,
                db=db,
                agent_id=agent_id,
                agent=agent,
                update_payload=update_payload,
                plan=provider_plan,
            )

            return DeploymentUpdateResult[WatsonxDeploymentUpdateResultData](
                id=deployment_id,
                provider_result=self.payload_schemas.deployment_update_result.apply(
                    WatsonxDeploymentUpdateResultData(
                        created_app_ids=apply_result.created_app_ids,
                        created_snapshot_ids=apply_result.created_snapshot_ids,
                        added_snapshot_ids=apply_result.added_snapshot_ids,
                        created_snapshot_bindings=apply_result.created_snapshot_bindings,
                        added_snapshot_bindings=apply_result.added_snapshot_bindings,
                        removed_snapshot_bindings=apply_result.removed_snapshot_bindings,
                        referenced_snapshot_bindings=apply_result.referenced_snapshot_bindings,
                    )
                ),
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
        """Delete the deployment agent from the provider.

        Only the agent itself is removed. Tools and connections are NOT
        deleted — direct deletion of tools/connections is not supported
        by this adapter.
        """
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
                pass_through=(AuthenticationError, AuthorizationError, ResourceNotFoundError, InvalidContentError),
            )

        return ExecutionCreateResult(
            execution_id=agent_run_result.get("execution_id"),
            deployment_id=agent_id,
            provider_result=self.payload_schemas.execution_create_result.parse(agent_run_result).model_dump(
                exclude_none=True
            ),
        )

    async def get_execution(
        self,
        *,
        user_id: IdLike,
        execution_id: IdLike,
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
                pass_through=(AuthenticationError, AuthorizationError, ResourceNotFoundError, InvalidContentError),
            )

        return ExecutionStatusResult(
            execution_id=run_id,
            deployment_id=agent_run_result.get("agent_id"),
            provider_result=self.payload_schemas.execution_status_result.parse(agent_run_result).model_dump(
                exclude_none=True
            ),
        )

    # TODO: allow listing all configs without filtering by deployment_id
    async def list_configs(
        self,
        *,
        user_id: IdLike,
        params: ConfigListParams | None = None,
        db: AsyncSession,
    ) -> ConfigListResult:
        """List configs visible to this adapter."""
        clients = await self._get_provider_clients(user_id=user_id, db=db)
        if not params or not params.deployment_ids:
            try:
                raw_connections = await asyncio.to_thread(clients.connections.list)
            except Exception as exc:  # noqa: BLE001
                raise_as_deployment_error(
                    exc,
                    error_prefix=ErrorPrefix.LIST_CONFIGS,
                    log_msg="Unexpected error while listing wxO tenant configs",
                )

            configs: list[ConfigListItem] = []
            seen_ids: set[str] = set()
            for connection in raw_connections or []:
                if not isinstance(connection, ListConfigsResponse):
                    logger.debug(
                        "list_configs: skipping unexpected connection entry type: %s",
                        type(connection).__name__,
                    )
                    continue
                config_id = str(connection.connection_id or "").strip()
                config_name = str(connection.app_id or "").strip()
                if not config_id or not config_name:
                    logger.debug(
                        "list_configs: skipping config with missing connection_id/app_id: connection_id=%s app_id=%s",
                        connection.connection_id,
                        connection.app_id,
                    )
                    continue
                if config_id in seen_ids:
                    continue
                seen_ids.add(config_id)
                config_type = self._normalize_optional_text(connection.security_scheme)
                configs.append(
                    self._build_config_list_item(
                        connection_id=config_id,
                        app_id=config_name,
                        config_type=config_type,
                    )
                )
            return ConfigListResult(
                configs=configs,
                provider_result=self.payload_schemas.config_list_result.parse({}).model_dump(exclude_none=True),
            )

        agent_id = _require_single_deployment_id(params, resource_label="config")
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
                provider_result=self.payload_schemas.config_list_result.parse(
                    {"deployment_id": agent_id, "tool_ids": []}
                ).model_dump(exclude_none=True),
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

        app_to_connection_id: dict[str, str] = {}
        for tool in tools or []:
            if not isinstance(tool, dict):
                continue
            connections = extract_langflow_connections_binding(tool)
            if not connections:
                continue
            for app_id, connection_id in connections.items():
                normalized_app_id = str(app_id).strip()
                normalized_connection_id = str(connection_id).strip()
                if not normalized_app_id:
                    continue
                app_to_connection_id.setdefault(
                    normalized_app_id,
                    normalized_connection_id or normalized_app_id,
                )

        connection_type_by_id: dict[str, str] = {}
        connection_ids = dedupe_list(
            [connection_id for connection_id in app_to_connection_id.values() if connection_id]
        )
        if connection_ids:
            try:
                detailed_connections = await asyncio.to_thread(clients.connections.get_drafts_by_ids, connection_ids)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "list_configs: failed to enrich deployment configs with connection types",
                    exc_info=exc,
                )
            else:
                for connection in detailed_connections or []:
                    if not isinstance(connection, ListConfigsResponse):
                        continue
                    connection_id = str(connection.connection_id or "").strip()
                    if not connection_id:
                        continue
                    config_type = self._normalize_optional_text(connection.security_scheme)
                    if config_type:
                        connection_type_by_id[connection_id] = config_type

        # Preserve first-seen binding order (tool order + per-tool connection order)
        # instead of re-sorting app_ids alphabetically.
        configs = [
            self._build_config_list_item(
                connection_id=connection_id,
                app_id=app_id,
                config_type=connection_type_by_id.get(connection_id),
            )
            for app_id, connection_id in app_to_connection_id.items()
        ]

        return ConfigListResult(
            configs=configs,
            provider_result=self.payload_schemas.config_list_result.parse({"deployment_id": agent_id}).model_dump(
                exclude_none=True
            ),
        )

    async def list_snapshots(
        self,
        *,
        user_id: IdLike,
        params: SnapshotListParams | None = None,
        db: AsyncSession,
    ) -> SnapshotListResult:
        """List snapshots visible to this adapter.

        Supports three modes:
        - **deployment-scoped**: requires exactly one ``deployment_id`` in params;
          returns tools bound to that agent.
        - **snapshot-ids-only**: when ``snapshot_ids`` is provided and
          ``deployment_ids`` is empty/None, fetches tools directly by ID to
          verify which ones still exist in the provider.
        - **tenant-scoped**: when neither deployment_ids nor snapshot_ids are
          provided, returns all draft tools visible in the provider tenant.
        """
        has_deployment_ids = params and params.deployment_ids
        has_snapshot_ids = params and params.snapshot_ids

        if has_snapshot_ids and has_deployment_ids:
            logger.warning(
                "list_snapshots called with both deployment_ids and snapshot_ids; "
                "snapshot_ids will be ignored in favour of the deployment-scoped path"
            )

        clients = await self._get_provider_clients(user_id=user_id, db=db)

        if has_snapshot_ids and not has_deployment_ids:
            return await verify_tools_by_ids(clients, params.snapshot_ids)  # type: ignore[union-attr]
        if not has_deployment_ids:
            try:
                raw_tools = await asyncio.to_thread(clients.get_tools_raw)
            except Exception as exc:  # noqa: BLE001
                raise_as_deployment_error(
                    exc,
                    error_prefix=ErrorPrefix.LIST,
                    log_msg="Unexpected error while listing wxO tenant snapshots",
                )
            snapshots = [
                SnapshotItem(
                    id=tool["id"],
                    name=tool.get("name") or tool["id"],
                    provider_data=self._validate_snapshot_item_provider_data(
                        {"connections": extract_langflow_connections_binding(tool)}
                    ),
                )
                for tool in (raw_tools or [])
                if isinstance(tool, dict) and tool.get("id")
            ]
            return SnapshotListResult(
                snapshots=snapshots,
                provider_result=self.payload_schemas.snapshot_list_result.parse({}).model_dump(exclude_none=True),
            )

        agent_id = _require_single_deployment_id(params, resource_label="snapshot")

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
                provider_data=self._validate_snapshot_item_provider_data(
                    {"connections": extract_langflow_connections_binding(tool)}
                ),
            )
            for tool in (tools or [])
            if isinstance(tool, dict) and tool.get("id")
        ]
        if not snapshots and requested_tool_ids:
            snapshots = [
                SnapshotItem(
                    id=tool_id,
                    name=tool_id,
                    provider_data=self._validate_snapshot_item_provider_data({"connections": {}}),
                )
                for tool_id in requested_tool_ids
            ]

        return SnapshotListResult(
            snapshots=snapshots,
            provider_result=self.payload_schemas.snapshot_list_result.parse({"deployment_id": agent_id}).model_dump(
                exclude_none=True
            ),
        )

    async def _list_snapshots_by_ids(
        self,
        *,
        user_id: IdLike,
        snapshot_ids: Sequence[str],
        db: AsyncSession,
    ) -> SnapshotListResult:
        """Fetch tools directly by ID to verify which ones still exist."""
        if not snapshot_ids:
            return SnapshotListResult(snapshots=[])

        clients = await self._get_provider_clients(user_id=user_id, db=db)
        try:
            snapshots = await verify_tools_by_ids(clients, list(snapshot_ids))
        except Exception as exc:  # noqa: BLE001
            raise_as_deployment_error(
                exc,
                error_prefix=ErrorPrefix.LIST,
                log_msg="Unexpected error while verifying wxO tool snapshots by ID",
            )
        return snapshots

    async def verify_credentials(
        self,
        *,
        user_id: IdLike,  # noqa: ARG002
        payload: VerifyCredentials,
    ) -> VerifyCredentialsResult:
        """Verify WXO credentials by obtaining a token from the provider."""
        verify_slot = self.payload_schemas.verify_credentials
        if verify_slot is None:
            msg = "Required slot 'verify_credentials' is not configured."
            raise DeploymentError(message=msg, error_code="deployment_error")

        provider_creds = verify_slot.parse(payload.provider_data)

        malformed_credentials_msg = (
            "Provider credentials are malformed. Please ensure the URL and API key are correctly formatted."
        )

        try:
            authenticator = get_authenticator(
                instance_url=payload.base_url,
                api_key=provider_creds.api_key,
            )
        except ValueError as exc:
            raise InvalidContentError(
                message=malformed_credentials_msg,
                cause=exc,
            ) from exc
        except AuthSchemeError:
            raise
        except Exception as exc:
            raise DeploymentError(
                message="Credential verification failed unexpectedly.",
                error_code="deployment_error",
                cause=exc,
            ) from exc

        try:
            await asyncio.to_thread(authenticator.token_manager.get_token)
        except ApiException as exc:
            # Log only the status code for diagnostics and avoid exposing
            # provider response details that could include sensitive values.
            logger.error(  # noqa: TRY400
                "Credential verification failed (status=%s)",
                exc.status_code,
            )
            raise_for_status_and_detail(
                status_code=exc.status_code,
                detail="Credential verification failed.",
                message_prefix="Credential verification",
                cause=None,
            )
        except Exception as exc:
            raise DeploymentError(
                message="Credential verification failed unexpectedly.",
                error_code="deployment_error",
                cause=exc,
            ) from exc

        return VerifyCredentialsResult()

    async def update_snapshot(
        self,
        *,
        user_id: IdLike,
        db: AsyncSession,
        snapshot_id: str,
        flow_artifact: BaseFlowArtifact,
    ) -> SnapshotUpdateResult:
        """Replace an existing snapshot's artifact content.

        This is a content-only mutation -- it re-uploads the artifact zip
        without touching the tool's name, metadata, or connection bindings.

        The tool name is fetched from wxO at call time, not derived from the
        Langflow flow name. This is intentional: the user may have set a
        custom tool name during initial deployment, or renamed the tool
        directly in the wxO console. Either way, the provider is the source
        of truth for the tool name.

        **Edge cases:**

        * **Tool renamed in wxO console** — The new name is picked up
          automatically on the next update since we always fetch it fresh.
          Langflow never stores the tool name locally.
        * **Tool deleted in wxO** — ``get_drafts_by_ids`` returns empty
          and we raise ``InvalidContentError`` before any mutation.
        * **Tool exists but name is empty/null** — Defensive check raises
          ``InvalidContentError`` rather than passing an empty name to the
          ADK, which would produce a cryptic validation error.
        * **Race condition (rename between fetch and upload)** — The
          artifact zip will contain the name as of the fetch. The tool's
          API-level name (set by wxO, not by the artifact) is unaffected
          by the zip contents, so this is harmless.
        * **Tool deleted + recreated with same name** — The new tool has
          a different ``tool_id``.  Our attachment still references the
          old (deleted) ID, so ``get_drafts_by_ids`` returns nothing and
          we fail with ``InvalidContentError``.  The user must re-deploy
          (or update the agent) to bind the new tool — we never silently
          adopt an unrelated tool just because the name matches.

        **Identity model:** we track tools by immutable ``tool_id``, not
        by name.  A rename preserves identity; a delete+recreate does not.

        **Blast-radius boundary:** callers must verify that ``snapshot_id``
        is tracked by a Langflow attachment record before calling this
        method; this prevents accidental overwrites of externally managed
        WXO tools.
        """
        from ibm_watsonx_orchestrate_core.types.tools.langflow_tool import (
            create_langflow_tool as _create_langflow_tool,
        )

        from langflow.utils.version import get_version_info

        clients = await self._get_provider_clients(user_id=user_id, db=db)

        # Fetch the existing tool to preserve its wxO name — the tool may have
        # been deployed with a custom name that differs from the Langflow flow
        # name, and we must not overwrite it with the flow name.
        existing_tools = await asyncio.to_thread(clients.tool.get_drafts_by_ids, [snapshot_id])
        if not existing_tools or not isinstance(existing_tools[0], dict):
            msg = f"Snapshot tool '{snapshot_id}' not found in provider."
            raise InvalidContentError(message=msg)
        existing_tool_name = str(existing_tools[0].get("name") or "").strip()
        if not existing_tool_name:
            msg = f"Snapshot tool '{snapshot_id}' exists but has no name. Cannot update artifact."
            raise InvalidContentError(message=msg)
        logger.debug("update_snapshot: snapshot_id='%s', existing tool name='%s'", snapshot_id, existing_tool_name)

        flow_definition = flow_artifact.model_dump(exclude={"provider_data"})
        flow_id = flow_definition.get("id")
        if flow_id is None:
            msg = "flow_definition must have an id"
            raise ValueError(msg)
        flow_definition["id"] = str(flow_id)
        flow_definition["name"] = existing_tool_name
        if not flow_definition.get("last_tested_version"):
            detected_version = (get_version_info() or {}).get("version")
            if detected_version:
                flow_definition["last_tested_version"] = detected_version

        tool = _create_langflow_tool(
            tool_definition=flow_definition,
            connections={},
            show_details=True,
        )

        artifact_bytes = build_langflow_artifact_bytes(
            tool=tool,
            flow_definition=flow_definition,
        )
        await asyncio.to_thread(
            upload_tool_artifact_bytes,
            clients,
            tool_id=snapshot_id,
            artifact_bytes=artifact_bytes,
        )
        return SnapshotUpdateResult(snapshot_id=snapshot_id)

    async def teardown(self) -> None:
        """Teardown provider-specific resources."""
