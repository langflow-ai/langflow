"""Graph analysis functions for finding nodes, edges, components, and topology."""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..types import EdgeInfo, NodeInfo

_LOOP_COMPONENT_TYPES = {"LoopComponent"}


def build_edges_by_target(edges: list[EdgeInfo]) -> dict[str, list[EdgeInfo]]:
    """Build mapping of target_id -> list of edges."""
    edges_by_target: dict[str, list[EdgeInfo]] = {}
    for edge in edges:
        if edge.target_id not in edges_by_target:
            edges_by_target[edge.target_id] = []
        edges_by_target[edge.target_id].append(edge)
    return edges_by_target


def find_tool_node_ids(edges: list[EdgeInfo]) -> set[str]:
    """Find nodes that are used as tools."""
    return {edge.source_id for edge in edges if edge.target_input == "tools"}


def find_loop_node_ids(nodes: list[NodeInfo]) -> set[str]:
    """Find nodes that are LoopComponent (create cycles)."""
    return {n.node_id for n in nodes if n.node_type in _LOOP_COMPONENT_TYPES}


def find_loop_feedback_edges(edges: list[EdgeInfo], loop_node_ids: set[str]) -> set[tuple[str, str]]:
    """Find edges that feed back into a LoopComponent (creating cycles)."""
    feedback_edges: set[tuple[str, str]] = set()
    for edge in edges:
        # Edge going INTO a loop component from non-data source is a feedback edge
        if edge.target_id in loop_node_ids and edge.target_input == "item":
            feedback_edges.add((edge.source_id, edge.target_id))
    return feedback_edges


def find_connected_components(nodes: list[NodeInfo], edges: list[EdgeInfo]) -> list[list[NodeInfo]]:
    """Find connected components (subgraphs) in the flow."""
    node_ids = {n.node_id for n in nodes}
    node_by_id = {n.node_id: n for n in nodes}

    # Build undirected adjacency for connectivity analysis
    adj: dict[str, set[str]] = {nid: set() for nid in node_ids}
    for edge in edges:
        if edge.source_id in adj and edge.target_id in adj:
            adj[edge.source_id].add(edge.target_id)
            adj[edge.target_id].add(edge.source_id)

    visited: set[str] = set()
    components: list[list[NodeInfo]] = []

    for node in nodes:
        if node.node_id in visited:
            continue
        # BFS to find all nodes in this component
        component_ids: list[str] = []
        queue: deque[str] = deque([node.node_id])
        while queue:
            nid = queue.popleft()
            if nid in visited:
                continue
            visited.add(nid)
            component_ids.append(nid)
            queue.extend(adj[nid] - visited)
        components.append([node_by_id[nid] for nid in component_ids])

    return components


def topological_sort(
    nodes: list[NodeInfo],
    edges_by_target: dict[str, list[EdgeInfo]],
    loop_node_ids: set[str],
) -> list[NodeInfo]:
    """Sort nodes in topological order so dependencies come first.

    Handles cycles created by LoopComponent by ignoring feedback edges.
    """
    node_ids = {n.node_id for n in nodes}
    node_by_id = {n.node_id: n for n in nodes}
    dependencies: dict[str, set[str]] = {n.node_id: set() for n in nodes}

    # Build flat edge list for feedback detection
    all_edges = [e for edges in edges_by_target.values() for e in edges]
    feedback_edges = find_loop_feedback_edges(all_edges, loop_node_ids)

    for target_id, edges in edges_by_target.items():
        if target_id in dependencies:
            for edge in edges:
                # Skip feedback edges to break cycles
                is_valid_source = edge.source_id in node_ids
                is_not_feedback = (edge.source_id, target_id) not in feedback_edges
                if is_valid_source and is_not_feedback:
                    dependencies[target_id].add(edge.source_id)

    # Kahn's algorithm for topological sort
    result: list[NodeInfo] = []
    no_deps = [n for n in nodes if not dependencies[n.node_id]]

    while no_deps:
        node = no_deps.pop(0)
        result.append(node)
        for other_id, deps in dependencies.items():
            if node.node_id in deps:
                deps.remove(node.node_id)
                if not deps and other_id not in {r.node_id for r in result}:
                    no_deps.append(node_by_id[other_id])

    # Handle any remaining nodes (cycles or isolated)
    remaining = [n for n in nodes if n not in result]
    result.extend(remaining)

    return result


def find_all_endpoints(nodes: list[NodeInfo], edges: list[EdgeInfo]) -> list[str]:
    """Find all endpoint nodes in a component (nodes with no outgoing edges)."""
    node_ids = {n.node_id for n in nodes}
    source_ids = {e.source_id for e in edges if e.source_id in node_ids and e.target_id in node_ids}
    end_node_ids = node_ids - source_ids

    # Prefer ChatOutput nodes, then others
    chat_outputs = [n.var_name for n in nodes if n.node_type == "ChatOutput" and n.node_id in end_node_ids]
    other_ends = [n.var_name for n in nodes if n.node_type != "ChatOutput" and n.node_id in end_node_ids]

    # Return ChatOutputs first, then other endpoints
    all_endpoints = chat_outputs + other_ends
    return all_endpoints if all_endpoints else [nodes[-1].var_name] if nodes else ["None"]


def find_all_start_nodes(nodes: list[NodeInfo], edges: list[EdgeInfo]) -> list[str]:
    """Find all start nodes in a component (nodes with no incoming edges)."""
    node_ids = {n.node_id for n in nodes}
    target_ids = {e.target_id for e in edges if e.target_id in node_ids and e.source_id in node_ids}
    start_node_ids = node_ids - target_ids

    # Prefer ChatInput nodes first, then others
    chat_inputs = [n.var_name for n in nodes if n.node_type == "ChatInput" and n.node_id in start_node_ids]
    other_starts = [n.var_name for n in nodes if n.node_type != "ChatInput" and n.node_id in start_node_ids]

    all_starts = chat_inputs + other_starts
    return all_starts if all_starts else [nodes[0].var_name] if nodes else ["None"]
