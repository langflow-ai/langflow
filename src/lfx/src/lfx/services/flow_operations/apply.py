"""Pure flow graph operation application for collaborative editing."""

from __future__ import annotations

import copy
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from lfx.services.flow_operations.exceptions import (
    FlowDataValidationError,
    FlowOperationError,
    FlowOperationValidationError,
)
from lfx.services.flow_operations.ops import (
    GRAPH_COLLECTION_KEYS,
    AddEdgesOp,
    AddNodesOp,
    DeleteEdgesOp,
    DeleteNodeFieldUpdate,
    DeleteNodesOp,
    FlowOperation,
    NodeFieldPath,
    NodeFieldPathSegment,
    OverwriteNodeUpdate,
    SetNodeFieldUpdate,
    UpdateMetadataOp,
    UpdateNodeEntry,
    UpdateNodesOp,
    coalesce_delete_ids,
    normalize_requested_ops,
)


@dataclass(frozen=True)
class FlowOperationsApplyResult:
    """Result of applying a batch of flow operations to flow.data."""

    flow_data: dict[str, Any]
    forward_ops: list[FlowOperation]
    deleted_edges: tuple[str, ...] = ()


@dataclass
class GraphState:
    """Indexed mutable graph state used while applying a batch."""

    flow_data: dict[str, Any]
    nodes_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    edges_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    edge_ids_by_node_id: dict[str, set[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.flow_data.get("nodes"), list):
            msg = "flow.data.nodes must be a list"
            raise FlowDataValidationError(msg)
        if not isinstance(self.flow_data.get("edges"), list):
            msg = "flow.data.edges must be a list"
            raise FlowDataValidationError(msg)

    @property
    def nodes(self) -> list[Any]:
        return self.flow_data["nodes"]

    @property
    def edges(self) -> list[Any]:
        return self.flow_data["edges"]


def build_graph_state(base_flow: dict[str, Any]) -> GraphState:
    """Deep-copy flow.data and build node/edge indexes."""
    copied = copy.deepcopy(base_flow)
    state = GraphState(flow_data=copied, edge_ids_by_node_id=defaultdict(set))
    for node in state.nodes:
        node_id = _require_node_id(node, context="flow.data.nodes", error_cls=FlowDataValidationError)
        if node_id in state.nodes_by_id:
            msg = f"flow.data.nodes: duplicate node id: {node_id!r}"
            raise FlowDataValidationError(msg)
        state.nodes_by_id[node_id] = node

    for edge in state.edges:
        edge_id, source, target = _require_edge_endpoints(
            edge,
            context="flow.data.edges",
            error_cls=FlowDataValidationError,
        )
        if edge_id in state.edges_by_id:
            msg = f"flow.data.edges: duplicate edge id: {edge_id!r}"
            raise FlowDataValidationError(msg)
        state.edges_by_id[edge_id] = edge
        state.edge_ids_by_node_id[source].add(edge_id)
        state.edge_ids_by_node_id[target].add(edge_id)

    return state


def finalize_graph(state: GraphState) -> dict[str, Any]:
    """Write indexed nodes and edges back into flow.data."""
    state.flow_data["nodes"] = list(state.nodes_by_id.values())
    state.flow_data["edges"] = list(state.edges_by_id.values())
    return state.flow_data


def apply_flow_operations(
    base_flow: dict[str, Any],
    operations: list[FlowOperation],
) -> FlowOperationsApplyResult:
    """Apply operation batches to a copy of flow.data without mutating the input."""
    requested_ops = normalize_requested_ops(operations)
    state = build_graph_state(base_flow)
    forward_ops: list[FlowOperation] = []
    deleted_edges: list[str] = []

    for op in requested_ops:
        emitted, derived_edge_deletes = _apply_operation(state, op)
        forward_ops.extend(emitted)
        deleted_edges.extend(derived_edge_deletes)

    finalized = finalize_graph(state)
    return FlowOperationsApplyResult(
        flow_data=finalized,
        forward_ops=forward_ops,
        deleted_edges=tuple(deleted_edges),
    )


def _apply_operation(state: GraphState, op: FlowOperation) -> tuple[list[FlowOperation], list[str]]:
    if isinstance(op, AddNodesOp):
        return _apply_add_nodes(state, op.nodes), []
    if isinstance(op, UpdateNodesOp):
        return _apply_update_nodes(state, op.updates), []
    if isinstance(op, DeleteNodesOp):
        return _apply_delete_nodes(state, op.ids)
    if isinstance(op, AddEdgesOp):
        return _apply_add_edges(state, op.edges), []
    if isinstance(op, DeleteEdgesOp):
        return _apply_delete_edges(state, op.ids), []
    if isinstance(op, UpdateMetadataOp):
        return _apply_update_metadata(state, op.fields, op.delete_keys), []
    msg = f"Unsupported operation type: {type(op)!r}"
    raise FlowOperationValidationError(msg)


def _apply_add_nodes(state: GraphState, nodes: list[dict[str, Any]]) -> list[FlowOperation]:
    if not nodes:
        return []

    payloads: list[dict[str, Any]] = []
    seen_in_request: set[str] = set()

    for index, node in enumerate(nodes):
        node_id = _require_node_id(node, context=f"add_nodes[{index}]")
        if node_id in seen_in_request:
            msg = f"add_nodes: duplicate node id in request: {node_id!r}"
            raise FlowOperationValidationError(msg)
        if node_id in state.nodes_by_id:
            msg = f"add_nodes: node id already exists: {node_id!r}"
            raise FlowOperationValidationError(msg)
        seen_in_request.add(node_id)
        payload = copy.deepcopy(node)
        state.nodes_by_id[node_id] = payload
        payloads.append(payload)

    return [AddNodesOp(type="add_nodes", nodes=payloads)]


def _apply_update_nodes(state: GraphState, updates: list[UpdateNodeEntry]) -> list[FlowOperation]:
    if not updates:
        return []

    _validate_update_node_entries(updates)
    accepted_updates_by_key: dict[tuple[Any, ...], _AcceptedNodeUpdate] = {}
    for index, (update, forward_update) in enumerate(zip(updates, copy.deepcopy(updates), strict=True)):
        accepted_update = _AcceptedNodeUpdate(update=update, forward_update=forward_update, input_index=index)
        if forward_update.op == "overwrite_node":
            accepted_updates_by_key[("overwrite_node", forward_update.id)] = accepted_update
            continue

        field_key = ("field", forward_update.id, forward_update.path)
        accepted_updates_by_key[field_key] = accepted_update

    forward_updates: list[UpdateNodeEntry] = []
    for accepted_update in accepted_updates_by_key.values():
        node_id = accepted_update.update.id
        if node_id not in state.nodes_by_id:
            msg = f"update_nodes: node does not exist: {node_id!r}"
            raise FlowOperationValidationError(msg)
        NODE_UPDATE_HANDLERS[accepted_update.update.op](state, accepted_update.update, accepted_update.input_index)
        forward_updates.append(accepted_update.forward_update)
    if not forward_updates:
        return []
    return [UpdateNodesOp(type="update_nodes", updates=forward_updates)]


@dataclass(frozen=True)
class _AcceptedNodeUpdate:
    update: UpdateNodeEntry
    forward_update: UpdateNodeEntry
    input_index: int


NodeUpdateHandler = Callable[[GraphState, Any, int], None]


def _apply_overwrite_node_update(
    state: GraphState,
    update: OverwriteNodeUpdate,
    _index: int,
) -> None:
    state.nodes_by_id[update.id] = update.node


def _apply_set_node_field_update(
    state: GraphState,
    update: SetNodeFieldUpdate,
    index: int,
) -> None:
    _validate_node_field_path(update.path, context=f"update_nodes[{index}].path")
    _set_node_field(state.nodes_by_id[update.id], update.path, update.value, context=f"update_nodes[{index}]")


def _apply_delete_node_field_update(
    state: GraphState,
    update: DeleteNodeFieldUpdate,
    index: int,
) -> None:
    _validate_node_field_path(update.path, context=f"update_nodes[{index}].path")
    _delete_node_field(state.nodes_by_id[update.id], update.path, context=f"update_nodes[{index}]")


NODE_UPDATE_HANDLERS: dict[str, NodeUpdateHandler] = {
    "overwrite_node": _apply_overwrite_node_update,
    "set_field": _apply_set_node_field_update,
    "delete_field": _apply_delete_node_field_update,
}


def _validate_update_node_entries(
    updates: list[UpdateNodeEntry],
) -> None:
    """Reject update batches with ambiguous per-node overwrite behavior.

    A node can be overwritten once, or patched through one or more field updates.
    It cannot do both in the same update_nodes operation. A field path can appear
    at most once per node.
    """
    overwrite_counts: Counter[str] = Counter()
    field_update_counts: defaultdict[str, Counter[NodeFieldPath]] = defaultdict(Counter)
    for update in updates:
        if update.op == "overwrite_node":
            overwrite_counts[update.id] += 1
        if update.op in {"set_field", "delete_field"}:
            field_update_counts[update.id][update.path] += 1
            if field_update_counts[update.id][update.path] > 1:
                msg = f"update_nodes: multiple field updates for node/path: {update.id!r} {update.path!r}"
                raise FlowOperationValidationError(msg)

        if overwrite_counts[update.id] > 1:
            msg = f"update_nodes: multiple overwrite_node entries for node id: {update.id!r}"
            raise FlowOperationValidationError(msg)
        if overwrite_counts[update.id] > 0 and update.id in field_update_counts:
            msg = f"update_nodes: cannot mix overwrite_node and field updates for node id: {update.id!r}"
            raise FlowOperationValidationError(msg)


def _validate_node_field_path(path: NodeFieldPath, *, context: str) -> None:
    if path[0] == "id":
        msg = f"{context}: cannot modify node identity"
        raise FlowOperationValidationError(msg)


def _read_object_path_part(
    json_object: dict[str, Any],
    path_part: NodeFieldPathSegment,
    *,
    context: str,
) -> Any:
    if not isinstance(path_part, str) or path_part not in json_object:
        msg = f"{context}: object path part must be an existing string key: {path_part!r}"
        raise FlowOperationValidationError(msg)
    return json_object[path_part]


def _read_array_path_part(
    json_array: list[Any],
    path_part: NodeFieldPathSegment,
    *,
    context: str,
) -> Any:
    if not _is_json_array_index(path_part):
        msg = f"{context}: array path part must be an integer index"
        raise FlowOperationValidationError(msg)
    if not (0 <= path_part < len(json_array)):
        msg = f"{context}: array index is out of range"
        raise FlowOperationValidationError(msg)
    return json_array[path_part]


def _write_object_path_part(
    json_object: dict[str, Any],
    path_part: NodeFieldPathSegment,
    value: Any,
    *,
    context: str,
) -> None:
    if not isinstance(path_part, str):
        msg = f"{context}: object path part must be a string: {path_part!r}"
        raise FlowOperationValidationError(msg)
    json_object[path_part] = value


def _write_array_path_part(
    json_array: list[Any],
    path_part: NodeFieldPathSegment,
    value: Any,
    *,
    context: str,
) -> None:
    if not _is_json_array_index(path_part):
        msg = f"{context}: array path part must be an integer index"
        raise FlowOperationValidationError(msg)
    if not (0 <= path_part < len(json_array)):
        msg = f"{context}: array index is out of range"
        raise FlowOperationValidationError(msg)
    json_array[path_part] = value


def _read_json_value_before_last_path_part(
    node: dict[str, Any],
    path: NodeFieldPath,
    *,
    context: str,
) -> dict[str, Any] | list[Any]:
    json_value: Any = node
    for path_index, path_part in enumerate(path[:-1]):
        if isinstance(json_value, dict):
            json_value = _read_object_path_part(json_value, path_part, context=f"{context}.path[{path_index}]")
            continue
        if isinstance(json_value, list):
            json_value = _read_array_path_part(json_value, path_part, context=f"{context}.path[{path_index}]")
            continue
        msg = f"{context}.path[{path_index}]: path must pass through objects or arrays"
        raise FlowOperationValidationError(msg)
    if not isinstance(json_value, (dict, list)):
        msg = f"{context}: path must end at an object or array"
        raise FlowOperationValidationError(msg)
    return json_value


def _set_node_field(node: dict[str, Any], path: NodeFieldPath, value: Any, *, context: str) -> None:
    json_value = _read_json_value_before_last_path_part(node, path, context=context)
    last_path_part = path[-1]
    if isinstance(json_value, dict):
        _write_object_path_part(json_value, last_path_part, value, context=context)
        return
    if isinstance(json_value, list):
        _write_array_path_part(json_value, last_path_part, value, context=context)
        return


def _delete_node_field(node: dict[str, Any], path: NodeFieldPath, *, context: str) -> None:
    json_value = _read_json_value_before_last_path_part(node, path, context=context)
    last_path_part = path[-1]
    if not isinstance(json_value, dict) or not isinstance(last_path_part, str):
        msg = f"{context}: delete only supports object properties"
        raise FlowOperationValidationError(msg)
    json_value.pop(last_path_part, None)


def _is_json_array_index(path_part: NodeFieldPathSegment) -> bool:
    return isinstance(path_part, int) and not isinstance(path_part, bool)


def _apply_delete_nodes(state: GraphState, ids: list[str]) -> tuple[list[FlowOperation], list[str]]:
    coalesced_ids = coalesce_delete_ids(ids)
    if not coalesced_ids:
        return [], []

    removed_node_ids: list[str] = []
    incident_edge_ids: list[str] = []

    for node_id in coalesced_ids:
        if node_id not in state.nodes_by_id:
            continue
        del state.nodes_by_id[node_id]
        removed_node_ids.append(node_id)
        incident_edge_ids.extend(state.edge_ids_by_node_id.pop(node_id, set()))

    if not removed_node_ids:
        return [], []

    removed_edge_ids = _remove_edges(state, incident_edge_ids)
    forward_ops: list[FlowOperation] = [DeleteNodesOp(type="delete_nodes", ids=removed_node_ids)]
    if removed_edge_ids:
        forward_ops.append(DeleteEdgesOp(type="delete_edges", ids=removed_edge_ids))
    return forward_ops, removed_edge_ids


def _apply_add_edges(state: GraphState, edges: list[dict[str, Any]]) -> list[FlowOperation]:
    if not edges:
        return []

    payloads: list[dict[str, Any]] = []
    seen_in_request: set[str] = set()

    for index, edge in enumerate(edges):
        edge_id, source, target = _require_edge_endpoints(edge, context=f"add_edges[{index}]")
        if edge_id in seen_in_request:
            msg = f"add_edges: duplicate edge id in request: {edge_id!r}"
            raise FlowOperationValidationError(msg)
        if edge_id in state.edges_by_id:
            msg = f"add_edges: edge id already exists: {edge_id!r}"
            raise FlowOperationValidationError(msg)
        if source not in state.nodes_by_id:
            msg = f"add_edges: source node does not exist: {source!r}"
            raise FlowOperationValidationError(msg)
        if target not in state.nodes_by_id:
            msg = f"add_edges: target node does not exist: {target!r}"
            raise FlowOperationValidationError(msg)
        seen_in_request.add(edge_id)
        payload = copy.deepcopy(edge)
        _insert_edge(state, payload)
        payloads.append(payload)

    return [AddEdgesOp(type="add_edges", edges=payloads)]


def _apply_delete_edges(state: GraphState, ids: list[str]) -> list[FlowOperation]:
    removed_edge_ids = _remove_edges(state, ids)
    if not removed_edge_ids:
        return []
    return [DeleteEdgesOp(type="delete_edges", ids=removed_edge_ids)]


def _apply_update_metadata(
    state: GraphState,
    fields: dict[str, Any],
    delete_keys: list[str],
) -> list[FlowOperation]:
    for key in fields:
        if key in GRAPH_COLLECTION_KEYS:
            msg = f"update_metadata: cannot set graph collection key {key!r}"
            raise FlowOperationValidationError(msg)
    for key in delete_keys:
        if key in GRAPH_COLLECTION_KEYS:
            msg = f"update_metadata: cannot delete graph collection key {key!r}"
            raise FlowOperationValidationError(msg)

    coalesced_delete_keys = coalesce_delete_ids(delete_keys)
    if not fields and not coalesced_delete_keys:
        return []

    for key, value in fields.items():
        state.flow_data[key] = copy.deepcopy(value)
    for key in coalesced_delete_keys:
        state.flow_data.pop(key, None)

    return [
        UpdateMetadataOp(
            type="update_metadata",
            fields=copy.deepcopy(fields),
            delete_keys=coalesced_delete_keys,
        )
    ]


def _remove_edges(state: GraphState, ids: list[str]) -> list[str]:
    removed_edge_ids: list[str] = []
    for edge_id in coalesce_delete_ids(ids):
        edge = state.edges_by_id.pop(edge_id, None)
        if edge is None:
            continue
        removed_edge_ids.append(edge_id)
        source = edge["source"]
        target = edge["target"]
        state.edge_ids_by_node_id[source].discard(edge_id)
        state.edge_ids_by_node_id[target].discard(edge_id)
        if not state.edge_ids_by_node_id[source]:
            del state.edge_ids_by_node_id[source]
        if not state.edge_ids_by_node_id[target]:
            del state.edge_ids_by_node_id[target]
    return removed_edge_ids


def _insert_edge(state: GraphState, edge: dict[str, Any]) -> None:
    edge_id = edge["id"]
    source = edge["source"]
    target = edge["target"]
    state.edges_by_id[edge_id] = edge
    state.edge_ids_by_node_id[source].add(edge_id)
    state.edge_ids_by_node_id[target].add(edge_id)


def _require_node_id(
    node: Any,
    *,
    context: str,
    error_cls: type[FlowOperationError] = FlowOperationValidationError,
) -> str:
    if not isinstance(node, dict):
        msg = f"{context}: node must be a dict"
        raise error_cls(msg)
    node_id = node.get("id")
    if not isinstance(node_id, str) or not node_id:
        msg = f"{context}: node must have a non-empty string id"
        raise error_cls(msg)
    return node_id


def _require_edge_endpoints(
    edge: Any,
    *,
    context: str,
    error_cls: type[FlowOperationError] = FlowOperationValidationError,
) -> tuple[str, str, str]:
    if not isinstance(edge, dict):
        msg = f"{context}: edge must be a dict"
        raise error_cls(msg)
    edge_id = edge.get("id")
    source = edge.get("source")
    target = edge.get("target")
    if not isinstance(edge_id, str) or not edge_id:
        msg = f"{context}: edge must have a non-empty string id"
        raise error_cls(msg)
    if not isinstance(source, str) or not source:
        msg = f"{context}: edge must have a non-empty string source"
        raise error_cls(msg)
    if not isinstance(target, str) or not target:
        msg = f"{context}: edge must have a non-empty string target"
        raise error_cls(msg)
    return edge_id, source, target
