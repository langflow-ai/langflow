"""Operation application helpers for collaborative flow editing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException
from lfx.services.flow_operations import FlowDataValidationError, FlowOperationValidationError, parse_flow_operations
from lfx.services.flow_operations.ops import FlowOperation
from sqlmodel import select

from langflow.api.utils.collab.helpers import rollback_and_restore_flow_filesystem, snapshot_flow_filesystem
from langflow.api.utils.core import is_api_key_template_field, remove_api_keys, remove_api_keys_from_template
from langflow.api.v1.flows_helpers import _save_flow_to_fs
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow.utils import get_webhook_component_in_flow
from langflow.services.deps import get_flow_operation_service, get_settings_service

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.storage.service import StorageService


TEMPLATE_FIELD_PATH_LENGTH = 4
TEMPLATE_FIELD_VALUE_PATH_LENGTH = 5


@dataclass(frozen=True)
class AcceptedFlowOperation:
    flow_id: UUID
    revision: int
    forward_ops: list[dict[str, Any]]
    actor_user_id: UUID
    created_at: datetime


class FlowOperationApplyError(Exception):
    """Structured failure from applying an operation batch."""

    def __init__(
        self,
        *,
        status_code: int,
        detail: str,
        current_revision: int | None = None,
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        self.current_revision = current_revision
        super().__init__(detail)


def _serialize_forward_ops(forward_ops: list[FlowOperation]) -> list[dict[str, Any]]:
    return [op.model_dump(mode="json") for op in forward_ops]


def _serialize_and_sanitize_forward_ops(
    forward_ops: list[FlowOperation],
    flow_data: dict[str, Any],
) -> list[dict[str, Any]]:
    serialized_ops: list[dict[str, Any]] = []
    for op in forward_ops:
        serialized_op = op.model_dump(mode="json")
        _sanitize_forward_op_api_keys(serialized_op, flow_data)
        serialized_ops.append(serialized_op)
    return serialized_ops


def _sanitize_forward_op_api_keys(serialized_op: dict[str, Any], flow_data: dict[str, Any]) -> None:
    if serialized_op["type"] == "add_nodes":
        _sanitize_add_nodes_forward_op(serialized_op)
        return
    if serialized_op["type"] == "update_nodes":
        _sanitize_update_nodes_forward_op(serialized_op, flow_data)


def _sanitize_add_nodes_forward_op(serialized_op: dict[str, Any]) -> None:
    for node in serialized_op["nodes"]:
        _remove_api_keys_from_node_payload(node)


def _sanitize_update_nodes_forward_op(serialized_op: dict[str, Any], flow_data: dict[str, Any]) -> None:
    for update in serialized_op["updates"]:
        if update["op"] == "set_field":
            _sanitize_update_node_value(update, flow_data)


def _remove_api_keys_from_node_payload(node: Any) -> None:
    if not isinstance(node, dict):
        return
    node_data = node.get("data")
    if isinstance(node_data, dict):
        _remove_api_keys_from_node_data(node_data)


def _remove_api_keys_from_node_data(node_data: dict[str, Any]) -> None:
    inner_node = node_data.get("node")
    if isinstance(inner_node, dict):
        _remove_api_keys_from_inner_node(inner_node)


def _remove_api_keys_from_inner_node(inner_node: dict[str, Any]) -> None:
    template = inner_node.get("template")
    if isinstance(template, dict):
        remove_api_keys_from_template(template)


def _sanitize_update_node_value(update: dict[str, Any], flow_data: dict[str, Any]) -> None:
    path = tuple(update["path"])
    value = update["value"]
    if path == ("data",):
        if isinstance(value, dict):
            _remove_api_keys_from_node_data(value)
        return
    if path == ("data", "node"):
        if isinstance(value, dict):
            _remove_api_keys_from_inner_node(value)
        return
    if path == ("data", "node", "template"):
        if isinstance(value, dict):
            remove_api_keys_from_template(value)
        return
    if (
        len(path) == TEMPLATE_FIELD_PATH_LENGTH
        and path[:3] == ("data", "node", "template")
        and isinstance(path[3], str)
    ):
        if is_api_key_template_field(value):
            value["value"] = None
        return
    if (
        len(path) == TEMPLATE_FIELD_VALUE_PATH_LENGTH
        and path[:3] == ("data", "node", "template")
        and isinstance(path[3], str)
        and path[4] == "value"
        and _is_api_key_template_value_update(flow_data, update["id"], path[3])
    ):
        update["value"] = None


def _is_api_key_template_value_update(flow_data: dict[str, Any], node_id: Any, field_name: str) -> bool:
    if not isinstance(node_id, str):
        return False
    for node in flow_data.get("nodes", []):
        if not isinstance(node, dict) or node.get("id") != node_id:
            continue
        node_data = node.get("data")
        if not isinstance(node_data, dict):
            return False
        inner_node = node_data.get("node")
        if not isinstance(inner_node, dict):
            return False
        template = inner_node.get("template")
        if not isinstance(template, dict):
            return False
        return is_api_key_template_field(template.get(field_name))
    return False


async def apply_flow_operation_batch(
    session: AsyncSession,
    *,
    flow_id: UUID,
    actor_user_id: UUID,
    base_revision: int,
    operations: list[dict[str, Any]],
    storage_service: StorageService,
) -> AcceptedFlowOperation:
    """Apply operations atomically after the API layer has authorized the actor."""
    stmt = select(Flow).where(Flow.id == flow_id).with_for_update()
    locked_flow = (await session.exec(stmt)).first()
    if locked_flow is None:
        raise FlowOperationApplyError(status_code=404, detail="Flow not found")

    current_revision = locked_flow.latest_operation_revision
    if base_revision != current_revision:
        raise FlowOperationApplyError(
            status_code=409,
            detail="Stale base revision",
            current_revision=current_revision,
        )

    if not isinstance(locked_flow.data, dict):
        raise FlowOperationApplyError(status_code=500, detail="Flow data is invalid, expected a dictionary.")
    base_data = locked_flow.data

    try:
        parsed_ops = parse_flow_operations(operations)
    except FlowOperationValidationError as exc:
        raise FlowOperationApplyError(status_code=400, detail=str(exc)) from exc

    try:
        apply_result = get_flow_operation_service().apply(base_data, parsed_ops)
    except FlowDataValidationError as exc:
        raise FlowOperationApplyError(status_code=500, detail="Flow data is invalid") from exc
    except FlowOperationValidationError as exc:
        raise FlowOperationApplyError(status_code=400, detail=str(exc)) from exc

    flow_data = apply_result.flow_data
    settings = get_settings_service().settings
    if settings.remove_api_keys:
        remove_api_keys({"data": flow_data})
        serialized_forward_ops = _serialize_and_sanitize_forward_ops(apply_result.forward_ops, flow_data)
    else:
        serialized_forward_ops = _serialize_forward_ops(apply_result.forward_ops)

    locked_flow.data = flow_data
    new_revision = current_revision + 1
    locked_flow.latest_operation_revision = new_revision
    locked_flow.updated_at = datetime.now(timezone.utc)
    locked_flow.webhook = get_webhook_component_in_flow(flow_data) is not None

    owner_user_id = locked_flow.user_id
    if owner_user_id is None:
        raise FlowOperationApplyError(status_code=500, detail="Flow has no owner")

    fs_snapshot = await snapshot_flow_filesystem(locked_flow, owner_user_id, storage_service)
    try:
        session.add(locked_flow)
        await _save_flow_to_fs(locked_flow, owner_user_id, storage_service)
        await session.commit()
    except Exception as exc:
        await rollback_and_restore_flow_filesystem(session, fs_snapshot)
        status_code = 500
        detail = "Failed to persist flow operation"
        if isinstance(exc, HTTPException):
            status_code = exc.status_code
            detail = str(exc.detail)
        raise FlowOperationApplyError(status_code=status_code, detail=detail) from exc

    return AcceptedFlowOperation(
        flow_id=flow_id,
        revision=new_revision,
        forward_ops=serialized_forward_ops,
        actor_user_id=actor_user_id,
        created_at=datetime.now(timezone.utc),
    )
