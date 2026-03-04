"""Utility functions for validating flows during upload/save."""

from http import HTTPStatus
from typing import Any

from fastapi import HTTPException
from lfx.custom.hash_validator import validate_flow_nodes
from lfx.exceptions.component import CustomComponentNotAllowedError


def require_flow_custom_components_valid(flow_data: dict[str, Any]) -> None:
    """Validate flow components and raise HTTPException(403) if any are blocked.

    This is the recommended entry point for save-time endpoint validation.
    It raises directly so callers cannot accidentally forget to check the return value.

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


def validate_flow_custom_components(flow_data: dict[str, Any]) -> list[dict[str, str]]:
    """Validate all custom components in a flow.

    Delegates to lfx's validate_flow_nodes() which walks nodes (including nested
    group nodes) and checks each code hash via is_code_hash_allowed().

    Args:
        flow_data: The flow data dictionary containing nodes

    Returns:
        List of blocked components with their details:
        [{"node_id": "...", "display_name": "...", "class_name": "..."}]
        Empty list if all components are valid.
    """
    nodes = flow_data.get("nodes", [])
    try:
        validate_flow_nodes(nodes)
    except CustomComponentNotAllowedError as exc:
        return exc.blocked_components
    return []


def validate_flows_custom_components(flows: list[dict[str, Any]]) -> dict[str, list[dict[str, str]]]:
    """Validate custom components in multiple flows.

    Args:
        flows: List of flow dictionaries

    Returns:
        Dictionary mapping flow names to lists of blocked components.
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
