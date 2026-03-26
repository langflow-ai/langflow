"""Helpers used to keep wxO deployment create flow lean."""

from __future__ import annotations

import asyncio
import copy
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from lfx.services.adapters.deployment.exceptions import (
    DeploymentError,
    InvalidContentError,
    InvalidDeploymentOperationError,
)
from lfx.services.adapters.payload import AdapterPayloadValidationError

from langflow.services.adapters.deployment.watsonx_orchestrate.constants import ErrorPrefix
from langflow.services.adapters.deployment.watsonx_orchestrate.core.config import validate_connection
from langflow.services.adapters.deployment.watsonx_orchestrate.core.retry import (
    retry_create,
    retry_update,
    rollback_created_resources,
    rollback_update_resources,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.core.shared import (
    ConnectionCreateBatchError,
    OrderedUniqueStrs,
    RawConnectionCreatePlan,
    RawToolCreatePlan,
    create_connection_with_conflict_mapping,
    create_raw_tools_with_bindings,
    log_batch_errors,
    resolve_connections_for_operations,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.core.tools import (
    ToolUploadBatchError,
    create_and_upload_wxo_flow_tools_with_bindings,
    ensure_langflow_connections_binding,
    to_writable_tool_payload,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.payloads import (
    WatsonxBindOperation,
    WatsonxDeploymentCreatePayload,
    WatsonxFlowArtifactProviderData,
    WatsonxProviderCreateApplyResult,
    WatsonxToolAppBinding,
    WatsonxToolRefBinding,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.utils import (
    build_agent_payload_from_values,
    dedupe_list,
    resolve_resource_name_prefix,
    validate_wxo_name,
)

if TYPE_CHECKING:
    from lfx.services.adapters.deployment.payloads import DeploymentPayloadSchemas
    from lfx.services.adapters.deployment.schema import (
        BaseDeploymentData,
        BaseFlowArtifact,
        DeploymentCreate,
        IdLike,
    )
    from sqlalchemy.ext.asyncio import AsyncSession

    from langflow.services.adapters.deployment.watsonx_orchestrate.types import WxOClient

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ProviderCreatePlan:
    resource_prefix: str
    prefixed_deployment_name: str
    existing_tool_ids: list[str]
    existing_tool_bindings: dict[str, list[str]]
    existing_app_ids: list[str]
    raw_connections_to_create: list[RawConnectionCreatePlan]
    raw_tools_to_create: list[RawToolCreatePlan]
    selected_operation_app_ids: list[str]


def validate_provider_create_request_sections(payload: DeploymentCreate) -> None:
    """Reject top-level create sections in watsonx."""
    if payload.snapshot is not None or payload.config is not None:
        msg = (
            "Top-level 'snapshot' and 'config' create sections are no longer supported for "
            "watsonx Orchestrate deployment creation. Use provider_data operations instead."
        )
        raise InvalidDeploymentOperationError(message=msg)


def build_provider_create_plan(
    *,
    deployment_name: str,
    provider_create: WatsonxDeploymentCreatePayload,
) -> ProviderCreatePlan:
    """Build a deterministic CPU-only plan for provider_data create operations."""
    normalized_deployment_name = validate_wxo_name(deployment_name)
    resource_prefix = resolve_resource_name_prefix(caller_prefix=provider_create.resource_name_prefix)
    prefixed_deployment_name = f"{resource_prefix}{normalized_deployment_name}"

    # existing_tool_ids: provider tool ids from bind operations that reference
    #   pre-existing tools (via tool_id_with_ref); included in the final agent.
    existing_tool_ids = OrderedUniqueStrs()
    # existing_tool_bindings: per existing tool_id, collects operation app_ids
    #   that should be bound to that tool during creation.
    existing_tool_bindings: dict[str, OrderedUniqueStrs] = {}
    # existing_app_ids: declared existing connection app_ids (identity-mapped).
    existing_app_ids = OrderedUniqueStrs.from_values(list(provider_create.connections.existing_app_ids or []))
    # selected_operation_app_ids: all app_ids referenced by any bind operation
    #   (used to determine which connections the create plan needs).
    selected_operation_app_ids = OrderedUniqueStrs()

    # raw_tool_app_ids: per raw tool name, collects operation app_ids to bind
    #   when the raw tool is created.
    raw_tool_app_ids: dict[str, OrderedUniqueStrs] = {}
    for operation in provider_create.operations:
        if not isinstance(operation, WatsonxBindOperation):
            continue
        selected_operation_app_ids.extend(operation.app_ids)
        if operation.tool.tool_id_with_ref is not None:
            tool_id = operation.tool.tool_id_with_ref.tool_id
            existing_tool_ids.add(tool_id)
            existing_bindings = existing_tool_bindings.setdefault(tool_id, OrderedUniqueStrs())
            existing_bindings.extend(operation.app_ids)
            continue
        raw_name = str(operation.tool.name_of_raw)
        raw_apps = raw_tool_app_ids.setdefault(raw_name, OrderedUniqueStrs())
        raw_apps.extend(operation.app_ids)

    raw_connections_to_create = [
        RawConnectionCreatePlan(
            operation_app_id=raw_payload.app_id,
            provider_app_id=raw_payload.app_id,
            payload=raw_payload,
        )
        for raw_payload in (provider_create.connections.raw_payloads or [])
    ]
    raw_tool_pool = {raw_payload.name: raw_payload for raw_payload in (provider_create.tools.raw_payloads or [])}
    raw_tools_to_create = [
        RawToolCreatePlan(raw_name=raw_name, payload=raw_tool_pool[raw_name], app_ids=app_ids.to_list())
        for raw_name, app_ids in raw_tool_app_ids.items()
    ]

    return ProviderCreatePlan(
        resource_prefix=resource_prefix,
        prefixed_deployment_name=prefixed_deployment_name,
        existing_tool_ids=existing_tool_ids.to_list(),
        existing_tool_bindings={tool_id: app_ids.to_list() for tool_id, app_ids in existing_tool_bindings.items()},
        existing_app_ids=existing_app_ids.to_list(),
        raw_connections_to_create=raw_connections_to_create,
        raw_tools_to_create=raw_tools_to_create,
        selected_operation_app_ids=selected_operation_app_ids.to_list(),
    )


async def apply_provider_create_plan_with_rollback(
    *,
    clients: WxOClient,
    user_id: IdLike,
    db: AsyncSession,
    deployment_spec: BaseDeploymentData,
    plan: ProviderCreatePlan,
) -> WatsonxProviderCreateApplyResult:
    """Apply provider create operations with rollback protection."""
    # Rollback journals — tracked so partial failures can undo side-effects:
    # - created_tool_ids: provider tool ids created during this operation.
    # - created_app_ids: provider app ids (connections) created during this operation.
    # - original_tools: writable pre-update payloads for existing tools that
    #     were mutated (connection bindings added); captured for rollback.
    created_tool_ids: list[str] = []
    created_app_ids: list[str] = []
    original_tools: dict[str, dict[str, Any]] = {}

    # Working state:
    # - created_snapshot_bindings: source_ref ↔ tool_id bindings for newly
    #     created tools; returned in the create result for reconciliation.
    # - created_tool_app_bindings: tool_id → app_ids bindings showing which
    #     connections were wired to each tool; returned in the create result.
    # - agent_create_response: wxO agent creation response (carries agent_id).
    # - operation_to_provider_app_id: operation app_id → provider app_id
    #     (identity mapping for both existing and raw-created connections).
    # - resolved_connections: provider_app_id → connection_id map for bind calls.
    created_snapshot_bindings: list[WatsonxToolRefBinding] = []
    created_tool_app_bindings: list[WatsonxToolAppBinding] = []
    agent_create_response = None
    operation_to_provider_app_id: dict[str, str] = {}
    resolved_connections: dict[str, str] = {}

    try:
        try:
            connection_result = await resolve_connections_for_operations(
                clients=clients,
                user_id=user_id,
                db=db,
                existing_app_ids=plan.existing_app_ids,
                raw_connections_to_create=plan.raw_connections_to_create,
                error_prefix=ErrorPrefix.CREATE.value,
                validate_connection_fn=validate_connection,
                create_connection_fn=create_connection_with_conflict_mapping,
            )
            operation_to_provider_app_id = connection_result.operation_to_provider_app_id
            resolved_connections = connection_result.resolved_connections
            created_app_ids.extend(connection_result.created_app_ids)
        except ConnectionCreateBatchError as exc:
            created_app_ids.extend(exc.created_app_ids)
            log_batch_errors(error_label="Connection create batch error", errors=exc.errors)
            raise exc.errors[0] from exc

        try:
            tool_create_result = await create_raw_tools_with_bindings(
                clients=clients,
                raw_tools_to_create=plan.raw_tools_to_create,
                operation_to_provider_app_id=operation_to_provider_app_id,
                resolved_connections=resolved_connections,
                resource_prefix=plan.resource_prefix,
                create_and_upload_tools_fn=create_and_upload_wxo_flow_tools_with_bindings,
            )
            created_tool_ids.extend(tool_create_result.created_tool_ids)
            created_snapshot_bindings.extend(tool_create_result.snapshot_bindings)
            created_tool_app_bindings.extend(
                _build_created_tool_app_bindings(
                    raw_tools_to_create=plan.raw_tools_to_create,
                    created_tool_ids=tool_create_result.created_tool_ids,
                    operation_to_provider_app_id=operation_to_provider_app_id,
                )
            )
        except ToolUploadBatchError as exc:
            created_tool_ids.extend(exc.created_tool_ids)
            log_batch_errors(error_label="Tool upload batch error", errors=exc.errors)
            raise exc.errors[0] from exc

        if plan.existing_tool_bindings:
            await _bind_existing_tools_for_create(
                clients=clients,
                existing_tool_bindings=plan.existing_tool_bindings,
                operation_to_provider_app_id=operation_to_provider_app_id,
                resolved_connections=resolved_connections,
                original_tools=original_tools,
            )
            created_tool_app_bindings.extend(
                _build_existing_tool_app_bindings(
                    existing_tool_bindings=plan.existing_tool_bindings,
                    operation_to_provider_app_id=operation_to_provider_app_id,
                )
            )

        final_tool_ids = dedupe_list([*plan.existing_tool_ids, *created_tool_ids])
        agent_create_response = await retry_create(
            create_agent_deployment,
            clients=clients,
            agent_name=plan.prefixed_deployment_name,
            agent_display_name=deployment_spec.name,
            deployment_name=deployment_spec.name,
            description=deployment_spec.description,
            tool_ids=final_tool_ids,
        )
    except Exception:
        # undo tool<->connection bindings of existing tools
        await rollback_update_resources(
            clients=clients,
            created_tool_ids=[],
            created_app_id=None,
            original_tools=original_tools,
        )
        logger.warning(
            "wxO create failed; rolling back agent_id=%s, tool_ids=%s, app_ids=%s, mutated_tool_ids=%s",
            getattr(agent_create_response, "id", None),
            created_tool_ids,
            created_app_ids,
            list(original_tools.keys()),
        )
        await rollback_created_resources(
            clients=clients,
            agent_id=getattr(agent_create_response, "id", None),
            tool_ids=created_tool_ids,
            app_ids=created_app_ids,
        )
        raise

    if not agent_create_response or not getattr(agent_create_response, "id", None):
        msg = f"{ErrorPrefix.CREATE.value} Deployment response was empty."
        raise DeploymentError(message=msg, error_code="deployment_error")

    return WatsonxProviderCreateApplyResult(
        agent_id=str(agent_create_response.id),
        app_ids=created_app_ids,
        tools_with_refs=created_snapshot_bindings,
        tool_app_bindings=created_tool_app_bindings,
        prefixed_name=plan.prefixed_deployment_name,
        display_name=deployment_spec.name,
    )


def _build_created_tool_app_bindings(
    *,
    raw_tools_to_create: list[RawToolCreatePlan],
    created_tool_ids: list[str],
    operation_to_provider_app_id: dict[str, str],
) -> list[WatsonxToolAppBinding]:
    # Unmapped operation app_ids are silently skipped here rather than raising
    # because this runs *after* the tools and connections have already been
    # created successfully.  Any missing mapping would indicate an operation
    # that was intentionally excluded from the plan (e.g. existing-only app_id
    # with no raw counterpart), not a validation failure.
    return [
        WatsonxToolAppBinding(
            tool_id=tool_id,
            app_ids=[
                operation_to_provider_app_id[operation_app_id]
                for operation_app_id in raw_plan.app_ids
                if operation_app_id in operation_to_provider_app_id
            ],
        )
        for raw_plan, tool_id in zip(raw_tools_to_create, created_tool_ids, strict=True)
    ]


def _build_existing_tool_app_bindings(
    *,
    existing_tool_bindings: dict[str, list[str]],
    operation_to_provider_app_id: dict[str, str],
) -> list[WatsonxToolAppBinding]:
    # Same silent-skip rationale as _build_created_tool_app_bindings.
    return [
        WatsonxToolAppBinding(
            tool_id=tool_id,
            app_ids=[
                operation_to_provider_app_id[operation_app_id]
                for operation_app_id in operation_app_ids
                if operation_app_id in operation_to_provider_app_id
            ],
        )
        for tool_id, operation_app_ids in existing_tool_bindings.items()
    ]


async def _bind_existing_tools_for_create(
    *,
    clients: WxOClient,
    existing_tool_bindings: dict[str, list[str]],
    operation_to_provider_app_id: dict[str, str],
    resolved_connections: dict[str, str],
    original_tools: dict[str, dict[str, Any]],
) -> None:
    tool_ids = list(existing_tool_bindings.keys())
    tools = await asyncio.to_thread(clients.tool.get_drafts_by_ids, tool_ids)
    tool_by_id = {str(tool.get("id")): tool for tool in tools if isinstance(tool, dict) and tool.get("id")}
    missing_tool_ids = [tool_id for tool_id in tool_ids if tool_id not in tool_by_id]
    if missing_tool_ids:
        missing_ids = ", ".join(missing_tool_ids)
        msg = f"Snapshot tool(s) not found: {missing_ids}"
        raise InvalidContentError(message=msg)

    tool_updates: list[tuple[str, dict[str, Any]]] = []
    for tool_id in tool_ids:
        original_tool = to_writable_tool_payload(tool_by_id[tool_id])
        original_tools[tool_id] = original_tool
        writable_tool = copy.deepcopy(original_tool)
        connections = ensure_langflow_connections_binding(writable_tool)

        for operation_app_id in existing_tool_bindings[tool_id]:
            provider_app_id = operation_to_provider_app_id.get(operation_app_id)
            if not provider_app_id:
                msg = f"No provider app id available for operation app_id '{operation_app_id}'."
                raise InvalidContentError(message=msg)
            connection_id = resolved_connections.get(provider_app_id)
            if not connection_id:
                msg = f"No resolved connection id available for app_id '{operation_app_id}'."
                raise InvalidContentError(message=msg)
            connections[provider_app_id] = connection_id

        tool_updates.append((tool_id, writable_tool))

    await asyncio.gather(
        *(
            retry_update(asyncio.to_thread, clients.tool.update, tool_id, writable_tool)
            for tool_id, writable_tool in tool_updates
        )
    )


async def create_agent_deployment(
    *,
    clients: WxOClient,
    tool_ids: list[str],
    agent_name: str,
    agent_display_name: str,
    deployment_name: str,
    description: str,
):
    """Create a provider agent deployment from explicit payload fields."""
    payload = build_agent_payload_from_values(
        agent_name=agent_name,
        agent_display_name=agent_display_name,
        deployment_name=deployment_name,
        description=description,
        tool_ids=tool_ids,
    )
    return await asyncio.to_thread(clients.agent.create, payload)


def validate_create_flow_provider_data(
    *,
    payload_schemas: DeploymentPayloadSchemas,
    flow_payloads: list[BaseFlowArtifact[WatsonxFlowArtifactProviderData]],
) -> list[BaseFlowArtifact[WatsonxFlowArtifactProviderData]]:
    """Validate and normalize flow artifact provider_data via adapter payload slot."""
    slot = payload_schemas.flow_artifact
    if slot is None:
        msg = f"{ErrorPrefix.CREATE.value} Required slot 'flow_artifact' is not configured."
        raise DeploymentError(message=msg, error_code="deployment_error")

    validated_payloads: list[BaseFlowArtifact[WatsonxFlowArtifactProviderData]] = []
    for flow_payload in flow_payloads:
        provider_data_raw = flow_payload.provider_data if isinstance(flow_payload.provider_data, dict) else {}
        try:
            provider_data = slot.apply(provider_data_raw)
        except AdapterPayloadValidationError as exc:
            msg = (
                "Flow payload must include provider_data with non-empty "
                "'project_id' and 'source_ref' for Watsonx deployment."
            )
            raise InvalidContentError(message=msg) from exc
        validated_payloads.append(flow_payload.model_copy(update={"provider_data": provider_data}))
    return validated_payloads
