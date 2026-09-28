"""Pure flow graph operation application."""

from __future__ import annotations

import copy
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from lfx.services.flow_operations.canonical import json_type, values_equal
from lfx.services.flow_operations.exceptions import (
    FlowOperationPreconditionError,
    FlowOperationValidationError,
)
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
    SetNodeFieldUpdate,
    UpdateEdgesOp,
    UpdateMetadataOp,
    UpdateNodeEntry,
    UpdateNodesOp,
    deduplicate_delete_ids,
    normalize_requested_ops,
)
from lfx.services.flow_operations.schema import KeyedList, load_node_schema
from lfx.services.flow_operations.validation import NODE_OBJECT_PATHS, validate_flow_data


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
    # Node ids read from base_flow["nodes"] before applying operations.
    base_flow_node_ids: set[str] = field(default_factory=set)
    # Base-flow node ids whose payload has already been copied before mutation.
    copied_base_flow_node_ids: set[str] = field(default_factory=set)
    # The same two sets for edges.
    base_flow_edge_ids: set[str] = field(default_factory=set)
    copied_base_flow_edge_ids: set[str] = field(default_factory=set)

    @property
    def nodes(self) -> list[Any]:
        return self.flow_data["nodes"]

    @property
    def edges(self) -> list[Any]:
        return self.flow_data["edges"]


def build_graph_state(base_flow: dict[str, Any]) -> GraphState:
    """Validate flow.data, shallow-copy it, and index graph payloads by reference.

    Values are not walked for NaN here: that check belongs to whoever accepts
    a graph from outside, and skipping it keeps each apply proportional to the
    number of nodes and edges rather than to the size of the flow.
    """
    validate_flow_data(base_flow, check_values=False)
    state = GraphState(flow_data=dict(base_flow), edge_ids_by_node_id=defaultdict(set))
    for node in state.nodes:
        node_id = node["id"]
        state.nodes_by_id[node_id] = node
        state.base_flow_node_ids.add(node_id)

    for edge in state.edges:
        edge_id, source, target = edge["id"], edge["source"], edge["target"]
        state.edges_by_id[edge_id] = edge
        state.base_flow_edge_ids.add(edge_id)
        state.edge_ids_by_node_id[source].add(edge_id)
        state.edge_ids_by_node_id[target].add(edge_id)

    return state


def finalize_graph(state: GraphState) -> dict[str, Any]:
    """Write indexed nodes and edges back into flow.data."""
    state.flow_data["nodes"] = list(state.nodes_by_id.values())
    state.flow_data["edges"] = list(state.edges_by_id.values())
    return state.flow_data


def _copy_mutable_graph_value(value: Any) -> Any:
    """Deep-copy mutable JSON values to prevent shared state between the original and applied graph."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return copy.deepcopy(value)


def _copy_base_flow_node_before_mutation(state: GraphState, node_id: str) -> dict[str, Any]:
    """Deep-copy mutable node payloads to prevent shared state between the original and applied graph."""
    if node_id in state.base_flow_node_ids and node_id not in state.copied_base_flow_node_ids:
        state.nodes_by_id[node_id] = copy.deepcopy(state.nodes_by_id[node_id])
        state.copied_base_flow_node_ids.add(node_id)
    return state.nodes_by_id[node_id]


def _copy_base_flow_edge_before_mutation(state: GraphState, edge_id: str) -> dict[str, Any]:
    """Deep-copy an edge from the base flow before its first write."""
    if edge_id in state.base_flow_edge_ids and edge_id not in state.copied_base_flow_edge_ids:
        state.edges_by_id[edge_id] = copy.deepcopy(state.edges_by_id[edge_id])
        state.copied_base_flow_edge_ids.add(edge_id)
    return state.edges_by_id[edge_id]


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
        node_id = _require_node_id(node, context=f"add_nodes[{index}]")
        _require_node_objects(node, context=f"add_nodes[{index}]")
        if node_id in seen_in_request:
            msg = f"add_nodes: duplicate node id in request: {node_id!r}"
            raise FlowOperationValidationError(msg)
        if node_id in state.nodes_by_id:
            msg = f"add_nodes: node id already exists: {node_id!r}"
            raise FlowOperationValidationError(msg)
        seen_in_request.add(node_id)
        payload = _copy_mutable_graph_value(node)
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
# Writes under these edge keys change which output or field the edge connects.
EDGE_HANDLE_ROOTS = frozenset({"sourceHandle", "targetHandle", "data"})

_TEMPLATE_PATH = ("data", "node", "template")
_OUTPUTS_PATH = ("data", "node", "outputs")


def _apply_update_nodes(state: GraphState, updates: list[UpdateNodeEntry]) -> tuple[list[FlowOperation], list[str]]:
    if not updates:
        return [], []

    _validate_update_entries(updates, kind="update_nodes")
    cascaded_edge_ids: list[str] = []
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
        node = state.nodes_by_id[node_id]
        _check_expectation(node, update, keyed_list_at=_node_keyed_list_at(node), context=context)
        node = _copy_base_flow_node_before_mutation(state, node_id)
        removed = _apply_field_update(node, update, keyed_list_at=_node_keyed_list_at(node), context=context)
        if removed is not None:
            cascaded_edge_ids.extend(_edges_attached_to(state, node_id, update.path, removed))

    forward_ops: list[FlowOperation] = [UpdateNodesOp(type="update_nodes", updates=copy.deepcopy(updates))]
    removed_edge_ids = _remove_edges(state, cascaded_edge_ids)
    if removed_edge_ids:
        forward_ops.append(DeleteEdgesOp(type="delete_edges", ids=removed_edge_ids))
    return forward_ops, removed_edge_ids


def _apply_update_edges(state: GraphState, updates: list[UpdateNodeEntry]) -> list[FlowOperation]:
    if not updates:
        return []

    _validate_update_entries(updates, kind="update_edges")
    endpoints_before: dict[str, tuple[Any, Any]] = {}
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
        edge = state.edges_by_id[edge_id]
        if root in EDGE_HANDLE_ROOTS and edge_id not in endpoints_before:
            endpoints_before[edge_id] = _edge_endpoint_names(edge)
        _check_expectation(edge, update, keyed_list_at=_no_keyed_lists, context=context)
        edge = _copy_base_flow_edge_before_mutation(state, edge_id)
        _apply_field_update(edge, update, keyed_list_at=_no_keyed_lists, context=context)

    for edge_id, before in endpoints_before.items():
        edge = state.edges_by_id[edge_id]
        # Only an edge that now connects a different output or field makes a
        # new claim; rewriting the types or data of an edge where it stands
        # keeps legacy edges editable.
        if _edge_endpoint_names(edge) != before:
            _check_edge_rules(state, edge, context=f"update_edges: edge {edge_id!r}")

    return [UpdateEdgesOp(type="update_edges", updates=copy.deepcopy(updates))]


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


# --- Walking paths ---------------------------------------------------------------------


def _node_keyed_list_at(node: dict[str, Any]):
    schema = load_node_schema()

    def keyed_list_at(prefix: tuple[Any, ...]) -> KeyedList | None:
        return schema.keyed_list_at(node, prefix)

    return keyed_list_at


def _no_keyed_lists(_prefix: tuple[Any, ...]) -> KeyedList | None:
    return None


def _keyed_list_for(path: NodeFieldPath, index: int, keyed_list_at, *, context: str) -> KeyedList:
    """Check that ``path[index]`` is the right kind of selector on a list the schema declares keyed."""
    selector = path[index]
    keyed = keyed_list_at(path[:index])
    if keyed is None:
        msg = f"{context}.path[{index}]: selector on a list the node schema does not declare keyed"
        raise FlowOperationValidationError(msg)
    expected = IdSelector if keyed.kind == "table" else KeySelector
    if not isinstance(selector, expected):
        msg = f"{context}.path[{index}]: items of this list are selected with {{{keyed.selector_name!r}: ...}}"
        raise FlowOperationValidationError(msg)
    return keyed


def _selected_list(
    container: Any,
    path: NodeFieldPath,
    index: int,
    keyed_list_at,
    *,
    context: str,
) -> tuple[KeyedList, list[Any]]:
    keyed = _keyed_list_for(path, index, keyed_list_at, context=context)
    if not isinstance(container, list):
        msg = f"{context}.path[{index}]: selector on a value that is not a list"
        raise FlowOperationValidationError(msg)
    return keyed, container


def _selector_key(selector: IdSelector | KeySelector) -> str:
    return selector.id if isinstance(selector, IdSelector) else selector.key


def _walk_to_parent(
    root: dict[str, Any],
    path: NodeFieldPath,
    keyed_list_at,
    *,
    context: str,
) -> Any:
    """Return the container holding the last path segment; every earlier segment must exist."""
    value: Any = root
    for index, part in enumerate(path[:-1]):
        if isinstance(part, str):
            if not isinstance(value, dict) or part not in value:
                msg = f"{context}.path[{index}]: object path part must be an existing string key: {part!r}"
                raise FlowOperationValidationError(msg)
            value = value[part]
            continue
        keyed, items = _selected_list(value, path, index, keyed_list_at, context=context)
        position = keyed.find(items, _selector_key(part))
        if position is None:
            msg = f"{context}.path[{index}]: list item does not exist: {_selector_key(part)!r}"
            raise FlowOperationValidationError(msg)
        value = items[position]
    return value


def _read_path(root: dict[str, Any], path: NodeFieldPath, keyed_list_at, *, context: str) -> tuple[bool, Any]:
    """Return whether ``path`` exists and its value, without changing anything."""
    value: Any = root
    for index, part in enumerate(path):
        if isinstance(part, str):
            if not isinstance(value, dict) or part not in value:
                return False, None
            value = value[part]
            continue
        keyed = _keyed_list_for(path, index, keyed_list_at, context=context)
        if not isinstance(value, list):
            return False, None
        position = keyed.find(value, _selector_key(part))
        if position is None:
            return False, None
        value = value[position]
    return True, value


def _check_expectation(root: dict[str, Any], update: UpdateNodeEntry, *, keyed_list_at, context: str) -> None:
    if update.expect is None:
        return
    exists, current = _read_path(root, update.path, keyed_list_at, context=context)
    if isinstance(update.expect, ExpectAbsent):
        if exists:
            msg = f"{context}: expected {_path_label(update.path)} to be absent, but it exists"
            raise FlowOperationPreconditionError(msg)
        return
    if not exists or not values_equal(current, update.expect.value):
        found = "a different value" if exists else "nothing"
        msg = f"{context}: expected {_path_label(update.path)} to hold the given value, but found {found}"
        raise FlowOperationPreconditionError(msg)


def _apply_field_update(
    root: dict[str, Any],
    update: UpdateNodeEntry,
    *,
    keyed_list_at,
    context: str,
) -> Any:
    """Apply one set_field or delete_field. Return what a delete removed, or None."""
    path = update.path
    parent = _walk_to_parent(root, path, keyed_list_at, context=context)
    last = path[-1]
    removed = None

    if isinstance(last, str):
        if not isinstance(parent, dict):
            if isinstance(update, DeleteNodeFieldUpdate):
                msg = f"{context}: delete only supports object properties and keyed list items"
            else:
                msg = f"{context}: path must end at an object property or a keyed list item"
            raise FlowOperationValidationError(msg)
        if isinstance(update, SetNodeFieldUpdate):
            exists = last in parent
            _check_value_type_change(exists, parent.get(last), update, context=context)
            # Prevent stored graph state from sharing mutable objects with the
            # operation payload returned in forward_ops.
            parent[last] = _copy_mutable_graph_value(update.value)
        elif last in parent:
            removed = parent.pop(last)
    else:
        keyed, items = _selected_list(parent, path, len(path) - 1, keyed_list_at, context=context)
        key = _selector_key(last)
        position = keyed.find(items, key)
        if isinstance(update, SetNodeFieldUpdate):
            if keyed.key_of(update.value) != key:
                msg = f"{context}: a list item written at a selector must carry the same key: {key!r}"
                raise FlowOperationValidationError(msg)
            _check_value_type_change(
                position is not None, items[position] if position is not None else None, update, context=context
            )
            value = _copy_mutable_graph_value(update.value)
            if position is None:
                items.append(value)
            else:
                items[position] = value
            keyed.sort(items)
        elif position is not None:
            removed = items.pop(position)

    _check_item_keys_unchanged(root, path, keyed_list_at, context=context)
    return removed


def _check_value_type_change(exists: bool, current: Any, update: SetNodeFieldUpdate, *, context: str) -> None:  # noqa: FBT001
    """Refuse a set_field that silently changes a value's JSON type.

    A type change must be declared with ``from_type`` naming the type being
    replaced, which also makes it a precondition: the write only applies to the
    value it was derived from.
    """
    from_type = update.from_type
    value = update.value
    if from_type is None:
        if exists and json_type(current) != json_type(value):
            msg = (
                f"{context}: set_field changes a {json_type(current)} to a {json_type(value)} "
                "without declaring from_type"
            )
            raise FlowOperationValidationError(msg, code="FIELD_TYPE_CHANGE_UNDECLARED")
        return
    if not exists or json_type(current) != from_type:
        found = json_type(current) if exists else "nothing"
        msg = f"{context}: set_field expected to replace a {from_type} but found {found}"
        raise FlowOperationValidationError(msg, code="FIELD_TYPE_PRECONDITION_FAILED")


def _check_item_keys_unchanged(root: dict[str, Any], path: NodeFieldPath, keyed_list_at, *, context: str) -> None:
    """After a write inside a keyed list item, the item must keep its key; re-sort a moved table row."""
    value: Any = root
    for index, part in enumerate(path[:-1]):
        if isinstance(part, str):
            value = value[part] if isinstance(value, dict) else None
            continue
        keyed = keyed_list_at(path[:index])
        items = value
        position = keyed.find(items, _selector_key(part))
        if position is None:
            msg = f"{context}: cannot change a list item's {keyed.selector_name}"
            raise FlowOperationValidationError(msg)
        if keyed.kind == "table" and path[index + 1 :] == (keyed.position,):
            keyed.sort(items)
            return
        value = items[position]


# --- Edges attached to a removed field or output ---------------------------------------


def _edges_attached_to(state: GraphState, node_id: str, path: NodeFieldPath, removed: Any) -> list[str]:
    """Return the edges a removed template field or output was connected through."""
    field_name = None
    output_name = None
    if len(path) == len(_TEMPLATE_PATH) + 1 and path[:-1] == _TEMPLATE_PATH and isinstance(removed, dict):
        field_name = path[-1]
    elif len(path) == len(_OUTPUTS_PATH) + 1 and path[:-1] == _OUTPUTS_PATH and isinstance(path[-1], KeySelector):
        output_name = path[-1].key
    else:
        return []

    attached: list[str] = []
    for edge_id in _edges_in_graph_order(state, state.edge_ids_by_node_id.get(node_id, ())):
        edge = state.edges_by_id[edge_id]
        source_handle, target_handle = _edge_handles(edge)
        if field_name is not None:
            if edge["target"] == node_id and target_handle is not None and target_handle.get("fieldName") == field_name:
                attached.append(edge_id)
            continue
        source_name = source_handle.get("name") if source_handle is not None else None
        from_output = edge["source"] == node_id and source_name == output_name
        into_loop_output = edge["target"] == node_id and _loop_target_output(target_handle) == output_name
        if from_output or into_loop_output:
            attached.append(edge_id)
    return attached


# --- Edge rules --------------------------------------------------------------------------


def _parse_handle(handle: Any) -> dict[str, Any] | None:
    """Parse a handle string, JSON with ``œ`` standing for ``"``, into its object."""
    if isinstance(handle, dict):
        return handle
    if not isinstance(handle, str):
        return None
    try:
        parsed = json.loads(handle.replace("œ", '"'))
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _edge_handles(edge: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Return an edge's source and target handle objects, preferring ``data`` over the strings."""
    data = edge.get("data") if isinstance(edge.get("data"), dict) else {}
    source = data.get("sourceHandle") if isinstance(data.get("sourceHandle"), dict) else None
    target = data.get("targetHandle") if isinstance(data.get("targetHandle"), dict) else None
    return (
        source if source is not None else _parse_handle(edge.get("sourceHandle")),
        target if target is not None else _parse_handle(edge.get("targetHandle")),
    )


def _loop_target_output(target_handle: dict[str, Any] | None) -> str | None:
    """Return the output a loop feedback edge targets, or None.

    A Loop component takes its feedback on one of its own outputs: the target
    handle then names an output (``name``) instead of a template field
    (``fieldName``), as in the Research Translation Loop starter project.
    """
    if target_handle is None or "fieldName" in target_handle:
        return None
    name = target_handle.get("name")
    return name if isinstance(name, str) else None


def _edge_endpoint_names(edge: dict[str, Any]) -> tuple[Any, Any]:
    source_handle, target_handle = _edge_handles(edge)
    source_name = source_handle.get("name") if source_handle is not None else None
    if target_handle is None:
        target_name = None
    elif "fieldName" in target_handle:
        target_name = ("field", target_handle.get("fieldName"))
    else:
        target_name = ("output", target_handle.get("name"))
    return source_name, target_name


def _is_exempt_node(node: dict[str, Any]) -> bool:
    """Group nodes and notes have no fixed fields or outputs to check edges against."""
    if node.get("type") == "noteNode":
        return True
    data = node.get("data")
    node_data = data.get("node") if isinstance(data, dict) else None
    return not isinstance(node_data, dict) or "flow" in node_data


def _node_part(node: dict[str, Any], key: str) -> Any:
    data = node.get("data")
    node_data = data.get("node") if isinstance(data, dict) else None
    return node_data.get(key) if isinstance(node_data, dict) else None


def _output_names(node: dict[str, Any]) -> set[str] | None:
    """Return a node's output names, or None when it has no outputs list to check against."""
    if _is_exempt_node(node):
        return None
    outputs = _node_part(node, "outputs")
    if not isinstance(outputs, list):
        return None
    return {output["name"] for output in outputs if isinstance(output, dict) and isinstance(output.get("name"), str)}


def _template_fields(node: dict[str, Any]) -> dict[str, Any] | None:
    if _is_exempt_node(node):
        return None
    template = _node_part(node, "template")
    return template if isinstance(template, dict) else None


def _check_edge_rules(state: GraphState, edge: dict[str, Any], *, context: str) -> None:
    """Check that an edge's handles name an existing output and field, and a single input stays single.

    Edges without handle data, and the ends of edges at group nodes, notes and
    nodes without a template or outputs, are not checked.
    """
    source_handle, target_handle = _edge_handles(edge)
    source = state.nodes_by_id[edge["source"]]
    target = state.nodes_by_id[edge["target"]]

    if source_handle is not None and isinstance(source_handle.get("name"), str):
        names = _output_names(source)
        if names is not None and source_handle["name"] not in names:
            msg = f"{context}: source node {edge['source']!r} has no output {source_handle['name']!r}"
            raise FlowOperationValidationError(msg, code="EDGE_HANDLE_NOT_FOUND")

    if target_handle is None:
        return
    loop_output = _loop_target_output(target_handle)
    if loop_output is not None:
        names = _output_names(target)
        if names is not None and loop_output not in names:
            msg = f"{context}: target node {edge['target']!r} has no output {loop_output!r}"
            raise FlowOperationValidationError(msg, code="EDGE_HANDLE_NOT_FOUND")
        return

    field_name = target_handle.get("fieldName")
    template = _template_fields(target)
    if template is None or not isinstance(field_name, str):
        return
    template_field = template.get(field_name)
    if not isinstance(template_field, dict):
        msg = f"{context}: target node {edge['target']!r} has no field {field_name!r}"
        raise FlowOperationValidationError(msg, code="EDGE_HANDLE_NOT_FOUND")
    if template_field.get("list") is True:
        return
    for other_id in _edges_in_graph_order(state, state.edge_ids_by_node_id.get(edge["target"], ())):
        other = state.edges_by_id[other_id]
        if other_id == edge["id"] or other["target"] != edge["target"]:
            continue
        _, other_target_handle = _edge_handles(other)
        if other_target_handle is not None and other_target_handle.get("fieldName") == field_name:
            msg = (
                f"{context}: field {field_name!r} of node {edge['target']!r} takes one connection "
                f"and already has one ({other_id!r})"
            )
            raise FlowOperationValidationError(msg, code="EDGE_TARGET_OCCUPIED")


def _apply_delete_nodes(state: GraphState, ids: list[str]) -> tuple[list[FlowOperation], list[str]]:
    delete_ids = deduplicate_delete_ids(ids)
    if not delete_ids:
        return [], []

    for node_id in delete_ids:
        if node_id not in state.base_flow_node_ids:
            msg = f"delete_nodes: cannot delete node that does not exist in the original flow: {node_id!r}"
            raise FlowOperationValidationError(msg)

    removed_node_ids: list[str] = []
    incident_edge_ids: list[str] = []

    for node_id in delete_ids:
        if node_id not in state.nodes_by_id:
            continue
        del state.nodes_by_id[node_id]
        removed_node_ids.append(node_id)
        incident_edge_ids.extend(_edges_in_graph_order(state, state.edge_ids_by_node_id.pop(node_id, set())))

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
        payload = _copy_mutable_graph_value(edge)
        _check_edge_rules(state, payload, context=f"add_edges[{index}]")
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

    keys_to_delete = deduplicate_delete_ids(delete_keys)
    if not fields and not keys_to_delete:
        return []

    for key, value in fields.items():
        state.flow_data[key] = _copy_mutable_graph_value(value)
    for key in keys_to_delete:
        state.flow_data.pop(key, None)

    return [
        UpdateMetadataOp(
            type="update_metadata",
            fields=copy.deepcopy(fields),
            delete_keys=keys_to_delete,
        )
    ]


def _edges_in_graph_order(state: GraphState, edge_ids: set[str]) -> list[str]:
    """Return edge ids in the order the graph lists the edges, so results never depend on set order."""
    if not edge_ids:
        return []
    return [edge_id for edge_id in state.edges_by_id if edge_id in edge_ids]


def _remove_edges(state: GraphState, ids: list[str]) -> list[str]:
    removed_edge_ids: list[str] = []
    for edge_id in deduplicate_delete_ids(ids):
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


def _require_node_id(node: Any, *, context: str) -> str:
    if not isinstance(node, dict):
        msg = f"{context}: node must be a dict"
        raise FlowOperationValidationError(msg)
    node_id = node.get("id")
    if not isinstance(node_id, str) or not node_id:
        msg = f"{context}: node must have a non-empty string id"
        raise FlowOperationValidationError(msg)
    return node_id


def _require_node_objects(node: dict[str, Any], *, context: str) -> None:
    value: Any = node
    for object_path in NODE_OBJECT_PATHS:
        value = value.get(object_path[-1]) if isinstance(value, dict) else None
        if not isinstance(value, dict):
            label = ".".join(str(part) for part in object_path)
            msg = f"{context}: node {label} must be an object"
            raise FlowOperationValidationError(msg)


def _require_edge_endpoints(edge: Any, *, context: str) -> tuple[str, str, str]:
    if not isinstance(edge, dict):
        msg = f"{context}: edge must be a dict"
        raise FlowOperationValidationError(msg)
    edge_id = edge.get("id")
    source = edge.get("source")
    target = edge.get("target")
    if not isinstance(edge_id, str) or not edge_id:
        msg = f"{context}: edge must have a non-empty string id"
        raise FlowOperationValidationError(msg)
    if not isinstance(source, str) or not source:
        msg = f"{context}: edge must have a non-empty string source"
        raise FlowOperationValidationError(msg)
    if not isinstance(target, str) or not target:
        msg = f"{context}: edge must have a non-empty string target"
        raise FlowOperationValidationError(msg)
    return edge_id, source, target
