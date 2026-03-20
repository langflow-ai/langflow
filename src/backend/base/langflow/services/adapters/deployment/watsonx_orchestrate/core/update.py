"""Helpers used to flatten wxO deployment update control flow."""

from __future__ import annotations

import asyncio
import copy
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from lfx.services.adapters.deployment.exceptions import (
    InvalidContentError,
    InvalidDeploymentOperationError,
)

from langflow.services.adapters.deployment.watsonx_orchestrate.constants import ErrorPrefix
from langflow.services.adapters.deployment.watsonx_orchestrate.core.config import validate_connection
from langflow.services.adapters.deployment.watsonx_orchestrate.core.retry import (
    retry_create,
    retry_rollback,
    retry_update,
    rollback_update_resources,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.core.shared import (
    OrderedUniqueStrs,
    RawConnectionCreatePlan,
    RawToolCreatePlan,
    create_connection_with_conflict_mapping,
    rollback_created_app_ids,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.core.tools import (
    FlowToolBindingSpec,
    ToolUploadBatchError,
    create_and_upload_wxo_flow_tools_with_bindings,
    ensure_langflow_connections_binding,
    to_writable_tool_payload,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.payloads import (
    WatsonxBindOperation,
    WatsonxCreateSnapshotBinding,
    WatsonxDeploymentUpdatePayload,
    WatsonxProviderUpdateApplyResult,
    WatsonxRemoveToolOperation,
    WatsonxUnbindOperation,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.utils import (
    dedupe_list,
    extract_agent_tool_ids,
    validate_wxo_name,
)

if TYPE_CHECKING:
    from lfx.services.adapters.deployment.schema import (
        BaseDeploymentDataUpdate,
        DeploymentUpdate,
        IdLike,
    )
    from sqlalchemy.ext.asyncio import AsyncSession

    from langflow.services.adapters.deployment.watsonx_orchestrate.types import WxOClient

logger = logging.getLogger(__name__)


class ToolConnectionOps:
    def __init__(
        self,
        *,
        bind: OrderedUniqueStrs | None = None,
        unbind: OrderedUniqueStrs | None = None,
    ) -> None:
        self.bind = bind or OrderedUniqueStrs()
        self.unbind = unbind or OrderedUniqueStrs()


def _get_or_create_tool_connection_ops(
    deltas: dict[str, ToolConnectionOps],
    *,
    tool_id: str,
) -> ToolConnectionOps:
    return deltas.setdefault(tool_id, ToolConnectionOps())


@dataclass(slots=True)
class ProviderUpdatePlan:
    resource_prefix: str
    existing_app_ids: list[str]
    raw_connections_to_create: list[RawConnectionCreatePlan]
    existing_tool_deltas: dict[str, ToolConnectionOps]
    raw_tools_to_create: list[RawToolCreatePlan]
    final_existing_tool_ids: list[str]
    bind_existing_tool_ids: list[str]


def validate_provider_update_request_sections(payload: DeploymentUpdate) -> None:
    """Reject top-level update sections in watsonx."""
    if payload.snapshot is not None or payload.config is not None:
        msg = (
            "Top-level 'snapshot' and 'config' update sections are no longer supported for "
            "watsonx Orchestrate deployment updates. Use provider_data.operations instead."
        )
        raise InvalidDeploymentOperationError(message=msg)


def build_provider_update_plan(
    *,
    agent: dict[str, Any],
    provider_update: WatsonxDeploymentUpdatePayload,
) -> ProviderUpdatePlan:
    """Build a deterministic CPU-only plan for provider_data update operations."""
    resource_prefix = (provider_update.resource_name_prefix or "").strip()
    agent_tool_ids = extract_agent_tool_ids(agent)
    final_existing_tool_ids = OrderedUniqueStrs.from_values(agent_tool_ids)

    # Per existing tool_id, track app_ids to bind/unbind during this update.
    existing_tool_deltas: dict[str, ToolConnectionOps] = {}
    # Existing tool_ids explicitly referenced by bind operations (for added snapshot reporting).
    bind_existing_tool_ids = OrderedUniqueStrs()
    # Per raw tool name, collect app_ids that should be bound when the raw tool is created.
    raw_tool_app_ids: dict[str, OrderedUniqueStrs] = {}

    for operation in provider_update.operations:
        if isinstance(operation, WatsonxBindOperation):
            if operation.tool.reference_id is not None:
                tool_id = operation.tool.reference_id
                bind_existing_tool_ids.add(tool_id)
                final_existing_tool_ids.add(tool_id)
                delta = _get_or_create_tool_connection_ops(existing_tool_deltas, tool_id=tool_id)
                delta.bind.extend(operation.app_ids)
                continue

            raw_name = str(operation.tool.name_of_raw)
            raw_apps = raw_tool_app_ids.setdefault(raw_name, OrderedUniqueStrs())
            raw_apps.extend(operation.app_ids)
            continue

        if isinstance(operation, WatsonxUnbindOperation):
            tool_id = operation.tool_id
            delta = _get_or_create_tool_connection_ops(existing_tool_deltas, tool_id=tool_id)
            delta.unbind.extend(operation.app_ids)
            continue

        if isinstance(operation, WatsonxRemoveToolOperation):
            final_existing_tool_ids.discard(operation.tool_id)
            continue

    raw_connections_to_create = [
        RawConnectionCreatePlan(
            operation_app_id=raw_payload.app_id,
            provider_app_id=f"{resource_prefix}{raw_payload.app_id}",
            payload=raw_payload,
        )
        for raw_payload in (provider_update.connections.raw_payloads or [])
    ]

    raw_tool_pool = {raw_payload.name: raw_payload for raw_payload in (provider_update.tools.raw_payloads or [])}
    raw_tools_to_create = [
        RawToolCreatePlan(raw_name=raw_name, payload=raw_tool_pool[raw_name], app_ids=app_ids.to_list())
        for raw_name, app_ids in raw_tool_app_ids.items()
    ]

    return ProviderUpdatePlan(
        resource_prefix=resource_prefix,
        existing_app_ids=list(provider_update.connections.existing_app_ids or []),
        raw_connections_to_create=raw_connections_to_create,
        existing_tool_deltas=existing_tool_deltas,
        raw_tools_to_create=raw_tools_to_create,
        final_existing_tool_ids=final_existing_tool_ids.to_list(),
        bind_existing_tool_ids=bind_existing_tool_ids.to_list(),
    )


async def _update_existing_tool_connection_deltas(
    *,
    clients: WxOClient,
    existing_tool_deltas: dict[str, ToolConnectionOps],
    resolved_connections: dict[str, str],
    operation_to_provider_app_id: dict[str, str],
    original_tools: dict[str, dict[str, Any]],
) -> None:
    if not existing_tool_deltas:
        return

    tool_ids = list(existing_tool_deltas.keys())
    tools = await asyncio.to_thread(clients.tool.get_drafts_by_ids, tool_ids)
    tool_by_id = {str(tool.get("id")): tool for tool in tools if isinstance(tool, dict) and tool.get("id")}
    missing_tool_ids = [tool_id for tool_id in tool_ids if tool_id not in tool_by_id]
    if missing_tool_ids:
        missing_ids = ", ".join(missing_tool_ids)
        msg = f"Snapshot tool(s) not found: {missing_ids}"
        raise InvalidContentError(message=msg)

    tool_updates: list[tuple[str, dict[str, Any]]] = []
    for tool_id in tool_ids:
        delta = existing_tool_deltas[tool_id]
        original_tool = to_writable_tool_payload(tool_by_id[tool_id])
        original_tools[tool_id] = original_tool
        writable_tool = copy.deepcopy(original_tool)
        connections = ensure_langflow_connections_binding(writable_tool)

        for app_id in delta.unbind:
            provider_app_id = operation_to_provider_app_id.get(app_id, app_id)
            connections.pop(provider_app_id, None)
        for app_id in delta.bind:
            provider_app_id = operation_to_provider_app_id.get(app_id)
            if not provider_app_id:
                msg = f"No provider app id available for operation app_id '{app_id}'."
                raise InvalidContentError(message=msg)
            connection_id = resolved_connections.get(provider_app_id)
            if not connection_id:
                msg = f"No resolved connection id available for app_id '{app_id}'."
                raise InvalidContentError(message=msg)
            connections[provider_app_id] = connection_id
        tool_updates.append((tool_id, writable_tool))

    await asyncio.gather(
        *(
            retry_update(asyncio.to_thread, clients.tool.update, tool_id, writable_tool)
            for tool_id, writable_tool in tool_updates
        )
    )


def _build_agent_rollback_payload(*, agent: dict[str, Any], final_update_payload: dict[str, Any]) -> dict[str, Any]:
    rollback_payload: dict[str, Any] = {}
    if "tools" in final_update_payload:
        rollback_payload["tools"] = extract_agent_tool_ids(agent)
    for update_field in ("name", "display_name", "description"):
        if update_field in final_update_payload and update_field in agent:
            rollback_payload[update_field] = agent[update_field]
    return rollback_payload


async def _rollback_agent_update(
    *,
    clients: WxOClient,
    agent_id: str,
    rollback_agent_payload: dict[str, Any],
) -> None:
    if not rollback_agent_payload:
        return
    try:
        await retry_rollback(asyncio.to_thread, clients.agent.update, agent_id, rollback_agent_payload)
    except Exception:
        logger.exception("Rollback failed for agent_id=%s — resource may be orphaned", agent_id)


async def apply_provider_update_plan_with_rollback(
    *,
    clients: WxOClient,
    user_id: IdLike,
    db: AsyncSession,
    agent_id: str,
    agent: dict[str, Any],
    update_payload: dict[str, Any],
    plan: ProviderUpdatePlan,
) -> WatsonxProviderUpdateApplyResult:
    """Apply provider_data update operations with rollback protection."""
    # Rollback journals:
    # - created_tool_ids: provider tool ids created during this update.
    # - created_app_ids: provider app ids created during this update.
    # - original_tools: writable pre-update payloads for mutated existing tools.
    created_tool_ids: list[str] = []
    created_app_ids: list[str] = []
    original_tools: dict[str, dict[str, Any]] = {}

    # Working state:
    # - resolved_connections: app_id -> connection_id map used for bind/update calls.
    # - added_snapshot_ids: snapshot/tool ids to return in update result.
    # - final_update_payload: outbound agent patch payload (spec + tools).
    # - rollback_agent_payload: best-effort restore payload for agent update rollback.
    resolved_connections: dict[str, str] = {}
    operation_to_provider_app_id: dict[str, str] = {app_id: app_id for app_id in plan.existing_app_ids}
    added_snapshot_ids: list[str] = []
    added_snapshot_bindings: list[WatsonxCreateSnapshotBinding] = []
    final_update_payload = dict(update_payload)
    rollback_agent_payload: dict[str, Any] = {}

    try:
        if plan.existing_app_ids:
            existing_connections = await asyncio.gather(
                *(
                    retry_create(validate_connection, clients.connections, app_id=app_id)
                    for app_id in plan.existing_app_ids
                )
            )
            for app_id, connection in zip(plan.existing_app_ids, existing_connections, strict=True):
                resolved_connections[app_id] = connection.connection_id

        if plan.raw_connections_to_create:
            created_connections_results = await asyncio.gather(
                *(
                    create_connection_with_conflict_mapping(
                        clients=clients,
                        app_id=create_plan.provider_app_id,
                        payload=create_plan.payload,
                        user_id=user_id,
                        db=db,
                        error_prefix=ErrorPrefix.UPDATE.value,
                    )
                    for create_plan in plan.raw_connections_to_create
                ),
                return_exceptions=True,
            )
            create_connection_errors: list[Exception] = []
            created_app_ids_journal: list[str] = []
            for result in created_connections_results:
                if isinstance(result, BaseException):
                    if isinstance(result, Exception):
                        create_connection_errors.append(result)
                    else:
                        create_connection_errors.append(
                            RuntimeError(
                                f"Connection create failed with non-standard exception: {type(result).__name__}"
                            )
                        )
                    continue
                created_app_ids_journal.append(result)
            created_app_ids.extend(dedupe_list(created_app_ids_journal))
            if create_connection_errors:
                for i, err in enumerate(create_connection_errors):
                    logger.error(
                        "Connection create batch error [%d/%d]: %s",
                        i + 1,
                        len(create_connection_errors),
                        err,
                    )
                raise create_connection_errors[0]
            validated_created_connections = await asyncio.gather(
                *(
                    retry_create(
                        validate_connection,
                        clients.connections,
                        app_id=create_plan.provider_app_id,
                    )
                    for create_plan in plan.raw_connections_to_create
                )
            )
            for create_plan, connection in zip(
                plan.raw_connections_to_create,
                validated_created_connections,
                strict=True,
            ):
                operation_to_provider_app_id[create_plan.operation_app_id] = create_plan.provider_app_id
                resolved_connections[create_plan.provider_app_id] = connection.connection_id

        if plan.raw_tools_to_create:
            tool_bindings = []
            for raw_plan in plan.raw_tools_to_create:
                binding_connections: dict[str, str] = {}
                for operation_app_id in raw_plan.app_ids:
                    provider_app_id = operation_to_provider_app_id.get(operation_app_id)
                    if not provider_app_id:
                        msg = f"No provider app id available for operation app_id '{operation_app_id}'."
                        raise InvalidContentError(message=msg)
                    connection_id = resolved_connections.get(provider_app_id)
                    if not connection_id:
                        msg = f"No resolved connection id available for app_id '{operation_app_id}'."
                        raise InvalidContentError(message=msg)
                    binding_connections[provider_app_id] = connection_id
                tool_bindings.append(
                    FlowToolBindingSpec(
                        flow_payload=raw_plan.payload,
                        connections=binding_connections,
                    )
                )
            try:
                raw_create_results = await create_and_upload_wxo_flow_tools_with_bindings(
                    clients=clients,
                    tool_bindings=tool_bindings,
                    tool_name_prefix=plan.resource_prefix,
                )
            except ToolUploadBatchError as exc:
                created_tool_ids.extend(exc.created_tool_ids)
                added_snapshot_ids.extend(exc.created_tool_ids)
                for i, err in enumerate(exc.errors):
                    logger.exception("Tool upload batch error [%d/%d]: %s", i + 1, len(exc.errors), err)
                raise exc.errors[0] from exc
            for raw_plan, created_tool_id in zip(plan.raw_tools_to_create, raw_create_results, strict=True):
                tool_id = str(created_tool_id).strip()
                if not tool_id:
                    msg = f"Failed to create tool for raw payload '{raw_plan.raw_name}'."
                    raise InvalidContentError(message=msg)
                created_tool_ids.append(tool_id)
                added_snapshot_ids.append(tool_id)
                added_snapshot_bindings.append(
                    WatsonxCreateSnapshotBinding(
                        source_ref=raw_plan.payload.provider_data.source_ref,
                        snapshot_id=tool_id,
                        source_name=str(raw_plan.payload.name).strip() or None,
                        provider_name=f"{plan.resource_prefix}{raw_plan.raw_name}",
                    )
                )

        if plan.existing_tool_deltas:
            await _update_existing_tool_connection_deltas(
                clients=clients,
                existing_tool_deltas=plan.existing_tool_deltas,
                resolved_connections=resolved_connections,
                operation_to_provider_app_id=operation_to_provider_app_id,
                original_tools=original_tools,
            )

        added_snapshot_ids.extend(plan.bind_existing_tool_ids)
        final_tools = dedupe_list([*plan.final_existing_tool_ids, *created_tool_ids])
        final_update_payload["tools"] = final_tools
        rollback_agent_payload = _build_agent_rollback_payload(
            agent=agent,
            final_update_payload=final_update_payload,
        )
        if final_update_payload:
            await retry_update(asyncio.to_thread, clients.agent.update, agent_id, final_update_payload)
    except Exception:
        await _rollback_agent_update(
            clients=clients,
            agent_id=agent_id,
            rollback_agent_payload=rollback_agent_payload,
        )
        await rollback_update_resources(
            clients=clients,
            created_tool_ids=created_tool_ids,
            created_app_id=None,
            original_tools=original_tools,
        )
        await rollback_created_app_ids(
            clients=clients,
            created_app_ids=created_app_ids,
        )
        raise

    return WatsonxProviderUpdateApplyResult(
        added_snapshot_ids=dedupe_list(added_snapshot_ids),
        added_snapshot_bindings=added_snapshot_bindings,
    )


def build_update_payload_from_spec(spec: BaseDeploymentDataUpdate | None) -> dict[str, Any]:
    """Build agent update payload from deployment spec updates."""
    update_payload: dict[str, Any] = {}
    if not spec:
        return update_payload

    spec_updates = spec.model_dump(exclude_unset=True)
    if "name" in spec_updates:
        update_payload.update(
            {
                "name": validate_wxo_name(spec_updates["name"]),
                "display_name": spec_updates["name"],
            }
        )
    if "description" in spec_updates:
        update_payload["description"] = spec_updates["description"]
    return update_payload
