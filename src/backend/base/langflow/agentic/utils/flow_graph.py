"""Flow graph visualization utilities for Langflow."""

from typing import TYPE_CHECKING, Any
from uuid import UUID

from lfx.graph.graph.ascii import draw_graph
from lfx.graph.graph.base import Graph
from lfx.log.logger import logger

from langflow.helpers.flow import get_flow_by_id_or_endpoint_name

if TYPE_CHECKING:
    from langflow.services.database.models.flow.model import FlowRead


async def get_flow_graph_representations(
    flow_id_or_name: str,
    user_id: str | UUID | None = None,
) -> dict[str, Any]:
    """Get both ASCII and text representations of a flow graph.

    Args:
        flow_id_or_name: Flow ID (UUID) or endpoint name.
        user_id: Optional user ID to filter flows.

    Returns:
        Dictionary containing:
        - flow_id: The flow ID
        - flow_name: The flow name
        - ascii_graph: ASCII art representation of the graph
        - text_repr: Text representation with vertices and edges
        - vertex_count: Number of vertices in the graph
        - edge_count: Number of edges in the graph
        - error: Error message if any (only if operation fails)

    Example:
        >>> result = await get_flow_graph_representations("my-flow-id")
        >>> print(result["ascii_graph"])
        >>> print(result["text_repr"])
    """
    try:
        # Get the flow
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

        # Create graph from flow data
        flow_id_str = str(flow.id)
        graph = Graph.from_payload(
            flow.data,
            flow_id=flow_id_str,
            flow_name=flow.name,
        )

        # Get text representation using __repr__
        text_repr = repr(graph)

        # Get ASCII representation using draw_graph
        # Extract vertex and edge data for ASCII drawing
        vertices = [vertex.id for vertex in graph.vertices]
        edges = [(edge.source_id, edge.target_id) for edge in graph.edges]

        ascii_graph = None
        if vertices and edges:
            try:
                ascii_graph = draw_graph(vertices, edges, return_ascii=True)
            except Exception as e:  # noqa: BLE001
                await logger.awarning(f"Failed to generate ASCII graph: {e}")
                ascii_graph = "ASCII graph generation failed (graph may be too complex or have cycles)"

        return {
            "flow_id": flow_id_str,
            "flow_name": flow.name,
            "ascii_graph": ascii_graph,
            "text_repr": text_repr,
            "vertex_count": len(graph.vertices),
            "edge_count": len(graph.edges),
            "tags": flow.tags,
            "description": flow.description,
        }

    except Exception as e:  # noqa: BLE001
        await logger.aerror(f"Error getting flow graph representations for {flow_id_or_name}: {e}")
        return {
            "error": str(e),
            "flow_id": flow_id_or_name,
        }

    finally:
        await logger.ainfo("Getting flow graph representations completed")


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
    return result.get("ascii_graph") or "No ASCII graph available"


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
        graph = Graph.from_payload(flow.data, flow_id=flow_id_str, flow_name=flow.name)

        return {
            "flow_id": flow_id_str,
            "flow_name": flow.name,
            "vertex_count": len(graph.vertices),
            "edge_count": len(graph.edges),
            "vertices": [vertex.id for vertex in graph.vertices],
            "edges": [(edge.source_id, edge.target_id) for edge in graph.edges],
            "tags": flow.tags,
            "description": flow.description,
        }

    except Exception as e:  # noqa: BLE001
        await logger.aerror(f"Error getting flow graph summary for {flow_id_or_name}: {e}")
        return {"error": str(e)}
