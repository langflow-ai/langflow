"""Flow graph visualization utilities for Langflow."""

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from langflow.helpers.flow import get_flow_by_id_or_endpoint_name

if TYPE_CHECKING:
    from langflow.services.database.models.flow.model import FlowRead

logger = logging.getLogger(__name__)


def _build_text_repr_from_raw(flow_data: dict[str, Any], flow_name: str) -> tuple[str, int, int]:
    """Build a text representation directly from raw flow data, bypassing Graph.from_payload().

    This avoids failures caused by encoded edge handles (œ-encoding) in flows produced
    by expand_compact_flow(), which Graph.from_payload() cannot parse.

    Returns:
        (text_repr, vertex_count, edge_count)
    """
    nodes: list[dict[str, Any]] = flow_data.get("nodes", [])
    edges: list[dict[str, Any]] = flow_data.get("edges", [])

    # Build node ID → display name map
    node_map: dict[str, str] = {}
    for node in nodes:
        node_id = node.get("id", "")
        data = node.get("data", {})
        # Prefer display name, fall back to component type
        node_type = data.get("type", "Unknown")
        display_name = data.get("node", {}).get("display_name", node_type)
        node_map[node_id] = display_name

    # Build lines
    lines = [f"Flow: {flow_name}"]
    lines.append(f"Nodes ({len(nodes)}):")
    for node in nodes:
        node_id = node.get("id", "")
        lines.append(f"  - {node_map.get(node_id, node_id)}")

    if edges:
        lines.append(f"Connections ({len(edges)}):")
        for edge in edges:
            src_id = edge.get("source", "")
            tgt_id = edge.get("target", "")
            # Use the unencoded data dict if present (set by expand_compact_flow)
            edge_data = edge.get("data", {})
            src_handle = edge_data.get("sourceHandle", {})
            tgt_handle = edge_data.get("targetHandle", {})
            src_port = src_handle.get("name", "") if isinstance(src_handle, dict) else ""
            tgt_port = tgt_handle.get("fieldName", "") if isinstance(tgt_handle, dict) else ""
            src_label = node_map.get(src_id, src_id)
            tgt_label = node_map.get(tgt_id, tgt_id)
            if src_port and tgt_port:
                lines.append(f"  {src_label}.{src_port} → {tgt_label}.{tgt_port}")
            else:
                lines.append(f"  {src_label} → {tgt_label}")

    return "\n".join(lines), len(nodes), len(edges)


async def get_flow_graph_representations(
    flow_id_or_name: str,
    user_id: str | UUID | None = None,
) -> dict[str, Any]:
    """Get text representation of a flow for context injection.

    Parses raw flow data directly instead of using Graph.from_payload() to avoid
    failures on flows with encoded edge handles (produced by expand_compact_flow).

    Args:
        flow_id_or_name: Flow ID (UUID) or endpoint name.
        user_id: Optional user ID to filter flows.

    Returns:
        Dictionary containing:
        - flow_id: The flow ID
        - flow_name: The flow name
        - text_repr: Text representation with vertices and edges
        - vertex_count: Number of vertices in the graph
        - edge_count: Number of edges in the graph
        - error: Error message if any (only if operation fails)
    """
    try:
        flow: FlowRead | None = await get_flow_by_id_or_endpoint_name(flow_id_or_name, user_id)

        if flow is None:
            return {
                "error": f"Flow {flow_id_or_name} not found",
                "flow_id": flow_id_or_name,
            }

        if flow.data is None:
            return {
                "error": f"Flow {flow_id_or_name} has no data",
                "flow_id": str(flow.id),
                "flow_name": flow.name,
            }

        flow_id_str = str(flow.id)
        text_repr, vertex_count, edge_count = _build_text_repr_from_raw(flow.data, flow.name or flow_id_str)

    except Exception as e:  # noqa: BLE001
        logger.warning("Could not read flow graph for context injection (%s): %s", flow_id_or_name, e)
        return {
            "error": str(e),
            "flow_id": flow_id_or_name,
        }
    else:
        return {
            "flow_id": flow_id_str,
            "flow_name": flow.name,
            "text_repr": text_repr,
            "vertex_count": vertex_count,
            "edge_count": edge_count,
            "tags": flow.tags,
            "description": flow.description,
        }


async def get_flow_ascii_graph(
    flow_id_or_name: str,
    user_id: str | UUID | None = None,
) -> str:
    """Get ASCII art representation of a flow graph.

    Args:
        flow_id_or_name: Flow ID (UUID) or endpoint name.
        user_id: Optional user ID to filter flows.

    Returns:
        ASCII art string representation of the graph, or error message.

    Example:
        >>> ascii_art = await get_flow_ascii_graph("my-flow-id")
        >>> print(ascii_art)
    """
    result = await get_flow_graph_representations(flow_id_or_name, user_id)
    if "error" in result:
        return f"Error: {result['error']}"
    return result.get("text_repr") or "No graph available"


async def get_flow_text_repr(
    flow_id_or_name: str,
    user_id: str | UUID | None = None,
) -> str:
    """Get text representation of a flow graph showing vertices and edges.

    Args:
        flow_id_or_name: Flow ID (UUID) or endpoint name.
        user_id: Optional user ID to filter flows.

    Returns:
        Text representation string with vertices and edges, or error message.

    Example:
        >>> text_repr = await get_flow_text_repr("my-flow-id")
        >>> print(text_repr)
    """
    result = await get_flow_graph_representations(flow_id_or_name, user_id)
    if "error" in result:
        return f"Error: {result['error']}"
    return result.get("text_repr") or "No text representation available"


async def get_flow_graph_summary(
    flow_id_or_name: str,
    user_id: str | UUID | None = None,
) -> dict[str, Any]:
    """Get a summary of flow graph metadata without full representations.

    Args:
        flow_id_or_name: Flow ID (UUID) or endpoint name.
        user_id: Optional user ID to filter flows.

    Returns:
        Dictionary with flow metadata:
        - flow_id: The flow ID
        - flow_name: The flow name
        - vertex_count: Number of vertices
        - edge_count: Number of edges
        - vertices: List of vertex IDs
        - edges: List of edge tuples (source_id, target_id)

    Example:
        >>> summary = await get_flow_graph_summary("my-flow-id")
        >>> print(f"Flow has {summary['vertex_count']} vertices")
    """
    try:
        flow: FlowRead | None = await get_flow_by_id_or_endpoint_name(flow_id_or_name, user_id)

        if flow is None:
            return {"error": f"Flow {flow_id_or_name} not found"}

        if flow.data is None:
            return {
                "error": f"Flow {flow_id_or_name} has no data",
                "flow_id": str(flow.id),
                "flow_name": flow.name,
            }

        flow_id_str = str(flow.id)
        _, vertex_count, edge_count = _build_text_repr_from_raw(flow.data, flow.name or flow_id_str)
        nodes: list[dict[str, Any]] = flow.data.get("nodes", [])
        edges_raw: list[dict[str, Any]] = flow.data.get("edges", [])

        return {
            "flow_id": flow_id_str,
            "flow_name": flow.name,
            "vertex_count": vertex_count,
            "edge_count": edge_count,
            "vertices": [n.get("id", "") for n in nodes],
            "edges": [(e.get("source", ""), e.get("target", "")) for e in edges_raw],
            "tags": flow.tags,
            "description": flow.description,
        }

    except Exception as e:
        logger.exception("Error getting flow graph summary for %s", flow_id_or_name)
        return {"error": str(e)}
