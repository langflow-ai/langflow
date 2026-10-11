"""The indexed graph an apply call works on.

Nodes and edges are indexed by id, and edges by the nodes they touch. Indexes
that only some writes need are built the first time a write asks for them and
kept up to date afterwards: keyed lists by item key, each edge's handles, and
each node's connections by the input or output they use.
"""

from __future__ import annotations

import copy
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from lfx.services.flow_operations.edge_rules import Connections, Handles, read_handles
from lfx.services.flow_operations.exceptions import (
    FlowDataValidationError,
    FlowOperationError,
    FlowOperationValidationError,
)
from lfx.services.flow_operations.keyed_lists import ListIndex

if TYPE_CHECKING:
    from lfx.services.flow_operations.schema import KeyedList


@dataclass
class GraphState:
    """Indexed mutable graph state used while applying a batch."""

    flow_data: dict[str, Any]
    nodes_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    edges_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    edge_ids_by_node_id: defaultdict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    # Node ids read from base_flow["nodes"] before applying operations.
    base_flow_node_ids: set[str] = field(default_factory=set)
    # Base-flow node ids whose payload has already been copied before mutation.
    copied_base_flow_node_ids: set[str] = field(default_factory=set)
    # The same two sets for edges.
    base_flow_edge_ids: set[str] = field(default_factory=set)
    copied_base_flow_edge_ids: set[str] = field(default_factory=set)
    # Keyed lists indexed so far, by the identity of the list object.
    list_indexes: dict[int, ListIndex] = field(default_factory=dict)
    # Handles read so far, by edge id.
    handles_by_edge_id: dict[str, Handles] = field(default_factory=dict)
    # Connections indexed so far, by node id. A node's entry, once built, covers
    # every edge at that node, and every one of those edges has its handles read.
    connections_by_node_id: dict[str, Connections] = field(default_factory=dict)

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

    def list_index(self, keyed: KeyedList, items: list[Any], *, context: str) -> ListIndex:
        """Return the index of ``items``, building it the first time the list is addressed."""
        index = self.list_indexes.get(id(items))
        if index is None or index.items is not items:
            index = ListIndex(keyed, items, context=context)
            self.list_indexes[id(items)] = index
        return index

    def handles(self, edge: dict[str, Any]) -> Handles:
        """Return an edge's handles, reading them strictly the first time."""
        handles = self.handles_by_edge_id.get(edge["id"])
        if handles is None:
            handles = read_handles(edge)
            self.handles_by_edge_id[edge["id"]] = handles
        return handles

    def connections(self, node_id: str) -> Connections:
        """Return a node's connections, reading the handles of its edges the first time."""
        connections = self.connections_by_node_id.get(node_id)
        if connections is None:
            connections = Connections()
            for edge_id in self.edge_ids_by_node_id.get(node_id, ()):
                _connect(connections, node_id, self.edges_by_id[edge_id], self.handles(self.edges_by_id[edge_id]))
            self.connections_by_node_id[node_id] = connections
        return connections

    def insert_edge(self, edge: dict[str, Any]) -> None:
        edge_id = edge["id"]
        self.edges_by_id[edge_id] = edge
        self.edge_ids_by_node_id[edge["source"]].add(edge_id)
        self.edge_ids_by_node_id[edge["target"]].add(edge_id)
        self._index_connections(edge)

    def remove_edges(self, ids: list[str]) -> list[str]:
        """Remove the edges that exist among ``ids`` and return their ids, each once."""
        removed: list[str] = []
        for edge_id in dict.fromkeys(ids):
            edge = self.edges_by_id.pop(edge_id, None)
            if edge is None:
                continue
            removed.append(edge_id)
            self._unindex_connections(edge)
            for node_id in (edge["source"], edge["target"]):
                self.edge_ids_by_node_id[node_id].discard(edge_id)
                if not self.edge_ids_by_node_id[node_id]:
                    del self.edge_ids_by_node_id[node_id]
        return removed

    def remove_node(self, node_id: str) -> set[str]:
        """Remove a node and return the ids of the edges at it, which the caller removes."""
        del self.nodes_by_id[node_id]
        self.connections_by_node_id.pop(node_id, None)
        return set(self.edge_ids_by_node_id.get(node_id, ()))

    def forget_handles(self, edge: dict[str, Any]) -> None:
        """Drop what is indexed about an edge's handles before they are rewritten."""
        self._unindex_connections(edge)

    def reindex_handles(self, edge: dict[str, Any]) -> None:
        """Index an edge's handles again after they were rewritten and checked."""
        self._index_connections(edge)

    def _index_connections(self, edge: dict[str, Any]) -> None:
        for node_id in {edge["source"], edge["target"]}:
            connections = self.connections_by_node_id.get(node_id)
            if connections is not None:
                _connect(connections, node_id, edge, self.handles(edge))

    def _unindex_connections(self, edge: dict[str, Any]) -> None:
        handles = self.handles_by_edge_id.pop(edge["id"], None)
        if handles is None:
            return
        for node_id in {edge["source"], edge["target"]}:
            connections = self.connections_by_node_id.get(node_id)
            if connections is not None:
                _disconnect(connections, node_id, edge, handles)


def _connect(connections: Connections, node_id: str, edge: dict[str, Any], handles: Handles) -> None:
    if edge["target"] == node_id:
        connections.inputs[handles.input].add(edge["id"])
    if edge["source"] == node_id:
        connections.outputs[handles.output].add(edge["id"])


def _disconnect(connections: Connections, node_id: str, edge: dict[str, Any], handles: Handles) -> None:
    if edge["target"] == node_id:
        connections.inputs[handles.input].discard(edge["id"])
    if edge["source"] == node_id:
        connections.outputs[handles.output].discard(edge["id"])


def build_graph_state(base_flow: dict[str, Any]) -> GraphState:
    """Shallow-copy flow.data and index graph payloads by reference."""
    state = GraphState(flow_data=dict(base_flow))
    for node in state.nodes:
        node_id = require_node_id(node, context="flow.data.nodes", error_cls=FlowDataValidationError)
        if node_id in state.nodes_by_id:
            msg = f"flow.data.nodes: duplicate node id: {node_id!r}"
            raise FlowDataValidationError(msg)
        state.nodes_by_id[node_id] = node
        state.base_flow_node_ids.add(node_id)

    for edge in state.edges:
        edge_id, source, target = require_edge_endpoints(
            edge,
            context="flow.data.edges",
            error_cls=FlowDataValidationError,
        )
        if edge_id in state.edges_by_id:
            msg = f"flow.data.edges: duplicate edge id: {edge_id!r}"
            raise FlowDataValidationError(msg)
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


def copy_mutable_graph_value(value: Any) -> Any:
    """Deep-copy mutable JSON values to prevent shared state between the original and applied graph."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return copy.deepcopy(value)


def writable_node(state: GraphState, node_id: str) -> dict[str, Any]:
    """Return the node to write to, deep-copying it from the base flow before its first write."""
    return _copy_on_write(state.nodes_by_id, state.base_flow_node_ids, state.copied_base_flow_node_ids, node_id)


def writable_edge(state: GraphState, edge_id: str) -> dict[str, Any]:
    """Return the edge to write to, deep-copying it from the base flow before its first write."""
    return _copy_on_write(state.edges_by_id, state.base_flow_edge_ids, state.copied_base_flow_edge_ids, edge_id)


def _copy_on_write(
    items_by_id: dict[str, dict[str, Any]],
    base_ids: set[str],
    copied_ids: set[str],
    item_id: str,
) -> dict[str, Any]:
    # The base flow is never mutated: its payloads are shared until the first write.
    if item_id in base_ids and item_id not in copied_ids:
        items_by_id[item_id] = copy.deepcopy(items_by_id[item_id])
        copied_ids.add(item_id)
    return items_by_id[item_id]


def require_node_id(
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


def require_edge_endpoints(
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
