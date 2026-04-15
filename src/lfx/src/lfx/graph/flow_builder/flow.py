"""Flow creation and inspection.

Pure functions for creating flow dicts and extracting summaries.
"""

from __future__ import annotations


def empty_flow(name: str = "Untitled Flow", description: str = "") -> dict:
    """Create a minimal valid Langflow flow structure."""
    return {
        "name": name,
        "description": description,
        "data": {
            "nodes": [],
            "edges": [],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
        },
    }


def flow_info(flow: dict) -> dict:
    """Extract summary information from a flow dict."""
    data = flow.get("data", {})
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    inputs = []
    outputs = []
    components = []
    for node in nodes:
        node_data = node.get("data", {})
        node_config = node_data.get("node", {})
        display_name = node_config.get("display_name", node_data.get("type", "Unknown"))
        node_type = node_data.get("type", "")
        component_id = node_data.get("id", node.get("id", ""))

        components.append(
            {
                "id": component_id,
                "display_name": display_name,
                "type": node_type,
            }
        )

        if "ChatInput" in node_type or "TextInput" in node_type:
            inputs.append(component_id)
        if "ChatOutput" in node_type or "TextOutput" in node_type:
            outputs.append(component_id)

    return {
        "name": flow.get("name", "Unknown"),
        "description": flow.get("description", ""),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "components": components,
        "inputs": inputs,
        "outputs": outputs,
    }


def flow_to_spec_summary(flow: dict) -> str:
    """Convert a flow dict to a compact summary with component IDs for LLM context.

    Includes full component IDs so the agent can reference them in tool calls.
    Field values are NOT included -- the agent should use get_field_value to inspect.
    """
    data = flow.get("data", {})
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    if not nodes:
        return "(empty canvas)"

    id_to_type: dict[str, str] = {}
    lines = [f"name: {flow.get('name', 'Untitled')}"]

    lines.append("\ncomponents:")
    for node in nodes:
        nd = node.get("data", {})
        nid = nd.get("id", node.get("id", ""))
        ntype = nd.get("type", "?")
        id_to_type[nid] = ntype
        lines.append(f"  {nid}: {ntype}")

    if edges:
        lines.append("\nconnections:")
        for edge in edges:
            src = edge.get("source", "")
            tgt = edge.get("target", "")
            edge_data = edge.get("data", {})
            src_handle = edge_data.get("sourceHandle", {}).get("name", "?")
            tgt_handle = edge_data.get("targetHandle", {}).get("fieldName", "?")
            lines.append(f"  {src}.{src_handle} -> {tgt}.{tgt_handle}")

    return "\n".join(lines)


def flow_graph_repr(flow: dict) -> str:
    """Build an ASCII DAG representation of a flow's graph.

    Uses lfx's ASCII graph renderer (grandalf-based Sugiyama layout),
    falling back to a simple chain representation if unavailable.
    """
    data = flow.get("data", {})
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    if not nodes:
        return "(empty)"

    # Build id -> label map, disambiguating duplicate types
    id_to_label: dict[str, str] = {}
    type_count: dict[str, int] = {}
    for node in nodes:
        nd = node.get("data", {})
        nid = nd.get("id", node.get("id", ""))
        node_type = nd.get("type", "?")
        count = type_count.get(node_type, 0) + 1
        type_count[node_type] = count
        id_to_label[nid] = f"{node_type} #{count}" if count > 1 else node_type

    # Go back and suffix the first occurrence too when there are duplicates
    for nid, label in id_to_label.items():
        if "#" not in label and type_count.get(label, 0) > 1:
            id_to_label[nid] = f"{label} #1"

    if not edges:
        return ", ".join(sorted(id_to_label.values()))

    vertexes = list(id_to_label.values())
    edge_pairs = []
    for edge in edges:
        src_label = id_to_label.get(edge.get("source", ""))
        tgt_label = id_to_label.get(edge.get("target", ""))
        if src_label and tgt_label:
            edge_pairs.append((src_label, tgt_label))

    try:
        from lfx.graph.graph.ascii import draw_graph

        return draw_graph(vertexes, edge_pairs, return_ascii=True) or "(empty)"
    except ImportError:
        # grandalf not available; fall back to simple representation
        return ", ".join(f"{s} -> {t}" for s, t in edge_pairs)
