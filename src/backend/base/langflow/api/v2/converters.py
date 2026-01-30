"""Schema converters for V2 Workflow API.

This module provides conversion functions between the new V2 workflow schemas
and the existing V1 schemas, enabling reuse of existing execution logic while
presenting a new API interface.

Key Functions:
    - parse_flat_inputs: Converts flat input format to tweaks structure
    - run_response_to_workflow_response: Converts V1 RunResponse to V2 WorkflowExecutionResponse
    - create_error_response: Creates standardized error responses
    - create_job_response: Creates background job responses

Internal Helpers:
    - _extract_nested_value: Safely extracts nested values from dict/object structures
    - _extract_text_from_message: Extracts plain text from various message formats
    - _simplify_output_content: Simplifies output content based on type
    - _get_raw_content: Extracts raw content from vertex output data
    - _extract_model_source: Extracts model information from LLM outputs
    - _extract_file_path: Extracts file path from SaveToFile outputs
    - _build_metadata_for_non_output: Builds metadata for non-output terminal nodes
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from lfx.schema.workflow import (
    ComponentOutput,
    ErrorDetail,
    JobStatus,
    WorkflowExecutionRequest,
    WorkflowExecutionResponse,
    WorkflowJobResponse,
)

if TYPE_CHECKING:
    from lfx.graph.graph.base import Graph

    from langflow.api.v1.schemas import RunResponse


def parse_flat_inputs(inputs: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], str | None]:
    """Parse flat inputs structure into tweaks and session_id.

    Format: {"component_id.param": value}
    Example: {"ChatInput-abc.input_value": "hi", "LLM-xyz.temperature": 0.7}

    All parameters (including input_value) are treated as tweaks.
    The graph's topological sort handles execution order automatically.

    Args:
        inputs: The inputs dictionary from WorkflowExecutionRequest

    Returns:
        Tuple of (tweaks_dict, session_id)
        - tweaks_dict: {component_id: {param: value}}
        - session_id: Session ID if provided

    Example:
        >>> inputs = {
        ...     "ChatInput-abc.input_value": "hello",
        ...     "ChatInput-abc.session_id": "session-123",
        ...     "LLM-xyz.temperature": 0.7
        ... }
        >>> tweaks, session_id = parse_flat_inputs(inputs)
        >>> tweaks
        {'ChatInput-abc': {'input_value': 'hello'}, 'LLM-xyz': {'temperature': 0.7}}
        >>> session_id
        'session-123'
    """
    tweaks: dict[str, dict[str, Any]] = {}
    session_id: str | None = None

    for key, value in inputs.items():
        if "." in key:
            # Split component_id.param
            component_id, param_name = key.split(".", 1)

            # Extract session_id if present (use first one found)
            if param_name == "session_id" and not session_id:
                session_id = value
            # Build tweaks for all parameters
            if component_id not in tweaks:
                tweaks[component_id] = {}
            tweaks[component_id][param_name] = value
        # No dot - treat as component-level dict (for backward compatibility)
        elif isinstance(value, dict):
            tweaks[key] = value

    return tweaks, session_id


def _extract_nested_value(data: Any, *keys: str) -> Any:
    """Safely extract nested value from dict-like structure.

    Args:
        data: The data structure to extract from
        *keys: Sequence of keys to traverse

    Returns:
        The extracted value or None if not found

    Example:
        >>> _extract_nested_value({'a': {'b': 'value'}}, 'a', 'b')
        'value'
    """
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        elif hasattr(current, key):
            current = getattr(current, key)
        else:
            return None
        if current is None:
            return None
    return current


def _extract_text_from_message(content: dict) -> str | None:
    """Extract plain text from nested message structures.

    Handles various message formats by trying common paths in order:
    - {'message': {'message': 'text', 'type': 'text'}}
    - {'text': {'message': 'text'}}
    - {'message': {'text': 'text'}}
    - {'message': 'text'}
    - {'text': {'text': 'text'}}
    - {'text': 'text'}

    Args:
        content: The message content dict

    Returns:
        Extracted text string or None
    """
    paths = [
        ("message", "message"),
        ("text", "message"),
        ("message", "text"),
        ("message",),
        ("text", "text"),
        ("text",),
    ]
    for path in paths:
        text = _extract_nested_value(content, *path)
        if isinstance(text, str):
            return text
    return None


def _extract_model_source(raw_content: dict, vertex_id: str, vertex_display_name: str) -> dict | None:
    """Extract model source information from LLM component output.

    Args:
        raw_content: The raw output data
        vertex_id: Vertex ID
        vertex_display_name: Vertex display name

    Returns:
        Source info dict or None
    """
    model_name = _extract_nested_value(raw_content, "model_output", "message", "model_name")
    if model_name:
        return {"id": vertex_id, "display_name": vertex_display_name, "source": model_name}
    return None


def _extract_file_path(raw_content: dict, vertex_type: str) -> str | None:
    """Extract file path from SaveToFile component output.

    Args:
        raw_content: The raw output data
        vertex_type: The vertex type

    Returns:
        File path string or None
    """
    if vertex_type != "SaveToFile":
        return None

    # Extract the message from SaveToFile component
    # Return the whole message instead of filtering by specific wording
    file_msg = _extract_nested_value(raw_content, "message", "message")
    if isinstance(file_msg, str):
        return file_msg

    return None


def _get_raw_content(vertex_output_data: Any) -> Any:
    """Extract raw content from vertex output data.

    Tries multiple fields in order: outputs, results, messages.
    Note: Uses 'is not None' checks to avoid treating empty collections as missing.

    Args:
        vertex_output_data: The output data from RunResponse

    Returns:
        Raw content or None
    """
    if hasattr(vertex_output_data, "outputs") and vertex_output_data.outputs is not None:
        return vertex_output_data.outputs
    if hasattr(vertex_output_data, "results") and vertex_output_data.results is not None:
        return vertex_output_data.results
    if hasattr(vertex_output_data, "messages") and vertex_output_data.messages is not None:
        return vertex_output_data.messages
    if isinstance(vertex_output_data, dict):
        # Check for 'results' first, then 'content' if results is None
        if "results" in vertex_output_data:
            return vertex_output_data["results"]
        if "content" in vertex_output_data:
            return vertex_output_data["content"]
    return vertex_output_data


def _simplify_output_content(content: Any, output_type: str) -> Any:
    """Simplify output content for output nodes.

    For message types, extracts plain text from nested structures.
    For data/dataframe types, extracts the actual data value.
    For other types, returns content as-is.

    Args:
        content: The raw content
        output_type: The output type

    Returns:
        Simplified content
    """
    if not isinstance(content, dict):
        return content

    if output_type in {"message", "text"}:
        text = _extract_text_from_message(content)
        return text if text is not None else content

    if output_type == "data":
        # For data types, try multiple path combinations in order
        # This allows flexibility for different component output structures
        data_paths = [
            ("result", "message"),  # Standard: {'result': {'message': {...}}}
            ("results", "message"),  # Plural variant: {'results': {'message': {...}}}
        ]
        for path in data_paths:
            result_data = _extract_nested_value(content, *path)
            if result_data is not None:
                return result_data
    # TODO: Future scope - Add dataframe-specific extraction logic
    # The following code is commented out pending further requirements analysis:
    if output_type == "dataframe":
        # For dataframe types, try multiple path combinations in order
        dataframe_paths = [
            ("results", "message"),  # Plural: {'results': {'message': {...}}}
            ("result", "message"),  # Singular fallback: {'result': {'message': {...}}}
            ("run_sql_query", "message"),  # SQL component specific
        ]
        for path in dataframe_paths:
            dataframe_data = _extract_nested_value(content, *path)
            if dataframe_data is not None:
                return dataframe_data

    return content


def _build_metadata_for_non_output(
    raw_content: Any, vertex_id: str, vertex_display_name: str, vertex_type: str, output_type: str
) -> dict[str, Any]:
    """Build metadata for non-output terminal nodes.

    Extracts:
    - source: Model information for LLM components
    - file_path: File path for SaveToFile components

    Args:
        raw_content: The raw output data
        vertex_id: Vertex ID
        vertex_display_name: Vertex display name
        vertex_type: Vertex type
        output_type: Output type

    Returns:
        Metadata dict
    """
    metadata: dict[str, Any] = {}

    if output_type != "message" or not isinstance(raw_content, dict):
        return metadata

    # Extract model source for LLM components
    source_info = _extract_model_source(raw_content, vertex_id, vertex_display_name)
    if source_info:
        metadata["source"] = source_info

    # Extract file path for SaveToFile components
    file_path = _extract_file_path(raw_content, vertex_type)
    if file_path:
        metadata["file_path"] = file_path

    return metadata


def _process_terminal_vertex(
    vertex: Any,
    output_data_map: dict[str, Any],
) -> tuple[str, ComponentOutput]:
    """Process a single terminal vertex and return (output_key, component_output).

    Args:
        vertex: The vertex to process
        output_data_map: Map of component_id to output data

    Returns:
        Tuple of (output_key, ComponentOutput)
    """
    # Get output data by vertex.id (component_id)
    vertex_output_data = output_data_map.get(vertex.id)

    # Determine output type from vertex
    output_type = "unknown"
    if vertex.outputs and len(vertex.outputs) > 0:
        types = vertex.outputs[0].get("types", [])
        if types:
            output_type = types[0].lower()
    if output_type == "unknown" and vertex.vertex_type:
        output_type = vertex.vertex_type.lower()

    # Initialize metadata with component_type
    metadata: dict[str, Any] = {"component_type": vertex.vertex_type}

    # Extract content
    content = None
    if vertex_output_data:
        raw_content = _get_raw_content(vertex_output_data)

        if vertex.is_output and raw_content is not None:
            # Output nodes: simplify content
            content = _simplify_output_content(raw_content, output_type)
        elif not vertex.is_output and raw_content is not None:
            # Non-output nodes:
            # - For data types: extract and show content
            # - For message types: extract metadata only (source, file_path)
            # TODO: Future scope - Add support for "dataframe" output type
            if output_type in ["data", "dataframe"]:
                # Show data content for non-output data nodes
                content = _simplify_output_content(raw_content, output_type)
            else:
                # For message types, extract metadata only
                extra_metadata = _build_metadata_for_non_output(
                    raw_content,
                    vertex.id,
                    vertex.display_name or vertex.vertex_type,
                    vertex.vertex_type,
                    output_type,
                )
                metadata.update(extra_metadata)

        # Add any additional metadata from result data
        if hasattr(vertex_output_data, "metadata") and vertex_output_data.metadata:
            metadata.update(vertex_output_data.metadata)
        elif isinstance(vertex_output_data, dict) and "metadata" in vertex_output_data:
            result_metadata = vertex_output_data.get("metadata")
            if isinstance(result_metadata, dict):
                metadata.update(result_metadata)

    # Determine output key: use vertex id but TODO: add alias handling when avialable
    output_key = vertex.id

    # Build ComponentOutput
    component_output = ComponentOutput(
        type=output_type,
        component_id=vertex.id,
        status=JobStatus.COMPLETED,
        content=content,
        metadata=metadata,
    )
    return output_key, component_output


def run_response_to_workflow_response(
    run_response: RunResponse,
    flow_id: str,
    job_id: str,
    workflow_request: WorkflowExecutionRequest,
    graph: Graph,
) -> WorkflowExecutionResponse:
    """Convert V1 RunResponse to V2 WorkflowExecutionResponse.

    This function transforms the V1 execution response to the new V2 schema format.
    It intelligently handles different node types and determines what content to expose.

    Terminal Node Processing Logic:
        1. Identifies all terminal nodes (vertices with no successors)
        2. For each terminal node:
           - Output nodes (is_output=True): Full content is exposed
           - Data/DataFrame nodes: Content is exposed regardless of is_output flag
           - Message nodes (non-output): Only metadata is exposed (source, file_path)

    Output Key Selection:
        - Uses vertex.display_name as the primary key for outputs
        - Falls back to vertex.id if duplicate display_names are detected
        - Stores original display_name in metadata when using id as key

    Args:
        run_response: The V1 response from simple_run_flow containing execution results
        flow_id: The flow identifier
        job_id: The generated job ID for tracking this execution
        workflow_request: Original workflow request (inputs are echoed back in response)
        graph: The Graph instance used for terminal node detection and vertex metadata

    Returns:
        WorkflowExecutionResponse: V2 schema response with structured outputs

    Example:
        Terminal nodes: ["ChatOutput-abc", "LLM-xyz", "DataNode-123"]
        - ChatOutput-abc (is_output=True, type=message): Full content exposed
        - LLM-xyz (is_output=False, type=message): Only metadata (model source)
        - DataNode-123 (is_output=False, type=data): Full content exposed
    """
    # Get terminal nodes (vertices with no successors)
    try:
        terminal_node_ids = graph.get_terminal_nodes()
    except AttributeError:
        # Fallback: manually check successor_map
        terminal_node_ids = [vertex.id for vertex in graph.vertices if not graph.successor_map.get(vertex.id, [])]

    # Build output data map from run_response using component_id as key
    # This ensures unique keys even when components have duplicate display_names
    output_data_map: dict[str, Any] = {}
    if run_response.outputs:
        for run_output in run_response.outputs:
            if hasattr(run_output, "outputs") and run_output.outputs:
                for result_data in run_output.outputs:
                    if not result_data:
                        continue
                    # Use component_id as key to ensure uniqueness
                    component_id = result_data.component_id if hasattr(result_data, "component_id") else None
                    if component_id:
                        output_data_map[component_id] = result_data

    # Collect all terminal vertices
    terminal_vertices = [graph.get_vertex(vertex_id) for vertex_id in terminal_node_ids]

    # Process each terminal vertex
    outputs: dict[str, ComponentOutput] = {}
    for vertex in terminal_vertices:
        output_key, component_output = _process_terminal_vertex(vertex, output_data_map)
        outputs[output_key] = component_output

    return WorkflowExecutionResponse(
        flow_id=flow_id,
        job_id=job_id,
        object="response",
        status=JobStatus.COMPLETED,
        errors=[],
        inputs=workflow_request.inputs or {},
        outputs=outputs,
        metadata={},
    )


def create_job_response(job_id: str, flow_id: str) -> WorkflowJobResponse:
    """Create a background job response.

    Args:
        job_id: The generated job ID
        flow_id: The flow ID

    Returns:
        WorkflowJobResponse for background execution
    """
    return WorkflowJobResponse(
        job_id=job_id,
        flow_id=flow_id,
        created_timestamp=datetime.now(timezone.utc).isoformat(),
        status=JobStatus.QUEUED,
        errors=[],
    )


def create_error_response(
    flow_id: str,
    job_id: str | None,
    workflow_request: WorkflowExecutionRequest,
    error: Exception,
) -> WorkflowExecutionResponse:
    """Create an error response in workflow format.

    Args:
        flow_id: The flow ID
        job_id: The job ID
        workflow_request: Original request
        error: The exception that occurred

    Returns:
        WorkflowExecutionResponse with error details
    """
    error_detail = ErrorDetail(
        error=str(error), code="EXECUTION_ERROR", details={"flow_id": flow_id, "error_type": type(error).__name__}
    )

    return WorkflowExecutionResponse(
        flow_id=flow_id,
        job_id=job_id,
        object="response",
        status=JobStatus.FAILED,
        errors=[error_detail],
        inputs=workflow_request.inputs or {},
        outputs={},
        metadata={},
    )
