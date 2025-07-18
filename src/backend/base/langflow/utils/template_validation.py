"""Template validation utilities for Langflow starter projects.

This module provides validation functions to ensure template integrity and prevent
unexpected breakage in starter project templates.
"""

import uuid
from typing import Any

from langflow.graph.graph.base import Graph


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


def validate_template_comprehensive(template_data: dict[str, Any], filename: str) -> dict[str, list[str]]:
    """Run comprehensive validation on a template.

    Args:
        template_data: The template data to validate
        filename: Name of the template file for error reporting

    Returns:
        Dictionary with validation results:
        {
            "structure_errors": [...],
            "security_issues": [...],
            "build_errors": [...]
        }
    """
    return {
        "structure_errors": validate_template_structure(template_data, filename),
        "build_errors": validate_flow_can_build(template_data, filename),
    }
