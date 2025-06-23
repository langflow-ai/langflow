import asyncio
import copy
import io
import json
import re
import shutil
import zipfile
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import AnyStr
from uuid import UUID

import anyio
import httpx
import orjson
import sqlalchemy as sa
from aiofile import async_open
from emoji import demojize, purely_emoji
from loguru import logger
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import selectinload
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.base.constants import (
    FIELD_FORMAT_ATTRIBUTES,
    NODE_FORMAT_ATTRIBUTES,
    ORJSON_OPTIONS,
    SKIPPED_COMPONENTS,
    SKIPPED_FIELD_ATTRIBUTES,
)
from langflow.initial_setup.constants import STARTER_FOLDER_DESCRIPTION, STARTER_FOLDER_NAME
from langflow.services.auth.utils import create_super_user
from langflow.services.database.models.flow.model import Flow, FlowCreate
from langflow.services.database.models.folder.constants import DEFAULT_FOLDER_NAME
from langflow.services.database.models.folder.model import Folder, FolderCreate, FolderRead
from langflow.services.database.models.user.crud import get_user_by_username
from langflow.services.deps import get_settings_service, get_storage_service, get_variable_service, session_scope
from langflow.template.field.prompt import DEFAULT_PROMPT_INTUT_TYPES
from langflow.utils.util import escape_json_dump

# In the folder ./starter_projects we have a few JSON files that represent
# starter projects. We want to load these into the database so that users
# can use them as a starting point for their own projects.


def update_projects_components_with_latest_component_versions(project_data, all_types_dict):
    # Flatten the all_types_dict for easy access
    all_types_dict_flat = {}
    for category in all_types_dict.values():
        for key, component in category.items():
            all_types_dict_flat[key] = component  # noqa: PERF403

    node_changes_log = defaultdict(list)
    project_data_copy = deepcopy(project_data)

    for node in project_data_copy.get("nodes", []):
        node_data = node.get("data").get("node")
        node_type = node.get("data").get("type")

        if node_type in all_types_dict_flat:
            latest_node = all_types_dict_flat.get(node_type)
            latest_template = latest_node.get("template")
            node_data["template"]["code"] = latest_template["code"]
            # skip components that are having dynamic values that need to be persisted for templates

            if node_data.get("key") in SKIPPED_COMPONENTS:
                continue

            is_tool_or_agent = node_data.get("tool_mode", False) or node_data.get("key") in {
                "Agent",
                "LanguageModelComponent",
            }
            has_tool_outputs = any(output.get("types") == ["Tool"] for output in node_data.get("outputs", []))
            if "outputs" in latest_node and not has_tool_outputs and not is_tool_or_agent:
                # Set selected output as the previous selected output
                for output in latest_node["outputs"]:
                    node_data_output = next(
                        (output_ for output_ in node_data["outputs"] if output_["name"] == output["name"]),
                        None,
                    )
                    if node_data_output:
                        output["selected"] = node_data_output.get("selected")
                node_data["outputs"] = latest_node["outputs"]

            if node_data["template"]["_type"] != latest_template["_type"]:
                node_data["template"]["_type"] = latest_template["_type"]
                if node_type != "Prompt":
                    node_data["template"] = latest_template
                else:
                    for key, value in latest_template.items():
                        if key not in node_data["template"]:
                            node_changes_log[node_type].append(
                                {
                                    "attr": key,
                                    "old_value": None,
                                    "new_value": value,
                                }
                            )
                            node_data["template"][key] = value
                        elif isinstance(value, dict) and value.get("value"):
                            node_changes_log[node_type].append(
                                {
                                    "attr": key,
                                    "old_value": node_data["template"][key],
                                    "new_value": value,
                                }
                            )
                            node_data["template"][key]["value"] = value["value"]
                    for key in node_data["template"]:
                        if key not in latest_template:
                            node_data["template"][key]["input_types"] = DEFAULT_PROMPT_INTUT_TYPES
                node_changes_log[node_type].append(
                    {
                        "attr": "_type",
                        "old_value": node_data["template"]["_type"],
                        "new_value": latest_template["_type"],
                    }
                )
            else:
                for attr in NODE_FORMAT_ATTRIBUTES:
                    if (
                        attr in latest_node
                        # Check if it needs to be updated
                        and latest_node[attr] != node_data.get(attr)
                    ):
                        node_changes_log[node_type].append(
                            {
                                "attr": attr,
                                "old_value": node_data.get(attr),
                                "new_value": latest_node[attr],
                            }
                        )
                        node_data[attr] = latest_node[attr]

                for field_name, field_dict in latest_template.items():
                    if field_name not in node_data["template"]:
                        node_data["template"][field_name] = field_dict
                        continue
                    # The idea here is to update some attributes of the field
                    to_check_attributes = FIELD_FORMAT_ATTRIBUTES
                    # Skip specific field attributes that should respect the starter project template values.
                    # Currently we skip 'advanced' so that a field marked as advanced in the component code
                    # will NOT overwrite the value specified in the starter project template. This preserves
                    # the intended UX configuration of the starter projects.
                    # SKIPPED_FIELD_ATTRIBUTES = {"advanced"}
                    # Iterate through the attributes we want to potentially update
                    for attr in to_check_attributes:
                        # Respect the template value by not updating if the attribute is in the skipped set
                        if attr in SKIPPED_FIELD_ATTRIBUTES:
                            continue
                        if (
                            attr in field_dict
                            and attr in node_data["template"].get(field_name)
                            # Check if it needs to be updated
                            and field_dict[attr] != node_data["template"][field_name][attr]
                        ):
                            node_changes_log[node_type].append(
                                {
                                    "attr": f"{field_name}.{attr}",
                                    "old_value": node_data["template"][field_name][attr],
                                    "new_value": field_dict[attr],
                                }
                            )
                            node_data["template"][field_name][attr] = field_dict[attr]
            # Remove fields that are not in the latest template
            if node_type != "Prompt":
                for field_name in list(node_data["template"].keys()):
                    is_tool_mode_and_field_is_tools_metadata = (
                        node_data.get("tool_mode", False) and field_name == "tools_metadata"
                    )
                    if field_name not in latest_template and not is_tool_mode_and_field_is_tools_metadata:
                        node_data["template"].pop(field_name)
    log_node_changes(node_changes_log)
    return project_data_copy


def scape_json_parse(json_string: str) -> dict:
    if json_string is None:
        return {}
    if isinstance(json_string, dict):
        return json_string
    parsed_string = json_string.replace("œ", '"')
    return json.loads(parsed_string)


def update_new_output(data):
    nodes = copy.deepcopy(data["nodes"])
    edges = copy.deepcopy(data["edges"])

    for edge in edges:
        if "sourceHandle" in edge and "targetHandle" in edge:
            new_source_handle = scape_json_parse(edge["sourceHandle"])
            new_target_handle = scape_json_parse(edge["targetHandle"])
            id_ = new_source_handle["id"]
            source_node_index = next((index for (index, d) in enumerate(nodes) if d["id"] == id_), -1)
            source_node = nodes[source_node_index] if source_node_index != -1 else None

            if "baseClasses" in new_source_handle:
                if "output_types" not in new_source_handle:
                    if source_node and "node" in source_node["data"] and "output_types" in source_node["data"]["node"]:
                        new_source_handle["output_types"] = source_node["data"]["node"]["output_types"]
                    else:
                        new_source_handle["output_types"] = new_source_handle["baseClasses"]
                del new_source_handle["baseClasses"]

            if new_target_handle.get("inputTypes"):
                intersection = [
                    type_ for type_ in new_source_handle["output_types"] if type_ in new_target_handle["inputTypes"]
                ]
            else:
                intersection = [
                    type_ for type_ in new_source_handle["output_types"] if type_ == new_target_handle["type"]
                ]

            selected = intersection[0] if intersection else None
            if "name" not in new_source_handle:
                new_source_handle["name"] = " | ".join(new_source_handle["output_types"])
            new_source_handle["output_types"] = [selected] if selected else []

            if source_node and not source_node["data"]["node"].get("outputs"):
                if "outputs" not in source_node["data"]["node"]:
                    source_node["data"]["node"]["outputs"] = []
                types = source_node["data"]["node"].get(
                    "output_types", source_node["data"]["node"].get("base_classes", [])
                )
                if not any(output.get("selected") == selected for output in source_node["data"]["node"]["outputs"]):
                    source_node["data"]["node"]["outputs"].append(
                        {
                            "types": types,
                            "selected": selected,
                            "name": " | ".join(types),
                            "display_name": " | ".join(types),
                        }
                    )
            deduplicated_outputs = []
            if source_node is None:
                source_node = {"data": {"node": {"outputs": []}}}

            for output in source_node["data"]["node"]["outputs"]:
                if output["name"] not in [d["name"] for d in deduplicated_outputs]:
                    deduplicated_outputs.append(output)
            source_node["data"]["node"]["outputs"] = deduplicated_outputs

            edge["sourceHandle"] = escape_json_dump(new_source_handle)
            edge["data"]["sourceHandle"] = new_source_handle
            edge["data"]["targetHandle"] = new_target_handle
    # The above sets the edges but some of the sourceHandles do not have valid name
    # which can be found in the nodes. We need to update the sourceHandle with the
    # name from node['data']['node']['outputs']
    for node in nodes:
        if "outputs" in node["data"]["node"]:
            for output in node["data"]["node"]["outputs"]:
                for edge in edges:
                    if node["id"] != edge["source"] or output.get("method") is None:
                        continue
                    source_handle = scape_json_parse(edge["sourceHandle"])
                    if source_handle["output_types"] == output.get("types") and source_handle["name"] != output["name"]:
                        source_handle["name"] = output["name"]
                        if isinstance(source_handle, str):
                            source_handle = scape_json_parse(source_handle)
                        edge["sourceHandle"] = escape_json_dump(source_handle)
                        edge["data"]["sourceHandle"] = source_handle

    data_copy = copy.deepcopy(data)
    data_copy["nodes"] = nodes
    data_copy["edges"] = edges
    return data_copy


def update_edges_with_latest_component_versions(project_data):
    """Update edges in a project with the latest component versions.

    This function processes each edge in the project data and ensures that the source and target handles
    are updated to match the latest component versions. It tracks all changes made to edges in a log
    for debugging purposes.

    Args:
        project_data (dict): The project data containing nodes and edges to be updated.

    Returns:
        dict: A deep copy of the project data with updated edges.

    The function performs the following operations:
    1. Creates a deep copy of the project data to avoid modifying the original
    2. For each edge, extracts and parses the source and target handles
    3. Finds the corresponding source and target nodes
    4. Updates output types in the source handle based on the node's outputs
    5. Updates input types in the target handle based on the node's template
    6. Escapes and updates the handles in the edge data
    7. Logs all changes made to the edges
    """
    # Initialize a dictionary to track changes for logging
    edge_changes_log = defaultdict(list)
    # Create a deep copy to avoid modifying the original data
    project_data_copy = deepcopy(project_data)

    # Create a mapping of node types to node IDs for node reconciliation
    node_type_map = {}
    for node in project_data_copy.get("nodes", []):
        node_type = node.get("data", {}).get("type", "")
        if node_type:
            if node_type not in node_type_map:
                node_type_map[node_type] = []
            node_type_map[node_type].append(node.get("id"))

    # Process each edge in the project
    for edge in project_data_copy.get("edges", []):
        # Extract and parse source and target handles
        source_handle = edge.get("data", {}).get("sourceHandle")
        source_handle = scape_json_parse(source_handle)
        target_handle = edge.get("data", {}).get("targetHandle")
        target_handle = scape_json_parse(target_handle)

        # Find the corresponding source and target nodes
        source_node = next(
            (node for node in project_data.get("nodes", []) if node.get("id") == edge.get("source")),
            None,
        )
        target_node = next(
            (node for node in project_data.get("nodes", []) if node.get("id") == edge.get("target")),
            None,
        )

        # Try to reconcile missing nodes by type
        if source_node is None and source_handle and "dataType" in source_handle:
            node_type = source_handle.get("dataType")
            if node_type_map.get(node_type):
                # Use the first node of matching type as replacement
                new_node_id = node_type_map[node_type][0]
                logger.info(f"Reconciling missing source node: replacing {edge.get('source')} with {new_node_id}")

                # Update edge source
                edge["source"] = new_node_id

                # Update source handle ID
                source_handle["id"] = new_node_id

                # Find the new source node
                source_node = next(
                    (node for node in project_data.get("nodes", []) if node.get("id") == new_node_id),
                    None,
                )

                # Update edge ID (complex as it contains encoded handles)
                # This is a simplified approach - in production you'd need to parse and rebuild the ID
                old_id_prefix = edge.get("id", "").split("{")[0]
                if old_id_prefix:
                    new_id_prefix = old_id_prefix.replace(edge.get("source"), new_node_id)
                    edge["id"] = edge.get("id", "").replace(old_id_prefix, new_id_prefix)

        if target_node is None and target_handle and "id" in target_handle:
            # Extract node type from target handle ID (e.g., "AstraDBGraph-jr8pY" -> "AstraDBGraph")
            id_parts = target_handle.get("id", "").split("-")
            if len(id_parts) > 0:
                node_type = id_parts[0]
                if node_type_map.get(node_type):
                    # Use the first node of matching type as replacement
                    new_node_id = node_type_map[node_type][0]
                    logger.info(f"Reconciling missing target node: replacing {edge.get('target')} with {new_node_id}")

                    # Update edge target
                    edge["target"] = new_node_id

                    # Update target handle ID
                    target_handle["id"] = new_node_id

                    # Find the new target node
                    target_node = next(
                        (node for node in project_data.get("nodes", []) if node.get("id") == new_node_id),
                        None,
                    )

                    # Update edge ID (simplified approach)
                    old_id_suffix = edge.get("id", "").split("}-")[1] if "}-" in edge.get("id", "") else ""
                    if old_id_suffix:
                        new_id_suffix = old_id_suffix.replace(edge.get("target"), new_node_id)
                        edge["id"] = edge.get("id", "").replace(old_id_suffix, new_id_suffix)

        if source_node and target_node:
            # Extract node data for easier access
            source_node_data = source_node.get("data", {}).get("node", {})
            target_node_data = target_node.get("data", {}).get("node", {})

            # Find the output data that matches the source handle name
            output_data = next(
                (
                    output
                    for output in source_node_data.get("outputs", [])
                    if output.get("name") == source_handle.get("name")
                ),
                None,
            )

            # If not found by name, try to find by display_name
            if not output_data:
                output_data = next(
                    (
                        output
                        for output in source_node_data.get("outputs", [])
                        if output.get("display_name") == source_handle.get("name")
                    ),
                    None,
                )
                # Update source handle name if found by display_name
                if output_data:
                    source_handle["name"] = output_data.get("name")

            # Determine the new output types based on the output data
            if output_data:
                if len(output_data.get("types", [])) == 1:
                    new_output_types = output_data.get("types", [])
                elif output_data.get("selected"):
                    new_output_types = [output_data.get("selected")]
                else:
                    new_output_types = []
            else:
                new_output_types = []

            # Update output types if they've changed and log the change
            if source_handle.get("output_types", []) != new_output_types:
                edge_changes_log[source_node_data.get("display_name", "unknown")].append(
                    {
                        "attr": "output_types",
                        "old_value": source_handle.get("output_types", []),
                        "new_value": new_output_types,
                    }
                )
                source_handle["output_types"] = new_output_types

            # Update input types if they've changed and log the change
            field_name = target_handle.get("fieldName")
            if field_name in target_node_data.get("template", {}) and target_handle.get(
                "inputTypes", []
            ) != target_node_data.get("template", {}).get(field_name, {}).get("input_types", []):
                edge_changes_log[target_node_data.get("display_name", "unknown")].append(
                    {
                        "attr": "inputTypes",
                        "old_value": target_handle.get("inputTypes", []),
                        "new_value": target_node_data.get("template", {}).get(field_name, {}).get("input_types", []),
                    }
                )
                target_handle["inputTypes"] = (
                    target_node_data.get("template", {}).get(field_name, {}).get("input_types", [])
                )

            # Escape the updated handles for JSON storage
            escaped_source_handle = escape_json_dump(source_handle)
            escaped_target_handle = escape_json_dump(target_handle)

            # Try to parse and escape the old handles for comparison
            try:
                old_escape_source_handle = escape_json_dump(json.loads(edge.get("sourceHandle", "{}")))
            except (json.JSONDecodeError, TypeError):
                old_escape_source_handle = edge.get("sourceHandle", "")

            try:
                old_escape_target_handle = escape_json_dump(json.loads(edge.get("targetHandle", "{}")))
            except (json.JSONDecodeError, TypeError):
                old_escape_target_handle = edge.get("targetHandle", "")

            # Update source handle if it's changed and log the change
            if old_escape_source_handle != escaped_source_handle:
                edge_changes_log[source_node_data.get("display_name", "unknown")].append(
                    {
                        "attr": "sourceHandle",
                        "old_value": old_escape_source_handle,
                        "new_value": escaped_source_handle,
                    }
                )
                edge["sourceHandle"] = escaped_source_handle
                if "data" in edge:
                    edge["data"]["sourceHandle"] = source_handle

            # Update target handle if it's changed and log the change
            if old_escape_target_handle != escaped_target_handle:
                edge_changes_log[target_node_data.get("display_name", "unknown")].append(
                    {
                        "attr": "targetHandle",
                        "old_value": old_escape_target_handle,
                        "new_value": escaped_target_handle,
                    }
                )
                edge["targetHandle"] = escaped_target_handle
                if "data" in edge:
                    edge["data"]["targetHandle"] = target_handle

        else:
            # Log an error if source or target node is not found after reconciliation attempt
            logger.error(f"Source or target node not found for edge: {edge}")

    # Log all the changes that were made
    log_node_changes(edge_changes_log)
    return project_data_copy


def log_node_changes(node_changes_log) -> None:
    # The idea here is to log the changes that were made to the nodes in debug
    # Something like:
    # Node: "Node Name" was updated with the following changes:
    # attr_name: old_value -> new_value
    # let's create one log per node
    formatted_messages = []
    for node_name, changes in node_changes_log.items():
        message = f"\nNode: {node_name} was updated with the following changes:"
        for change in changes:
            message += f"\n- {change['attr']}: {change['old_value']} -> {change['new_value']}"
        formatted_messages.append(message)
    if formatted_messages:
        logger.debug("\n".join(formatted_messages))


async def load_starter_projects(retries=3, delay=1) -> list[tuple[anyio.Path, dict]]:
    starter_projects = []
    folder = anyio.Path(__file__).parent / "starter_projects"
    logger.debug("Loading starter projects")
    async for file in folder.glob("*.json"):
        attempt = 0
        while attempt < retries:
            async with async_open(str(file), "r", encoding="utf-8") as f:
                content = await f.read()
            try:
                project = orjson.loads(content)
                starter_projects.append((file, project))
                break  # Break if load is successful
            except orjson.JSONDecodeError as e:
                attempt += 1
                if attempt >= retries:
                    msg = f"Error loading starter project {file}: {e}"
                    raise ValueError(msg) from e
                await asyncio.sleep(delay)  # Wait before retrying
    logger.debug(f"Loaded {len(starter_projects)} starter projects")
    return starter_projects


async def copy_profile_pictures() -> None:
    """Asynchronously copies profile pictures from the source directory to the target configuration directory.

    This function copies profile pictures while optimizing I/O operations by:
    1. Using a set to track existing files and avoid redundant filesystem checks
    2. Performing bulk copy operations concurrently using asyncio.gather
    3. Offloading blocking I/O to threads

    The directory structure is:
    profile_pictures/
    ├── People/
    │   └── [profile images]
    └── Space/
        └── [profile images]
    """
    # Get config directory from settings
    config_dir = get_storage_service().settings_service.settings.config_dir
    if config_dir is None:
        msg = "Config dir is not set in the settings"
        raise ValueError(msg)

    # Setup source and target paths
    origin = anyio.Path(__file__).parent / "profile_pictures"
    target = anyio.Path(config_dir) / "profile_pictures"

    if not await origin.exists():
        msg = f"The source folder '{origin}' does not exist."
        raise ValueError(msg)

    # Create target dir if needed
    if not await target.exists():
        await target.mkdir(parents=True, exist_ok=True)

    try:
        # Get set of existing files in target to avoid redundant checks
        target_files = {str(f.relative_to(target)) async for f in target.rglob("*") if await f.is_file()}

        # Define a helper coroutine to copy a single file concurrently
        async def copy_file(src_file, dst_file, rel_path):
            # Create parent directories if needed
            await dst_file.parent.mkdir(parents=True, exist_ok=True)
            # Offload blocking I/O to a thread
            await asyncio.to_thread(shutil.copy2, str(src_file), str(dst_file))
            logger.debug(f"Copied file '{rel_path}'")

        tasks = []
        async for src_file in origin.rglob("*"):
            if not await src_file.is_file():
                continue

            rel_path = src_file.relative_to(origin)
            if str(rel_path) not in target_files:
                dst_file = target / rel_path
                tasks.append(copy_file(src_file, dst_file, rel_path))

        if tasks:
            await asyncio.gather(*tasks)

    except Exception as exc:
        logger.exception("Error copying profile pictures")
        msg = "An error occurred while copying profile pictures."
        raise RuntimeError(msg) from exc


def get_project_data(project):
    project_name = project.get("name")
    project_description = project.get("description")
    project_is_component = project.get("is_component")
    project_updated_at = project.get("updated_at")
    if not project_updated_at:
        updated_at_datetime = datetime.now(tz=timezone.utc)
    else:
        updated_at_datetime = datetime.fromisoformat(project_updated_at)
    project_data = project.get("data")
    project_icon = project.get("icon")
    project_icon = demojize(project_icon) if project_icon and purely_emoji(project_icon) else project_icon
    project_icon_bg_color = project.get("icon_bg_color")
    project_gradient = project.get("gradient")
    project_tags = project.get("tags")
    return (
        project_name,
        project_description,
        project_is_component,
        updated_at_datetime,
        project_data,
        project_icon,
        project_icon_bg_color,
        project_gradient,
        project_tags,
    )


async def update_project_file(project_path: anyio.Path, project: dict, updated_project_data) -> None:
    project["data"] = updated_project_data
    async with async_open(str(project_path), "w", encoding="utf-8") as f:
        await f.write(orjson.dumps(project, option=ORJSON_OPTIONS).decode())
    logger.debug(f"Updated starter project {project['name']} file")


def update_existing_project(
    existing_project,
    project_name,
    project_description,
    project_is_component,
    updated_at_datetime,
    project_data,
    project_icon,
    project_icon_bg_color,
) -> None:
    logger.info(f"Updating starter project {project_name}")
    existing_project.data = project_data
    existing_project.folder = STARTER_FOLDER_NAME
    existing_project.description = project_description
    existing_project.is_component = project_is_component
    existing_project.updated_at = updated_at_datetime
    existing_project.icon = project_icon
    existing_project.icon_bg_color = project_icon_bg_color


def create_new_project(
    session,
    project_name,
    project_description,
    project_is_component,
    updated_at_datetime,
    project_data,
    project_gradient,
    project_tags,
    project_icon,
    project_icon_bg_color,
    new_folder_id,
) -> None:
    new_project = FlowCreate(
        name=project_name,
        description=project_description,
        icon=project_icon,
        icon_bg_color=project_icon_bg_color,
        data=project_data,
        is_component=project_is_component,
        updated_at=updated_at_datetime,
        folder_id=new_folder_id,
        gradient=project_gradient,
        tags=project_tags,
    )
    db_flow = Flow.model_validate(new_project, from_attributes=True)
    session.add(db_flow)


async def get_all_flows_similar_to_project(session: AsyncSession, folder_id: UUID) -> list[Flow]:
    stmt = select(Folder).options(selectinload(Folder.flows)).where(Folder.id == folder_id)
    return list((await session.exec(stmt)).first().flows)


async def delete_starter_projects(session, folder_id) -> None:
    flows = await get_all_flows_similar_to_project(session, folder_id)
    for flow in flows:
        await session.delete(flow)
    await session.commit()


async def folder_exists(session, folder_name):
    stmt = select(Folder).where(Folder.name == folder_name)
    folder = (await session.exec(stmt)).first()
    return folder is not None


async def get_or_create_starter_folder(session):
    if not await folder_exists(session, STARTER_FOLDER_NAME):
        new_folder = FolderCreate(name=STARTER_FOLDER_NAME, description=STARTER_FOLDER_DESCRIPTION)
        db_folder = Folder.model_validate(new_folder, from_attributes=True)
        session.add(db_folder)
        await session.commit()
        await session.refresh(db_folder)
        return db_folder
    stmt = select(Folder).where(Folder.name == STARTER_FOLDER_NAME)
    return (await session.exec(stmt)).first()


def _is_valid_uuid(val):
    try:
        uuid_obj = UUID(val)
    except ValueError:
        return False
    return str(uuid_obj) == val


async def load_flows_from_directory() -> None:
    """On langflow startup, this loads all flows from the directory specified in the settings.

    All flows are uploaded into the default folder for the superuser.
    Note that this feature currently only works if AUTO_LOGIN is enabled in the settings.
    """
    settings_service = get_settings_service()
    flows_path = settings_service.settings.load_flows_path
    if not flows_path:
        return
    if not settings_service.auth_settings.AUTO_LOGIN:
        logger.warning("AUTO_LOGIN is disabled, not loading flows from directory")
        return

    async with session_scope() as session:
        user = await get_user_by_username(session, settings_service.auth_settings.SUPERUSER)
        if user is None:
            msg = "Superuser not found in the database"
            raise NoResultFound(msg)

        # Ensure that the default folder exists for this user
        _ = await get_or_create_default_folder(session, user.id)

        for file_path in await asyncio.to_thread(Path(flows_path).iterdir):
            if not await anyio.Path(file_path).is_file() or file_path.suffix != ".json":
                continue
            logger.info(f"Loading flow from file: {file_path.name}")
            async with async_open(str(file_path), "r", encoding="utf-8") as f:
                content = await f.read()
            await upsert_flow_from_file(content, file_path.stem, session, user.id)


async def detect_github_url(url: str) -> str:
    if matched := re.match(r"https?://(?:www\.)?github\.com/([\w.-]+)/([\w.-]+)?/?$", url):
        owner, repo = matched.groups()

        repo = repo.removesuffix(".git")

        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(f"https://api.github.com/repos/{owner}/{repo}")
            response.raise_for_status()
            default_branch = response.json().get("default_branch")
            return f"https://github.com/{owner}/{repo}/archive/refs/heads/{default_branch}.zip"

    if matched := re.match(r"https?://(?:www\.)?github\.com/([\w.-]+)/([\w.-]+)/tree/([\w\\/.-]+)", url):
        owner, repo, branch = matched.groups()
        if branch[-1] == "/":
            branch = branch[:-1]
        return f"https://github.com/{owner}/{repo}/archive/refs/heads/{branch}.zip"

    if matched := re.match(r"https?://(?:www\.)?github\.com/([\w.-]+)/([\w.-]+)/releases/tag/([\w\\/.-]+)", url):
        owner, repo, tag = matched.groups()
        if tag[-1] == "/":
            tag = tag[:-1]
        return f"https://github.com/{owner}/{repo}/archive/refs/tags/{tag}.zip"

    if matched := re.match(r"https?://(?:www\.)?github\.com/([\w.-]+)/([\w.-]+)/commit/(\w+)/?$", url):
        owner, repo, commit = matched.groups()
        return f"https://github.com/{owner}/{repo}/archive/{commit}.zip"

    return url


async def load_bundles_from_urls() -> tuple[list[TemporaryDirectory], list[str]]:
    component_paths: set[str] = set()
    temp_dirs = []
    settings_service = get_settings_service()
    bundle_urls = settings_service.settings.bundle_urls
    if not bundle_urls:
        return [], []
    if not settings_service.auth_settings.AUTO_LOGIN:
        logger.warning("AUTO_LOGIN is disabled, not loading flows from URLs")

    async with session_scope() as session:
        user = await get_user_by_username(session, settings_service.auth_settings.SUPERUSER)
        if user is None:
            msg = "Superuser not found in the database"
            raise NoResultFound(msg)
        user_id = user.id

        for url in bundle_urls:
            url_ = await detect_github_url(url)

            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.get(url_)
                response.raise_for_status()

            with zipfile.ZipFile(io.BytesIO(response.content)) as zfile:
                dir_names = [f.filename for f in zfile.infolist() if f.is_dir() and "/" not in f.filename[:-1]]
                temp_dir = None
                for filename in zfile.namelist():
                    path = Path(filename)
                    for dir_name in dir_names:
                        if (
                            settings_service.auth_settings.AUTO_LOGIN
                            and path.is_relative_to(f"{dir_name}flows/")
                            and path.suffix == ".json"
                        ):
                            file_content = zfile.read(filename)
                            await upsert_flow_from_file(file_content, path.stem, session, user_id)
                        elif path.is_relative_to(f"{dir_name}components/"):
                            if temp_dir is None:
                                temp_dir = await asyncio.to_thread(TemporaryDirectory)
                                temp_dirs.append(temp_dir)
                            component_paths.add(str(Path(temp_dir.name) / f"{dir_name}components"))
                            await asyncio.to_thread(zfile.extract, filename, temp_dir.name)

    return temp_dirs, list(component_paths)


async def upsert_flow_from_file(file_content: AnyStr, filename: str, session: AsyncSession, user_id: UUID) -> None:
    flow = orjson.loads(file_content)
    flow_endpoint_name = flow.get("endpoint_name")
    if _is_valid_uuid(filename):
        flow["id"] = filename
    flow_id = flow.get("id")

    if isinstance(flow_id, str):
        try:
            flow_id = UUID(flow_id)
        except ValueError:
            logger.error(f"Invalid UUID string: {flow_id}")
            return

    existing = await find_existing_flow(session, flow_id, flow_endpoint_name)
    if existing:
        logger.debug(f"Found existing flow: {existing.name}")
        logger.info(f"Updating existing flow: {flow_id} with endpoint name {flow_endpoint_name}")
        for key, value in flow.items():
            if hasattr(existing, key):
                # flow dict from json and db representation are not 100% the same
                setattr(existing, key, value)
        existing.updated_at = datetime.now(tz=timezone.utc).astimezone()
        existing.user_id = user_id

        # Ensure that the flow is associated with an existing default folder
        if existing.folder_id is None:
            folder_id = await get_or_create_default_folder(session, user_id)
            existing.folder_id = folder_id

        if isinstance(existing.id, str):
            try:
                existing.id = UUID(existing.id)
            except ValueError:
                logger.error(f"Invalid UUID string: {existing.id}")
                return

        session.add(existing)
    else:
        logger.info(f"Creating new flow: {flow_id} with endpoint name {flow_endpoint_name}")

        # Assign the newly created flow to the default folder
        folder = await get_or_create_default_folder(session, user_id)
        flow["user_id"] = user_id
        flow["folder_id"] = folder.id
        flow = Flow.model_validate(flow)
        flow.updated_at = datetime.now(tz=timezone.utc).astimezone()

        session.add(flow)


async def find_existing_flow(session, flow_id, flow_endpoint_name):
    if flow_endpoint_name:
        logger.debug(f"flow_endpoint_name: {flow_endpoint_name}")
        stmt = select(Flow).where(Flow.endpoint_name == flow_endpoint_name)
        if existing := (await session.exec(stmt)).first():
            logger.debug(f"Found existing flow by endpoint name: {existing.name}")
            return existing

    stmt = select(Flow).where(Flow.id == flow_id)
    if existing := (await session.exec(stmt)).first():
        logger.debug(f"Found existing flow by id: {flow_id}")
        return existing
    return None


async def create_or_update_starter_projects(all_types_dict: dict) -> None:
    """Create or update starter projects.

    Args:
        all_types_dict (dict): Dictionary containing all component types and their templates
    """
    if not get_settings_service().settings.create_starter_projects:
        # no-op for environments that don't want to create starter projects.
        # note that this doesn't check if the starter projects are already loaded in the db;
        # this is intended to be used to skip all startup project logic.
        return

    async with session_scope() as session:
        new_folder = await get_or_create_starter_folder(session)
        starter_projects = await load_starter_projects()

        if get_settings_service().settings.update_starter_projects:
            logger.debug("Updating starter projects")
            # 1. Delete all existing starter projects
            successfully_updated_projects = 0
            await delete_starter_projects(session, new_folder.id)
            await copy_profile_pictures()

            # 2. Update all starter projects with the latest component versions (this modifies the actual file data)
            for project_path, project in starter_projects:
                (
                    project_name,
                    project_description,
                    project_is_component,
                    updated_at_datetime,
                    project_data,
                    project_icon,
                    project_icon_bg_color,
                    project_gradient,
                    project_tags,
                ) = get_project_data(project)
                updated_project_data = update_projects_components_with_latest_component_versions(
                    project_data.copy(), all_types_dict
                )
                updated_project_data = update_edges_with_latest_component_versions(updated_project_data)
                if updated_project_data != project_data:
                    project_data = updated_project_data
                    await update_project_file(project_path, project, updated_project_data)

                try:
                    # Create the updated starter project
                    create_new_project(
                        session=session,
                        project_name=project_name,
                        project_description=project_description,
                        project_is_component=project_is_component,
                        updated_at_datetime=updated_at_datetime,
                        project_data=project_data,
                        project_icon=project_icon,
                        project_icon_bg_color=project_icon_bg_color,
                        project_gradient=project_gradient,
                        project_tags=project_tags,
                        new_folder_id=new_folder.id,
                    )
                except Exception:  # noqa: BLE001
                    logger.exception(f"Error while creating starter project {project_name}")

                successfully_updated_projects += 1
            logger.debug(f"Successfully updated {successfully_updated_projects} starter projects")
        else:
            # Even if we're not updating starter projects, we still need to create any that don't exist
            logger.debug("Creating new starter projects")
            successfully_created_projects = 0
            existing_flows = await get_all_flows_similar_to_project(session, new_folder.id)
            existing_flow_names = [existing_flow.name for existing_flow in existing_flows]
            for _, project in starter_projects:
                (
                    project_name,
                    project_description,
                    project_is_component,
                    updated_at_datetime,
                    project_data,
                    project_icon,
                    project_icon_bg_color,
                    project_gradient,
                    project_tags,
                ) = get_project_data(project)
                if project_name not in existing_flow_names:
                    try:
                        create_new_project(
                            session=session,
                            project_name=project_name,
                            project_description=project_description,
                            project_is_component=project_is_component,
                            updated_at_datetime=updated_at_datetime,
                            project_data=project_data,
                            project_icon=project_icon,
                            project_icon_bg_color=project_icon_bg_color,
                            project_gradient=project_gradient,
                            project_tags=project_tags,
                            new_folder_id=new_folder.id,
                        )
                    except Exception:  # noqa: BLE001
                        logger.exception(f"Error while creating starter project {project_name}")
                    successfully_created_projects += 1
                logger.debug(f"Successfully created {successfully_created_projects} starter projects")


async def initialize_super_user_if_needed() -> None:
    settings_service = get_settings_service()
    if not settings_service.auth_settings.AUTO_LOGIN:
        return
    username = settings_service.auth_settings.SUPERUSER
    password = settings_service.auth_settings.SUPERUSER_PASSWORD
    if not username or not password:
        msg = "SUPERUSER and SUPERUSER_PASSWORD must be set in the settings if AUTO_LOGIN is true."
        raise ValueError(msg)

    async with session_scope() as async_session:
        super_user = await create_super_user(db=async_session, username=username, password=password)
        await get_variable_service().initialize_user_variables(super_user.id, async_session)
        _ = await get_or_create_default_folder(async_session, super_user.id)
    logger.debug("Super user initialized")


async def get_or_create_default_folder(session: AsyncSession, user_id: UUID) -> FolderRead:
    """Ensure the default folder exists for the given user_id. If it doesn't exist, create it.

    Uses an idempotent insertion approach to handle concurrent creation gracefully.

    This implementation avoids an external distributed lock and works with both SQLite and PostgreSQL.

    Args:
        session (AsyncSession): The active database session.
        user_id (UUID): The ID of the user who owns the folder.

    Returns:
        UUID: The ID of the default folder.
    """
    stmt = select(Folder).where(Folder.user_id == user_id, Folder.name == DEFAULT_FOLDER_NAME)
    result = await session.exec(stmt)
    folder = result.first()
    if folder:
        return FolderRead.model_validate(folder, from_attributes=True)

    try:
        folder_obj = Folder(user_id=user_id, name=DEFAULT_FOLDER_NAME)
        session.add(folder_obj)
        await session.commit()
        await session.refresh(folder_obj)
    except sa.exc.IntegrityError as e:
        # Another worker may have created the folder concurrently.
        await session.rollback()
        result = await session.exec(stmt)
        folder = result.first()
        if folder:
            return FolderRead.model_validate(folder, from_attributes=True)
        msg = "Failed to get or create default folder"
        raise ValueError(msg) from e
    return FolderRead.model_validate(folder_obj, from_attributes=True)


async def sync_flows_from_fs():
    flow_mtimes = {}
    fs_flows_polling_interval = get_settings_service().settings.fs_flows_polling_interval / 1000
    try:
        while True:
            try:
                async with session_scope() as session:
                    stmt = select(Flow).where(col(Flow.fs_path).is_not(None))
                    flows = (await session.exec(stmt)).all()
                    for flow in flows:
                        mtime = flow_mtimes.setdefault(flow.id, 0)
                        path = anyio.Path(flow.fs_path)
                        try:
                            if await path.exists():
                                new_mtime = (await path.stat()).st_mtime
                                if new_mtime > mtime:
                                    update_data = orjson.loads(await path.read_text(encoding="utf-8"))
                                    try:
                                        for field_name in ("name", "description", "data", "locked"):
                                            if new_value := update_data.get(field_name):
                                                setattr(flow, field_name, new_value)
                                        if folder_id := update_data.get("folder_id"):
                                            flow.folder_id = UUID(folder_id)
                                        await session.commit()
                                        await session.refresh(flow)
                                    except Exception:  # noqa: BLE001
                                        logger.exception(f"Couldn't update flow {flow.id} in database from path {path}")
                                    flow_mtimes[flow.id] = new_mtime
                        except Exception:  # noqa: BLE001
                            logger.exception(f"Error while handling flow file {path}")
            except asyncio.CancelledError:
                logger.debug("Flow sync cancelled")
                break
            except (sa.exc.OperationalError, ValueError) as e:
                if "no active connection" in str(e) or "connection is closed" in str(e):
                    logger.debug("Database connection lost, assuming shutdown")
                    break  # Exit gracefully, don't error
                raise  # Re-raise if it's a real connection problem
            except Exception:
                logger.exception("Error while syncing flows from database")
                break

            await asyncio.sleep(fs_flows_polling_interval)
    except asyncio.CancelledError:
        logger.debug("Flow sync task cancelled")
