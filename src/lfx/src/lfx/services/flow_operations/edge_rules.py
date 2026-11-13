"""The rules an edge follows when a write adds it or changes its handles.

An edge connects one output of its source node to one input of its target
node, and its handles name them: ``sourceHandle.name`` is an output of the
source, and ``targetHandle.fieldName`` is a template field of the target. A
loop feedback edge instead names an output of its target, with
``targetHandle.name``, and that output must declare ``allows_loop``.

Every edge carries each handle twice: as an object under ``data``, and as an
escaped JSON string (``œ`` stands for ``"``). Both forms must be present and
agree. Nothing is exempt: group nodes are checked like any node, and an edge
may not touch a note, which has no handles.

An edge never changes in place: a write deletes it and adds it again. The
rules apply only to the edges a write adds. A stored edge that breaks them
stays until something touches it; but an edge whose handles a rule must read,
to see whether a field is taken or which edges a removed output carries, is
read strictly too.

An edge needs both of its ends. A node's endpoints are the keys of its
template, which edges enter, and the items of its outputs list, which edges
leave and loop feedback edges enter. When an endpoint goes, its edges go with
it (a cascade delete): a deleted node takes every edge at it, and a write that
removes an endpoint, directly or by replacing what holds it, takes the
endpoint's edges (``removed_endpoints``).

This is the Rust engine's ``lfx::ops::edges``, rule for rule.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, NamedTuple, Protocol

from lfx.services.flow_operations.canonical import (
    EDGE_VIEW_STATE_KEYS,
    edge_data_with_type_sets,
    handle_with_type_sets,
    parse_handle,
    read_handle,
    values_equal,
)
from lfx.services.flow_operations.codes import GraphViolationCode
from lfx.services.flow_operations.exceptions import FlowDataValidationError, FlowOperationValidationError
from lfx.services.flow_operations.keyed_lists import ListIndex
from lfx.services.flow_operations.schema import OUTPUTS_PATH, TEMPLATE_PATH, load_node_schema

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

HANDLE_KEYS = ("sourceHandle", "targetHandle")
HANDLE_QUOTE = "œ"
NOTE_NODE_TYPE = "noteNode"
OUTPUTS_LIST = load_node_schema().natural_list_at(OUTPUTS_PATH)
FIELD = "field"
LOOP_OUTPUT = "output"

# The input an edge connects at its target: ("field", template key) or ("output", loop output name).
Input = tuple[str, str]

_MISSING = object()


class Handles(NamedTuple):
    """The output an edge leaves from and the input it enters."""

    output: str
    input: Input


class Connections:
    """A node's edges, by the input they enter and the output they leave from, each an ordered set of edge ids."""

    __slots__ = ("inputs", "outputs")

    def __init__(self) -> None:
        self.inputs: dict[Input, dict[str, None]] = {}
        self.outputs: dict[str, dict[str, None]] = {}

    def copy(self) -> Connections:
        copied = Connections()
        copied.inputs = {key: dict(ids) for key, ids in self.inputs.items()}
        copied.outputs = {key: dict(ids) for key, ids in self.outputs.items()}
        return copied

    def at(self, endpoint: tuple[str, str]) -> list[str]:
        """The ids of the edges at an endpoint: into a field, or out of an output and, for a loop output, into it."""
        kind, name = endpoint
        if kind == FIELD:
            return list(self.inputs.get((FIELD, name), ()))
        return [*self.inputs.get((LOOP_OUTPUT, name), ()), *self.outputs.get(name, ())]


class GraphRead(Protocol):
    """Read access to an indexed graph, enough to check edges."""

    def has_node(self, node_id: str) -> bool: ...

    def node(self, node_id: str) -> dict[str, Any] | None:
        """The node as the reader sees it."""
        ...

    def edge(self, edge_id: str) -> dict[str, Any] | None: ...

    def edge_ids_at(self, node_id: str) -> Iterable[str]: ...


def node_value(graph: GraphRead, node_id: str, keys: tuple[str, ...]) -> Any:
    """The value at the object keys ``keys`` of a node, or ``_MISSING``."""
    value: Any = graph.node(node_id)
    if value is None:
        return _MISSING
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            return _MISSING
        value = value[key]
    return value


def _endpoint(edge: dict[str, Any], end: str) -> str:
    value = edge.get(end)
    return value if isinstance(value, str) else ""


class EdgeIndex:
    """What is indexed so far about edges: each edge's handles, and each node's connections.

    Both are built the first time something asks for them, and a batch changes
    them through its layer, as it changes the graph: ``fold`` keeps the layer
    and ``discard`` drops it.
    """

    __slots__ = ("_connections", "_connections_layer", "_handles", "_handles_layer")

    def __init__(self) -> None:
        self._handles: dict[str, Handles] = {}
        self._handles_layer: dict[str, Handles | None] = {}
        self._connections: dict[str, Connections] = {}
        self._connections_layer: dict[str, Connections | None] = {}

    def _cached_handles(self, edge_id: str) -> Handles | None:
        if edge_id in self._handles_layer:
            return self._handles_layer[edge_id]
        return self._handles.get(edge_id)

    def handles(self, edge: dict[str, Any]) -> Handles:
        """An edge's handles, read strictly the first time."""
        edge_id = edge["id"]
        handles = self._cached_handles(edge_id)
        if handles is None:
            handles = read_handles(edge)
            self._handles_layer[edge_id] = handles
        return handles

    def has_connections(self, node_id: str) -> bool:
        if node_id in self._connections_layer:
            return self._connections_layer[node_id] is not None
        return node_id in self._connections

    def _connections_mut(self, node_id: str) -> Connections | None:
        """A node's connections, to change them; the first change in a batch copies the stored ones."""
        if node_id in self._connections_layer:
            return self._connections_layer[node_id]
        stored = self._connections.get(node_id)
        if stored is None:
            return None
        copied = stored.copy()
        self._connections_layer[node_id] = copied
        return copied

    def connections(self, graph: GraphRead, node_id: str) -> Connections:
        """A node's connections, reading the handles of its edges the first time."""
        if node_id in self._connections_layer:
            connections = self._connections_layer[node_id]
            if connections is not None:
                return connections
        else:
            stored = self._connections.get(node_id)
            if stored is not None:
                return stored
        connections = Connections()
        for edge_id in graph.edge_ids_at(node_id):
            edge = graph.edge(edge_id)
            if edge is None:
                msg = f"edge {edge_id!r} does not exist"
                raise FlowOperationValidationError(msg)
            _connect(connections, node_id, edge, self.handles(edge))
        self._connections_layer[node_id] = connections
        return connections

    def insert(self, edge: dict[str, Any]) -> None:
        """Index a new edge at the nodes whose connections are built.

        An edge whose handles do not read (which only a backward operation puts
        back) leaves those nodes to be indexed again when something asks.
        """
        ends = (_endpoint(edge, "source"), _endpoint(edge, "target"))
        if not any(self.has_connections(end) for end in ends):
            return
        try:
            handles = self.handles(edge)
        except FlowOperationValidationError:
            for end in ends:
                self.forget_node(end)
            return
        for end in ends:
            connections = self._connections_mut(end)
            if connections is not None:
                _connect(connections, end, edge, handles)

    def forget(self, edge: dict[str, Any]) -> None:
        """Drop what is indexed about an edge, before it is removed."""
        edge_id = edge["id"]
        handles = self._cached_handles(edge_id)
        if handles is None:
            return
        self._handles_layer[edge_id] = None
        for end in (_endpoint(edge, "source"), _endpoint(edge, "target")):
            connections = self._connections_mut(end)
            if connections is not None:
                _disconnect(connections, end, edge, handles)

    def forget_node(self, node_id: str) -> None:
        """Drop a node's connections."""
        if node_id in self._connections:
            self._connections_layer[node_id] = None
        else:
            self._connections_layer.pop(node_id, None)

    def fold(self) -> None:
        """Make a batch's changes part of the index."""
        handles = self._handles
        for edge_id, value in self._handles_layer.items():
            if value is None:
                handles.pop(edge_id, None)
            else:
                handles[edge_id] = value
        connections = self._connections
        for node_id, value in self._connections_layer.items():
            if value is None:
                connections.pop(node_id, None)
            else:
                connections[node_id] = value
        self._handles_layer = {}
        self._connections_layer = {}

    def discard(self) -> None:
        """Drop a batch's changes."""
        if self._handles_layer:
            self._handles_layer = {}
        if self._connections_layer:
            self._connections_layer = {}


def _connect(connections: Connections, node_id: str, edge: dict[str, Any], handles: Handles) -> None:
    edge_id = edge["id"]
    if _endpoint(edge, "target") == node_id:
        ids = connections.inputs.get(handles.input)
        if ids is None:
            connections.inputs[handles.input] = {edge_id: None}
        else:
            ids[edge_id] = None
    if _endpoint(edge, "source") == node_id:
        ids = connections.outputs.get(handles.output)
        if ids is None:
            connections.outputs[handles.output] = {edge_id: None}
        else:
            ids[edge_id] = None


def _disconnect(connections: Connections, node_id: str, edge: dict[str, Any], handles: Handles) -> None:
    edge_id = edge["id"]
    if _endpoint(edge, "target") == node_id:
        ids = connections.inputs.get(handles.input)
        if ids is not None:
            ids.pop(edge_id, None)
    if _endpoint(edge, "source") == node_id:
        ids = connections.outputs.get(handles.output)
        if ids is not None:
            ids.pop(edge_id, None)


def _error(edge: dict[str, Any], code: GraphViolationCode, reason: str) -> FlowOperationValidationError:
    edge_id = edge.get("id") if isinstance(edge.get("id"), str) else ""
    return FlowOperationValidationError(f"edge {edge_id!r}: {reason}", code=code.value, edge_id=edge_id)


def read_handles(edge: dict[str, Any]) -> Handles:
    """Read an edge's handles strictly: both forms present, the string parsing to the object."""
    source = _handle(edge, "sourceHandle")
    target = _handle(edge, "targetHandle")
    output = source.get("name")
    if not isinstance(output, str) or not output:
        raise _error(edge, GraphViolationCode.EDGE_HANDLE_INVALID, "sourceHandle must name an output")
    # A key that is present counts, whatever its value: a field handle with "name": null names both.
    names_field = "fieldName" in target
    if names_field == ("name" in target):
        raise _error(
            edge, GraphViolationCode.EDGE_HANDLE_INVALID, "targetHandle must name exactly one of a field or an output"
        )
    name = target["fieldName"] if names_field else target["name"]
    if not isinstance(name, str) or not name:
        raise _error(
            edge, GraphViolationCode.EDGE_HANDLE_INVALID, "targetHandle must name its field or output as a string"
        )
    return Handles(output, (FIELD if names_field else LOOP_OUTPUT, name))


def _handle(edge: dict[str, Any], key: str) -> dict[str, Any]:
    # A key that is present counts, whatever its value: "data": null is not an object.
    data = edge.get("data", _MISSING)
    if data is _MISSING:
        data = None
    elif not isinstance(data, dict):
        raise _error(edge, GraphViolationCode.EDGE_HANDLE_INVALID, "data must be an object")
    has_object = data is not None and key in data
    if has_object and not isinstance(data[key], dict):
        raise _error(edge, GraphViolationCode.EDGE_HANDLE_INVALID, f"data.{key} must be an object")
    has_string = key in edge
    if has_string:
        parsed = read_handle(edge[key])
        if parsed is None:
            raise _error(edge, GraphViolationCode.EDGE_HANDLE_INVALID, f"{key} must be an escaped JSON object")
        if has_object and not values_equal(parsed, data[key]):
            raise _error(edge, GraphViolationCode.EDGE_HANDLE_INVALID, f"{key} and data.{key} name different handles")
    if has_object and has_string:
        return data[key]
    if has_object:
        raise _error(edge, GraphViolationCode.EDGE_HANDLE_FORM_MISSING, f"{key} is missing")
    if has_string:
        raise _error(edge, GraphViolationCode.EDGE_HANDLE_FORM_MISSING, f"data.{key} is missing")
    raise _error(edge, GraphViolationCode.EDGE_HANDLE_INVALID, f"edge has no {key}")


def edge_changed(before: dict[str, Any], after: dict[str, Any]) -> bool:
    """Return whether an edge changed between two graphs.

    View state is not a change, and neither is another spelling of the same
    handle, or another order of a handle's type list. A changed edge is
    deleted and added again, so the edge rules check it like a new one.
    """
    keys = dict.fromkeys(before)
    keys.update(dict.fromkeys(after))
    for key in keys:
        if key in EDGE_VIEW_STATE_KEYS:
            continue
        if key not in before or key not in after:
            return True
        old, new = before[key], after[key]
        if key in HANDLE_KEYS:
            old, new = _handle_value(old), _handle_value(new)
            same = values_equal(old, new) or values_equal(handle_with_type_sets(old), handle_with_type_sets(new))
        elif key == "data":
            same = values_equal(old, new) or values_equal(edge_data_with_type_sets(old), edge_data_with_type_sets(new))
        else:
            same = values_equal(old, new)
        if not same:
            return True
    return False


def _handle_value(handle: Any) -> Any:
    """Compare a handle string by the object it encodes."""
    parsed = read_handle(handle)
    return parsed if parsed is not None else handle


def escape_handle(handle: Any) -> str:
    """Return a handle's string form: compact JSON with ``œ`` standing for ``"``."""
    return json.dumps(handle, separators=(",", ":"), ensure_ascii=False).replace('"', HANDLE_QUOTE)


def derive_missing_handle_forms(edge: dict[str, Any]) -> None:
    """Write each handle's missing form from the one present, in place, as the editor spells them."""
    if "data" not in edge:
        edge["data"] = {}
    data = edge["data"]
    for key in HANDLE_KEYS:
        has_object = isinstance(data, dict) and key in data
        if has_object:
            if key not in edge:
                edge[key] = escape_handle(data[key])
        elif key in edge:
            parsed = parse_handle(edge[key])
            if parsed is not None and isinstance(data, dict):
                data[key] = parsed


# --- Outputs and the edge check ---------------------------------------------------------------


class Outputs:
    """A node's outputs, indexed by name."""

    __slots__ = ("index", "items")

    def __init__(self, items: list[Any], index: ListIndex) -> None:
        self.items = items
        self.index = index

    def get(self, name: str) -> Any:
        slot = self.index.slot(name)
        return None if slot is None else self.items[slot]

    def names(self) -> list[str]:
        return self.index.keys()


def index_outputs(items: Any, node_id: str) -> Outputs:
    """Index an outputs list. Every output must have a name that no other output has."""
    if not isinstance(items, list):
        msg = f"node {node_id!r}: data.node.outputs must be a list"
        raise FlowOperationValidationError(msg)
    index = ListIndex(OUTPUTS_LIST, items)
    index.check_keys(f"node {node_id!r}: data.node.outputs")
    return Outputs(items, index)


def node_outputs(graph: GraphRead, node_id: str) -> Outputs | None:
    """A node's outputs, or None for a node without an ``outputs`` key."""
    if not graph.has_node(node_id):
        msg = f"node {node_id!r} does not exist"
        raise FlowOperationValidationError(msg)
    outputs = node_value(graph, node_id, OUTPUTS_PATH)
    if outputs is _MISSING:
        return None
    if not isinstance(outputs, list):
        msg = f"node {node_id!r}: data.node.outputs must be a list"
        raise FlowDataValidationError(msg)
    return index_outputs(outputs, node_id)


def check_edge(graph: GraphRead, index: EdgeIndex, edge: dict[str, Any]) -> Handles:
    """Check an edge a write adds, and return its handles.

    The edge must not touch a note, its handles must be valid and name an
    output of its source and an input of its target, and a single input must
    not be taken by another edge.
    """
    for end in ("source", "target"):
        node_id = _endpoint(edge, end)
        if not graph.has_node(node_id):
            msg = f"edge {edge['id']!r}: {end} node does not exist"
            raise FlowOperationValidationError(msg)
        if node_value(graph, node_id, ("type",)) == NOTE_NODE_TYPE:
            raise _error(
                edge, GraphViolationCode.EDGE_TOUCHES_NOTE, f"its {end} {node_id!r} is a note, which has no handles"
            )
    handles = index.handles(edge)
    source = _endpoint(edge, "source")
    outputs = node_outputs(graph, source)
    if outputs is None or outputs.get(handles.output) is None:
        raise _error(
            edge, GraphViolationCode.EDGE_HANDLE_NOT_FOUND, f"source node {source!r} has no output {handles.output!r}"
        )
    kind, name = handles.input
    target = _endpoint(edge, "target")
    if kind == FIELD:
        field = node_value(graph, target, (*TEMPLATE_PATH, name))
        if not isinstance(field, dict):
            raise _error(
                edge, GraphViolationCode.EDGE_HANDLE_NOT_FOUND, f"target node {target!r} has no field {name!r}"
            )
        single = field.get("list") is not True
    else:
        target_outputs = node_outputs(graph, target)
        output = target_outputs.get(name) if target_outputs is not None else None
        if not isinstance(output, dict) or output.get("allows_loop") is not True:
            raise _error(
                edge, GraphViolationCode.EDGE_HANDLE_NOT_FOUND, f"target node {target!r} has no loop output {name!r}"
            )
        single = True
    if single:
        edge_id = edge["id"]
        taken = [other for other in index.connections(graph, target).inputs.get(handles.input, ()) if other != edge_id]
        if taken:
            label = "field" if kind == FIELD else "output"
            raise _error(
                edge,
                GraphViolationCode.EDGE_TARGET_OCCUPIED,
                f"{label} {name!r} of node {target!r} takes one connection and already has {min(taken)!r}",
            )
    return handles


# --- Cascade deletes --------------------------------------------------------------------------

# Where a node keeps its endpoints: the template holds its fields, and the
# outputs list its outputs. (path, keyed, endpoint kind)
_HOLDERS = ((TEMPLATE_PATH, False, FIELD), (OUTPUTS_PATH, True, LOOP_OUTPUT))


def reads_before(path: tuple[Any, ...]) -> bool:
    """Whether ``removed_endpoints`` reads what a write at ``path`` replaced: at a holder's path or an ancestor."""
    return any(len(path) <= len(holder) and path == holder[: len(path)] for holder, _, _ in _HOLDERS)


def removed_endpoints(
    path: tuple[Any, ...],
    is_delete: bool,  # noqa: FBT001
    before: Any,
    after: Callable[[tuple[str, ...]], Any],
    node_id: str,
) -> list[tuple[str, str]]:
    """The endpoints that a write at ``path`` of node ``node_id`` removed.

    ``before`` is what the path held before the write, which only a write that
    ``reads_before`` needs, and ``after(keys)`` is the value at the object keys
    ``keys`` of the node after it (``_MISSING`` when there is none). A delete of
    one template key or one output removes that endpoint. A write that
    replaces or deletes the outputs list removes the outputs it held that the
    node no longer has. Any other write removes none.
    """
    removed: list[tuple[str, str]] = []
    for holder, keyed, kind in _HOLDERS:
        size = len(holder)
        if len(path) == size + 1 and path[:size] == holder:
            if not is_delete:
                continue
            segment = path[size]
            if keyed and segment.__class__ is tuple:
                removed.append((kind, segment[0]))
            elif not keyed and segment.__class__ is str:
                removed.append((kind, segment))
        elif len(path) <= size and path == holder[: len(path)]:
            held_value = before
            for key in holder[len(path) :]:
                held_value = held_value.get(key, _MISSING) if isinstance(held_value, dict) else _MISSING
            held = _holder_names(held_value, keyed, node_id)
            kept = set(_holder_names(after(holder), keyed, node_id))
            removed.extend((kind, name) for name in held if name not in kept)
    return removed


def _holder_names(held: Any, keyed: bool, node_id: str) -> list[str]:  # noqa: FBT001
    """The names of the endpoints in a value of a holder: an outputs list's names, or a template's keys."""
    if held is _MISSING:
        return []
    if keyed:
        return index_outputs(held, node_id).names()
    return list(held) if isinstance(held, dict) else []


MISSING = _MISSING
