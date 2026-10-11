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
  ``delete_nodes``, ``add_nodes``, ``update_nodes``, ``update_edges``,
  ``add_edges``, ``update_metadata``, each listing every item it applies to:
  deletions in the order the stored graph lists them, everything else in the
  order the target lists it. Nothing is sorted, so the same two graphs always
  give the same operations;
- nodes, edges and table rows are matched by ID, and array order is never a
  change;
- inside a node, the diff follows ``node_schema.json``: it splits only the
  paths the schema lists under ``whole_values.recursed`` (the node, ``data``,
  ``data.node`` and ``data.node.template``) into their keys. Every other value
  is written whole when it changes;
- a template field is written in units: its value (``value`` with the keys
  that qualify it), its definition (every other key), and each toggle. When
  any key of a unit changes, the whole unit is written, so concurrent writers
  never mix two versions of one unit. A new field is one write, a removed
  field one delete;
- keyed lists (outputs, tool actions, table rows) are written per item by
  selector, and per key inside an item. A natural-key list whose order
  changed, and a table that is not keyed by row ids on both sides, is written
  whole;
- an edge that still connects the same two nodes is updated in place, key by
  key; one whose source or target changed is deleted and added again;
- view state is never recorded, and two spellings of one handle are not a
  change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lfx.services.flow_operations.apply import apply_flow_operations
from lfx.services.flow_operations.canonical import (
    EDGE_HANDLE_KEYS,
    EDGE_VIEW_STATE_KEYS,
    FLOW_VIEW_STATE_KEYS,
    NODE_VIEW_STATE_KEYS,
    graphs_equal,
    is_row_position,
    json_type,
    parse_handle,
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
    IdSelector,
    KeySelector,
    NodeFieldPath,
    SetNodeFieldUpdate,
    UpdateEdgesOp,
    UpdateMetadataOp,
    UpdateNodeEntry,
    UpdateNodesOp,
)
from lfx.services.flow_operations.schema import KeyedList, load_node_schema
from lfx.services.flow_operations.validation import validate_flow_data

_SCHEMA = load_node_schema()
_NON_METADATA_KEYS = GRAPH_COLLECTION_KEYS | FLOW_VIEW_STATE_KEYS
_TEMPLATE_PATH: NodeFieldPath = ("data", "node", "template")
_OUTPUTS_PATH: NodeFieldPath = ("data", "node", "outputs")
_NODE_DATA_VIEW_STATE = frozenset(path[-1] for path in _SCHEMA.node_view_state_paths if path[:-1] == ("data", "node"))
_EDGE_IDENTITY_KEYS = frozenset({"id", "source", "target"})
_VALUE_UNIT = frozenset(_SCHEMA.value_unit)
_TOGGLES = frozenset(_SCHEMA.toggles)
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

    reconnected_edge_ids = {
        edge_id
        for edge_id, edge in target_edges.items()
        if edge_id in base_edges
        and (edge["source"], edge["target"]) != (base_edges[edge_id]["source"], base_edges[edge_id]["target"])
    }
    deleted_edge_ids = [
        edge_id for edge_id in base_edges if edge_id not in target_edges or edge_id in reconnected_edge_ids
    ]
    added_edge_ids = [
        edge_id for edge_id in target_edges if edge_id not in base_edges or edge_id in reconnected_edge_ids
    ]
    deleted_node_ids = [node_id for node_id in base_nodes if node_id not in target_nodes]
    added_node_ids = [node_id for node_id in target_nodes if node_id not in base_nodes]

    node_updates: list[UpdateNodeEntry] = []
    for node_id, node in target_nodes.items():
        if node_id in base_nodes:
            node_updates.extend(_diff_node(node_id, base_nodes[node_id], node))

    edge_updates: list[UpdateNodeEntry] = []
    for edge_id, edge in target_edges.items():
        if edge_id in base_edges and edge_id not in reconnected_edge_ids:
            edge_updates.extend(_diff_edge(edge_id, base_edges[edge_id], edge))

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
    if node_updates:
        operations.append(UpdateNodesOp(type="update_nodes", updates=node_updates))
    if edge_updates:
        operations.append(UpdateEdgesOp(type="update_edges", updates=edge_updates))
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


def _without(mapping: dict[str, Any], keys: frozenset[str]) -> dict[str, Any]:
    return {key: value for key, value in mapping.items() if key not in keys}


# --- Edges ---------------------------------------------------------------------------


def _diff_edge(edge_id: str, base: dict[str, Any], target: dict[str, Any]) -> list[UpdateNodeEntry]:
    updates: list[UpdateNodeEntry] = []
    for key, value in target.items():
        if key in _EDGE_IDENTITY_KEYS:
            continue
        if key not in base:
            updates.append(_set(edge_id, (key,), value))
            continue
        previous = base[key]
        if key in EDGE_HANDLE_KEYS:
            unchanged = values_equal(_handle_value(previous), _handle_value(value))
        else:
            unchanged = values_equal(previous, value)
        if not unchanged:
            updates.append(_set(edge_id, (key,), value, previous=previous))
    updates.extend(_delete(edge_id, (key,)) for key in base if key not in target and key not in _EDGE_IDENTITY_KEYS)
    return updates


def _handle_value(handle: Any) -> Any:
    """Compare a handle string by the object it encodes, so two spellings of one handle are the same value."""
    parsed = parse_handle(handle)
    return parsed if parsed is not None else handle


# --- Nodes ---------------------------------------------------------------------------

Updates = list[UpdateNodeEntry]

# Keys never written at a path the diff splits, besides a node's identity.
_SKIPPED_AT: dict[NodeFieldPath, frozenset[str]] = {
    (): NODE_VIEW_STATE_KEYS | {"id"},
    ("data", "node"): _NODE_DATA_VIEW_STATE,
    _TEMPLATE_PATH: _SCHEMA.template_view_state,
}


def _diff_node(node_id: str, base: dict[str, Any], target: dict[str, Any]) -> Updates:
    updates: Updates = []
    _diff_object(node_id, base, target, (), target["data"]["node"]["template"], updates)
    return updates


def _diff_object(
    node_id: str,
    base: dict[str, Any],
    target: dict[str, Any],
    path: NodeFieldPath,
    template: dict[str, Any],
    updates: Updates,
) -> None:
    """Diff an object the schema splits: split its children where the schema does, write the others whole."""
    skip = _SKIPPED_AT.get(path, frozenset())
    for key, value in target.items():
        if key in skip:
            continue
        key_path = (*path, key)
        if key not in base:
            updates.append(_set(node_id, key_path, value, template=template))
            continue
        previous = base[key]
        if _diff_child(node_id, previous, value, key_path, template, updates):
            continue
        if not values_equal(previous, value):
            updates.append(_set(node_id, key_path, value, previous=previous, template=template))
    updates.extend(_delete(node_id, (*path, key)) for key in base if key not in target and key not in skip)


def _diff_child(node_id: str, base: Any, target: Any, path: NodeFieldPath, template: dict, updates: Updates) -> bool:
    """Diff a value the schema splits further. Returns False when it is written whole."""
    if path in _SCHEMA.recursed_paths:
        # Validation keeps the node's data, data.node and template objects.
        _diff_object(node_id, base, target, path, template, updates)
        return True
    if len(path) == len(_TEMPLATE_PATH) + 1 and path[:-1] == _TEMPLATE_PATH:
        return _diff_field(node_id, base, target, path, template, updates)
    if path == _OUTPUTS_PATH:
        return _diff_keyed_list(node_id, _SCHEMA.keyed_list_at({}, path), base, target, path, template, updates)
    return False


def _diff_field(node_id: str, base: Any, target: Any, path: NodeFieldPath, template: dict, updates: Updates) -> bool:
    """Diff a template field unit by unit. Returns False for a key that is not a field."""
    if not (isinstance(base, dict) and isinstance(target, dict)):
        return False
    hidden = _SCHEMA.field_view_state
    base = _without(base, hidden)
    target = _without(target, hidden)

    def changed(keys: set[str]) -> bool:
        return any(
            (key in base) != (key in target) or (key in base and not values_equal(base[key], target[key]))
            for key in keys
        )

    all_keys = set(base) | set(target)
    definition = {key for key in all_keys if key not in _VALUE_UNIT and key not in _TOGGLES}
    written: set[str] = set()
    if changed(definition):
        written |= definition
    written |= {key for key in _TOGGLES & all_keys if changed({key})}

    value_path = (*path, "value")
    keyed = _SCHEMA.keyed_list_at({"data": {"node": {"template": {path[-1]: target}}}}, value_path)
    items_diff: Updates = []
    per_item = (
        keyed is not None
        and "value" in base
        and "value" in target
        and _diff_keyed_list(node_id, keyed, base["value"], target["value"], value_path, template, items_diff)
    )
    value_keys = set(_VALUE_UNIT & all_keys)
    if per_item:
        value_keys.discard("value")
    if changed(value_keys):
        written |= value_keys

    for key, value in target.items():
        if key == "value" and per_item:
            updates.extend(items_diff)
        elif key in written:
            updates.append(_set(node_id, (*path, key), value, previous=base.get(key, _ABSENT), template=template))
    updates.extend(_delete(node_id, (*path, key)) for key in base if key not in target and key in written)
    return True


# --- Keyed lists -----------------------------------------------------------------------


def _diff_keyed_list(
    node_id: str,
    keyed: KeyedList,
    base: Any,
    target: Any,
    path: NodeFieldPath,
    template: dict[str, Any],
    updates: Updates,
) -> bool:
    """Diff a keyed list item by item. Returns False when it has to be written whole."""
    base_items = _items_by_key(keyed, base)
    target_items = _items_by_key(keyed, target)
    if base_items is None or target_items is None:
        return False
    if keyed.kind != "table":
        # A natural list's order is state; a table's order is its rows' positions.
        kept = [key for key in base_items if key in target_items]
        added = [key for key in target_items if key not in base_items]
        if list(target_items) != kept + added:
            return False

    for key, item in target_items.items():
        item_path = (*path, _selector(keyed, key))
        if key not in base_items:
            updates.append(_set(node_id, item_path, item, template=template))
            continue
        previous = base_items[key]
        for item_key, value in item.items():
            before = previous.get(item_key, _ABSENT)
            if before is _ABSENT or not values_equal(before, value):
                updates.append(_set(node_id, (*item_path, item_key), value, previous=before, template=template))
        removed = [item_key for item_key in previous if item_key not in item]
        updates.extend(_delete(node_id, (*item_path, item_key)) for item_key in removed)
    updates.extend(_delete(node_id, (*path, _selector(keyed, key))) for key in base_items if key not in target_items)
    return True


def _items_by_key(keyed: KeyedList, items: Any) -> dict[str, dict[str, Any]] | None:
    """Index a list by item key, or return None when it cannot be written item by item.

    That is a list whose items do not all carry a unique key, or a table whose
    rows do not all carry a numeric position: such a list (a legacy table) is
    written whole, which brings it within the rules.
    """
    if not isinstance(items, list):
        return None
    by_key: dict[str, dict[str, Any]] = {}
    for item in items:
        key = keyed.key_of(item)
        if not key or key in by_key:
            return None
        if keyed.kind == "table" and not is_row_position(item.get(keyed.position)):
            return None
        by_key[key] = item
    return by_key


def _selector(keyed: KeyedList, key: str) -> IdSelector | KeySelector:
    return IdSelector(id=key) if keyed.kind == "table" else KeySelector(key=key)


# --- Entries ---------------------------------------------------------------------------

_ABSENT = object()


def _set(
    entry_id: str,
    path: NodeFieldPath,
    value: Any,
    *,
    previous: Any = _ABSENT,
    template: dict[str, Any] | None = None,
) -> SetNodeFieldUpdate:
    from_type = None
    if previous is not _ABSENT and json_type(previous) != json_type(value):
        from_type = json_type(previous)
    return SetNodeFieldUpdate(
        id=entry_id,
        op="set_field",
        path=path,
        value=value,
        from_type=from_type,
        template_field=_template_field_metadata(path, template) if template is not None else None,
    )


def _delete(entry_id: str, path: NodeFieldPath) -> DeleteNodeFieldUpdate:
    return DeleteNodeFieldUpdate(id=entry_id, op="delete_field", path=path)


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
        for key, value in target.items()
        if key not in _NON_METADATA_KEYS and (key not in base or not values_equal(base[key], value))
    }
    delete_keys = [key for key in base if key not in _NON_METADATA_KEYS and key not in target]
    if not fields and not delete_keys:
        return None
    return UpdateMetadataOp(type="update_metadata", fields=fields, delete_keys=delete_keys)
