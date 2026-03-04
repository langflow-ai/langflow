"""Utility functions for validating flows during upload."""

from http import HTTPStatus
from typing import Any

from fastapi import HTTPException
from lfx.custom.hash_validator import is_code_hash_allowed
from lfx.custom.validate import extract_display_name
from lfx.log.logger import logger


def require_flow_custom_components_valid(flow_data: dict[str, Any]) -> None:
    """Validate flow components and raise HTTPException(403) if any are blocked.

    This is the recommended entry point for endpoint validation. It raises
    directly so callers cannot accidentally forget to check the return value.

    Args:
        flow_data: The flow data dictionary containing nodes.

    Raises:
        HTTPException: 403 Forbidden if any components are blocked.
    """
    blocked = validate_flow_custom_components(flow_data)
    if blocked:
        component_names = [comp["display_name"] for comp in blocked]
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail=f"Flow build blocked: custom components are not allowed: {', '.join(component_names)}",
        )


def require_flows_custom_components_valid(flows: list[dict[str, Any]]) -> None:
    """Validate multiple flows and raise HTTPException(403) if any are blocked.

    Args:
        flows: List of flow dictionaries.

    Raises:
        HTTPException: 403 Forbidden if any flow contains blocked components.
    """
    blocked_by_flow = validate_flows_custom_components(flows)
    if blocked_by_flow:
        details = []
        for flow_name, blocked_components in blocked_by_flow.items():
            component_names = [comp["display_name"] for comp in blocked_components]
            details.append(f"{flow_name}: {', '.join(component_names)}")
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail=f"Flow build blocked: custom components are not allowed: {'; '.join(details)}",
        )


def validate_flow_custom_components(flow_data: dict[str, Any]) -> list[dict[str, str | bool]]:
    """Validate all custom components in a flow.

    This validates ALL nodes with code against the hash allowlist, regardless of
    client-provided metadata like 'edited' or 'type'. This prevents bypass by
    forging metadata. Also recursively validates nodes inside group/sub-flow nodes.

    Args:
        flow_data: The flow data dictionary containing nodes

    Returns:
        List of blocked components with their details:
        [{"node_id": "...", "display_name": "...", "class_name": "...", "is_edited_builtin": bool}]
        Empty list if all components are valid.
    """
    blocked_components: list[dict[str, str | bool]] = []
    _validate_nodes(flow_data.get("nodes", []), blocked_components)
    return blocked_components


def _validate_nodes(nodes: list[dict[str, Any]], blocked_components: list[dict[str, str | bool]]) -> None:
    """Validate a list of nodes, recursively checking group/sub-flow nodes.

    Args:
        nodes: List of node dictionaries to validate
        blocked_components: List to append blocked component details to (mutated in place)
    """
    for node in nodes:
        node_data = node.get("data", {})
        node_info = node_data.get("node", {})

        # Recursively validate nodes inside group/sub-flow nodes
        nested_flow = node_info.get("flow", {})
        if nested_flow:
            nested_flow_data = nested_flow.get("data", {})
            nested_nodes = nested_flow_data.get("nodes", [])
            if nested_nodes:
                _validate_nodes(nested_nodes, blocked_components)

        # Check if node has code
        template = node_info.get("template", {})
        code_field = template.get("code", {})
        code = code_field.get("value", "")

        # Skip nodes without code (e.g. note nodes, group wrappers).
        # These have no executable code, so there is nothing to validate.
        if not code:
            logger.debug(f"Skipping node {node.get('id', 'unknown')} — no code field")
            continue

        # Validate ALL nodes with code directly against the hash allowlist.
        # Do NOT trust client-provided 'edited' or 'type' metadata —
        # the hash check determines if the code is an allowed built-in.
        # Use is_code_hash_allowed directly instead of validate_code to avoid
        # conflating hash-blocked errors with legitimate code validation errors.
        try:
            is_allowed = is_code_hash_allowed(code)
        except Exception:  # noqa: BLE001
            # Fail closed: if hash validation raises, treat as blocked
            logger.error("Hash validation failed with exception, blocking component", exc_info=True)
            is_allowed = False

        if not is_allowed:
            # Extract display name from code
            display_name = extract_display_name(code)

            # Get display name from the node metadata
            class_name = node_info.get("display_name") or node.get("id", "Unknown")

            node_type = node_data.get("type")
            is_edited = node_info.get("edited", False)

            blocked_components.append(
                {
                    "node_id": node.get("id", "unknown"),
                    "display_name": display_name or class_name,
                    "class_name": class_name,
                    "is_edited_builtin": is_edited and node_type != "CustomComponent",
                }
            )


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
