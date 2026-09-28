"""Deriving operations from two whole flow graphs.

A whole-flow save hands the server the graph it wants stored. ``diff_flow_data``
expresses the change from the stored graph as the operations a client would
have sent for it, and ``derive_flow_operations`` proves they are right by
replaying them and requiring the canonical result to equal the target exactly.
There is no whole-graph replacement fallback: every valid transition is
expressible in the vocabulary, so a mismatch is a bug and the save must fail.

Shape of the result, so whole-flow saves and future operation submissions
record the same history:

- at most one operation of each type, in the order ``delete_edges``,
  ``delete_nodes``, ``add_nodes``, ``update_nodes``, ``add_edges``,
  ``update_metadata``, each listing every item it applies to, ordered by ID;
- nodes and edges are matched by ID, and array order is never a change;
- existing nodes change through field patches; arrays inside a node are atomic
  values, since their elements carry no stable identity;
- an edge that changed is deleted and added again;
- view state is never recorded.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lfx.services.flow_operations.apply import apply_flow_operations
from lfx.services.flow_operations.canonical import (
    EDGE_VIEW_STATE_KEYS,
    FLOW_VIEW_STATE_KEYS,
    NODE_VIEW_STATE_KEYS,
    graphs_equal,
    json_type,
    values_equal,
)
from lfx.services.flow_operations.exceptions import FlowOperationReplayError
from lfx.services.flow_operations.ops import (
    GRAPH_COLLECTION_KEYS,
    AddEdgesOp,
    AddNodesOp,
    DeleteEdgesOp,
    DeleteNodeFieldUpdate,
    DeleteNodesOp,
    FlowOperation,
    NodeFieldPath,
    SetNodeFieldUpdate,
    UpdateMetadataOp,
    UpdateNodeEntry,
    UpdateNodesOp,
)
from lfx.services.flow_operations.validation import validate_flow_data

_NON_METADATA_KEYS = GRAPH_COLLECTION_KEYS | FLOW_VIEW_STATE_KEYS
_TEMPLATE_PATH: NodeFieldPath = ("data", "node", "template")
# The parts of a template field that decide whether its value is a secret.
TEMPLATE_FIELD_METADATA_KEYS = ("name", "type", "password", "load_from_db", "_input_type", "table_schema")


@dataclass(frozen=True)
class DerivedFlowOperations:
    """Operations that turn one graph into another, verified by replay."""

    operations: list[FlowOperation]
    flow_data: dict[str, Any]


def diff_flow_data(base: dict[str, Any], target: dict[str, Any]) -> list[FlowOperation]:
    """Return the ordered operations that turn ``base`` into ``target``.

    Both graphs must follow the engine's rules. ``base`` is stored data and is
    checked structurally; ``target`` comes from outside and is checked fully,
    so a broken target fails with the engine's own error rather than surfacing
    later as a replay mismatch.
    """
    validate_flow_data(base, check_values=False)
    validate_flow_data(target, context="target flow.data")

    base_nodes = {node["id"]: node for node in base["nodes"]}
    target_nodes = {node["id"]: node for node in target["nodes"]}
    base_edges = {edge["id"]: _without(edge, EDGE_VIEW_STATE_KEYS) for edge in base["edges"]}
    target_edges = {edge["id"]: _without(edge, EDGE_VIEW_STATE_KEYS) for edge in target["edges"]}

    changed_edge_ids = {
        edge_id
        for edge_id, edge in target_edges.items()
        if edge_id in base_edges and not values_equal(base_edges[edge_id], edge)
    }
    deleted_edge_ids = sorted(
        (edge_id for edge_id in base_edges if edge_id not in target_edges or edge_id in changed_edge_ids),
        key=_id_order,
    )
    added_edge_ids = sorted(
        (edge_id for edge_id in target_edges if edge_id not in base_edges or edge_id in changed_edge_ids),
        key=_id_order,
    )
    deleted_node_ids = sorted((node_id for node_id in base_nodes if node_id not in target_nodes), key=_id_order)
    added_node_ids = sorted((node_id for node_id in target_nodes if node_id not in base_nodes), key=_id_order)

    updates: list[UpdateNodeEntry] = []
    for node_id in sorted((node_id for node_id in target_nodes if node_id in base_nodes), key=_id_order):
        updates.extend(_diff_node(node_id, base_nodes[node_id], target_nodes[node_id]))

    operations: list[FlowOperation] = []
    if deleted_edge_ids:
        operations.append(DeleteEdgesOp(type="delete_edges", ids=deleted_edge_ids))
    if deleted_node_ids:
        operations.append(DeleteNodesOp(type="delete_nodes", ids=deleted_node_ids))
    if added_node_ids:
        operations.append(
            AddNodesOp(
                type="add_nodes",
                nodes=[_without(target_nodes[node_id], NODE_VIEW_STATE_KEYS) for node_id in added_node_ids],
            )
        )
    if updates:
        operations.append(UpdateNodesOp(type="update_nodes", updates=updates))
    if added_edge_ids:
        operations.append(AddEdgesOp(type="add_edges", edges=[target_edges[edge_id] for edge_id in added_edge_ids]))

    metadata = _diff_metadata(base, target)
    if metadata is not None:
        operations.append(metadata)
    return operations


def derive_flow_operations(base: dict[str, Any], target: dict[str, Any]) -> DerivedFlowOperations:
    """Diff two graphs and prove the result replays exactly.

    Returns the operations as the engine normalized them, which is what gets
    recorded, together with the replayed graph.
    """
    result = apply_flow_operations(base, diff_flow_data(base, target))
    if not graphs_equal(result.flow_data, target):
        msg = "derived operations do not replay to the target graph"
        raise FlowOperationReplayError(msg)
    return DerivedFlowOperations(operations=result.forward_ops, flow_data=result.flow_data)


def _id_order(entry_id: str) -> bytes:
    # UTF-16 code units, the order JavaScript's default sort uses, so every
    # implementation of this diff agrees on it.
    return entry_id.encode("utf-16-be", "surrogatepass")


def _without(mapping: dict[str, Any], keys: frozenset[str]) -> dict[str, Any]:
    return {key: value for key, value in mapping.items() if key not in keys}


def _diff_node(node_id: str, base_node: dict[str, Any], target_node: dict[str, Any]) -> list[UpdateNodeEntry]:
    ignored = NODE_VIEW_STATE_KEYS | {"id"}
    updates: list[UpdateNodeEntry] = []
    _diff_object(
        node_id,
        _without(base_node, ignored),
        _without(target_node, ignored),
        (),
        _template_of(target_node),
        updates,
    )
    return updates


def _template_of(node: dict[str, Any]) -> dict[str, Any]:
    # validate_flow_data guarantees these are objects.
    return node["data"]["node"]["template"]


def _diff_object(
    node_id: str,
    base: dict[str, Any],
    target: dict[str, Any],
    path: NodeFieldPath,
    template: dict[str, Any],
    updates: list[UpdateNodeEntry],
) -> None:
    for key in sorted(target, key=_id_order):
        field_path = (*path, key)
        value = target[key]
        if key not in base:
            updates.append(_set_field(node_id, field_path, value, template))
            continue
        previous = base[key]
        previous_type = json_type(previous)
        value_type = json_type(value)
        if previous_type == value_type == "object":
            _diff_object(node_id, previous, value, field_path, template, updates)
        elif previous_type != value_type:
            updates.append(_set_field(node_id, field_path, value, template, from_type=previous_type))
        elif not values_equal(previous, value):
            updates.append(_set_field(node_id, field_path, value, template))

    updates.extend(
        DeleteNodeFieldUpdate(id=node_id, op="delete_field", path=(*path, key))
        for key in sorted(base, key=_id_order)
        if key not in target
    )


def _set_field(
    node_id: str,
    path: NodeFieldPath,
    value: Any,
    template: dict[str, Any],
    *,
    from_type: str | None = None,
) -> SetNodeFieldUpdate:
    return SetNodeFieldUpdate(
        id=node_id,
        op="set_field",
        path=path,
        value=value,
        from_type=from_type,
        template_field=_template_field_metadata(path, template),
    )


def _template_field_metadata(path: NodeFieldPath, template: dict[str, Any]) -> dict[str, Any] | None:
    """Return the metadata of the template field a path writes inside of.

    A path that sets a whole template field carries its metadata in the value
    already, and a path outside the template writes no field value, so only
    writes strictly inside one field need it recorded.
    """
    depth = len(_TEMPLATE_PATH)
    if len(path) <= depth + 1 or path[:depth] != _TEMPLATE_PATH:
        return None
    field = template.get(path[depth])
    if not isinstance(field, dict):
        return None
    metadata = {key: field[key] for key in TEMPLATE_FIELD_METADATA_KEYS if key in field}
    return metadata or None


def _diff_metadata(base: dict[str, Any], target: dict[str, Any]) -> UpdateMetadataOp | None:
    fields = {
        key: value
        for key, value in sorted(target.items(), key=lambda item: _id_order(item[0]))
        if key not in _NON_METADATA_KEYS and (key not in base or not values_equal(base[key], value))
    }
    delete_keys = sorted((key for key in base if key not in _NON_METADATA_KEYS and key not in target), key=_id_order)
    if not fields and not delete_keys:
        return None
    return UpdateMetadataOp(type="update_metadata", fields=fields, delete_keys=delete_keys)
