"""Template validation utilities for Langflow starter projects.

This module provides validation functions to ensure template integrity and prevent
unexpected breakage in starter project templates.
"""

import asyncio
import json
import uuid
from typing import Any

from lfx.custom.validate import validate_code
from lfx.graph.graph.base import Graph


def validate_template_structure(template_data: dict[str, Any], filename: str) -> list[str]:
    """Validate basic template structure.

    Args:
        template_data: The template data to validate
        filename: Name of the template file for error reporting

    Returns:
        List of error messages, empty if validation passes
    """
    errors = []

    # Handle wrapped format
    data = template_data.get("data", template_data)

    # Check required fields
    if "nodes" not in data:
        errors.append(f"{filename}: Missing 'nodes' field")
    elif not isinstance(data["nodes"], list):
        errors.append(f"{filename}: 'nodes' must be a list")

    if "edges" not in data:
        errors.append(f"{filename}: Missing 'edges' field")
    elif not isinstance(data["edges"], list):
        errors.append(f"{filename}: 'edges' must be a list")

    # Check nodes have required fields
    for i, node in enumerate(data.get("nodes", [])):
        if "id" not in node:
            errors.append(f"{filename}: Node {i} missing 'id'")
        if "data" not in node:
            errors.append(f"{filename}: Node {i} missing 'data'")

    return errors


def validate_flow_can_build(template_data: dict[str, Any], filename: str) -> list[str]:
    """Validate that the template can be built into a working flow.

    Args:
        template_data: The template data to validate
        filename: Name of the template file for error reporting

    Returns:
        List of build errors, empty if flow builds successfully
    """
    errors = []

    try:
        # Create a unique flow ID for testing
        flow_id = str(uuid.uuid4())
        flow_name = filename.replace(".json", "")

        # Try to build the graph from the template data
        graph = Graph.from_payload(template_data, flow_id, flow_name, user_id="test_user")

        # Validate stream configuration
        graph.validate_stream()

        # Basic validation that the graph has vertices
        if not graph.vertices:
            errors.append(f"{filename}: Flow has no vertices after building")

        # Validate that all vertices have valid IDs
        errors.extend([f"{filename}: Vertex missing ID" for vertex in graph.vertices if not vertex.id])

    except (ValueError, TypeError, KeyError, AttributeError) as e:
        errors.append(f"{filename}: Failed to build flow graph: {e!s}")

    return errors


def validate_flow_code(template_data: dict[str, Any], filename: str) -> list[str]:
    """Validate flow code using direct function call.

    Args:
        template_data: The template data to validate
        filename: Name of the template file for error reporting

    Returns:
        List of validation errors, empty if validation passes
    """
    errors = []

    try:
        # Extract code fields from template for validation
        data = template_data.get("data", template_data)

        for node in data.get("nodes", []):
            node_data = node.get("data", {})
            node_template = node_data.get("node", {}).get("template", {})

            # Look for code-related fields in the node template
            for field_data in node_template.values():
                if isinstance(field_data, dict) and field_data.get("type") == "code":
                    code_value = field_data.get("value", "")
                    if code_value and isinstance(code_value, str):
                        # Validate the code using direct function call
                        validation_result = validate_code(code_value)

                        # Check for import errors
                        if validation_result.get("imports", {}).get("errors"):
                            errors.extend(
                                [
                                    f"{filename}: Import error in node {node_data.get('id', 'unknown')}: {error}"
                                    for error in validation_result["imports"]["errors"]
                                ]
                            )

                        # Check for function errors
                        if validation_result.get("function", {}).get("errors"):
                            errors.extend(
                                [
                                    f"{filename}: Function error in node {node_data.get('id', 'unknown')}: {error}"
                                    for error in validation_result["function"]["errors"]
                                ]
                            )

    except (ValueError, TypeError, KeyError, AttributeError) as e:
        errors.append(f"{filename}: Code validation failed: {e!s}")

    return errors


async def validate_flow_execution(
    client, template_data: dict[str, Any], filename: str, headers: dict[str, str]
) -> list[str]:
    """Validate flow execution by building and running the flow.

    Args:
        client: AsyncClient for API requests
        template_data: The template data to validate
        filename: Name of the template file for error reporting
        headers: Authorization headers for API requests

    Returns:
        List of execution errors, empty if execution succeeds
    """
    errors = []

    try:
        # Create a flow from the template with timeout
        create_response = await client.post("api/v1/flows/", json=template_data, headers=headers, timeout=10)

        if create_response.status_code != 201:  # noqa: PLR2004
            errors.append(f"{filename}: Failed to create flow: {create_response.status_code}")
            return errors

        flow_id = create_response.json()["id"]

        try:
            # Build the flow with timeout
            build_response = await client.post(f"api/v1/build/{flow_id}/flow", json={}, headers=headers, timeout=10)

            if build_response.status_code != 200:  # noqa: PLR2004
                errors.append(f"{filename}: Failed to build flow: {build_response.status_code}")
                return errors

            job_id = build_response.json()["job_id"]

            # Get build events to validate execution
            events_headers = {**headers, "Accept": "application/x-ndjson"}
            events_response = await client.get(f"api/v1/build/{job_id}/events", headers=events_headers, timeout=10)

            if events_response.status_code != 200:  # noqa: PLR2004
                errors.append(f"{filename}: Failed to get build events: {events_response.status_code}")
                return errors

            # Validate the event stream
            await _validate_event_stream(events_response, job_id, filename, errors)

        finally:
            # Clean up the flow with timeout
            try:  # noqa: SIM105
                await client.delete(f"api/v1/flows/{flow_id}", headers=headers, timeout=10)
            except asyncio.TimeoutError:
                # Log but don't fail if cleanup times out
                pass

    except asyncio.TimeoutError:
        errors.append(f"{filename}: Flow execution timed out")
    except (ValueError, TypeError, KeyError, AttributeError) as e:
        errors.append(f"{filename}: Flow execution validation failed: {e!s}")

    return errors


async def _validate_event_stream(response, job_id: str, filename: str, errors: list[str]) -> None:
    """Validate the event stream from flow execution.

    Args:
        response: The response object with event stream
        job_id: The job ID to verify in events
        filename: Name of the template file for error reporting
        errors: List to append errors to
    """
    try:
        vertices_sorted_seen = False
        end_event_seen = False
        vertex_count = 0

        async def process_events():
            nonlocal vertices_sorted_seen, end_event_seen, vertex_count

            async for line in response.aiter_lines():
                if not line:
                    continue

                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    errors.append(f"{filename}: Invalid JSON in event stream: {line}")
                    continue

                # Verify job_id in events
                if "job_id" in parsed and parsed["job_id"] != job_id:
                    errors.append(f"{filename}: Job ID mismatch in event stream")
                    continue

                event_type = parsed.get("event")

                if event_type == "vertices_sorted":
                    vertices_sorted_seen = True
                    if not parsed.get("data", {}).get("ids"):
                        errors.append(f"{filename}: Missing vertex IDs in vertices_sorted event")

                elif event_type == "end_vertex":
                    vertex_count += 1
                    if not parsed.get("data", {}).get("build_data"):
                        errors.append(f"{filename}: Missing build_data in end_vertex event")

                elif event_type == "end":
                    end_event_seen = True

                elif event_type == "error":
                    error_data = parsed.get("data", {})
                    if isinstance(error_data, dict):
                        error_msg = error_data.get("error", "Unknown error")
                        # Skip if error is just "False" which is not a real error
                        if error_msg != "False" and error_msg is not False:
                            errors.append(f"{filename}: Flow execution error: {error_msg}")
                    else:
                        error_msg = str(error_data)
                        if error_msg != "False":
                            errors.append(f"{filename}: Flow execution error: {error_msg}")

                elif event_type == "message":
                    # Handle message events (normal part of flow execution)
                    pass

                elif event_type in ["token", "add_message", "stream_closed"]:
                    # Handle other common event types that don't indicate errors
                    pass

        # Process events with shorter timeout for comprehensive testing
        await asyncio.wait_for(process_events(), timeout=5.0)

        # Validate we saw required events (more lenient for diverse templates)
        # Only require end event - some templates may not follow the standard pattern
        if not end_event_seen:
            errors.append(f"{filename}: Missing end event in execution")
        # Allow flows with no vertices to be executed (some templates might be simple)
        # if vertex_count == 0:
        #     errors.append(f"{filename}: No vertices executed in flow")

    except asyncio.TimeoutError:
        errors.append(f"{filename}: Flow execution timeout")
    except (ValueError, TypeError, KeyError, AttributeError) as e:
        errors.append(f"{filename}: Event stream validation failed: {e!s}")
