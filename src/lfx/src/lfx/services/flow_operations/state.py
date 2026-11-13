"""``GraphState``: the indexed graph that apply and replay work on, kept between batches.

Nodes and edges are indexed by id, and edges by the nodes they touch.
Indexes that only some writes need are built the first time a write asks for
them and kept up to date afterwards: keyed lists by item key, each edge's
handles, and each node's connections by the input or output they use.

A batch is all or nothing, and it never writes to the graph it starts from.
A node or an edge that a batch adds, removes or writes, and an index entry it
changes, goes into the batch's layer (``_Batch``). A field write copies only
the containers on its path (the node, ``data``, ``data.node``, and so on down
to the written key) and writes into the copies; every other container stays
shared with the stored graph. So a stored container is never changed, and a
copy belongs to one batch until the batch is committed. Reads in the batch
look in the layer first. A batch that succeeds folds its layer into the
graph; a batch that fails drops it. So nothing is ever undone, and a failed
batch keeps the indexes that earlier batches built.

A batch can also stay staged after it succeeds (``stage``): its layer waits
until the caller keeps it (``keep``) or drops it (``drop``), for example
after a database commit. While a batch is staged, the graph as read
(``to_value``, ``to_dict``, ``to_json``) is the committed graph, and another
batch is refused.

This is the Rust engine's ``lfx::ops::state`` with Python's tools: a copied
path takes the place of the Rust field layer.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

from lfx.services.flow_operations.canonical import graph_hash_checked
from lfx.services.flow_operations.edge_rules import EdgeIndex
from lfx.services.flow_operations.exceptions import FlowDataValidationError
from lfx.services.flow_operations.json_io import copy_json, dumps
from lfx.services.flow_operations.keyed_lists import ListIndex
from lfx.services.flow_operations.parse import DELETE_NODES, parse_operations
from lfx.services.flow_operations.validation import find_load_violations, validate_flow_data, violations_error

if TYPE_CHECKING:
    from lfx.services.flow_operations.schema import KeyedList

# A layer entry for something the batch removed.
GONE = object()


class _Batch:
    """What one batch changed: the layer over the stored graph."""

    __slots__ = ("edges", "edges_at", "layers", "lists", "nodes", "owned", "replaced", "set_paths")

    def __init__(self) -> None:
        # The node as the batch sees it, by id, or GONE: added, removed, or a copy the batch writes.
        self.nodes: dict[str, Any] = {}
        # The ids of nodes the batch added or removed, rather than wrote.
        self.replaced: set[str] = set()
        self.edges: dict[str, Any] = {}
        self.edges_at: dict[str, Any] = {}
        # The containers this batch made, by identity, so it may change them.
        # Holding them keeps their identities from being reused.
        self.owned: dict[int, Any] = {}
        # The indexes of the keyed lists this batch reads or writes, by the
        # list's identity: (index, node id, list path).
        self.lists: dict[int, tuple[ListIndex, str, tuple[str, ...]]] = {}
        # The item writes of the keyed lists of a node, by (node id, list path) (``ListLayer``).
        self.layers: dict[tuple[str, tuple[str, ...]], ListLayer] = {}
        # The paths this batch set a value at, by node id: a list at or under
        # one is part of that value, and takes writes at once.
        self.set_paths: dict[str, list[tuple[Any, ...]]] = {}


# The kinds of item write a list layer keeps.
SET = "set"
CHANGED = "changed"
REMOVE = "remove"


class ListLayer:
    """The item writes a batch makes in one keyed list of a node, kept apart from the list.

    A batch writes items into a node's keyed list as the Rust engine's field
    layer does: each item key keeps the batch's last write to it, in the
    order the keys were first written, and the list as the batch sees it is
    the list the batch started from with those writes made in that order. So
    an item deleted and written again in one batch stays in its place, and
    one batch gives one order whichever engine applies it. The node holds the
    list as the batch sees it, so every reader sees the writes.
    """

    __slots__ = ("base", "base_index", "keyed", "list_path", "node_id", "writes")

    def __init__(
        self, node_id: str, list_path: tuple[str, ...], keyed: KeyedList, base: list[Any], base_index: ListIndex
    ):
        self.node_id = node_id
        self.list_path = list_path
        self.keyed = keyed
        self.base = base
        self.base_index = base_index
        # Item key -> (kind, value), in the order the keys were first written.
        self.writes: dict[str, tuple[str, Any]] = {}

    def writable_item(self, state: GraphState, key: str) -> Any:
        """The item with ``key``, as a container the batch owns, to write inside it."""
        entry = self.writes.get(key)
        if entry is None:
            owned = state.own(self.base[self.base_index.slot(key)])
            self.writes[key] = (CHANGED, owned)
            return owned
        kind, value = entry
        owned = state.own(value)
        self.writes[key] = (kind, owned)
        return owned

    def write(self, key: str, value: Any, *, delete: bool) -> None:
        """Set the item with ``key``, or delete it. A deleted item the batch added leaves no trace."""
        if not delete:
            self.writes[key] = (SET, value)
        elif self.base_index.slot(key) is not None:
            self.writes[key] = (REMOVE, None)
        else:
            self.writes.pop(key, None)

    def materialize(self, state: GraphState) -> list[Any]:
        """The list as the batch sees it: the base list with the writes made in order, and its index."""
        items = list(self.base)
        index = self.base_index.copy(items)
        for key, (kind, value) in self.writes.items():
            if kind == REMOVE:
                index.remove(key)
                continue
            slot = index.slot(key)
            if slot is None:
                index.add(key, value)
            else:
                index.replace(slot, value)
        state.batch.lists[id(items)] = (index, self.node_id, self.list_path)
        return items


class GraphState:
    """A flow graph, indexed for applying operations.

    It keeps the graph and its indexes between batches, so the graph is
    indexed once, and each batch costs only what it changes. Threads can
    share one state: each call holds the state's lock.
    """

    __slots__ = (
        "_base_checked",
        "_lock",
        "_root",
        "_staged",
        "batch",
        "edge_index",
        "edges",
        "edges_at",
        "lists",
        "nodes",
    )

    def __init__(self, flow: Any) -> None:
        """Load a flow graph that this state may share, and build its indexes.

        Loading checks only what the indexes need: flow data is an object,
        ``nodes`` and ``edges`` are lists of objects, ids are unique, and each
        node and edge has its shape. Apply checks the other structural rules
        before its first batch; replay does not check them.

        The state never changes a container of ``flow``: a batch copies what
        it writes. The caller must not change ``flow`` either, so a caller
        that keeps using it passes a copy (``json_io.read_data``).
        """
        violations_error(find_load_violations(flow), "flow.data")
        root = dict(flow)
        self.nodes: dict[str, dict[str, Any]] = {node["id"]: node for node in flow["nodes"]}
        self.edges: dict[str, dict[str, Any]] = {edge["id"]: edge for edge in flow["edges"]}
        edges_at: dict[str, dict[str, None]] = {}
        for edge_id, edge in self.edges.items():
            source, target = edge["source"], edge["target"]
            at = edges_at.get(source)
            if at is None:
                edges_at[source] = {edge_id: None}
            else:
                at[edge_id] = None
            if target != source:
                at = edges_at.get(target)
                if at is None:
                    edges_at[target] = {edge_id: None}
                else:
                    at[edge_id] = None
        root["nodes"] = None
        root["edges"] = None
        self._root = root
        self.edges_at = edges_at
        self.edge_index = EdgeIndex()
        # The keyed lists of stored nodes indexed so far: node id -> list path -> index.
        self.lists: dict[str, dict[tuple[str, ...], ListIndex]] = {}
        self.batch: _Batch | None = None
        self._base_checked = False
        self._staged = False
        self._lock = threading.Lock()

    @classmethod
    def checked(cls, flow: Any) -> GraphState:
        """Load a flow graph that apply changes next, after checking it against the structural rules.

        Values are not walked for numbers that are not finite: that check
        belongs to whoever accepts a graph from outside, and skipping it keeps
        the check proportional to the number of nodes and edges.
        """
        validate_flow_data(flow, check_values=False)
        state = cls(flow)
        state._base_checked = True
        return state

    # --- Reading the graph -----------------------------------------------------------------

    def to_value(self) -> dict[str, Any]:
        """The committed graph, without a staged batch. Its nodes and edges are shared, and never change."""
        return self._value(self.nodes, self.edges)

    def _value(self, nodes: dict[str, Any], edges: dict[str, Any]) -> dict[str, Any]:
        out = {}
        for key, value in self._root.items():
            if key == "nodes":
                out[key] = list(nodes.values())
            elif key == "edges":
                out[key] = list(edges.values())
            else:
                out[key] = value
        return out

    def _staged_value(self) -> dict[str, Any]:
        """The graph with the staged batch, as ``keep`` makes it, without changing the committed graph."""
        batch = self.batch
        nodes, edges = dict(self.nodes), dict(self.edges)
        _fold(nodes, batch.nodes)
        _fold(edges, batch.edges)
        return self._value(nodes, edges)

    def to_dict(self) -> dict[str, Any]:
        """The committed graph, as a copy that shares no container with the state."""
        with self._lock:
            value = self.to_value()
        return copy_json(value)

    def to_json(self, *, staged: bool = False) -> str:
        """The committed graph, as JSON text. With ``staged``, the graph with the staged batch, as ``keep`` makes
        it: a server writes it in the transaction that records the batch. Raises ``RuntimeError`` when ``staged``
        is true and no batch is staged.
        """  # noqa: D205
        with self._lock:
            if not staged:
                value = self.to_value()
            elif self._staged:
                value = self._staged_value()
            else:
                msg = "no batch is staged"
                raise RuntimeError(msg)
        return dumps(value)

    def graph_hash(self, *, staged: bool = False) -> str:
        """The SHA-256 hex digest of the committed graph's canonical form, as ``GraphPlain.graph_hash`` gives for
        its JSON text, without writing or reading the text. With ``staged``, the graph with the staged batch, as
        ``keep`` makes it. Raises ``RuntimeError`` when ``staged`` is true and no batch is staged.
        """  # noqa: D205
        with self._lock:
            if not staged:
                value = self.to_value()
            elif self._staged:
                value = self._staged_value()
            else:
                msg = "no batch is staged"
                raise RuntimeError(msg)
        # The graph was read with the JSON limits, and every batch keeps them.
        return graph_hash_checked(value)

    def snapshot(self) -> GraphSnapshot:
        """The committed graph as it is now, without a staged batch, to write and hash while batches go on.

        It shares the graph's nodes and edges, which no batch changes in place: it costs a list of each.
        """
        with self._lock:
            return GraphSnapshot(self.to_value())

    @property
    def staged(self) -> bool:
        """Whether a batch is staged."""
        return self._staged

    # --- Reads in a batch: the GraphRead protocol of edge_rules ------------------------------

    def node(self, node_id: str) -> dict[str, Any] | None:
        """The node as the batch sees it."""
        batch = self.batch
        if batch is not None and node_id in batch.nodes:
            node = batch.nodes[node_id]
            return None if node is GONE else node
        return self.nodes.get(node_id)

    def has_node(self, node_id: str) -> bool:
        return self.node(node_id) is not None

    def edge(self, edge_id: str) -> dict[str, Any] | None:
        batch = self.batch
        if batch is not None and edge_id in batch.edges:
            edge = batch.edges[edge_id]
            return None if edge is GONE else edge
        return self.edges.get(edge_id)

    def has_edge(self, edge_id: str) -> bool:
        return self.edge(edge_id) is not None

    def edge_ids_at(self, node_id: str) -> list[str]:
        batch = self.batch
        if batch is not None and node_id in batch.edges_at:
            ids = batch.edges_at[node_id]
            return [] if ids is GONE else list(ids)
        return list(self.edges_at.get(node_id, ()))

    def is_base_node(self, node_id: str) -> bool:
        """Whether the node existed when the batch started."""
        return node_id in self.nodes

    def is_stored_node(self, node_id: str) -> bool:
        """Whether node ``node_id`` is a stored node, not one the batch added in its place."""
        batch = self.batch
        return node_id in self.nodes and (batch is None or node_id not in batch.replaced)

    # --- Keyed list indexes ------------------------------------------------------------------

    def list_index(self, node_id: str, list_path: tuple[str, ...], keyed: KeyedList, items: list[Any]) -> ListIndex:
        """The index of ``items``, the keyed list at ``list_path`` of a node, built the first time it is read."""
        batch = self.batch
        key = id(items)
        if batch is not None:
            entry = batch.lists.get(key)
            if entry is not None and entry[0].items is items:
                return entry[0]
        node_lists = self.lists.get(node_id)
        if node_lists is not None:
            index = node_lists.get(list_path)
            if index is not None and index.items is items and index.keyed is keyed:
                return index
        index = ListIndex(keyed, items)
        if self.is_stored_node(node_id) and _at_keys(self.nodes[node_id], list_path) is items:
            # The stored node's own list: the index stays good until a batch replaces the list.
            self.lists.setdefault(node_id, {})[list_path] = index
        elif batch is not None:
            batch.lists[key] = (index, node_id, list_path)
        return index

    def transfer_index(self, node_id: str, list_path: tuple[Any, ...], original: list[Any], copied: list[Any]) -> None:
        """Give ``copied``, the batch's copy of the list ``original``, a copy of the index of ``original``, if any."""
        batch = self.batch
        entry = batch.lists.get(id(original))
        index = entry[0] if entry is not None and entry[0].items is original else None
        if index is None:
            cached = self.lists.get(node_id, {}).get(list_path)
            if cached is not None and cached.items is original:
                index = cached
        if index is not None:
            batch.lists[id(copied)] = (index.copy(copied), node_id, list_path)

    def writable_list_index(
        self, node_id: str, list_path: tuple[str, ...], keyed: KeyedList, items: list[Any]
    ) -> ListIndex:
        """The index of ``items``, a keyed list the batch owns, to change it along with the list."""
        batch = self.batch
        entry = batch.lists.get(id(items))
        if entry is not None and entry[0].items is items and entry[0].keyed is keyed:
            return entry[0]
        index = ListIndex(keyed, items)
        batch.lists[id(items)] = (index, node_id, list_path)
        return index

    # --- Writes in a batch ---------------------------------------------------------------------

    def own(self, value: Any) -> Any:
        """A container this batch may change: ``value`` itself if the batch made it, else a shallow copy."""
        owned = self.batch.owned
        if id(value) in owned:
            return value
        copied = list(value) if value.__class__ is list else dict(value)
        owned[id(copied)] = copied
        return copied

    def writable_node(self, node_id: str) -> dict[str, Any]:
        """The node to write to, as a container this batch owns."""
        node = self.node(node_id)
        owned = self.own(node)
        if owned is not node:
            self.batch.nodes[node_id] = owned
        return owned

    def insert_node(self, node: dict[str, Any]) -> None:
        """Add ``node``, whose id the graph does not have."""
        batch = self.batch
        node_id = node["id"]
        batch.nodes[node_id] = node
        batch.replaced.add(node_id)
        self._forget_writes(node_id)

    def _forget_writes(self, node_id: str) -> None:
        """Drop the batch's record of writes to a node it adds or removes."""
        batch = self.batch
        batch.set_paths.pop(node_id, None)
        for key in [key for key in batch.layers if key[0] == node_id]:
            del batch.layers[key]

    def list_is_layered(self, node_id: str, list_path: tuple[Any, ...]) -> bool:
        """Whether item writes to the node's keyed list at ``list_path`` go through a ``ListLayer``.

        They do unless the batch set a value at the list's path or at an
        ancestor of it: the list is then part of that value, and takes writes
        at once.
        """
        return all(list_path[: len(set_path)] != set_path for set_path in self.batch.set_paths.get(node_id, ()))

    def list_layer(self, node_id: str, list_path: tuple[str, ...], keyed: KeyedList, items: list[Any]) -> ListLayer:
        """The layer of the node's keyed list at ``list_path``, whose list is ``items`` when it is new."""
        key = (node_id, list_path)
        layer = self.batch.layers.get(key)
        if layer is None:
            layer = ListLayer(node_id, list_path, keyed, items, self.list_index(node_id, list_path, keyed, items))
            self.batch.layers[key] = layer
        return layer

    def wrote_key(self, node_id: str, path: tuple[Any, ...], *, delete: bool) -> None:
        """Note a write at ``path``, which ends at an object key: the lists at or under it are replaced or gone."""
        batch = self.batch
        for key in [key for key in batch.layers if key[0] == node_id and key[1][: len(path)] == path]:
            del batch.layers[key]
        if not delete:
            batch.set_paths.setdefault(node_id, []).append(path)

    def remove_node(self, node_id: str) -> None:
        """Remove the node, if it exists. Its edges stay; the caller removes them."""
        batch = self.batch
        if node_id in self.nodes:
            batch.nodes[node_id] = GONE
        else:
            batch.nodes.pop(node_id, None)
        batch.replaced.add(node_id)
        self._forget_writes(node_id)
        self.edge_index.forget_node(node_id)
        # The list indexes are a cache: a failed batch rebuilds what it needs.
        self.lists.pop(node_id, None)

    def _edges_at_mut(self, node_id: str) -> dict[str, None] | None:
        batch = self.batch
        if node_id in batch.edges_at:
            ids = batch.edges_at[node_id]
            return None if ids is GONE else ids
        stored = self.edges_at.get(node_id)
        if stored is None:
            return None
        copied = dict(stored)
        batch.edges_at[node_id] = copied
        return copied

    def insert_edge(self, edge: dict[str, Any]) -> None:
        """Add ``edge``, whose id the graph does not have."""
        batch = self.batch
        edge_id = edge["id"]
        for end in _ends(edge):
            ids = self._edges_at_mut(end)
            if ids is None:
                batch.edges_at[end] = {edge_id: None}
            else:
                ids[edge_id] = None
        self.edge_index.insert(edge)
        batch.edges[edge_id] = edge

    def remove_edge(self, edge_id: str) -> None:
        """Remove the edge, if it exists."""
        edge = self.edge(edge_id)
        if edge is None:
            return
        batch = self.batch
        self.edge_index.forget(edge)
        for end in _ends(edge):
            ids = self._edges_at_mut(end)
            if ids is not None:
                ids.pop(edge_id, None)
                if not ids:
                    if end in self.edges_at:
                        batch.edges_at[end] = GONE
                    else:
                        batch.edges_at.pop(end, None)
        if edge_id in self.edges:
            batch.edges[edge_id] = GONE
        else:
            batch.edges.pop(edge_id, None)

    # --- Batches -------------------------------------------------------------------------------

    def begin(self) -> None:
        """Start a batch: an empty layer."""
        self.edge_index.discard()
        self.batch = _Batch()

    def commit(self) -> None:
        """End a batch that succeeded: its layer becomes the graph."""
        batch = self.batch
        self.batch = None
        if batch is None:
            return
        _fold(self.nodes, batch.nodes)
        _fold(self.edges, batch.edges)
        _fold(self.edges_at, batch.edges_at)
        nodes = self.nodes
        for index, node_id, list_path in batch.lists.values():
            node = nodes.get(node_id)
            if node is not None and _at_keys(node, list_path) is index.items:
                self.lists.setdefault(node_id, {})[list_path] = index
        self.edge_index.fold()

    def discard(self) -> None:
        """End a batch that failed: drop its layer."""
        self.batch = None
        self.edge_index.discard()

    def check_base(self) -> None:
        """Check the flow against the structural rules, unless it passed them since it was loaded or replayed."""
        if not self._base_checked:
            validate_flow_data(self.to_value(), check_values=False)
            self._base_checked = True

    def uncheck_base(self) -> None:
        """Note that a replay changed the flow, so apply checks it again."""
        self._base_checked = False

    # --- The calls ----------------------------------------------------------------------------

    def _unstaged(self) -> None:
        if self._staged:
            msg = "a batch is staged: keep or drop it before the next batch"
            raise RuntimeError(msg)

    def apply(self, operations: Any, *, forward: bool = False, backward: bool = False) -> dict[str, Any]:
        """Apply a batch with every rule; returns what it did. A refused batch changes nothing.

        ``operations`` is the batch as JSON (``json_io.read_operations``), parsed here.
        """
        from lfx.services.flow_operations.apply import apply_batch

        with self._lock:
            self._unstaged()
            result = apply_batch(self, parse_operations(operations), forward=forward, backward=backward)
            self.commit()
            return result

    def stage(self, operations: Any, *, forward: bool = False, backward: bool = False) -> dict[str, Any]:
        """Apply a batch with every rule, as ``apply`` does, and keep it staged until ``keep`` or ``drop``."""
        from lfx.services.flow_operations.apply import apply_batch

        with self._lock:
            self._unstaged()
            result = apply_batch(self, parse_operations(operations), forward=forward, backward=backward)
            self._staged = True
            return result

    def keep(self) -> None:
        """Commit the staged batch. Raises ``RuntimeError`` when no batch is staged."""
        with self._lock:
            if not self._staged:
                msg = "no batch is staged"
                raise RuntimeError(msg)
            self._staged = False
            self.commit()

    def drop(self) -> bool:
        """Drop the staged batch, so the graph stays as it was before it. Returns whether a batch was staged."""
        with self._lock:
            if not self._staged:
                return False
            self._staged = False
            self.discard()
            return True

    def replay(self, operations: Any, *, backward: bool = False) -> dict[str, Any]:
        """Replay stored operations in order, with no rule; returns what it did. A failure replays nothing."""
        from lfx.services.flow_operations.replay import replay_batch

        with self._lock:
            self._unstaged()
            parsed = parse_operations(operations)
            deleted = [node_id for kind, payload in parsed if kind == DELETE_NODES for node_id in payload]
            result = replay_batch(self, parsed, backward=backward)
            self.commit()
            # Replay checks no rule. Of the structural rules that apply checks before its first batch, the only one a
            # replay can break is that an edge's nodes exist: replay deletes no edge with its node. Stored operations
            # delete those edges in the same batch, so the graph stays checked unless a node the batch deleted still
            # has edges. Then apply checks the whole graph again, and refuses it.
            if any(node_id not in self.nodes and self.edges_at.get(node_id) for node_id in deleted):
                self.uncheck_base()
            return result


def _ends(edge: dict[str, Any]) -> tuple[str, ...]:
    source, target = edge["source"], edge["target"]
    return (source,) if source == target else (source, target)


class GraphSnapshot:
    """A graph as a ``GraphState`` held it when ``snapshot`` took it: read only, and unchanged by later batches."""

    __slots__ = ("_value",)

    def __init__(self, value: dict[str, Any]) -> None:
        self._value = value

    def to_json(self) -> str:
        """The graph as JSON text: what the state's ``to_json`` gave when the snapshot was taken."""
        return dumps(self._value)

    def graph_hash(self) -> str:
        """The graph's ``graph_hash``: what the state's ``graph_hash`` gave when the snapshot was taken."""
        # The graph was read with the JSON limits, and every batch keeps them.
        return graph_hash_checked(self._value)


def _fold(stored: dict[str, Any], layer: dict[str, Any]) -> None:
    for key, value in layer.items():
        if value is GONE:
            stored.pop(key, None)
        else:
            stored[key] = value


def _at_keys(value: Any, keys: tuple[str, ...]) -> Any:
    for key in keys:
        if value.__class__ is not dict:
            return None
        value = value.get(key)
    return value


__all__ = ["GONE", "FlowDataValidationError", "GraphSnapshot", "GraphState"]
