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
  ``delete_nodes``, ``add_nodes``, ``update_nodes``, ``add_edges``, each
  listing every item it applies to: deletions in the order the stored graph
  lists them, everything else in the order the target lists it. Nothing is
  sorted;
- nodes, edges and table rows are matched by id, and array order is never a
  change;
- inside a node, the diff follows ``node_schema.json``: it splits only the
  paths the schema lists under ``whole_values.recursed`` into their keys.
  Every other value is written whole when it changes;
- a template field is written in units: its value (``value`` with the keys
  that qualify it), its definition (every other key), and each toggle. When
  any key of a unit changes, the whole unit is written. A new field is one
  write, a removed field one delete;
- keyed lists (outputs, tool actions, table rows) are written per item, at the
  item's key, and per key inside an item. Their order is their items'
  ``__pos__``, so a move is a write to ``__pos__``. A list whose items do not
  all carry a unique key and a position on both sides is written whole;
- an edge that changed in any way is deleted and added again;
- view state is never recorded, and two spellings of one handle are not a
  change. Every top-level key other than ``nodes`` and ``edges`` is view
  state.

This is the Rust engine's ``lfx::ops::diff``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lfx.services.flow_operations.canonical import (
    EDGE_VIEW_STATE_KEYS,
    NODE_VIEW_STATE_KEYS,
    graphs_equal,
    is_row_position,
    same_json,
    values_equal,
    values_trusted,
)
from lfx.services.flow_operations.edge_rules import edge_changed
from lfx.services.flow_operations.exceptions import FlowOperationReplayError
from lfx.services.flow_operations.ops import FlowOperation, parse_flow_operation
from lfx.services.flow_operations.parse import (
    ADD_EDGES,
    ADD_NODES,
    DELETE_EDGES,
    DELETE_NODES,
    UPDATE_NODES,
    FieldUpdate,
    Operation,
    checked_node_path,
    operation_json,
)
from lfx.services.flow_operations.schema import OUTPUTS_PATH, TEMPLATE_PATH, KeyedList, load_node_schema
from lfx.services.flow_operations.validation import validate_flow_data

_SCHEMA = load_node_schema()
_NODE_DATA_VIEW_STATE = _SCHEMA.node_data_view_state
_FIELD_VIEW_STATE = _SCHEMA.field_view_state
_VALUE_UNIT = frozenset(_SCHEMA.value_unit)
_TOGGLES = frozenset(_SCHEMA.toggles)
_OUTPUTS_LIST = _SCHEMA.natural_list_at(OUTPUTS_PATH)


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
    return [parse_flow_operation(operation_json(operation)) for operation in diff_checked(base, target)]


def derive_flow_operations(base: dict[str, Any], target: dict[str, Any]) -> DerivedFlowOperations:
    """Diff two graphs and prove the result replays exactly.

    Returns the operations as the engine normalized them, which is what gets
    recorded, together with the replayed graph.
    """
    validate_flow_data(base, check_values=False)
    validate_flow_data(target, context="target flow.data")
    operations, flow_data = derive_checked(base, target)
    return DerivedFlowOperations(
        operations=[parse_flow_operation(operation) for operation in operations], flow_data=flow_data
    )


def derive_checked(base: dict[str, Any], target: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """``derive_flow_operations`` for graphs that passed its checks: the forward operations as JSON, and the graph.

    Both results share values with ``base`` and ``target``, which nothing changes.
    """
    from lfx.services.flow_operations.apply import apply_batch
    from lfx.services.flow_operations.state import GraphState

    operations = diff_checked(base, target)
    state = GraphState(base)
    applied = apply_batch(state, operations, forward=True)
    state.commit()
    flow_data = state.to_value()
    if not graphs_equal(flow_data, target):
        msg = "derived operations do not replay to the target graph"
        raise FlowOperationReplayError(msg)
    return applied["forward_operations"], flow_data


def diff_checked(base: dict[str, Any], target: dict[str, Any]) -> list[Operation]:
    """``diff_flow_data`` for graphs that passed its checks, as the engine's operations."""
    base_nodes = _by_id(base, "nodes")
    target_nodes = _by_id(target, "nodes")
    base_edges = _by_id(base, "edges")
    target_edges = _by_id(target, "edges")

    changed_edges = {
        edge_id
        for edge_id, edge in target_edges.items()
        if edge_id in base_edges and edge_changed(base_edges[edge_id], edge)
    }
    deleted_edges = [edge_id for edge_id in base_edges if edge_id not in target_edges or edge_id in changed_edges]
    added_edges = [
        _without(edge, EDGE_VIEW_STATE_KEYS)
        for edge_id, edge in target_edges.items()
        if edge_id not in base_edges or edge_id in changed_edges
    ]
    deleted_nodes = [node_id for node_id in base_nodes if node_id not in target_nodes]
    added_nodes = [
        _without(node, NODE_VIEW_STATE_KEYS) for node_id, node in target_nodes.items() if node_id not in base_nodes
    ]

    updates: list[FieldUpdate] = []
    for node_id, node in target_nodes.items():
        before = base_nodes.get(node_id)
        if before is None:
            continue
        # A node equal as it stands writes nothing, so its walk is skipped:
        # most nodes of a save are unchanged. Equal JSON text tells it when
        # the values hold only finite numbers.
        if values_trusted() and same_json(before, node):
            continue
        _NodeDiff(node_id, updates).object(before, node, ())

    operations: list[Operation] = []
    if deleted_edges:
        operations.append((DELETE_EDGES, deleted_edges))
    if deleted_nodes:
        operations.append((DELETE_NODES, deleted_nodes))
    if added_nodes:
        operations.append((ADD_NODES, added_nodes))
    if updates:
        operations.append((UPDATE_NODES, updates))
    if added_edges:
        operations.append((ADD_EDGES, added_edges))
    return operations


def _by_id(graph: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    """A validated graph's nodes or edges, by id, in the graph's order."""
    return {entry["id"]: entry for entry in graph[key]}


def _without(mapping: dict[str, Any], keys: frozenset[str]) -> dict[str, Any]:
    return {key: value for key, value in mapping.items() if key not in keys}


# --- Nodes ---------------------------------------------------------------------------


class _NodeDiff:
    """The writes that turn one node into another."""

    __slots__ = ("id", "updates")

    def __init__(self, node_id: str, updates: list[FieldUpdate]) -> None:
        self.id = node_id
        self.updates = updates

    def set(self, path: tuple[Any, ...], value: Any) -> None:
        self.updates.append(FieldUpdate(self.id, checked_node_path(path), value))

    def delete(self, path: tuple[Any, ...]) -> None:
        self.updates.append(FieldUpdate(self.id, checked_node_path(path), delete=True))

    @staticmethod
    def skipped(path: tuple[Any, ...], key: str) -> bool:
        """The keys never written at a path the diff splits, besides a node's identity."""
        if not path:
            return key == "id" or key in NODE_VIEW_STATE_KEYS
        if path == ("data", "node"):
            return key in _NODE_DATA_VIEW_STATE
        if path == TEMPLATE_PATH:
            return key in _SCHEMA.template_view_state
        return False

    def object(self, base: dict[str, Any], target: dict[str, Any], path: tuple[Any, ...]) -> None:
        """Diff an object the schema splits: split its children where the schema does, write the others whole."""
        for key, value in target.items():
            if self.skipped(path, key):
                continue
            key_path = (*path, key)
            if key not in base:
                self.set(key_path, value)
                continue
            previous = base[key]
            if not self.split(previous, value, key_path) and not values_equal(previous, value):
                self.set(key_path, value)
        for key in base:
            if key not in target and not self.skipped(path, key):
                self.delete((*path, key))

    def split(self, base: Any, target: Any, path: tuple[Any, ...]) -> bool:
        """Diff a value the schema splits further. Returns False when it is written whole."""
        if path in _SCHEMA.recursed_paths:
            # Validation keeps the node's data, data.node and template objects.
            if isinstance(base, dict) and isinstance(target, dict):
                self.object(base, target, path)
                return True
            return False
        if len(path) == len(TEMPLATE_PATH) + 1 and path[:-1] == TEMPLATE_PATH:
            return self.field(base, target, path)
        if path == OUTPUTS_PATH:
            writes: list[tuple[tuple[Any, ...], Any]] = []
            if _keyed_list(_OUTPUTS_LIST, base, target, path, writes):
                self.write_all(writes)
                return True
        return False

    def write_all(self, writes: list[tuple[tuple[Any, ...], Any]]) -> None:
        for path, value in writes:
            if value is _DELETE:
                self.delete(path)
            else:
                self.set(path, value)

    def field(self, base: Any, target: Any, path: tuple[Any, ...]) -> bool:
        """Diff a template field unit by unit. Returns False for a key that is not a field."""
        if not (isinstance(base, dict) and isinstance(target, dict)):
            return False
        target_field = target
        base = _without(base, _FIELD_VIEW_STATE)
        target = _without(target, _FIELD_VIEW_STATE)
        all_keys = list(base) + [key for key in target if key not in base]

        def changed(key: str) -> bool:
            if key in base and key in target:
                return not values_equal(base[key], target[key])
            return (key in base) != (key in target)

        written: set[str] = set()
        # The definition is every key outside the value and the toggles, written together.
        definition = [key for key in all_keys if key not in _VALUE_UNIT and key not in _TOGGLES]
        if any(changed(key) for key in definition):
            written.update(definition)
        # Each toggle is a unit of its own.
        written.update(key for key in all_keys if key in _TOGGLES and changed(key))
        # The value is ``value`` with the keys that qualify it. A keyed list
        # value is written item by item instead, when both sides allow it.
        keyed = _SCHEMA.field_value_list(path[-1], target_field)
        item_writes: list[tuple[tuple[Any, ...], Any]] = []
        per_item = (
            keyed is not None
            and "value" in base
            and "value" in target
            and _keyed_list(keyed, base["value"], target["value"], (*path, "value"), item_writes)
        )
        value_keys = [key for key in all_keys if key in _VALUE_UNIT and not (per_item and key == "value")]
        if any(changed(key) for key in value_keys):
            written.update(value_keys)

        # Write in the target's key order, the item writes where ``value`` stands.
        for key, value in target.items():
            if key == "value" and per_item:
                self.write_all(item_writes)
            elif key in written:
                self.set((*path, key), value)
        for key in base:
            if key not in target and key in written:
                self.delete((*path, key))
        return True


# --- Keyed lists -----------------------------------------------------------------------

_DELETE = object()


def _keyed_list(
    keyed: KeyedList, base: Any, target: Any, path: tuple[Any, ...], writes: list[tuple[tuple[Any, ...], Any]]
) -> bool:
    """Diff a keyed list item by item. Returns False when it has to be written whole."""
    base_items = _items_by_key(keyed, base)
    if base_items is None:
        return False
    target_items = _items_by_key(keyed, target)
    if target_items is None:
        return False
    for key, item in target_items.items():
        item_path = (*path, (key,))
        previous = base_items.get(key)
        if previous is None:
            writes.append((item_path, item))
            continue
        for item_key, value in item.items():
            if item_key not in previous or not values_equal(previous[item_key], value):
                writes.append(((*item_path, item_key), value))
        writes.extend(((*item_path, item_key), _DELETE) for item_key in previous if item_key not in item)
    writes.extend(((*path, (key,)), _DELETE) for key in base_items if key not in target_items)
    return True


def _items_by_key(keyed: KeyedList, items: Any) -> dict[str, dict[str, Any]] | None:
    """A list by item key, or None when it cannot be written item by item.

    That is a list whose items do not all carry a unique key and a numeric
    position: such a list (a legacy list) is written whole, which brings it
    within the rules.
    """
    if not isinstance(items, list):
        return None
    position_key = keyed.position
    by_key: dict[str, dict[str, Any]] = {}
    for item in items:
        key = keyed.key_of(item)
        if not key or not isinstance(item, dict) or key in by_key:
            return None
        if position_key not in item or not is_row_position(item[position_key]):
            return None
        by_key[key] = item
    return by_key
