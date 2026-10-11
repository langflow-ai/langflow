"""Pure flow graph operation application."""

from __future__ import annotations

import copy
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from lfx.services.flow_operations.canonical import values_equal
from lfx.services.flow_operations.edge_rules import HANDLE_KEYS, OUTPUTS_PATH, check_edge, node_outputs
from lfx.services.flow_operations.exceptions import FlowOperationPreconditionError, FlowOperationValidationError
from lfx.services.flow_operations.keyed_lists import ListIndex, RowOrder
from lfx.services.flow_operations.ops import (
    GRAPH_COLLECTION_KEYS,
    AddEdgesOp,
    AddNodesOp,
    DeleteEdgesOp,
    DeleteNodeFieldUpdate,
    DeleteNodesOp,
    ExpectAbsent,
    FlowOperation,
    IdSelector,
    KeySelector,
    NodeFieldPath,
    UpdateEdgesOp,
    UpdateMetadataOp,
    UpdateNodeEntry,
    UpdateNodesOp,
    deduplicate_delete_ids,
    normalize_requested_ops,
)
from lfx.services.flow_operations.schema import load_node_schema
from lfx.services.flow_operations.state import (
    GraphState,
    build_graph_state,
    copy_mutable_graph_value,
    finalize_graph,
    require_edge_endpoints,
    require_node_id,
    writable_edge,
    writable_node,
)


@dataclass(frozen=True)
class FlowOperationsApplyResult:
    """Result of applying a batch of flow operations to flow.data."""

    flow_data: dict[str, Any]
    forward_ops: list[FlowOperation]
    deleted_edges: tuple[str, ...] = ()


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
        return _apply_update_nodes(state, op.updates)
    if isinstance(op, DeleteNodesOp):
        return _apply_delete_nodes(state, op.ids)
    if isinstance(op, AddEdgesOp):
        return _apply_add_edges(state, op.edges), []
    if isinstance(op, UpdateEdgesOp):
        return _apply_update_edges(state, op.updates), []
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
        node_id = require_node_id(node, context=f"add_nodes[{index}]")
        if node_id in seen_in_request:
            msg = f"add_nodes: duplicate node id in request: {node_id!r}"
            raise FlowOperationValidationError(msg)
        if node_id in state.nodes_by_id:
            msg = f"add_nodes: node id already exists: {node_id!r}"
            raise FlowOperationValidationError(msg)
        seen_in_request.add(node_id)
        payload = copy_mutable_graph_value(node)
        state.nodes_by_id[node_id] = payload
        payloads.append(payload)

    return [AddNodesOp(type="add_nodes", nodes=payloads)]


# --- Field updates on nodes and edges ------------------------------------------------

# Replacing these whole objects would record an entire node as one opaque value.
# Callers send narrower field-level updates instead.
FORBIDDEN_WHOLE_NODE_UPDATE_PATHS: frozenset[NodeFieldPath] = frozenset(
    {
        ("data",),
        ("data", "node"),
        ("data", "node", "template"),
    }
)
# Preformat the path list once so validation errors stay explicit without
# rebuilding the same string on every update.
FORBIDDEN_WHOLE_NODE_UPDATE_PATHS_ERROR_LABEL = ", ".join(
    ".".join(root_path) for root_path in sorted(FORBIDDEN_WHOLE_NODE_UPDATE_PATHS)
)
# An edge's endpoints are its identity: connecting other nodes is another edge.
FORBIDDEN_EDGE_UPDATE_ROOTS = frozenset({"id", "source", "target"})
# Writes under these edge keys can change which output or input the edge connects.
EDGE_HANDLE_ROOTS = frozenset({*HANDLE_KEYS, "data"})

_TEMPLATE_PATH = ("data", "node", "template")


def _apply_update_nodes(state: GraphState, updates: list[UpdateNodeEntry]) -> tuple[list[FlowOperation], list[str]]:
    if not updates:
        return [], []

    _validate_update_entries(updates, kind="update_nodes")
    detached_edge_ids: set[str] = set()
    for index, update in enumerate(updates):
        node_id = update.id
        context = f"update_nodes[{index}]"
        if node_id not in state.nodes_by_id:
            msg = f"update_nodes: node does not exist: {node_id!r}"
            raise FlowOperationValidationError(msg)
        if node_id not in state.base_flow_node_ids:
            msg = f"update_nodes: cannot update node that does not exist in the original flow: {node_id!r}"
            raise FlowOperationValidationError(msg)
        _validate_node_field_path(update.path, context=f"{context}.path")
        node = writable_node(state, node_id)
        before = _apply_field_update(state, node, node, update, context=context)
        detached_edge_ids |= _detached_edges(state, node_id, update, before)

    forward_ops: list[FlowOperation] = [UpdateNodesOp(type="update_nodes", updates=copy.deepcopy(updates))]
    removed_edge_ids = state.remove_edges(list(detached_edge_ids))
    if removed_edge_ids:
        forward_ops.append(DeleteEdgesOp(type="delete_edges", ids=removed_edge_ids))
    return forward_ops, removed_edge_ids


def _detached_edges(state: GraphState, node_id: str, update: UpdateNodeEntry, before: Any) -> set[str]:
    """Return the edges a write left without an end: into a removed template field, or from or into a removed output."""
    path = update.path
    if before is _ABSENT:
        return set()
    if (
        isinstance(update, DeleteNodeFieldUpdate)
        and len(path) == len(_TEMPLATE_PATH) + 1
        and path[:-1] == _TEMPLATE_PATH
    ):
        return set(state.connections(node_id).inputs.get(("field", path[-1]), ()))
    if path[: len(OUTPUTS_PATH)] != OUTPUTS_PATH:
        return set()
    if len(path) == len(OUTPUTS_PATH) + 1 and isinstance(update, DeleteNodeFieldUpdate):
        removed_outputs = {path[-1].key}
    elif len(path) == len(OUTPUTS_PATH):
        # The whole list was replaced or deleted: the outputs it no longer has are gone.
        outputs_after = node_outputs(state, node_id)
        removed_outputs = set(_outputs_by_name(before, node_id=node_id)) - set(
            outputs_after.by_key if outputs_after is not None else ()
        )
    else:
        return set()
    if not removed_outputs:
        return set()
    connections = state.connections(node_id)
    detached: set[str] = set()
    for name in removed_outputs:
        detached |= connections.outputs.get(name, set())
        detached |= connections.inputs.get(("output", name), set())
    return detached


def _outputs_by_name(outputs: Any, *, node_id: str) -> dict[str, dict[str, Any]]:
    """Index an outputs list a write replaced, which follows the same rules as the one that replaces it."""
    if not isinstance(outputs, list):
        msg = f"node {node_id!r}: data.node.outputs must be a list"
        raise FlowOperationValidationError(msg)
    keyed = load_node_schema().keyed_list_at({}, OUTPUTS_PATH)
    return ListIndex(keyed, outputs, context=f"node {node_id!r}: data.node.outputs").by_key


def _apply_update_edges(state: GraphState, updates: list[UpdateNodeEntry]) -> list[FlowOperation]:
    if not updates:
        return []

    _validate_update_entries(updates, kind="update_edges")
    # The handles of each edge the batch writes under a handle key, as they were before.
    handles_before: dict[str, dict[str, Any]] = {}
    for index, update in enumerate(updates):
        edge_id = update.id
        context = f"update_edges[{index}]"
        if edge_id not in state.edges_by_id:
            msg = f"update_edges: edge does not exist: {edge_id!r}"
            raise FlowOperationValidationError(msg)
        if edge_id not in state.base_flow_edge_ids:
            msg = f"update_edges: cannot update edge that does not exist in the original flow: {edge_id!r}"
            raise FlowOperationValidationError(msg)
        root = update.path[0]
        if root in FORBIDDEN_EDGE_UPDATE_ROOTS:
            msg = (
                f"{context}.path: cannot modify an edge's {root}; "
                "connecting different nodes is a different edge, so delete it and add another"
            )
            raise FlowOperationValidationError(msg)
        edge = writable_edge(state, edge_id)
        if root in EDGE_HANDLE_ROOTS and edge_id not in handles_before:
            handles_before[edge_id] = _raw_handles(edge)
        _apply_field_update(state, edge, None, update, context=context)

    # An edge whose handles the batch changed is rewired, so it is checked like a new one.
    for edge_id, before in handles_before.items():
        edge = state.edges_by_id[edge_id]
        if not values_equal(_raw_handles(edge), before):
            state.forget_handles(edge)
            check_edge(state, edge)
            state.reindex_handles(edge)

    return [UpdateEdgesOp(type="update_edges", updates=copy.deepcopy(updates))]


def _raw_handles(edge: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of both forms of an edge's handles, whatever their shape, to tell whether a write changed them."""
    data = edge.get("data")
    return copy.deepcopy(
        {
            "strings": {key: edge[key] for key in HANDLE_KEYS if key in edge},
            "data": {key: data[key] for key in HANDLE_KEYS if key in data} if isinstance(data, dict) else data,
        }
    )


def _validate_update_entries(updates: list[UpdateNodeEntry], *, kind: str) -> None:
    """Reject update batches with duplicate field paths for the same node or edge."""
    field_update_counts: defaultdict[str, Counter[NodeFieldPath]] = defaultdict(Counter)
    for update in updates:
        field_update_counts[update.id][update.path] += 1
        if field_update_counts[update.id][update.path] > 1:
            msg = f"{kind}: multiple field updates for one id and path: {update.id!r} {_path_label(update.path)}"
            raise FlowOperationValidationError(msg)


def _validate_node_field_path(path: NodeFieldPath, *, context: str) -> None:
    if path[0] == "id":
        msg = f"{context}: cannot modify node identity"
        raise FlowOperationValidationError(msg)
    if path in FORBIDDEN_WHOLE_NODE_UPDATE_PATHS:
        msg = (
            f"{context}: cannot update entire node data objects at path {_path_label(path)}; "
            f"forbidden paths are: {FORBIDDEN_WHOLE_NODE_UPDATE_PATHS_ERROR_LABEL}"
        )
        raise FlowOperationValidationError(msg)


def _path_label(path: NodeFieldPath) -> str:
    return json.dumps([part if isinstance(part, str) else part.model_dump() for part in path])


# --- Walking a path ----------------------------------------------------------------------

# What a write replaced or removed when there was nothing there; None is a value a field can hold.
_ABSENT = object()


@dataclass(frozen=True)
class _ItemStep:
    """A keyed list item a path passes through, as it was before the write."""

    items: ListIndex
    item: dict[str, Any]
    key: str
    # A table row's place before the write, to put it back in order if its position changes.
    order: RowOrder | None


def _apply_field_update(
    state: GraphState,
    root: dict[str, Any],
    node: dict[str, Any] | None,
    update: UpdateNodeEntry,
    *,
    context: str,
) -> Any:
    """Apply one set_field or delete_field to ``root``, a node or an edge, walking its path once.

    ``node`` is the node whose schema declares keyed lists, or None for an
    edge, which has none. Return the value the write replaced or removed, or
    ``_ABSENT`` when there was none.
    """
    path = update.path
    parent, steps, missing_at = _walk(state, root, node, path, context=context)
    exists, current = (False, None)
    if missing_at is None:
        exists, current = _read_last(state, node, parent, path, context=context)
    _check_expectation(update, exists=exists, current=current, context=context)
    if missing_at is not None:
        part = path[missing_at]
        if isinstance(part, str):
            msg = f"{context}.path[{missing_at}]: object path part must be an existing string key: {part!r}"
        else:
            msg = f"{context}.path[{missing_at}]: list item does not exist: {_selector_key(part)!r}"
        raise FlowOperationValidationError(msg)

    before = _write_last(state, node, parent, update, context=context)
    # A write inside a keyed list item must leave its key alone; a table row whose
    # position changed goes back in order.
    for step in reversed(steps):
        if step.items.keyed.key_of(step.item) != step.key:
            msg = f"{context}: cannot change a list item's {step.items.keyed.selector_name}"
            raise FlowOperationValidationError(msg)
        if step.order is not None:
            step.items.reorder(step.item, step.order, context=context)
    return before


def _walk(
    state: GraphState,
    root: dict[str, Any],
    node: dict[str, Any] | None,
    path: NodeFieldPath,
    *,
    context: str,
) -> tuple[Any, list[_ItemStep], int | None]:
    """Follow ``path[:-1]`` from ``root``.

    Return the value holding the last segment, the keyed list items passed
    through, and the index of the first segment that does not exist (None when
    every one does). A segment that does not fit the value it reads, such as a
    key of a list, is an error rather than a missing value.
    """
    value: Any = root
    steps: list[_ItemStep] = []
    for index, part in enumerate(path[:-1]):
        if isinstance(part, str):
            if not isinstance(value, dict):
                msg = f"{context}.path[{index}]: {part!r} reads a key of a value that is not an object"
                raise FlowOperationValidationError(msg)
            if part not in value:
                return None, steps, index
            value = value[part]
            continue
        items = _keyed_list(state, node, path, index, value, context=context)
        key = _selector_key(part)
        item = items.by_key.get(key)
        if item is None:
            return None, steps, index
        order = items.order(item, context=context) if items.keyed.kind == "table" else None
        steps.append(_ItemStep(items=items, item=item, key=key, order=order))
        value = item
    return value, steps, None


def _read_last(
    state: GraphState,
    node: dict[str, Any] | None,
    parent: Any,
    path: NodeFieldPath,
    *,
    context: str,
) -> tuple[bool, Any]:
    """Return whether the last segment of ``path`` exists in ``parent``, and its value."""
    last = path[-1]
    if isinstance(last, str):
        if not isinstance(parent, dict):
            msg = f"{context}.path[{len(path) - 1}]: {last!r} reads a key of a value that is not an object"
            raise FlowOperationValidationError(msg)
        return last in parent, parent.get(last)
    item = _keyed_list(state, node, path, len(path) - 1, parent, context=context).by_key.get(_selector_key(last))
    return item is not None, item


def _write_last(
    state: GraphState,
    node: dict[str, Any] | None,
    parent: Any,
    update: UpdateNodeEntry,
    *,
    context: str,
) -> Any:
    """Write or delete the last segment of the update's path. Return what it replaced or removed, or ``_ABSENT``."""
    path = update.path
    last = path[-1]
    if isinstance(last, str):
        if not isinstance(parent, dict):
            msg = f"{context}: path must end at an object property or a keyed list item"
            raise FlowOperationValidationError(msg)
        if isinstance(update, DeleteNodeFieldUpdate):
            return parent.pop(last, _ABSENT)
        before = parent.get(last, _ABSENT)
        # Prevent stored graph state from sharing mutable objects with the
        # operation payload returned in forward_ops.
        parent[last] = copy_mutable_graph_value(update.value)
        return before

    items = _keyed_list(state, node, path, len(path) - 1, parent, context=context)
    key = _selector_key(last)
    if isinstance(update, DeleteNodeFieldUpdate):
        return items.remove(key, context=context) if key in items.by_key else _ABSENT
    value = copy_mutable_graph_value(update.value)
    if items.keyed.key_of(value) != key:
        msg = f"{context}: a list item written at a selector must carry the same key: {key!r}"
        raise FlowOperationValidationError(msg)
    if key in items.by_key:
        return items.replace(key, value, context=context)
    items.add(value, context=context)
    return _ABSENT


def _keyed_list(
    state: GraphState,
    node: dict[str, Any] | None,
    path: NodeFieldPath,
    index: int,
    value: Any,
    *,
    context: str,
) -> ListIndex:
    """Return the index of the keyed list ``path[index]`` selects from, checking the selector fits it."""
    keyed = load_node_schema().keyed_list_at(node, path[:index]) if node is not None else None
    if keyed is None:
        msg = f"{context}.path[{index}]: selector on a list the node schema does not declare keyed"
        raise FlowOperationValidationError(msg)
    if not isinstance(path[index], IdSelector if keyed.kind == "table" else KeySelector):
        msg = f"{context}.path[{index}]: items of this list are selected with {{{keyed.selector_name!r}: ...}}"
        raise FlowOperationValidationError(msg)
    if not isinstance(value, list):
        msg = f"{context}.path[{index}]: selector on a value that is not a list"
        raise FlowOperationValidationError(msg)
    return state.list_index(keyed, value, context=f"{context}.path[{index}]")


def _selector_key(selector: IdSelector | KeySelector) -> str:
    return selector.id if isinstance(selector, IdSelector) else selector.key


def _check_expectation(update: UpdateNodeEntry, *, exists: bool, current: Any, context: str) -> None:
    if update.expect is None:
        return
    if isinstance(update.expect, ExpectAbsent):
        if exists:
            msg = f"{context}: expected {_path_label(update.path)} to be absent, but it exists"
            raise FlowOperationPreconditionError(msg)
        return
    if not exists or not values_equal(current, update.expect.value):
        found = "a different value" if exists else "nothing"
        msg = f"{context}: expected {_path_label(update.path)} to hold the given value, but found {found}"
        raise FlowOperationPreconditionError(msg)


# --- Nodes, edges and metadata -----------------------------------------------------------


def _apply_delete_nodes(state: GraphState, ids: list[str]) -> tuple[list[FlowOperation], list[str]]:
    delete_ids = deduplicate_delete_ids(ids)
    if not delete_ids:
        return [], []

    for node_id in delete_ids:
        if node_id not in state.base_flow_node_ids:
            msg = f"delete_nodes: cannot delete node that does not exist in the original flow: {node_id!r}"
            raise FlowOperationValidationError(msg)

    removed_node_ids: list[str] = []
    incident_edge_ids: set[str] = set()

    for node_id in delete_ids:
        if node_id not in state.nodes_by_id:
            continue
        incident_edge_ids |= state.remove_node(node_id)
        removed_node_ids.append(node_id)

    if not removed_node_ids:
        return [], []

    removed_edge_ids = state.remove_edges(list(incident_edge_ids))
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
        edge_id, source, target = require_edge_endpoints(edge, context=f"add_edges[{index}]")
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
        payload = copy_mutable_graph_value(edge)
        check_edge(state, payload)
        state.insert_edge(payload)
        payloads.append(payload)

    return [AddEdgesOp(type="add_edges", edges=payloads)]


def _apply_delete_edges(state: GraphState, ids: list[str]) -> list[FlowOperation]:
    removed_edge_ids = state.remove_edges(ids)
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

    keys_to_delete = deduplicate_delete_ids(delete_keys)
    if not fields and not keys_to_delete:
        return []

    for key, value in fields.items():
        state.flow_data[key] = copy_mutable_graph_value(value)
    for key in keys_to_delete:
        state.flow_data.pop(key, None)

    return [
        UpdateMetadataOp(
            type="update_metadata",
            fields=copy.deepcopy(fields),
            delete_keys=keys_to_delete,
        )
    ]
