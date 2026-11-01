"""Applying an operation batch to a flow.

Apply is the write path, so it runs every rule. A batch applies in order, and
all of it or none of it: on an error the flow is as it was before the batch.
Stored operations go through replay instead (``replay.py``), which carries
them out with the same steps and calls no rule.

Each operation of the batch can give apply two results:

- When the caller asks for ``forward``, its forward operations. They can
  differ from the operation that was sent: a ``delete_edges`` or a
  ``delete_field`` that finds nothing is dropped, and the edges that a delete
  takes with it (a cascade delete) become a ``delete_edges`` of their own. So
  one operation gives none, one or several.
- When the caller asks for ``backward``, its backward operations: a list of
  the operations that undo it, read from the values it replaces.

To undo a whole batch, undo the last operation first: replay each list of
backward operations in a call of its own, from last to first, to show an
earlier version of the flow; or put the lists into one batch, in that order,
and apply it, to undo an edit with a new edit that passes every rule.

This is the Rust engine's ``lfx::ops::apply``, step for step.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from lfx.services.flow_operations.edge_rules import MISSING, check_edge, node_value, reads_before, removed_endpoints
from lfx.services.flow_operations.exceptions import FlowOperationValidationError
from lfx.services.flow_operations.keyed_lists import check_position
from lfx.services.flow_operations.ops import FlowOperation, dump_flow_operation, parse_flow_operation
from lfx.services.flow_operations.parse import (
    ADD_EDGES,
    ADD_NODES,
    DELETE_EDGES,
    DELETE_NODES,
    UPDATE_NODES,
    FieldUpdate,
    Operation,
    operation_json,
    parse_operations,
)
from lfx.services.flow_operations.schema import MISSING as FIELD_MISSING
from lfx.services.flow_operations.schema import KeyedList, load_node_schema

if TYPE_CHECKING:
    from lfx.services.flow_operations.keyed_lists import ListIndex
    from lfx.services.flow_operations.state import GraphState

_SCHEMA = load_node_schema()


def invalid(message: str) -> FlowOperationValidationError:
    return FlowOperationValidationError(message)


# --- Reports ------------------------------------------------------------------------------------


class Report:
    """What a batch reports as it applies: forward and backward operations, each only when asked for."""

    __slots__ = ("backward", "cascaded", "forward", "keep_backward", "keep_forward")

    def __init__(self, *, forward: bool, backward: bool) -> None:
        self.keep_forward = forward
        self.keep_backward = backward
        self.forward: list[Operation] = []
        self.backward: list[list[Operation]] = []
        # The ids of the edges cascade deletes removed.
        self.cascaded: list[str] = []

    def begin_operation(self) -> None:
        if self.keep_backward:
            self.backward.append([])

    def record(self, operation: Operation) -> None:
        if self.keep_forward:
            self.forward.append(operation)

    def record_backward(self, operation: Operation) -> None:
        if self.keep_backward:
            self.backward[-1].append(operation)

    def result(self) -> dict[str, Any]:
        """What the batch did, as JSON that shares the batch's values."""
        out: dict[str, Any] = {}
        if self.keep_forward:
            out["forward_operations"] = [operation_json(operation) for operation in self.forward]
        if self.keep_backward:
            out["backward_operations"] = [
                [operation_json(operation) for operation in operations] for operations in self.backward
            ]
        return out


Step = Callable[["GraphState", Operation, Report], None]


def run_batch(state: GraphState, operations: list[Operation], report: Report, step: Step) -> None:
    """Carry out each operation with ``step``, in order, into a new layer. On an error, drop the layer."""
    state.begin()
    try:
        for operation in operations:
            report.begin_operation()
            step(state, operation, report)
    except BaseException:
        state.discard()
        raise


def apply_batch(
    state: GraphState, operations: list[Operation], *, forward: bool = False, backward: bool = False
) -> dict[str, Any]:
    """Apply a parsed batch with every rule into a new layer, which the caller commits or stages.

    Before its first batch, apply checks the flow against the structural rules.
    It checks again after a replay.
    """
    state.discard()
    state.check_base()
    report = Report(forward=forward, backward=backward)
    run_batch(state, operations, report, _apply_operation)
    return report.result()


def _apply_operation(state: GraphState, operation: Operation, report: Report) -> None:
    kind, payload = operation
    if kind == UPDATE_NODES:
        _update_nodes(state, payload, report)
    elif kind == ADD_NODES:
        add_nodes(state, payload, report)
    elif kind == DELETE_NODES:
        _delete_nodes(state, payload, report)
    elif kind == ADD_EDGES:
        _add_edges(state, payload, report)
    else:
        remove_edges(state, payload, report)


# --- Nodes --------------------------------------------------------------------------------------


def add_nodes(state: GraphState, nodes: list[dict[str, Any]], report: Report) -> None:
    """Add nodes. The parser checked each node's shape, and that no id repeats; an id the flow has is refused."""
    if not nodes:
        return
    added = []
    for node in nodes:
        node_id = node["id"]
        if state.has_node(node_id):
            msg = f"add_nodes: node id already exists: {node_id!r}"
            raise invalid(msg)
        added.append(node_id)
        state.insert_node(node)
    # A node is never changed in place once it is in the graph: a later write
    # in the batch copies what it writes, so the forward operation keeps the
    # node as it was added.
    report.record((ADD_NODES, list(nodes)))
    report.record_backward((DELETE_NODES, added))


def _update_nodes(state: GraphState, updates: list[FieldUpdate], report: Report) -> None:
    if not updates:
        return
    backward = FieldBackward() if report.keep_backward else None
    applied = []
    cascaded: dict[str, None] = {}
    for place, update in enumerate(updates):
        require_node(state, update.id)
        if not state.is_base_node(update.id):
            msg = f"update_nodes: cannot update node that does not exist in the original flow: {update.id!r}"
            raise invalid(msg)
        found, before = _apply_field_update(state, update, place, backward)
        if found:
            for edge_id in _edges_at_removed(state, update, before):
                cascaded[edge_id] = None
        # A delete that found nothing is not recorded.
        if report.keep_forward and (found or not update.delete):
            applied.append(update)
    if applied:
        report.record((UPDATE_NODES, applied))
    if backward is not None:
        backward.record(report)
    remove_edges(state, cascaded, report, cascade=True)


def require_node(state: GraphState, node_id: str) -> None:
    """Check that the node an update writes exists."""
    if not state.has_node(node_id):
        msg = f"update_nodes: node does not exist: {node_id!r}"
        raise invalid(msg)


def _edges_at_removed(state: GraphState, update: FieldUpdate, before: Any) -> list[str]:
    """The edges at the endpoints that ``update`` removed from its node, which go with them."""
    node_id = update.id
    removed = removed_endpoints(
        update.path, update.delete, before, lambda keys: node_value(state, node_id, keys), node_id
    )
    if not removed:
        return []
    connections = state.edge_index.connections(state, node_id)
    ids: dict[str, None] = {}
    for endpoint in removed:
        for edge_id in connections.at(endpoint):
            ids[edge_id] = None
    return list(ids)


def _delete_nodes(state: GraphState, ids: list[str], report: Report) -> None:
    unique = list(dict.fromkeys(ids))
    for node_id in unique:
        if not state.is_base_node(node_id):
            msg = f"delete_nodes: cannot delete node that does not exist in the original flow: {node_id!r}"
            raise invalid(msg)
    incident = remove_nodes(state, unique, report)
    remove_edges(state, incident, report, cascade=True)


def remove_nodes(state: GraphState, ids: list[str], report: Report) -> list[str]:
    """Remove the nodes among ``ids`` that exist, and record them. Returns the ids of the edges at them."""
    removed = []
    removed_nodes = []
    incident: dict[str, None] = {}
    for node_id in ids:
        node = state.node(node_id)
        if node is None:
            continue
        for edge_id in state.edge_ids_at(node_id):
            incident[edge_id] = None
        if report.keep_backward:
            removed_nodes.append(node)
        state.remove_node(node_id)
        removed.append(node_id)
    if removed:
        report.record((DELETE_NODES, removed))
        report.record_backward((ADD_NODES, removed_nodes))
    return list(incident)


# --- Edges --------------------------------------------------------------------------------------


def _add_edges(state: GraphState, edges: list[dict[str, Any]], report: Report) -> None:
    added = AddedEdges(report)
    for edge in edges:
        require_new_edge(state, edge)
        check_edge(state, state.edge_index, edge)
        added.insert(state, edge)
    added.record()


def require_new_edge(state: GraphState, edge: dict[str, Any]) -> None:
    """Check that ``edge`` can be added: the flow does not have its id yet, and has both of its nodes."""
    if state.has_edge(edge["id"]):
        msg = f"add_edges: edge id already exists: {edge['id']!r}"
        raise invalid(msg)
    if not state.has_node(edge["source"]):
        msg = f"add_edges: source node does not exist: {edge['source']!r}"
        raise invalid(msg)
    if not state.has_node(edge["target"]):
        msg = f"add_edges: target node does not exist: {edge['target']!r}"
        raise invalid(msg)


class AddedEdges:
    """The edges an ``add_edges`` adds, kept for its forward and backward operations."""

    __slots__ = ("count", "edges", "ids", "report")

    def __init__(self, report: Report) -> None:
        self.report = report
        self.edges: list[dict[str, Any]] = []
        self.ids: list[str] = []
        self.count = 0

    def insert(self, state: GraphState, edge: dict[str, Any]) -> None:
        if self.report.keep_forward:
            self.edges.append(edge)
        if self.report.keep_backward:
            self.ids.append(edge["id"])
        self.count += 1
        state.insert_edge(edge)

    def record(self) -> None:
        if self.count:
            self.report.record((ADD_EDGES, self.edges))
            self.report.record_backward((DELETE_EDGES, self.ids))


def remove_edges(state: GraphState, ids: Any, report: Report, *, cascade: bool = False) -> None:
    """Remove the edges among ``ids`` that exist, each once, and record them as a ``delete_edges``."""
    removed = []
    copies = []
    seen: set[str] = set()
    for edge_id in ids:
        if edge_id in seen:
            continue
        seen.add(edge_id)
        edge = state.edge(edge_id)
        if edge is None:
            continue
        if report.keep_backward:
            copies.append(edge)
        state.remove_edge(edge_id)
        removed.append(edge_id)
    if not removed:
        return
    if cascade:
        report.cascaded.extend(removed)
    report.record((DELETE_EDGES, removed))
    report.record_backward((ADD_EDGES, copies))


# --- Field writes -------------------------------------------------------------------------------


class Walk:
    """Where a field update's path leads in the batch's view of its node, and what it holds."""

    __slots__ = ("current", "found", "last_list", "list_items", "list_problem", "missing_at")

    def __init__(self) -> None:
        # What the path holds, when ``found``.
        self.current: Any = MISSING
        self.found = False
        # The keyed list whose item the last segment names, if it names one.
        self.last_list: KeyedList | None = None
        # The segment indexes of the keyed list items the path passes through, before its last segment.
        self.list_items: list[int] = []
        # The first rule a keyed list on the path breaks: (segment index, problem).
        self.list_problem: tuple[int, str] | None = None
        # The index of the first segment that does not exist.
        self.missing_at: int | None = None


def _place(place: int, segment: int | None = None) -> str:
    return f"update_nodes[{place}]" if segment is None else f"update_nodes[{place}].path[{segment}]"


def walk(state: GraphState, update: FieldUpdate, place: int) -> Walk:
    """Follow the update's path in the batch's view of its node, and read what it holds, before anything is written.

    A segment that does not fit the value it reads, such as a key of a list,
    is an error rather than a missing value. Apply and replay both walk this way.
    """
    node_id, path = update.id, update.path
    last = len(path) - 1
    result = Walk()
    value: Any = state.node(node_id)
    for index, segment in enumerate(path):
        if segment.__class__ is str:
            if not isinstance(value, dict):
                msg = f"{_place(place, index)}: {segment!r} reads a key of a value that is not an object"
                raise invalid(msg)
            child = value.get(segment, MISSING)
        else:
            keyed, list_path = _keyed_list(state, update, index, value, place)
            list_index = state.list_index(node_id, list_path, keyed, value)
            if result.list_problem is None:
                problem = list_index.problem()
                if problem is not None:
                    result.list_problem = (index, problem)
            slot = list_index.find(segment[0], _place(place, index))
            if index == last:
                result.last_list = keyed
            else:
                result.list_items.append(index)
            child = MISSING if slot is None else value[slot]
        if index == last:
            result.found = child is not MISSING
            result.current = child
            return result
        if child is MISSING:
            result.missing_at = index
            return result
        value = child
    return result


def _keyed_list(
    state: GraphState, update: FieldUpdate, index: int, value: Any, place: int
) -> tuple[KeyedList, tuple[str, ...]]:
    """The keyed list whose item ``path[index]`` names, and its path; it must be declared keyed, and be a list.

    The schema decides whether a template field's value is a table from the
    field's keys, read in the batch's view of the node.
    """
    list_path = update.path[:index]
    node = state.node(update.id)

    def field_key(field_path: tuple[str, ...], key: str) -> Any:
        found = node_value(state, update.id, (*field_path, key)) if node is not None else MISSING
        return FIELD_MISSING if found is MISSING else found

    keyed = _SCHEMA.keyed_list_by(list_path, field_key)
    if keyed is None:
        msg = f"{_place(place, index)}: list item key on a list the node schema does not declare keyed"
        raise invalid(msg)
    if not isinstance(value, list):
        msg = f"{_place(place, index)}: list item key on a value that is not a list"
        raise invalid(msg)
    return keyed, list_path


def require_path(update: FieldUpdate, walked: Walk, place: int) -> None:
    """Check that the path exists up to its last segment."""
    missing = walked.missing_at
    if missing is None:
        return
    segment = update.path[missing]
    if segment.__class__ is str:
        msg = f"{_place(place, missing)}: object path part must be an existing string key: {segment!r}"
    else:
        msg = f"{_place(place, missing)}: list item does not exist: {segment[0]!r}"
    raise invalid(msg)


def _apply_field_update(
    state: GraphState, update: FieldUpdate, place: int, backward: FieldBackward | None
) -> tuple[bool, Any]:
    """Apply one ``set_field`` or ``delete_field``, with the rules for list items.

    Returns whether the path held a value, and what it held when the cascade
    delete reads it (``reads_before``).
    """
    walked = walk(state, update, place)
    if walked.list_problem is not None:
        segment, problem = walked.list_problem
        msg = f"{_place(place, segment)}: {problem}"
        raise invalid(msg)
    require_path(update, walked, place)
    if backward is not None:
        backward.add(update, walked)
    before = walked.current if walked.found and reads_before(update.path) else MISSING
    last = len(update.path) - 1
    if update.path[last].__class__ is tuple and not update.delete:
        # A list item written at its key carries a position; the parser checked its key.
        check_position(walked.last_list, update.value, _place(place, last))
    items = write_update(state, update, walked)
    for keyed, item in reversed(items):
        if not keyed.has_position(item):
            msg = f"{_place(place)}: a list item's {keyed.position} must be a finite number"
            raise invalid(msg)
    return walked.found, before


def write_update(state: GraphState, update: FieldUpdate, walked: Walk) -> list[tuple[KeyedList, Any]]:
    """Write or delete the last segment of the update's path, after ``walk``. Apply and replay both write this way.

    Every container on the path is replaced by one the batch owns
    (``GraphState.own``), so the write changes only containers the batch made.
    An item write in a node's keyed list goes into the list's layer
    (``ListLayer``), and the node then holds the list as the batch sees it.
    Returns the list items on the path, after the write, with their lists.
    """
    if update.delete and not walked.found:
        # A delete that finds nothing writes nothing.
        return []
    node_id, path = update.id, update.path
    last = len(path) - 1
    container: Any = state.writable_node(node_id)
    items: list[tuple[ListIndex | None, KeyedList, Any, bool]] = []
    # The layered list on the path, if any: (layer, the container that holds the list, its key).
    layered = None
    for index in range(last):
        segment = path[index]
        if segment.__class__ is str:
            child = container[segment]
            child_cls = child.__class__
            if (
                child_cls is list
                and path[index + 1].__class__ is tuple
                and state.list_is_layered(node_id, path[: index + 1])
            ):
                keyed = _SCHEMA.listed_at(path[: index + 1])
                layer = state.list_layer(node_id, path[: index + 1], keyed, child)
                layered = (layer, container, segment)
                container = child
                continue
            if child_cls is dict or child_cls is list:
                owned = state.own(child)
                if owned is not child:
                    container[segment] = owned
                    if child_cls is list:
                        state.transfer_index(node_id, path[: index + 1], child, owned)
                child = owned
            container = child
        elif layered is not None and layered[0].list_path == path[:index]:
            owned = layered[0].writable_item(state, segment[0])
            items.append((None, layered[0].keyed, owned, False))
            container = owned
        else:
            keyed = _SCHEMA.listed_at(path[:index])
            list_index = state.writable_list_index(node_id, path[:index], keyed, container)
            slot = list_index.slot(segment[0])
            item = container[slot]
            owned = state.own(item)
            if owned is not item:
                container[slot] = owned
            items.append((list_index, keyed, owned, keyed.has_position(owned)))
            container = owned
    segment = path[last]
    if segment.__class__ is str:
        if update.delete:
            del container[segment]
        else:
            container[segment] = update.value
        state.wrote_key(node_id, path, delete=update.delete)
    elif layered is not None and layered[0].list_path == path[:last]:
        layered[0].write(segment[0], update.value, delete=update.delete)
    else:
        keyed = _SCHEMA.listed_at(path[:last])
        list_index = state.writable_list_index(node_id, path[:last], keyed, container)
        key = segment[0]
        if update.delete:
            list_index.remove(key)
        else:
            slot = list_index.slot(key)
            if slot is None:
                list_index.add(key, update.value)
            else:
                list_index.replace(slot, update.value)
    if layered is not None:
        layer, holder, key = layered
        holder[key] = layer.materialize(state)
    after = []
    for list_index, keyed, item, had_position in items:
        if list_index is not None:
            list_index.position_changed(had_position, keyed.has_position(item))
        after.append((keyed, item))
    return after


class FieldBackward:
    """The writes that undo an ``update_nodes``, read from the values each write replaces.

    They are undone last first; a path written twice is split into separate
    operations, since one operation may write a path once.
    """

    __slots__ = ("entries",)

    def __init__(self) -> None:
        self.entries: list[FieldUpdate] = []

    def add(self, update: FieldUpdate, walked: Walk) -> None:
        """Add what undoes ``update``, before it is applied: put back what the path holds, or delete it."""
        if walked.found:
            self.entries.append(FieldUpdate(update.id, update.path, walked.current))
        elif not update.delete:
            self.entries.append(FieldUpdate(update.id, update.path, delete=True))

    def record(self, report: Report) -> None:
        batch: list[FieldUpdate] = []
        written: set[tuple[str, Any]] = set()
        for entry in reversed(self.entries):
            key = (entry.id, entry.path)
            if key in written:
                report.record_backward((UPDATE_NODES, batch))
                batch = []
                written = set()
            written.add(key)
            batch.append(entry)
        if batch:
            report.record_backward((UPDATE_NODES, batch))


# --- The function API ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FlowOperationsApplyResult:
    """Result of applying a batch of flow operations to flow.data."""

    flow_data: dict[str, Any]
    forward_ops: list[FlowOperation]
    # The edges that cascade deletes removed.
    deleted_edges: tuple[str, ...] = ()


def build_graph_state(base_flow: dict[str, Any]) -> GraphState:
    """Validate flow.data structurally and index it, sharing its payloads, which the state never changes."""
    from lfx.services.flow_operations.state import GraphState

    return GraphState.checked(base_flow)


def apply_flow_operations(
    base_flow: dict[str, Any],
    operations: list[FlowOperation] | list[dict[str, Any]],
) -> FlowOperationsApplyResult:
    """Apply a batch to flow.data without changing it; the result shares every container no write passed through."""
    from lfx.services.flow_operations.state import GraphState

    parsed = parse_operations([op if isinstance(op, dict) else dump_flow_operation(op) for op in operations])
    state = GraphState.checked(base_flow)
    state.discard()
    report = Report(forward=True, backward=False)
    run_batch(state, parsed, report, _apply_operation)
    state.commit()
    return FlowOperationsApplyResult(
        flow_data=state.to_value(),
        forward_ops=[parse_flow_operation(operation_json(operation)) for operation in report.forward],
        deleted_edges=tuple(report.cascaded),
    )


__all__ = [
    "FlowOperationsApplyResult",
    "Report",
    "apply_batch",
    "apply_flow_operations",
    "build_graph_state",
    "run_batch",
]
