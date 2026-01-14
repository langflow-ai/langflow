"""Schema converters for V2 Workflow API.

This module provides conversion functions between the new V2 workflow schemas
and the existing V1 schemas, enabling reuse of existing execution logic while
presenting a new API interface.
"""

from __future__ import annotations

import time
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
            if param_name == "session_id":
                if session_id is None:
                    session_id = value
            else:
                # Build tweaks for all parameters except session_id
                if component_id not in tweaks:
                    tweaks[component_id] = {}
                tweaks[component_id][param_name] = value
        # No dot - treat as component-level dict (for backward compatibility)
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

    Handles various message formats:
    - {'message': {'message': 'text', 'type': 'text'}}
    - {'message': 'text'}
    - {'text': 'text'}

    Args:
        content: The message content dict

    Returns:
        Extracted text string or None
    """
    # Try message.message (nested structure)
    message = content.get("message")
    if isinstance(message, dict):
        text = message.get("message")
        if isinstance(text, str):
            return text
        text = message.get("text")
        if isinstance(text, str):
            return text
    elif isinstance(message, str):
        return message

    # Try text.text for rare structure
    text_val = content.get("text")
    if isinstance(text_val, dict):
        text = text_val.get("text")
        if isinstance(text, str):
            return text
    elif isinstance(text_val, str):
        return text_val

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

    file_msg = _extract_nested_value(raw_content, "message", "message")
    if isinstance(file_msg, str) and "saved successfully" in file_msg.lower():
        return file_msg

    return None


def _get_raw_content(vertex_output_data: Any) -> Any:
    """Extract raw content from vertex output data.

    Tries multiple fields in order: outputs, results, messages.

    Args:
        vertex_output_data: The output data from RunResponse

    Returns:
        Raw content or None
    """
    outputs = getattr(vertex_output_data, "outputs", None)
    if outputs:
        return outputs
    results = getattr(vertex_output_data, "results", None)
    if results:
        return results
    messages = getattr(vertex_output_data, "messages", None)
    if messages:
        return messages
    if isinstance(vertex_output_data, dict):
        return vertex_output_data.get("results") or vertex_output_data.get("content")
    return vertex_output_data


def _simplify_output_content(content: Any, output_type: str) -> Any:
    """Simplify output content for output nodes.

    For message types, extracts plain text from nested structures.
    For data types, extracts the actual data value.
    For other types, returns content as-is.

    Args:
        content: The raw content
        output_type: The output type

    Returns:
        Simplified content
    """
    if not isinstance(content, dict):
        return content

    if output_type == "message":
        text = _extract_text_from_message(content)
        return text if text is not None else content

    if output_type == "data":
        # For data types, extract from result.message structure
        # Example: {'result': {'message': {'result': '4'}, 'type': 'object'}}
        # Content is already confirmed to be a dict, so directly access nested dicts.
        result = content.get("result")
        if isinstance(result, dict):
            message_val = result.get("message")
            if message_val is not None:
                return message_val

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
    if output_type != "message" or not isinstance(raw_content, dict):
        return {}

    metadata = {}

    # Extract model source for LLM components
    model_output = raw_content.get("model_output")
    if isinstance(model_output, dict):
        message = model_output.get("message")
        if isinstance(message, dict):
            model_name = message.get("model_name")
            if model_name:
                metadata["source"] = {"id": vertex_id, "display_name": vertex_display_name, "source": model_name}

    # Extract file path for SaveToFile components
    if vertex_type == "SaveToFile":
        message_dict = raw_content.get("message")
        if isinstance(message_dict, dict):
            file_msg = message_dict.get("message")
            if isinstance(file_msg, str) and "saved successfully" in file_msg.lower():
                metadata["file_path"] = file_msg

    return metadata


def run_response_to_workflow_response(
    run_response: RunResponse,
    flow_id: str,
    job_id: str,
    workflow_request: WorkflowExecutionRequest,
    graph: Graph,
) -> WorkflowExecutionResponse:
    """Convert RunResponse to WorkflowExecutionResponse.

    This function transforms the V1 response to the new V2 schema with the following logic:
    - All terminal nodes (vertices with no successors) are included in outputs
    - Only vertices with is_output=True get actual content populated
    - Other terminal nodes get content=null with metadata
    - Uses vertex.display_name as the output key (component alias)

    Args:
        run_response: The response from simple_run_flow
        flow_id: The flow ID
        job_id: The generated job ID for tracking
        workflow_request: Original workflow request for input echo
        graph: The Graph instance for terminal node detection

    Returns:
        WorkflowExecutionResponse with new V2 schema

    Example:
        Terminal nodes: ["ChatOutput-abc", "SQLNode-xyz"]
        - ChatOutput-abc: is_output=True → gets content
        - SQLNode-xyz: is_output=False → gets content=null with metadata
    """
    # Get terminal nodes (vertices with no successors)
    get_term = getattr(graph, "get_terminal_nodes", None)
    if callable(get_term):
        terminal_node_ids = get_term()
    else:
        # Fallback: manually check successor_map
        # Fallback: manually check successor_map
        terminal_node_ids = [vertex.id for vertex in graph.vertices if not graph.successor_map.get(vertex.id, [])]

    # Build output data map from run_response using component_id as key
    # This ensures unique keys even when components have duplicate display_names
    output_data_map: dict[str, Any] = {}
    if run_response.outputs:
        for run_output in run_response.outputs:
            outputs_attr = getattr(run_output, "outputs", None)
            if outputs_attr:
                for result_data in outputs_attr:
                    if not result_data:
                        continue
                    component_id = getattr(result_data, "component_id", None)
                    if component_id:
                        output_data_map[component_id] = result_data

    # First pass: collect all terminal vertices and check for duplicate display_names
    terminal_set = set(terminal_node_ids)
    terminal_vertices = [v for v in graph.vertices if v.id in terminal_set]
    display_name_counts: dict[str, int] = {}
    for vertex in terminal_vertices:
        display_name = vertex.display_name or vertex.id
        display_name_counts[display_name] = display_name_counts.get(display_name, 0) + 1

    # Process each terminal vertex
    outputs: dict[str, ComponentOutput] = {}
    for vertex in terminal_vertices:
        # Get output data by vertex.id (component_id)
        vertex_output_data = output_data_map.get(vertex.id)

        # Determine output type from vertex
        output_type = "unknown"
        if vertex.outputs and len(vertex.outputs) > 0:
            first_output = vertex.outputs[0]
            types = first_output.get("types", []) if isinstance(first_output, dict) else []
            if types:
                output_type = types[0].lower()
        if output_type == "unknown" and vertex.vertex_type:
            output_type = vertex.vertex_type.lower()

        # Initialize metadata with component_type
        metadata = {"component_type": vertex.vertex_type}

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
                if output_type == "data":
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
            result_meta = getattr(vertex_output_data, "metadata", None)
            if isinstance(result_meta, dict) and result_meta:
                metadata.update(result_meta)
            elif isinstance(vertex_output_data, dict) and "metadata" in vertex_output_data:
                result_metadata = vertex_output_data.get("metadata")
                if isinstance(result_metadata, dict):
                    metadata.update(result_metadata)

        # Build ComponentOutput
        component_output = ComponentOutput(
            type=output_type,
            component_id=vertex.id,
            status=JobStatus.COMPLETED,
            content=content,
            metadata=metadata,
        )

        # Determine output key: use display_name if unique, otherwise use id
        display_name = vertex.display_name or vertex.id
        if display_name_counts.get(display_name, 0) > 1:
            # Duplicate display_name detected, use id instead
            output_key = vertex.id
            # Store the display_name in metadata for reference
            if vertex.display_name and vertex.display_name != vertex.id:
                metadata["display_name"] = vertex.display_name
        else:
            # Unique display_name, use it as key
            output_key = display_name

        outputs[output_key] = component_output

    return WorkflowExecutionResponse(
        flow_id=flow_id,
        job_id=job_id,
        object="response",
        created_timestamp=str(int(time.time())),
        status=JobStatus.COMPLETED,
        errors=[],
        inputs=workflow_request.inputs or {},
        outputs=outputs,
        metadata={},
    )


def create_job_response(job_id: str) -> WorkflowJobResponse:
    """Create a background job response.

    Args:
        job_id: The generated job ID

    Returns:
        WorkflowJobResponse for background execution
    """
    return WorkflowJobResponse(
        job_id=job_id,
        created_timestamp=str(int(time.time())),
        status=JobStatus.QUEUED,
        errors=[],
    )


def create_error_response(
    flow_id: str,
    job_id: str,
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
        created_timestamp=str(int(time.time())),
        status=JobStatus.FAILED,
        errors=[error_detail],
        inputs=workflow_request.inputs or {},
        outputs={},
        metadata={},
    )
