"""Flow repository functions for lfx package.

This module contains functions for listing, finding, and loading flows
from local files or the database backend.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from lfx.log.logger import logger

if TYPE_CHECKING:
    from lfx.graph.graph.base import Graph
    from lfx.schema.data import Data


async def list_flows(*, user_id: str | None = None) -> list[Data]:
    """List flows for a user.

    In lfx, this is a stub that returns an empty list since we don't have
    a database backend by default.

    Args:
        user_id: The user ID to list flows for.

    Returns:
        List of flow data objects.
    """
    if not user_id:
        msg = "Session is invalid"
        raise ValueError(msg)

    logger.warning("list_flows called but lfx doesn't have database backend by default")
    return []


async def list_flows_by_flow_folder(
    *,
    user_id: str | None = None,
    flow_id: str | None = None,
    order_params: dict | None = {"column": "updated_at", "direction": "desc"},  # noqa: B006, ARG001
) -> list[Data]:
    """Lists flows for the given user and in the same folder as the specified flow.

    Retrieves all flows belonging to the given user and identified by user_id
    that belong to the same folder as the flow identified by flow_id if the flow belongs to the user.

    In lfx, this is a stub that returns an empty list since we don't have
    a database backend by default.

    Args:
        user_id (str | None, optional): The user ID to list flows for. Defaults to None.
        flow_id (str | None, optional): The flow ID to list flows in the same folder as. Defaults to None.
        order_params (dict | None, optional): Parameters for ordering the flows.
        Defaults to {"column": "updated_at", "direction": "desc"}.

    Returns:
        list[Data]: List of flows in the same folder as the flow identified by flow_id.

    Raises:
        ValueError: If user_id is not provided.
        ValueError: If Flow ID is not provided.
    """
    if not user_id:
        msg = "Session is invalid"
        raise ValueError(msg)
    if not flow_id:
        msg = "Flow ID is required"
        raise ValueError(msg)

    logger.warning("list_flows_by_flow_folder called but lfx doesn't have database backend by default")
    return []


async def list_flows_by_folder_id(
    *,
    user_id: str | None = None,
    folder_id: str | None = None,
) -> list[Data]:
    """Lists flows for the given user and in the same folder as the specified folder.

    In lfx, this is a stub that returns an empty list since we don't have
    a database backend by default.

    Args:
        user_id (str | None, optional): The user ID to list flows for. Defaults to None.
        folder_id (str | None, optional): The folder ID to list flows in the same folder as. Defaults to None.

    Returns:
        list[Data]: List of flows in the same folder as the folder identified by folder_id.

    Raises:
        ValueError: If user_id is not provided.
        ValueError: If Folder ID is not provided.
    """
    if not user_id:
        msg = "Session is invalid"
        raise ValueError(msg)
    if not folder_id:
        msg = "Folder ID is required"
        raise ValueError(msg)

    logger.warning("list_flows_by_folder_id called but lfx doesn't have database backend by default")
    return []


def _load_flow_from_file(file_path: Path) -> Data | None:
    """Load a flow from a JSON file.

    Args:
        file_path: Path to the JSON flow file.

    Returns:
        Data object with flow content, or None if file doesn't exist or is invalid.
    """
    from lfx.schema.data import Data

    if not file_path.exists():
        return None

    try:
        flow_content = json.loads(file_path.read_text(encoding="utf-8"))

        flow_data = {
            "id": flow_content.get("id", file_path.stem),
            "name": flow_content.get("name", file_path.stem),
            "description": flow_content.get("description", ""),
            "data": flow_content.get("data", flow_content),
            "updated_at": flow_content.get("updated_at"),
        }

        return Data(data=flow_data)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load flow from {file_path}: {e}")
        return None


def _find_flow_in_project(
    project_path: Path,
    flow_id: str | None = None,
    flow_name: str | None = None,
) -> Data | None:
    """Find a flow in the project directory by ID or name.

    Search strategy:
    1. If flow_name provided: look for {flow_name}.json
    2. If flow_id provided: look for {flow_id}.json
    3. Search all JSON files for matching name or id field

    Args:
        project_path: Directory to search for flows.
        flow_id: Optional flow ID to search for.
        flow_name: Optional flow name to search for.

    Returns:
        Data object with flow content, or None if not found.
    """
    if not project_path.is_dir():
        logger.warning(f"Project path is not a directory: {project_path}")
        return None

    # Strategy 1: Direct file name match with flow_name
    if flow_name:
        direct_path = project_path / f"{flow_name}.json"
        if direct_path.exists():
            logger.debug(f"Found flow by name match: {direct_path}")
            return _load_flow_from_file(direct_path)

    # Strategy 2: Direct file name match with flow_id
    if flow_id:
        direct_path = project_path / f"{flow_id}.json"
        if direct_path.exists():
            logger.debug(f"Found flow by ID match: {direct_path}")
            return _load_flow_from_file(direct_path)

    # Strategy 3: Search all JSON files for matching name or id field
    for json_file in project_path.glob("*.json"):
        try:
            content = json.loads(json_file.read_text(encoding="utf-8"))
            file_name = content.get("name", "")
            file_id = content.get("id", "")

            if (flow_name and file_name == flow_name) or (flow_id and file_id == flow_id):
                logger.debug(f"Found flow by content match: {json_file}")
                return _load_flow_from_file(json_file)
        except (json.JSONDecodeError, OSError):
            continue

    return None


async def get_flow_by_id_or_name(
    user_id: str | None = None,
    flow_id: str | None = None,
    flow_name: str | None = None,
    project_path: Path | str | None = None,
) -> Data | None:
    """Get a flow by ID or name.

    Retrieves a flow by ID or name. If both are provided, flow_id is used.

    This function supports two modes:
    1. Local file mode (lfx): When project_path is provided, searches for flows in that directory
    2. Database mode (langflow backend): When project_path is not provided and langflow backend
       is available, delegates to the backend implementation

    Args:
        user_id (str | None, optional): The user ID (required for database mode).
        flow_id (str | None, optional): The flow ID. Defaults to None.
        flow_name (str | None, optional): The flow name. Defaults to None.
        project_path (Path | str | None, optional): Project directory to search for flows.

    Returns:
        Data | None: The flow data or None if not found.
    """
    if not (flow_id or flow_name):
        msg = "Flow ID or Flow Name is required"
        raise ValueError(msg)

    # If project_path is provided, search for flows in the project directory (lfx mode)
    if project_path:
        if isinstance(project_path, str):
            project_path = Path(project_path)

        flow = _find_flow_in_project(project_path, flow_id=flow_id, flow_name=flow_name)
        if flow:
            logger.info(f"Found flow '{flow_name or flow_id}' in project: {project_path}")
            return flow

        logger.warning(f"Flow '{flow_name or flow_id}' not found in project: {project_path}")
        return None

    # Without project_path, try to use langflow backend if available (database mode)
    try:
        from langflow.helpers.flow import get_flow_by_id_or_name as backend_get_flow

        return await backend_get_flow(user_id=user_id, flow_id=flow_id, flow_name=flow_name)
    except ImportError:
        pass

    # No project_path and no backend - require user_id for error message
    if not user_id:
        msg = "Session is invalid"
        raise ValueError(msg)

    logger.warning("get_flow_by_id_or_name called but lfx doesn't have database backend by default")
    return None


async def load_flow(
    user_id: str,  # noqa: ARG001
    flow_id: str | None = None,
    flow_name: str | None = None,
    tweaks: dict | None = None,  # noqa: ARG001
) -> Graph:
    """Load a flow by ID or name.

    In lfx, this is a stub that raises an error since we don't have
    a database backend by default.

    Args:
        user_id: The user ID.
        flow_id: The flow ID to load.
        flow_name: The flow name to load.
        tweaks: Optional tweaks to apply to the flow.

    Returns:
        The loaded flow graph.
    """
    if not flow_id and not flow_name:
        msg = "Flow ID or Flow Name is required"
        raise ValueError(msg)

    msg = f"load_flow not implemented in lfx - cannot load flow {flow_id or flow_name}"
    raise NotImplementedError(msg)
