"""Utilities for handling exported projects in LFX CLI."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from lfx.cli.export_schemas import FlowExport, ProjectExport

if TYPE_CHECKING:
    from pathlib import Path


def is_project_export(data: dict[str, Any]) -> bool:
    """Check if the given data is a project export.

    Args:
        data: Dictionary containing the potential project export data

    Returns:
        True if the data matches the project export format
    """
    # Check for required fields that identify a project export
    return (
        isinstance(data, dict)
        and data.get("export_type") == "project"
        and "version" in data
        and "project" in data
        and "flows" in data
        and isinstance(data.get("flows"), list)
    )


def load_project_export(file_path: Path) -> ProjectExport | None:
    """Load and validate a project export file.

    Args:
        file_path: Path to the JSON file

    Returns:
        ProjectExport object if valid, None otherwise
    """
    try:
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if not is_project_export(data):
            return None

        # Create ProjectExport instance with validation
        return ProjectExport(**data)
    except (json.JSONDecodeError, ValueError):
        return None


def extract_flows_from_export(export_data: ProjectExport) -> list[tuple[str, dict[str, Any]]]:
    """Extract flow data from a project export.

    Args:
        export_data: The validated project export

    Returns:
        List of tuples (flow_id, flow_data) for each flow
    """
    flows = []

    for flow in export_data.flows:
        if isinstance(flow, FlowExport):
            flow_id = str(flow.id)
            flow_data = flow.model_dump()
        elif isinstance(flow, dict):
            flow_id = str(flow.get("id", ""))
            flow_data = flow
        else:
            continue

        if flow_id and flow_data:
            flows.append((flow_id, flow_data))

    return flows


def create_flow_metadata_from_export(
    export_data: ProjectExport, flow_id: str, flow_data: dict[str, Any]
) -> dict[str, Any]:
    """Create metadata for a flow from project export data.

    Args:
        export_data: The project export
        flow_id: The flow ID
        flow_data: The flow data dictionary

    Returns:
        Metadata dictionary for the flow
    """
    return {
        "id": flow_id,
        "relative_path": f"{export_data.project.name}/{flow_data.get('name', 'flow')}.json",
        "title": flow_data.get("name", "Unnamed Flow"),
        "description": flow_data.get("description"),
        "project_id": export_data.project.id,
        "project_name": export_data.project.name,
        "is_component": flow_data.get("is_component", False),
        "mcp_enabled": flow_data.get("mcp_enabled", False),
        "action_name": flow_data.get("action_name"),
        "action_description": flow_data.get("action_description"),
    }


def prepare_graph_from_flow_data(flow_data: dict[str, Any]) -> dict[str, Any]:
    """Prepare graph data from flow export data.

    Args:
        flow_data: The flow data from export

    Returns:
        Graph data suitable for loading into a Graph object
    """
    # Extract the actual graph data
    graph_data = flow_data.get("data", {})

    # Handle empty flows
    if not graph_data:
        # Return minimal graph structure for empty flows
        return {"nodes": [], "edges": [], "viewport": {"x": 0, "y": 0, "zoom": 1}}

    # Ensure required fields exist
    if "nodes" not in graph_data:
        graph_data["nodes"] = []
    if "edges" not in graph_data:
        graph_data["edges"] = []
    if "viewport" not in graph_data:
        graph_data["viewport"] = {"x": 0, "y": 0, "zoom": 1}

    # Graph.from_payload expects either {"data": {...}} or just the graph data
    # Since we extracted the data field, we can return it directly
    return graph_data
