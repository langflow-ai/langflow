"""Graph layout: assign positions to nodes using a layered algorithm.

Uses topological sorting to assign nodes to layers (columns),
then spaces them out horizontally and vertically.
"""

from __future__ import annotations

from collections import defaultdict, deque

from lfx.graph.flow_builder._utils import node_id as _node_id

LAYER_SPACING_X = 600
NODE_SPACING_Y = 350


def layout_flow(flow: dict) -> None:
    """Assign positions to all nodes in a flow based on edge topology."""
    nodes = flow.get("data", {}).get("nodes", [])
    edges = flow.get("data", {}).get("edges", [])

    if not nodes:
        return

    node_ids = [_node_id(n) for n in nodes]
    id_to_node = {_node_id(n): n for n in nodes}

    # Build adjacency: source -> [targets]
    successors: dict[str, list[str]] = defaultdict(list)
    predecessors: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        src = edge.get("source", "")
        tgt = edge.get("target", "")
        if src in id_to_node and tgt in id_to_node:
            successors[src].append(tgt)
            predecessors[tgt].append(src)

    # Assign layers via longest path from sources (nodes with no predecessors)
    layers = _assign_layers(node_ids, successors, predecessors)

    # Group nodes by layer
    layer_groups: dict[int, list[str]] = defaultdict(list)
    for nid, layer in layers.items():
        layer_groups[layer].append(nid)

    # Assign positions
    for layer_idx, group in sorted(layer_groups.items()):
        x = layer_idx * LAYER_SPACING_X
        total_height = (len(group) - 1) * NODE_SPACING_Y
        start_y = -total_height / 2
        for i, nid in enumerate(group):
            node = id_to_node[nid]
            node["position"] = {"x": x, "y": start_y + i * NODE_SPACING_Y}


def _assign_layers(
    node_ids: list[str],
    successors: dict[str, list[str]],
    predecessors: dict[str, list[str]],
) -> dict[str, int]:
    """Assign each node to a layer using longest-path layering."""
    layers: dict[str, int] = {}
    in_degree = {nid: len(predecessors.get(nid, [])) for nid in node_ids}

    # Start with source nodes (no predecessors)
    queue = deque()
    for nid in node_ids:
        if in_degree[nid] == 0:
            queue.append(nid)
            layers[nid] = 0

    # BFS: each node's layer = max(predecessor layers) + 1
    while queue:
        nid = queue.popleft()
        for succ in successors.get(nid, []):
            new_layer = layers[nid] + 1
            if succ not in layers or new_layer > layers[succ]:
                layers[succ] = new_layer
            in_degree[succ] -= 1
            if in_degree[succ] == 0:
                queue.append(succ)

    # Handle disconnected nodes (no edges)
    next_layer = max(layers.values(), default=-1) + 1
    for nid in node_ids:
        if nid not in layers:
            layers[nid] = next_layer
            next_layer += 1

    return layers
