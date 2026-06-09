"""Utility functions for loop component execution."""

from collections import deque
from typing import TYPE_CHECKING

from lfx.schema.data import Data

if TYPE_CHECKING:
    from lfx.graph.graph.base import Graph
    from lfx.graph.vertex.base import Vertex


def get_loop_body_vertices(
    vertex: "Vertex",
    graph: "Graph",
    get_incoming_edge_by_target_param_fn,
    loop_output_name: str = "item",
    feedback_input_name: str | None = None,
) -> set[str]:
    """Get all vertex IDs that are part of the loop body.

    Uses BFS to traverse from the loop's output to the vertex
    that feeds back to the loop's input, then includes all
    predecessors of vertices in the loop body.

    Args:
        vertex: The loop component's vertex
        graph: The graph containing the loop
        get_incoming_edge_by_target_param_fn: Function to get incoming edge by target param
        loop_output_name: Name of the output that starts the loop body
            (default: "item" for Loop, use "loop" for WhileLoop)
        feedback_input_name: Name of the input that receives feedback
            (default: same as loop_output_name)

    Returns:
        Set of vertex IDs that form the loop body
    """
    if feedback_input_name is None:
        feedback_input_name = loop_output_name

    # Find where the loop body starts (edges from loop output)
    start_edges = [e for e in vertex.outgoing_edges if e.source_handle.name == loop_output_name]
    if not start_edges:
        return set()

    # Find where it ends (vertex feeding back to loop input)
    end_vertex_id = get_incoming_edge_by_target_param_fn(feedback_input_name)
    if not end_vertex_id:
        return set()

    # BFS from start vertices, collecting all vertices until end_vertex
    loop_body = set()
    queue = deque([e.target_id for e in start_edges])
    visited = set()

    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        loop_body.add(current)

        # Don't traverse beyond the end vertex
        if current == end_vertex_id:
            continue

        # Add successors
        for successor_id in graph.successor_map.get(current, []):
            if successor_id not in visited:
                queue.append(successor_id)

    # Now recursively include all predecessors of vertices in the loop body
    # This ensures we include all dependencies like LLM models
    # We need to find predecessors by looking at successor_map in reverse
    def add_all_predecessors(vertex_id: str, visited_predecessors: set[str]) -> None:
        """Recursively add all predecessors of a vertex."""
        # Find predecessors by checking which vertices have this vertex as a successor
        for potential_pred_id, successors in graph.successor_map.items():
            if (
                vertex_id in successors
                and potential_pred_id != vertex.id
                and potential_pred_id not in visited_predecessors
            ):
                visited_predecessors.add(potential_pred_id)
                loop_body.add(potential_pred_id)
                # Recursively add predecessors of this predecessor
                add_all_predecessors(potential_pred_id, visited_predecessors)

    # Track visited predecessors to avoid infinite loops
    visited_predecessors: set[str] = set()

    # Add all predecessors for each vertex in the loop body
    for body_vertex_id in list(loop_body):  # Use list() to avoid modifying set during iteration
        add_all_predecessors(body_vertex_id, visited_predecessors)

    return loop_body


def get_loop_body_start_vertex(vertex: "Vertex", loop_output_name: str = "item") -> str | None:
    """Get the first vertex in the loop body (connected to loop's output).

    Args:
        vertex: The loop component's vertex
        loop_output_name: Name of the output that starts the loop body
            (default: "item" for Loop, use "loop" for WhileLoop)

    Returns:
        The vertex ID of the first vertex in the loop body, or None if not found
    """
    start_edges = [e for e in vertex.outgoing_edges if e.source_handle.name == loop_output_name]
    if start_edges:
        return start_edges[0].target_id
    return None


def get_loop_body_start_edge(vertex: "Vertex", loop_output_name: str = "item"):
    """Get the edge connecting loop's output to the first vertex in loop body.

    Args:
        vertex: The loop component's vertex
        loop_output_name: Name of the output that starts the loop body
            (default: "item" for Loop, use "loop" for WhileLoop)

    Returns:
        The edge object, or None if not found
    """
    start_edges = [e for e in vertex.outgoing_edges if e.source_handle.name == loop_output_name]
    if start_edges:
        return start_edges[0]
    return None


def extract_loop_output(results: list, end_vertex_id: str | None) -> Data:
    """Extract the output from subgraph execution results.

    Args:
        results: List of VertexBuildResult objects from subgraph execution
        end_vertex_id: The vertex ID that feeds back to the item input (end of loop body)

    Returns:
        Data object containing the loop iteration output
    """
    if not results:
        return Data(text="")

    if not end_vertex_id:
        return Data(text="")

    # Find the result for the end vertex
    for result in results:
        if hasattr(result, "vertex") and result.vertex.id == end_vertex_id and hasattr(result, "result_dict"):
            result_dict = result.result_dict
            if result_dict.outputs:
                # Get first output value
                first_output = next(iter(result_dict.outputs.values()))
                # Handle both dict (from model_dump()) and object formats
                message = None
                if isinstance(first_output, dict) and "message" in first_output:
                    message = first_output["message"]
                elif hasattr(first_output, "message"):
                    message = first_output.message

                if message is not None:
                    # If message is a dict, wrap it in a Data object
                    if isinstance(message, dict):
                        return Data(data=message)
                    # If it's already a Data object, return it directly
                    if isinstance(message, Data):
                        return message
                    # For other types, wrap in Data with text
                    return Data(text=str(message))

    return Data(text="")


def validate_data_input(data) -> list[Data]:
    """Validate and normalize data input to a list of Data objects.

    Args:
        data: Input data (DataFrame, Data, or list of Data)

    Returns:
        List of Data objects

    Raises:
        TypeError: If data is not a valid type
    """
    from lfx.schema.dataframe import DataFrame

    if isinstance(data, DataFrame):
        return data.to_data_list()
    if isinstance(data, Data):
        return [data]
    if isinstance(data, list) and all(isinstance(item, Data) for item in data):
        return data
    msg = f"Data input must be a DataFrame, Data object, or list of Data objects, got {type(data)}"
    raise TypeError(msg)


async def execute_loop_body(
    graph: "Graph",
    data_list: list[Data],
    loop_body_vertex_ids: set[str],
    start_vertex_id: str | None,
    start_edge,
    end_vertex_id: str | None,
    event_manager=None,
) -> list[Data]:
    """Execute loop body for each data item.

    Creates an isolated subgraph for the loop body and executes it
    for each item in the data list, collecting results.

    Args:
        graph: The graph containing the loop
        data_list: List of Data objects to iterate over
        loop_body_vertex_ids: Set of vertex IDs that form the loop body
        start_vertex_id: The vertex ID of the first vertex in the loop body
        start_edge: The edge connecting loop's item output to start vertex (contains target param info)
        end_vertex_id: The vertex ID that feeds back to the loop's item input
        event_manager: Optional event manager to pass to subgraph execution for UI events

    Returns:
        List of Data objects containing results from each iteration
    """
    if not loop_body_vertex_ids:
        return []

    aggregated_results = []

    for item in data_list:
        # Create fresh subgraph for each iteration. This gives clean vertex/edge state
        # while sharing context between iterations (intentional for loop state).
        # Using async context manager ensures proper cleanup of trace tasks on exit.
        async with graph.create_subgraph(loop_body_vertex_ids) as iteration_subgraph:
            # Inject current item into vertex data BEFORE preparing the subgraph.
            # This ensures components have data during build/validation.
            if start_vertex_id and start_edge:
                # Get the target parameter name from the edge
                if not hasattr(start_edge.target_handle, "field_name"):
                    msg = f"Edge target_handle missing field_name attribute for loop item injection: {start_edge}"
                    raise ValueError(msg)
                target_param = start_edge.target_handle.field_name

                # Find and update the start vertex's frontend data before components are built
                for vertex_data in iteration_subgraph._vertices:  # noqa: SLF001
                    if vertex_data.get("id") == start_vertex_id:
                        # Inject the loop item into the vertex's template data
                        if "data" in vertex_data and "node" in vertex_data["data"]:
                            template = vertex_data["data"]["node"].get("template", {})
                            if target_param in template:
                                template[target_param]["value"] = item
                        break

            # Prepare the subgraph - components will be built with the injected data
            iteration_subgraph.prepare()

            # CRITICAL: Also set the value in the vertex's raw_params
            # Fields with type="other" (like HandleInput) are skipped during field param processing
            # They normally get values from edges, but we filtered out the Loop->Parser edge
            # So we must inject the value directly into raw_params
            if start_vertex_id and start_edge:
                start_vertex = iteration_subgraph.get_vertex(start_vertex_id)
                start_vertex.update_raw_params({target_param: item}, overwrite=True)

            # Execute subgraph and collect results
            # Pass event_manager so UI receives events from subgraph execution
            results = []
            async for result in iteration_subgraph.async_start(event_manager=event_manager):
                results.append(result)
                # Stop all on error (as per design decision)
                if hasattr(result, "valid") and not result.valid:
                    msg = f"Error in loop iteration: {result}"
                    raise RuntimeError(msg)

            # Extract output from final result
            output = extract_loop_output(results, end_vertex_id)
            aggregated_results.append(output)

    return aggregated_results
