"""Helpers used to flatten wxO deployment update control flow."""

from __future__ import annotations

import asyncio
import copy
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException, status
from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException
from lfx.services.adapters.deployment.exceptions import (
    DeploymentConflictError,
    InvalidContentError,
    InvalidDeploymentOperationError,
)

from langflow.services.adapters.deployment.watsonx_orchestrate.constants import ErrorPrefix
from langflow.services.adapters.deployment.watsonx_orchestrate.core.config import create_config, validate_connection
from langflow.services.adapters.deployment.watsonx_orchestrate.core.retry import (
    delete_config_if_exists,
    retry_create,
    retry_rollback,
    retry_update,
    rollback_update_resources,
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
    WatsonxConnectionRawPayload,
    WatsonxDeploymentUpdatePayload,
    WatsonxRemoveToolOperation,
    WatsonxUnbindOperation,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.utils import (
    dedupe_list,
    extract_agent_tool_ids,
    extract_error_detail,
    validate_wxo_name,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from lfx.services.adapters.deployment.schema import (
        BaseDeploymentDataUpdate,
        BaseFlowArtifact,
        DeploymentUpdate,
        IdLike,
    )
    from sqlalchemy.ext.asyncio import AsyncSession

    from langflow.services.adapters.deployment.watsonx_orchestrate.types import WxOClient

logger = logging.getLogger(__name__)


class OrderedUniqueStrs:
    """Ordered, de-duplicating string collection used for deterministic update plans.

    We intentionally avoid a plain list to avoid repeated O(n) membership checks.
    Using a dictionary keeps membership/update checks O(1) while preserving insertion order.

    Deterministic order is primarily for rollback correctness
    Stable ordering ensures we undo the exact resources we created
    in the correct (reverse) sequence.
    """

    def __init__(self, items: dict[str, None] | None = None) -> None:
        self._items: dict[str, None] = items or {}

    @classmethod
    def from_values(cls, values: list[str]) -> OrderedUniqueStrs:
        ordered = cls()
        ordered.extend(values)
        return ordered

    def __iter__(self) -> Iterator[str]:
        return iter(self._items)

    def to_list(self) -> list[str]:
        # Snapshot keys only at list-boundary call sites.
        return list(self._items)

    def add(self, value: str) -> None:
        self._items.setdefault(value, None)

    def extend(self, values: list[str]) -> None:
        for value in values:
            self.add(value)

    def discard(self, value: str) -> None:
        self._items.pop(value, None)


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
class RawConnectionCreatePlan:
    operation_app_id: str
    provider_app_id: str
    payload: WatsonxConnectionRawPayload


@dataclass(slots=True)
class RawToolCreatePlan:
    raw_name: str
    payload: BaseFlowArtifact
    app_ids: list[str]


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
    """Reject legacy top-level update sections in watsonx clean-break mode."""
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


async def _create_update_connection_with_conflict_mapping(
    *,
    clients: WxOClient,
    app_id: str,
    payload: WatsonxConnectionRawPayload,
    user_id: IdLike,
    db: AsyncSession,
) -> str:
    from lfx.services.adapters.deployment.schema import DeploymentConfig

    config_payload = DeploymentConfig(
        name=app_id,
        description=None,
        environment_variables=payload.environment_variables,
        provider_config=payload.provider_config,
    )
    try:
        return await retry_create(
            create_config,
            clients=clients,
            config=config_payload,
            user_id=user_id,
            db=db,
        )
    except (ClientAPIException, HTTPException) as exc:
        if isinstance(exc, ClientAPIException):
            status_code = exc.response.status_code
            error_detail = str(extract_error_detail(exc.response.text))
        else:
            status_code = exc.status_code
            error_detail = str(extract_error_detail(str(exc.detail)))
        is_conflict = status_code == status.HTTP_409_CONFLICT or "already exists" in error_detail.lower()
        if is_conflict:
            msg = f"{ErrorPrefix.UPDATE.value} error details: {error_detail}"
            raise DeploymentConflictError(message=msg) from exc
        raise


async def _update_existing_tool_connection_deltas(
    *,
    clients: WxOClient,
    existing_tool_deltas: dict[str, ToolConnectionOps],
    resolved_connections: dict[str, str],
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
            connections.pop(app_id, None)
        for app_id in delta.bind:
            connection_id = resolved_connections.get(app_id)
            if not connection_id:
                msg = f"No resolved connection id available for app_id '{app_id}'."
                raise InvalidContentError(message=msg)
            connections[app_id] = connection_id
        tool_updates.append((tool_id, writable_tool))

    await asyncio.gather(
        *(
            retry_update(asyncio.to_thread, clients.tool.update, tool_id, writable_tool)
            for tool_id, writable_tool in tool_updates
        )
    )


async def _rollback_created_app_ids(
    *,
    clients: WxOClient,
    created_app_ids: list[str],
) -> None:
    for app_id in reversed(created_app_ids):
        try:
            await retry_rollback(delete_config_if_exists, clients, app_id=app_id)
        except Exception:
            logger.exception("Rollback failed for created app_id=%s — resource may be orphaned", app_id)


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
) -> list[str]:
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
    added_snapshot_ids: list[str] = []
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
            created_connections = await asyncio.gather(
                *(
                    _create_update_connection_with_conflict_mapping(
                        clients=clients,
                        app_id=create_plan.provider_app_id,
                        payload=create_plan.payload,
                        user_id=user_id,
                        db=db,
                    )
                    for create_plan in plan.raw_connections_to_create
                )
            )
            created_app_ids.extend(created_connections)
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
                plan.raw_connections_to_create, validated_created_connections, strict=True
            ):
                resolved_connections[create_plan.operation_app_id] = connection.connection_id

        if plan.raw_tools_to_create:
            tool_bindings = [
                FlowToolBindingSpec(
                    flow_payload=raw_plan.payload,
                    connections={app_id: resolved_connections[app_id] for app_id in raw_plan.app_ids},
                )
                for raw_plan in plan.raw_tools_to_create
            ]
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

        if plan.existing_tool_deltas:
            await _update_existing_tool_connection_deltas(
                clients=clients,
                existing_tool_deltas=plan.existing_tool_deltas,
                resolved_connections=resolved_connections,
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
        await _rollback_created_app_ids(
            clients=clients,
            created_app_ids=created_app_ids,
        )
        raise

    return dedupe_list(added_snapshot_ids)


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
