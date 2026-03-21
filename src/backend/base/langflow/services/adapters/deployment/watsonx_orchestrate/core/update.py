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
    retry_rollback,
    retry_update,
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
    rollback_created_app_ids,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.core.tools import (
    ToolUploadBatchError,
    create_and_upload_wxo_flow_tools_with_bindings,
    ensure_langflow_connections_binding,
    to_writable_tool_payload,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.payloads import (
    WatsonxBindOperation,
    WatsonxDeploymentUpdatePayload,
    WatsonxProviderUpdateApplyResult,
    WatsonxRemoveToolOperation,
    WatsonxResultToolRefBinding,
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
    existing_tool_refs: list[WatsonxResultToolRefBinding]


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
    # final_existing_tool_ids: tool ids the agent should have after the update
    #   (seeded from current agent, then mutated by bind/remove operations).
    final_existing_tool_ids = OrderedUniqueStrs.from_values(agent_tool_ids)

    # existing_tool_deltas: per existing tool_id, tracks app_ids to bind/unbind.
    existing_tool_deltas: dict[str, ToolConnectionOps] = {}
    # bind_existing_tool_ids: existing tool_ids explicitly referenced by bind
    #   operations (used for added-snapshot reporting in the result).
    bind_existing_tool_ids = OrderedUniqueStrs()
    # raw_tool_app_ids: per raw tool name, collects operation app_ids to bind
    #   when the raw tool is created.
    raw_tool_app_ids: dict[str, OrderedUniqueStrs] = {}
    # existing_tool_refs: source_ref ↔ tool_id correlations (created=False)
    #   collected from all operations that reference existing tools (bind,
    #   unbind, remove_tool). Deduped by tool_id before storing in the plan,
    #   then merged directly into the update result alongside newly-created
    #   snapshot bindings.
    existing_tool_refs: list[WatsonxResultToolRefBinding] = []

    for operation in provider_update.operations:
        if isinstance(operation, WatsonxBindOperation):
            if operation.tool.tool_id_with_ref is not None:
                ref = operation.tool.tool_id_with_ref
                tool_id = ref.tool_id
                bind_existing_tool_ids.add(tool_id)
                final_existing_tool_ids.add(tool_id)
                existing_tool_refs.append(
                    WatsonxResultToolRefBinding(source_ref=ref.source_ref, tool_id=tool_id, created=False)
                )
                delta = _get_or_create_tool_connection_ops(existing_tool_deltas, tool_id=tool_id)
                delta.bind.extend(operation.app_ids)
                continue

            raw_name = str(operation.tool.name_of_raw)
            raw_apps = raw_tool_app_ids.setdefault(raw_name, OrderedUniqueStrs())
            raw_apps.extend(operation.app_ids)
            continue

        if isinstance(operation, WatsonxUnbindOperation):
            tool_id = operation.tool.tool_id
            existing_tool_refs.append(
                WatsonxResultToolRefBinding(source_ref=operation.tool.source_ref, tool_id=tool_id, created=False)
            )
            delta = _get_or_create_tool_connection_ops(existing_tool_deltas, tool_id=tool_id)
            delta.unbind.extend(operation.app_ids)
            continue

        if isinstance(operation, WatsonxRemoveToolOperation):
            existing_tool_refs.append(
                WatsonxResultToolRefBinding(
                    source_ref=operation.tool.source_ref,
                    tool_id=operation.tool.tool_id,
                    created=False,
                )
            )
            final_existing_tool_ids.discard(operation.tool.tool_id)
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

    seen_ref_ids: dict[str, WatsonxResultToolRefBinding] = {}
    for ref in existing_tool_refs:
        seen_ref_ids.setdefault(ref.tool_id, ref)
    deduped_existing_tool_refs = list(seen_ref_ids.values())

    return ProviderUpdatePlan(
        resource_prefix=resource_prefix,
        existing_app_ids=list(provider_update.connections.existing_app_ids or []),
        raw_connections_to_create=raw_connections_to_create,
        existing_tool_deltas=existing_tool_deltas,
        raw_tools_to_create=raw_tools_to_create,
        final_existing_tool_ids=final_existing_tool_ids.to_list(),
        bind_existing_tool_ids=bind_existing_tool_ids.to_list(),
        existing_tool_refs=deduped_existing_tool_refs,
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
    # Rollback journals — tracked so partial failures can undo side-effects:
    # - created_tool_ids: provider tool ids created during this update.
    # - created_app_ids: provider app ids created during this update.
    # - original_tools: writable pre-update payloads for mutated existing tools.
    created_tool_ids: list[str] = []
    created_app_ids: list[str] = []
    original_tools: dict[str, dict[str, Any]] = {}

    # Working state:
    # - resolved_connections: provider_app_id → connection_id map for bind/update calls.
    # - operation_to_provider_app_id: operation app_id → provider app_id
    #     (identity for existing, prefixed for raw-created connections).
    # - added_snapshot_ids: snapshot/tool ids to return in the update result.
    # - created_snapshot_bindings: source_ref ↔ tool_id bindings for newly
    #     created tools (created=True); combined with existing refs in the result.
    # - final_update_payload: outbound agent patch payload (spec + tools).
    # - rollback_agent_payload: best-effort restore payload for agent rollback.
    resolved_connections: dict[str, str] = {}
    operation_to_provider_app_id: dict[str, str] = {app_id: app_id for app_id in plan.existing_app_ids}
    added_snapshot_ids: list[str] = []
    created_snapshot_bindings: list[WatsonxResultToolRefBinding] = []
    final_update_payload = dict(update_payload)
    rollback_agent_payload: dict[str, Any] = {}

    try:
        try:
            connection_result = await resolve_connections_for_operations(
                clients=clients,
                user_id=user_id,
                db=db,
                existing_app_ids=plan.existing_app_ids,
                raw_connections_to_create=plan.raw_connections_to_create,
                error_prefix=ErrorPrefix.UPDATE.value,
                validate_connection_fn=validate_connection,
                create_connection_fn=create_connection_with_conflict_mapping,
            )
            operation_to_provider_app_id = connection_result.operation_to_provider_app_id
            resolved_connections.update(connection_result.resolved_connections)
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
            added_snapshot_ids.extend(tool_create_result.created_tool_ids)
            created_snapshot_bindings.extend(tool_create_result.snapshot_bindings)
        except ToolUploadBatchError as exc:
            created_tool_ids.extend(exc.created_tool_ids)
            added_snapshot_ids.extend(exc.created_tool_ids)
            log_batch_errors(error_label="Tool upload batch error", errors=exc.errors)
            raise exc.errors[0] from exc

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
        created_app_ids=dedupe_list(created_app_ids),
        added_snapshot_ids=dedupe_list(added_snapshot_ids),
        added_snapshot_bindings=[*plan.existing_tool_refs, *created_snapshot_bindings],
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
