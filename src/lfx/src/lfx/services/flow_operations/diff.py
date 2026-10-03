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
  ``add_edges``, ``update_metadata``, each listing every item it applies to,
  ordered by ID;
- nodes and edges are matched by ID, and array order is never a change;
- inside a node, the diff follows ``node_schema.json``: it recurses only into
  the node, ``data``, ``data.node`` and ``data.node.template``. Every other
  value is written whole when it changes;
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

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from lfx.services.flow_operations.apply import apply_flow_operations
from lfx.services.flow_operations.canonical import (
    EDGE_HANDLE_KEYS,
    EDGE_VIEW_STATE_KEYS,
    FLOW_VIEW_STATE_KEYS,
    NODE_VIEW_STATE_KEYS,
    canonical_handle,
    graphs_equal,
    json_type,
    utf16_sort_key,
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
    deleted_edge_ids = sorted(
        (edge_id for edge_id in base_edges if edge_id not in target_edges or edge_id in reconnected_edge_ids),
        key=utf16_sort_key,
    )
    added_edge_ids = sorted(
        (edge_id for edge_id in target_edges if edge_id not in base_edges or edge_id in reconnected_edge_ids),
        key=utf16_sort_key,
    )
    deleted_node_ids = sorted((node_id for node_id in base_nodes if node_id not in target_nodes), key=utf16_sort_key)
    added_node_ids = sorted((node_id for node_id in target_nodes if node_id not in base_nodes), key=utf16_sort_key)

    node_updates: list[UpdateNodeEntry] = []
    for node_id in sorted((node_id for node_id in target_nodes if node_id in base_nodes), key=utf16_sort_key):
        node_updates.extend(_diff_node(node_id, base_nodes[node_id], target_nodes[node_id]))

    edge_updates: list[UpdateNodeEntry] = []
    for edge_id in sorted(
        (edge_id for edge_id in target_edges if edge_id in base_edges and edge_id not in reconnected_edge_ids),
        key=utf16_sort_key,
    ):
        edge_updates.extend(_diff_edge(edge_id, base_edges[edge_id], target_edges[edge_id]))

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


def _sorted_keys(mapping: dict[str, Any]) -> list[str]:
    return sorted(mapping, key=utf16_sort_key)


# --- Edges ---------------------------------------------------------------------------


def _diff_edge(edge_id: str, base: dict[str, Any], target: dict[str, Any]) -> list[UpdateNodeEntry]:
    updates: list[UpdateNodeEntry] = []
    for key in _sorted_keys(target):
        if key in _EDGE_IDENTITY_KEYS:
            continue
        value = target[key]
        if key not in base:
            updates.append(_set(edge_id, (key,), value))
            continue
        previous = base[key]
        if key in EDGE_HANDLE_KEYS:
            unchanged = values_equal(canonical_handle(previous), canonical_handle(value))
        else:
            unchanged = values_equal(previous, value)
        if not unchanged:
            updates.append(_set(edge_id, (key,), value, previous=previous))
    updates.extend(
        _delete(edge_id, (key,)) for key in _sorted_keys(base) if key not in target and key not in _EDGE_IDENTITY_KEYS
    )
    return updates


# --- Nodes ---------------------------------------------------------------------------

Updates = list[UpdateNodeEntry]
ChildDiff = Callable[[str, Any, Any, NodeFieldPath, dict[str, Any], Updates], bool]


def _diff_node(node_id: str, base: dict[str, Any], target: dict[str, Any]) -> Updates:
    updates: Updates = []
    template = target["data"]["node"]["template"]
    _diff_keys(
        node_id,
        base,
        target,
        (),
        template,
        updates,
        skip=NODE_VIEW_STATE_KEYS | {"id"},
        children={"data": _diff_data},
    )
    return updates


def _diff_data(node_id: str, base: Any, target: Any, path: NodeFieldPath, template: dict, updates: Updates) -> bool:
    if not (isinstance(base, dict) and isinstance(target, dict)):
        return False
    _diff_keys(node_id, base, target, path, template, updates, children={"node": _diff_node_data})
    return True


def _diff_node_data(
    node_id: str, base: Any, target: Any, path: NodeFieldPath, template: dict, updates: Updates
) -> bool:
    if not (isinstance(base, dict) and isinstance(target, dict)):
        return False
    _diff_keys(
        node_id,
        base,
        target,
        path,
        template,
        updates,
        skip=_NODE_DATA_VIEW_STATE,
        children={"template": _diff_template, "outputs": _diff_outputs},
    )
    return True


def _diff_template(node_id: str, base: Any, target: Any, path: NodeFieldPath, template: dict, updates: Updates) -> bool:
    if not (isinstance(base, dict) and isinstance(target, dict)):
        return False
    _diff_keys(
        node_id,
        base,
        target,
        path,
        template,
        updates,
        skip=_SCHEMA.template_view_state,
        default_child=_diff_field,
    )
    return True


def _diff_outputs(node_id: str, base: Any, target: Any, path: NodeFieldPath, template: dict, updates: Updates) -> bool:
    keyed = _SCHEMA.keyed_list_at({}, path)
    if keyed is None:
        return False
    return _diff_keyed_list(node_id, keyed, base, target, path, template, updates)


def _diff_keys(
    node_id: str,
    base: dict[str, Any],
    target: dict[str, Any],
    path: NodeFieldPath,
    template: dict[str, Any],
    updates: Updates,
    *,
    skip: frozenset[str] = frozenset(),
    children: dict[str, ChildDiff] | None = None,
    default_child: ChildDiff | None = None,
) -> None:
    """Diff one object level: recurse where a child handler applies, write other keys whole."""
    children = children or {}
    for key in _sorted_keys(target):
        if key in skip:
            continue
        key_path = (*path, key)
        value = target[key]
        if key not in base:
            updates.append(_set(node_id, key_path, value, template=template))
            continue
        previous = base[key]
        child = children.get(key, default_child)
        if child is not None and child(node_id, previous, value, key_path, template, updates):
            continue
        if not values_equal(previous, value):
            updates.append(_set(node_id, key_path, value, previous=previous, template=template))
    removed = [key for key in _sorted_keys(base) if key not in target and key not in skip]
    updates.extend(_delete(node_id, (*path, key)) for key in removed)


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

    for key in _sorted_keys(target):
        if key == "value" and per_item:
            updates.extend(items_diff)
        elif key in written:
            updates.append(_set(node_id, (*path, key), target[key], previous=base.get(key, _ABSENT), template=template))
    updates.extend(_delete(node_id, (*path, key)) for key in _sorted_keys(base) if key not in target and key in written)
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
    if keyed.kind == "table":
        if not (_is_sorted_table(keyed, base) and _is_sorted_table(keyed, target)):
            return False
    else:
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
        for item_key in _sorted_keys(item):
            value, before = item[item_key], previous.get(item_key, _ABSENT)
            if before is _ABSENT or not values_equal(before, value):
                updates.append(_set(node_id, (*item_path, item_key), value, previous=before, template=template))
        removed = [item_key for item_key in _sorted_keys(previous) if item_key not in item]
        updates.extend(_delete(node_id, (*item_path, item_key)) for item_key in removed)
    updates.extend(_delete(node_id, (*path, _selector(keyed, key))) for key in base_items if key not in target_items)
    return True


def _items_by_key(keyed: KeyedList, items: Any) -> dict[str, dict[str, Any]] | None:
    """Index a list by item key, or return None when an item has no key or keys repeat."""
    if not isinstance(items, list):
        return None
    by_key: dict[str, dict[str, Any]] = {}
    for item in items:
        key = keyed.key_of(item)
        if key is None or not key or key in by_key:
            return None
        by_key[key] = item
    return by_key


def _is_sorted_table(keyed: KeyedList, rows: list[Any]) -> bool:
    if any(not isinstance(row.get(keyed.position), str) for row in rows):
        return False
    ordered = list(rows)
    keyed.sort(ordered)
    return all(left is right for left, right in zip(ordered, rows, strict=True))


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
        for key, value in sorted(target.items(), key=lambda item: utf16_sort_key(item[0]))
        if key not in _NON_METADATA_KEYS and (key not in base or not values_equal(base[key], value))
    }
    delete_keys = sorted(
        (key for key in base if key not in _NON_METADATA_KEYS and key not in target), key=utf16_sort_key
    )
    if not fields and not delete_keys:
        return None
    return UpdateMetadataOp(type="update_metadata", fields=fields, delete_keys=delete_keys)
