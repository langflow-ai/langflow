"""Helpers used to flatten wxO deployment update control flow."""

from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger
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
    verify_langflow_owned,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.payloads import (
    WatsonxAttachToolOperation,
    WatsonxBindOperation,
    WatsonxDeploymentUpdatePayload,
    WatsonxRemoveToolOperation,
    WatsonxRenameToolOperation,
    WatsonxResultToolRefBinding,
    WatsonxUnbindOperation,
    build_langflow_wxo_resource_name,
    ensure_field_not_empty,
    validate_description,
    validate_technical_name,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.utils import dedupe_list

if TYPE_CHECKING:
    from lfx.services.adapters.deployment.schema import (
        BaseDeploymentDataUpdate,
        DeploymentUpdate,
        IdLike,
    )
    from sqlalchemy.ext.asyncio import AsyncSession

    from langflow.services.adapters.deployment.watsonx_orchestrate.types import WxOClient


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
    existing_app_ids: list[str]
    raw_connections_to_create: list[RawConnectionCreatePlan]
    existing_tool_deltas: dict[str, ToolConnectionOps]
    raw_tools_to_create: list[RawToolCreatePlan]
    tool_renames: dict[str, str]  # tool_id → tool display name
    final_existing_tool_ids: list[str]
    added_existing_tool_refs: list[WatsonxResultToolRefBinding]
    removed_existing_tool_refs: list[WatsonxResultToolRefBinding]
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
    # put_tools is a standalone full replacement of the agent's tool list
    # (no operations accompany it).
    if provider_update.put_tools is not None:
        return ProviderUpdatePlan(
            existing_app_ids=[],
            raw_connections_to_create=[],
            existing_tool_deltas={},
            raw_tools_to_create=[],
            tool_renames={},
            final_existing_tool_ids=list(dict.fromkeys(provider_update.put_tools)),
            added_existing_tool_refs=[],
            removed_existing_tool_refs=[],
            existing_tool_refs=[],
        )

    agent_tool_ids = agent["tools"]
    final_existing_tool_ids = OrderedUniqueStrs.from_values(agent_tool_ids)

    # existing_tool_deltas: per existing tool_id, tracks app_ids to bind/unbind.
    existing_tool_deltas: dict[str, ToolConnectionOps] = {}
    # added_existing_tool_refs: existing refs newly attached to this agent by
    #   bind(existing)/attach_tool operations (i.e. not in agent_tool_ids at
    #   plan start).
    added_existing_tool_refs: list[WatsonxResultToolRefBinding] = []
    # removed_existing_tool_refs: existing refs detached by remove_tool.
    removed_existing_tool_refs: list[WatsonxResultToolRefBinding] = []
    # raw_tool_app_ids: per raw tool provider_data.tool_name, collects operation app_ids to bind
    #   when the raw tool is created. Initialize with all declared raw tools so
    #   unbound tools are still created and attached with empty connections.
    raw_tool_app_ids: dict[str, OrderedUniqueStrs] = {
        raw_payload.provider_data.tool_name: OrderedUniqueStrs()
        for raw_payload in (provider_update.tools.raw_payloads or [])
    }
    # operation_app_ids: every app_id referenced by bind/unbind operations.
    #   Used later to derive existing_app_ids by subtracting raw connection
    #   app_ids declared in connections.raw_payloads.
    operation_app_ids = OrderedUniqueStrs()
    # existing_tool_refs: source_ref ↔ tool_id correlations (created=False)
    #   collected from all operations that reference existing tools (bind,
    #   unbind, remove_tool). Deduped by tool_id before storing in the plan,
    #   then merged directly into the update result alongside newly-created
    #   snapshot bindings.
    existing_tool_refs: list[WatsonxResultToolRefBinding] = []
    # tool_renames: tool_id → user-facing display label for rename_tool operations.
    tool_renames: dict[str, str] = {}

    for operation in provider_update.operations:
        if isinstance(operation, WatsonxBindOperation):
            operation_app_ids.extend(operation.app_ids)
            if operation.tool.tool_id_with_ref is not None:
                ref = operation.tool.tool_id_with_ref
                tool_id = ref.tool_id
                if tool_id not in agent_tool_ids:
                    added_existing_tool_refs.append(
                        WatsonxResultToolRefBinding(source_ref=ref.source_ref, tool_id=tool_id, created=False)
                    )
                final_existing_tool_ids.add(tool_id)
                existing_tool_refs.append(
                    WatsonxResultToolRefBinding(source_ref=ref.source_ref, tool_id=tool_id, created=False)
                )
                if operation.app_ids:
                    delta = _get_or_create_tool_connection_ops(existing_tool_deltas, tool_id=tool_id)
                    delta.bind.extend(operation.app_ids)
                continue

            raw_name = str(operation.tool.name_of_raw)
            raw_apps = raw_tool_app_ids.setdefault(raw_name, OrderedUniqueStrs())
            raw_apps.extend(operation.app_ids)
            continue

        if isinstance(operation, WatsonxAttachToolOperation):
            tool_id = operation.tool.tool_id
            if tool_id not in agent_tool_ids:
                added_existing_tool_refs.append(
                    WatsonxResultToolRefBinding(source_ref=operation.tool.source_ref, tool_id=tool_id, created=False)
                )
            final_existing_tool_ids.add(tool_id)
            existing_tool_refs.append(
                WatsonxResultToolRefBinding(source_ref=operation.tool.source_ref, tool_id=tool_id, created=False)
            )
            continue

        if isinstance(operation, WatsonxUnbindOperation):
            operation_app_ids.extend(operation.app_ids)
            tool_id = operation.tool.tool_id
            existing_tool_refs.append(
                WatsonxResultToolRefBinding(source_ref=operation.tool.source_ref, tool_id=tool_id, created=False)
            )
            delta = _get_or_create_tool_connection_ops(existing_tool_deltas, tool_id=tool_id)
            delta.unbind.extend(operation.app_ids)
            continue

        if isinstance(operation, WatsonxRenameToolOperation):
            tool_renames[operation.tool.tool_id] = operation.tool_display_name
            existing_tool_refs.append(
                WatsonxResultToolRefBinding(
                    source_ref=operation.tool.source_ref, tool_id=operation.tool.tool_id, created=False
                )
            )
            continue

        if isinstance(operation, WatsonxRemoveToolOperation):
            removed_ref = WatsonxResultToolRefBinding(
                source_ref=operation.tool.source_ref,
                tool_id=operation.tool.tool_id,
                created=False,
            )
            removed_existing_tool_refs.append(removed_ref)
            existing_tool_refs.append(removed_ref)
            final_existing_tool_ids.discard(operation.tool.tool_id)
            continue

    raw_connections_to_create = [
        RawConnectionCreatePlan(
            operation_app_id=raw_payload.app_id,
            provider_app_id=raw_payload.app_id,
            payload=raw_payload,
        )
        for raw_payload in (provider_update.connections.raw_payloads or [])
    ]

    raw_tool_pool = {
        raw_payload.provider_data.tool_name: raw_payload for raw_payload in (provider_update.tools.raw_payloads or [])
    }
    raw_tools_to_create = [
        RawToolCreatePlan(raw_name=raw_name, payload=raw_tool_pool[raw_name], app_ids=app_ids.to_list())
        for raw_name, app_ids in raw_tool_app_ids.items()
    ]

    seen_ref_ids: dict[str, WatsonxResultToolRefBinding] = {}
    for ref in existing_tool_refs:
        seen_ref_ids.setdefault(ref.tool_id, ref)
    deduped_existing_tool_refs = list(seen_ref_ids.values())

    seen_added_ref_ids: dict[str, WatsonxResultToolRefBinding] = {}
    for ref in added_existing_tool_refs:
        seen_added_ref_ids.setdefault(ref.tool_id, ref)
    deduped_added_existing_tool_refs = list(seen_added_ref_ids.values())

    seen_removed_ref_ids: dict[str, WatsonxResultToolRefBinding] = {}
    for ref in removed_existing_tool_refs:
        seen_removed_ref_ids.setdefault(ref.tool_id, ref)
    deduped_removed_existing_tool_refs = list(seen_removed_ref_ids.values())

    raw_app_ids = {raw_payload.app_id for raw_payload in (provider_update.connections.raw_payloads or [])}
    existing_app_ids = [app_id for app_id in operation_app_ids.to_list() if app_id not in raw_app_ids]

    return ProviderUpdatePlan(
        existing_app_ids=existing_app_ids,
        raw_connections_to_create=raw_connections_to_create,
        existing_tool_deltas=existing_tool_deltas,
        raw_tools_to_create=raw_tools_to_create,
        tool_renames=tool_renames,
        final_existing_tool_ids=final_existing_tool_ids.to_list(),
        added_existing_tool_refs=deduped_added_existing_tool_refs,
        removed_existing_tool_refs=deduped_removed_existing_tool_refs,
        existing_tool_refs=deduped_existing_tool_refs,
    )


async def _update_existing_tools(
    *,
    clients: WxOClient,
    existing_tool_deltas: dict[str, ToolConnectionOps],
    tool_renames: dict[str, str],
    resolved_connections: dict[str, str],
    operation_to_provider_app_id: dict[str, str],
    original_tools: dict[str, dict[str, Any]],
    tool_by_id: dict[str, dict[str, Any]],
) -> None:
    if not existing_tool_deltas and not tool_renames:
        return

    rename_tool_ids = list(tool_renames.keys())
    missing_rename_tool_ids = [tool_id for tool_id in rename_tool_ids if tool_id not in tool_by_id]
    if missing_rename_tool_ids:
        missing_ids = ", ".join(missing_rename_tool_ids)
        msg = f"Cannot rename tool(s) not found in provider: {missing_ids}"
        raise InvalidContentError(message=msg)

    updated_tool_by_id: dict[str, dict[str, Any]] = {}
    connection_delta_tool_ids = list(existing_tool_deltas.keys())
    missing_tool_ids = [tool_id for tool_id in connection_delta_tool_ids if tool_id not in tool_by_id]
    if missing_tool_ids:
        missing_ids = ", ".join(missing_tool_ids)
        msg = f"Snapshot tool(s) not found: {missing_ids}"
        raise InvalidContentError(message=msg)

    for tool_id in connection_delta_tool_ids:
        tool = tool_by_id[tool_id]
        verify_langflow_owned(tool, tool_id=tool_id)

        delta = existing_tool_deltas[tool_id]
        original_tool = to_writable_tool_payload(tool)
        original_tools[tool_id] = original_tool
        writable_tool = copy.deepcopy(original_tool)
        connections = ensure_langflow_connections_binding(writable_tool)
        for app_id in delta.unbind:
            provider_app_id = operation_to_provider_app_id.get(app_id, app_id)
            connections.pop(provider_app_id, None)
        for app_id in delta.bind:
            provider_app_id_opt = operation_to_provider_app_id.get(app_id)
            if not provider_app_id_opt:
                msg = f"No provider app id available for operation app_id '{app_id}'."
                raise InvalidContentError(message=msg)
            connection_id = resolved_connections.get(provider_app_id_opt)
            if not connection_id:
                msg = f"No resolved connection id available for app_id '{app_id}'."
                raise InvalidContentError(message=msg)
            connections[provider_app_id_opt] = connection_id

        updated_tool_by_id[tool_id] = writable_tool

    for tool_id in rename_tool_ids:
        tool = tool_by_id[tool_id]

        verify_langflow_owned(tool, tool_id=tool_id)

        if tool_id not in original_tools:
            original_tools[tool_id] = to_writable_tool_payload(tool)

        writable_tool = updated_tool_by_id.get(tool_id)
        if writable_tool is None:
            writable_tool = to_writable_tool_payload(tool)
        tool_display_name = tool_renames[tool_id]
        writable_tool["name"] = build_langflow_wxo_resource_name(tool_display_name, resource="Tool")
        writable_tool["display_name"] = tool_display_name
        updated_tool_by_id[tool_id] = writable_tool

    tool_updates = list(updated_tool_by_id.items())

    await asyncio.gather(
        *(
            retry_update(asyncio.to_thread, clients.tool.update, tool_id, writable_tool)
            for tool_id, writable_tool in tool_updates
        )
    )
    tool_by_id.update(updated_tool_by_id)


def _build_agent_rollback_payload(*, agent: dict[str, Any], final_update_payload: dict[str, Any]) -> dict[str, Any]:
    rollback_payload: dict[str, Any] = {}
    if "tools" in final_update_payload:
        rollback_payload["tools"] = agent["tools"]
    for update_field in ("name", "display_name", "description", "llm"):
        if update_field in final_update_payload and update_field in agent:
            rollback_payload[update_field] = agent[update_field]
    return rollback_payload


def _resolve_provider_update_result_field(
    field_name: str,
    *,
    agent: dict[str, Any],
    update_payload: dict[str, Any],
) -> Any:
    return update_payload[field_name] if field_name in update_payload else agent[field_name]


def build_provider_update_result_metadata(*, agent: dict[str, Any], update_payload: dict[str, Any]) -> dict[str, Any]:
    """Optimistically derive metadata returned by the adapter update result.

    The wxO ADK/API update call does not return a full updated agent payload
    with fields such as ``name``. Use outbound patch values when present,
    otherwise keep values from the provider resource fetched before the update.
    """
    return {
        "name": _resolve_provider_update_result_field("name", agent=agent, update_payload=update_payload),
        "display_name": _resolve_provider_update_result_field(
            "display_name", agent=agent, update_payload=update_payload
        ),
        "description": _resolve_provider_update_result_field("description", agent=agent, update_payload=update_payload),
    }


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
    except Exception:  # noqa: BLE001
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
) -> dict[str, Any]:
    """Apply provider_data update operations and return update-result kwargs."""
    logger.debug(
        "apply_provider_update_plan: agent_id='%s', %d raw tools, %d renames, %d connection deltas, %d raw connections",
        agent_id,
        len(plan.raw_tools_to_create),
        len(plan.tool_renames),
        len(plan.existing_tool_deltas),
        len(plan.raw_connections_to_create),
    )
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
    #     (identity mapping for both existing and raw-created connections).
    # - created_snapshot_ids: snapshot/tool ids created during this update.
    # - added_snapshot_ids: snapshot/tool ids newly attached to the agent by
    #     this update (created + newly attached existing).
    # - created_snapshot_bindings: source_ref ↔ tool_id bindings for newly
    #     created tools (created=True).
    # - added_snapshot_bindings: source_ref ↔ tool_id bindings for newly
    #     attached tools (created + newly attached existing).
    # - removed_snapshot_bindings: source_ref ↔ tool_id bindings detached from
    #     the agent by this update.
    # - referenced_snapshot_bindings: full operation correlation set.
    # - final_update_payload: outbound agent patch payload (spec + tools).
    # - rollback_agent_payload: best-effort restore payload for agent rollback.
    # - created_app_ids_journal: app_ids recorded immediately after successful
    #     provider connection creation; used to ensure rollback sees partial
    #     successes even if create later fails before returning.
    resolved_connections: dict[str, str] = {}
    operation_to_provider_app_id: dict[str, str] = {app_id: app_id for app_id in plan.existing_app_ids}
    tool_by_id: dict[str, dict[str, Any]] = {}
    created_snapshot_ids: list[str] = []
    added_snapshot_ids: list[str] = []
    created_snapshot_bindings: list[WatsonxResultToolRefBinding] = []
    final_update_payload = dict(update_payload)
    update_result_metadata = build_provider_update_result_metadata(
        agent=agent,
        update_payload=final_update_payload,
    )
    rollback_agent_payload: dict[str, Any] = {}
    created_app_ids_journal: list[str] = []

    # Fetch only the existing tools that update operations need to mutate
    # (connection deltas and renames). We intentionally do not fetch every
    # currently attached agent tool here: operation app_ids are resolved below
    # through resolve_connections_for_operations, so unrelated attached tools
    # should not pre-seed connection state for this update.
    #
    # Edge cases:
    # - Tool deleted in wxO but still referenced by an operation:
    #   get_drafts_by_ids silently omits missing tools. _update_existing_tools
    #   detects the missing target before any tool mutation and raises.
    # - Connection deleted in wxO but referenced by an operation:
    #   resolve_connections_for_operations validates operation app_ids before
    #   bindings are applied, so the update fails before mutating tools.
    # - Multiple tools share the same app_id: explicit operation resolution is
    #   authoritative for this update; unrelated tool bindings are not reused.
    operation_tool_ids = dedupe_list([*plan.existing_tool_deltas.keys(), *plan.tool_renames.keys()])
    if operation_tool_ids:
        existing_tools = await asyncio.to_thread(clients.tool.get_drafts_by_ids, operation_tool_ids)
        tool_by_id.update({tool["id"]: tool for tool in existing_tools})

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
                created_app_ids_journal=created_app_ids_journal,
            )
            operation_to_provider_app_id.update(connection_result.operation_to_provider_app_id)
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
                create_and_upload_tools_fn=create_and_upload_wxo_flow_tools_with_bindings,
            )
            created_tool_ids.extend(tool_create_result.created_tool_ids)
            created_snapshot_ids.extend(tool_create_result.created_tool_ids)
            added_snapshot_ids.extend(tool_create_result.created_tool_ids)
            created_snapshot_bindings.extend(tool_create_result.snapshot_bindings)
        except ToolUploadBatchError as exc:
            created_tool_ids.extend(exc.created_tool_ids)
            created_snapshot_ids.extend(exc.created_tool_ids)
            added_snapshot_ids.extend(exc.created_tool_ids)
            log_batch_errors(error_label="Tool upload batch error", errors=exc.errors)
            raise exc.errors[0] from exc

        if plan.existing_tool_deltas or plan.tool_renames:
            await _update_existing_tools(
                clients=clients,
                existing_tool_deltas=plan.existing_tool_deltas,
                tool_renames=plan.tool_renames,
                resolved_connections=resolved_connections,
                operation_to_provider_app_id=operation_to_provider_app_id,
                original_tools=original_tools,
                tool_by_id=tool_by_id,
            )

        added_snapshot_ids.extend(ref.tool_id for ref in plan.added_existing_tool_refs)
        final_tools = dedupe_list([*plan.final_existing_tool_ids, *created_tool_ids])
        final_update_payload["tools"] = final_tools
        rollback_agent_payload = _build_agent_rollback_payload(
            agent=agent,
            final_update_payload=final_update_payload,
        )
        if final_update_payload:
            await retry_update(asyncio.to_thread, clients.agent.update, agent_id, final_update_payload)
    except Exception:
        logger.warning(
            "Provider update failed for agent_id=%s — initiating rollback (tools=%s, apps=%s)",
            agent_id,
            created_tool_ids,
            created_app_ids,
        )
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

    return {
        **update_result_metadata,
        "created_app_ids": created_app_ids,
        "created_snapshot_ids": created_snapshot_ids,
        "added_snapshot_ids": added_snapshot_ids,
        "created_snapshot_bindings": created_snapshot_bindings,
        "added_snapshot_bindings": [*plan.added_existing_tool_refs, *created_snapshot_bindings],
        "removed_snapshot_bindings": plan.removed_existing_tool_refs,
        "referenced_snapshot_bindings": [*plan.existing_tool_refs, *created_snapshot_bindings],
    }


def build_update_payload_from_spec(
    spec: BaseDeploymentDataUpdate | None,
    *,
    core_update: WatsonxDeploymentUpdatePayload | None = None,
) -> dict[str, Any]:
    """Build agent update payload from deployment spec updates.

    Uses ``model_fields_set`` so fields the caller did not explicitly provide
    are left untouched on the provider side (e.g. sending ``description=None``
    clears the description, while omitting description leaves it unchanged).
    """
    update_payload: dict[str, Any] = {}

    if core_update is not None:
        if "llm" in core_update.model_fields_set:
            update_payload["llm"] = ensure_field_not_empty(core_update.llm, field_label="Agent llm")

        if "display_name" in core_update.model_fields_set:
            update_payload["display_name"] = ensure_field_not_empty(
                core_update.display_name,
                field_label="Agent display name",
            )

    if spec is not None:
        if "name" in spec.model_fields_set:
            update_payload["name"] = validate_technical_name(spec.name, field_label="Agent name")
        if "description" in spec.model_fields_set:
            update_payload["description"] = validate_description(spec.description, field_label="Agent description")

    if "display_name" in update_payload and "name" not in update_payload:
        update_payload["name"] = build_langflow_wxo_resource_name(update_payload["display_name"], resource="Agent")

    return update_payload
