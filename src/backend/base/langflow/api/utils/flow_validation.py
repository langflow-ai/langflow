"""Utility functions for validating flows during upload."""

from typing import Any

from lfx.custom.validate import extract_display_name, validate_code


def validate_flow_custom_components(flow_data: dict[str, Any]) -> list[dict[str, str]]:
    """Validate all custom components in a flow.

    This checks for:
    1. Nodes with type "CustomComponent"
    2. ANY node with custom code (edited built-in components)

    Args:
        flow_data: The flow data dictionary containing nodes

    Returns:
        List of blocked components with their details:
        [{"node_id": "...", "display_name": "...", "class_name": "..."}]
        Empty list if all components are valid.
    """
    blocked_components = []

    # Extract nodes from flow data
    nodes = flow_data.get("nodes", [])

    for node in nodes:
        node_data = node.get("data", {})
        node_type = node_data.get("type")
        node_info = node_data.get("node", {})

        # Check if node has custom code
        template = node_info.get("template", {})
        code_field = template.get("code", {})
        code = code_field.get("value", "")

        # Skip nodes without code
        if not code:
            continue

        # Check if this is a CustomComponent OR if it's an edited built-in component
        is_custom_component = node_type == "CustomComponent"
        is_edited = node_info.get("edited", False)

        # If it's not a custom component and not edited, skip validation
        # (it's using the original built-in code)
        if not is_custom_component and not is_edited:
            continue

        # Validate the code
        validation_result = validate_code(code)

        # Check if there are any errors (blocked by security)
        if validation_result.get("function", {}).get("errors"):
            # Extract display name from code
            display_name = extract_display_name(code)

            # Try to get class name from the node
            class_name = node_info.get("display_name") or node.get("id", "Unknown")

            blocked_components.append(
                {
                    "node_id": node.get("id", "unknown"),
                    "display_name": display_name or class_name,
                    "class_name": class_name,
                    "is_edited_builtin": is_edited and not is_custom_component,
                }
            )

    return blocked_components


def validate_flows_custom_components(flows: list[dict[str, Any]]) -> dict[str, list[dict[str, str]]]:
    """Validate custom components in multiple flows.

    Args:
        flows: List of flow dictionaries

    Returns:
        Dictionary mapping flow names to lists of blocked components:
        {"flow_name": [{"node_id": "...", "display_name": "...", "class_name": "..."}]}
        Only includes flows with blocked components.
    """
    blocked_by_flow = {}

    for flow in flows:
        flow_name = flow.get("name", "Unknown Flow")
        flow_data = flow.get("data", {})

        blocked = validate_flow_custom_components(flow_data)
        if blocked:
            blocked_by_flow[flow_name] = blocked

    return blocked_by_flow
