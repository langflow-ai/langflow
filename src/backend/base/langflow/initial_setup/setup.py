import json
import logging
import os
import shutil
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import orjson
from emoji import demojize, purely_emoji  # type: ignore
from loguru import logger
from sqlmodel import select

from langflow.base.constants import FIELD_FORMAT_ATTRIBUTES, NODE_FORMAT_ATTRIBUTES, ORJSON_OPTIONS
from langflow.interface.types import get_all_components
from langflow.services.auth.utils import create_super_user
from langflow.services.database.models.flow.model import Flow, FlowCreate
from langflow.services.database.models.folder.model import Folder, FolderCreate
from langflow.services.database.models.folder.utils import create_default_folder_if_it_doesnt_exist
from langflow.services.database.models.user.crud import get_user_by_username
from langflow.services.deps import get_settings_service, get_storage_service, get_variable_service, session_scope

STARTER_FOLDER_NAME = "Starter Projects"
STARTER_FOLDER_DESCRIPTION = "Starter projects to help you get started in Langflow."

# In the folder ./starter_projects we have a few JSON files that represent
# starter projects. We want to load these into the database so that users
# can use them as a starting point for their own projects.


def update_projects_components_with_latest_component_versions(project_data, all_types_dict):
    # project data has a nodes key, which is a list of nodes
    # we want to run through each node and see if it exists in the all_types_dict
    # if so, we go into  the template key and also get the template from all_types_dict
    # and update it all
    node_changes_log = defaultdict(list)
    project_data_copy = deepcopy(project_data)
    for node in project_data_copy.get("nodes", []):
        node_data = node.get("data").get("node")
        if node_data.get("display_name") in all_types_dict:
            latest_node = all_types_dict.get(node_data.get("display_name"))
            latest_template = latest_node.get("template")
            node_data["template"]["code"] = latest_template["code"]

            for attr in NODE_FORMAT_ATTRIBUTES:
                if attr in latest_node:
                    # Check if it needs to be updated
                    if latest_node[attr] != node_data.get(attr):
                        node_changes_log[node_data["display_name"]].append(
                            {
                                "attr": attr,
                                "old_value": node_data.get(attr),
                                "new_value": latest_node[attr],
                            }
                        )
                        node_data[attr] = latest_node[attr]

            for field_name, field_dict in latest_template.items():
                if field_name not in node_data["template"]:
                    continue
                # The idea here is to update some attributes of the field
                for attr in FIELD_FORMAT_ATTRIBUTES:
                    if attr in field_dict and attr in node_data["template"].get(field_name):
                        # Check if it needs to be updated
                        if field_dict[attr] != node_data["template"][field_name][attr]:
                            node_changes_log[node_data["display_name"]].append(
                                {
                                    "attr": f"{field_name}.{attr}",
                                    "old_value": node_data["template"][field_name][attr],
                                    "new_value": field_dict[attr],
                                }
                            )
                            node_data["template"][field_name][attr] = field_dict[attr]
            # Remove fields that are not in the latest template
            if node_data.get("display_name") != "Prompt":
                for field_name in list(node_data["template"].keys()):
                    if field_name not in latest_template:
                        node_data["template"].pop(field_name)
    log_node_changes(node_changes_log)
    return project_data_copy


def update_edges_with_latest_component_versions(project_data):
    edge_changes_log = defaultdict(list)
    project_data_copy = deepcopy(project_data)
    for edge in project_data_copy.get("edges", []):
        source_handle = edge.get("data").get("sourceHandle")
        target_handle = edge.get("data").get("targetHandle")
        # Now find the source and target nodes in the nodes list
        source_node = next(
            (node for node in project_data.get("nodes", []) if node.get("id") == edge.get("source")), None
        )
        target_node = next(
            (node for node in project_data.get("nodes", []) if node.get("id") == edge.get("target")), None
        )
        if source_node and target_node:
            source_node_data = source_node.get("data").get("node")
            target_node_data = target_node.get("data").get("node")
            new_base_classes = source_node_data.get("base_classes")
            if source_handle["baseClasses"] != new_base_classes:
                edge_changes_log[source_node_data["display_name"]].append(
                    {
                        "attr": "baseClasses",
                        "old_value": source_handle["baseClasses"],
                        "new_value": new_base_classes,
                    }
                )
                source_handle["baseClasses"] = new_base_classes

            field_name = target_handle.get("fieldName")
            if field_name in target_node_data.get("template"):
                if target_handle["inputTypes"] != target_node_data.get("template").get(field_name).get("input_types"):
                    edge_changes_log[target_node_data["display_name"]].append(
                        {
                            "attr": "inputTypes",
                            "old_value": target_handle["inputTypes"],
                            "new_value": target_node_data.get("template").get(field_name).get("input_types"),
                        }
                    )
                    target_handle["inputTypes"] = target_node_data.get("template").get(field_name).get("input_types")
            escaped_source_handle = escape_json_dump(source_handle)
            escaped_target_handle = escape_json_dump(target_handle)
            if edge["sourceHandle"] != escaped_source_handle:
                edge_changes_log[source_node_data["display_name"]].append(
                    {
                        "attr": "sourceHandle",
                        "old_value": edge["sourceHandle"],
                        "new_value": escaped_source_handle,
                    }
                )
                edge["sourceHandle"] = escaped_source_handle
            if edge["targetHandle"] != escaped_target_handle:
                edge_changes_log[target_node_data["display_name"]].append(
                    {
                        "attr": "targetHandle",
                        "old_value": edge["targetHandle"],
                        "new_value": escaped_target_handle,
                    }
                )
                edge["targetHandle"] = escaped_target_handle

        else:
            logger.error(f"Source or target node not found for edge: {edge}")
    log_node_changes(edge_changes_log)
    return project_data_copy


def escape_json_dump(edge_dict):
    return json.dumps(edge_dict).replace('"', "œ")


def log_node_changes(node_changes_log):
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


def load_starter_projects() -> list[tuple[Path, dict]]:
    starter_projects = []
    folder = Path(__file__).parent / "starter_projects"
    for file in folder.glob("*.json"):
        project = orjson.loads(file.read_text(encoding="utf-8"))
        starter_projects.append((file, project))
        logger.info(f"Loaded starter project {file}")
    return starter_projects


def copy_profile_pictures():
    config_dir = get_storage_service().settings_service.settings.config_dir
    origin = Path(__file__).parent / "profile_pictures"
    target = Path(config_dir) / "profile_pictures"

    if not os.path.exists(origin):
        raise ValueError(f"The source folder '{origin}' does not exist.")

    if not os.path.exists(target):
        os.makedirs(target)

    try:
        shutil.copytree(origin, target, dirs_exist_ok=True)
        logger.debug(f"Folder copied from '{origin}' to '{target}'")

    except Exception as e:
        logger.error(f"Error copying the folder: {e}")


def get_project_data(project):
    project_name = project.get("name")
    project_description = project.get("description")
    project_is_component = project.get("is_component")
    project_updated_at = project.get("updated_at")
    if not project_updated_at:
        project_updated_at = datetime.now(tz=timezone.utc).isoformat()
        updated_at_datetime = datetime.strptime(project_updated_at, "%Y-%m-%dT%H:%M:%S.%f%z")
    else:
        updated_at_datetime = datetime.strptime(project_updated_at, "%Y-%m-%dT%H:%M:%S.%f")
    project_data = project.get("data")
    project_icon = project.get("icon")
    if project_icon and purely_emoji(project_icon):
        project_icon = demojize(project_icon)
    else:
        project_icon = ""
    project_icon_bg_color = project.get("icon_bg_color")
    return (
        project_name,
        project_description,
        project_is_component,
        updated_at_datetime,
        project_data,
        project_icon,
        project_icon_bg_color,
    )


def update_project_file(project_path, project, updated_project_data):
    project["data"] = updated_project_data
    with open(project_path, "w", encoding="utf-8") as f:
        f.write(orjson.dumps(project, option=ORJSON_OPTIONS).decode())
    logger.info(f"Updated starter project {project['name']} file")


def update_existing_project(
    existing_project,
    project_name,
    project_description,
    project_is_component,
    updated_at_datetime,
    project_data,
    project_icon,
    project_icon_bg_color,
):
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
    project_icon,
    project_icon_bg_color,
    new_folder_id,
):
    logger.debug(f"Creating starter project {project_name}")
    new_project = FlowCreate(
        name=project_name,
        description=project_description,
        icon=project_icon,
        icon_bg_color=project_icon_bg_color,
        data=project_data,
        is_component=project_is_component,
        updated_at=updated_at_datetime,
        folder_id=new_folder_id,
    )
    db_flow = Flow.model_validate(new_project, from_attributes=True)
    session.add(db_flow)


def get_all_flows_similar_to_project(session, folder_id):
    flows = session.exec(select(Folder).where(Folder.id == folder_id)).first().flows
    return flows


def delete_start_projects(session, folder_id):
    flows = session.exec(select(Folder).where(Folder.id == folder_id)).first().flows
    for flow in flows:
        session.delete(flow)
    session.commit()


def folder_exists(session, folder_name):
    folder = session.exec(select(Folder).where(Folder.name == folder_name)).first()
    return folder is not None


def create_starter_folder(session):
    if not folder_exists(session, STARTER_FOLDER_NAME):
        new_folder = FolderCreate(name=STARTER_FOLDER_NAME, description=STARTER_FOLDER_DESCRIPTION)
        db_folder = Folder.model_validate(new_folder, from_attributes=True)
        session.add(db_folder)
        session.commit()
        session.refresh(db_folder)
        return db_folder
    else:
        return session.exec(select(Folder).where(Folder.name == STARTER_FOLDER_NAME)).first()


def _is_valid_uuid(val):
    try:
        uuid_obj = UUID(val)
    except ValueError:
        return False
    return str(uuid_obj) == val


def load_flows_from_directory():
    settings_service = get_settings_service()
    flows_path = settings_service.settings.load_flows_path
    if not flows_path:
        return
    if not settings_service.auth_settings.AUTO_LOGIN:
        logging.warning("AUTO_LOGIN is disabled, not loading flows from directory")
        return

    with session_scope() as session:
        user_id = get_user_by_username(session, settings_service.auth_settings.SUPERUSER).id
        files = [f for f in os.listdir(flows_path) if os.path.isfile(os.path.join(flows_path, f))]
        for filename in files:
            if not filename.endswith(".json"):
                continue
            logger.info(f"Loading flow from file: {filename}")
            with open(os.path.join(flows_path, filename), "r", encoding="utf-8") as file:
                flow = orjson.loads(file.read())
                no_json_name = filename.replace(".json", "")
                flow_endpoint_name = flow.get("endpoint_name")
                if _is_valid_uuid(no_json_name):
                    flow["id"] = no_json_name
                flow_id = flow.get("id")

                existing = find_existing_flow(session, flow_id, flow_endpoint_name)
                if existing:
                    logger.info(f"Updating existing flow: {flow_id} with endpoint name {flow_endpoint_name}")
                    for key, value in flow.items():
                        setattr(existing, key, value)
                    existing.updated_at = datetime.utcnow()
                    existing.user_id = user_id
                    session.add(existing)
                    session.commit()
                else:
                    logger.info(f"Creating new flow: {flow_id} with endpoint name {flow_endpoint_name}")
                    flow["user_id"] = user_id
                    flow = Flow.model_validate(flow, from_attributes=True)
                    flow.updated_at = datetime.utcnow()
                    session.add(flow)
                session.commit()


def find_existing_flow(session, flow_id, flow_endpoint_name):
    if flow_endpoint_name:
        stmt = select(Flow).where(Flow.endpoint_name == flow_endpoint_name)
        if existing := session.exec(stmt).first():
            return existing
    stmt = select(Flow).where(Flow.id == flow_id)
    if existing := session.exec(stmt).first():
        return existing
    return None


def create_or_update_starter_projects():
    components_paths = get_settings_service().settings.components_path
    try:
        all_types_dict = get_all_components(components_paths, as_dict=True)
    except Exception as e:
        logger.exception(f"Error loading components: {e}")
        raise e
    with session_scope() as session:
        new_folder = create_starter_folder(session)
        starter_projects = load_starter_projects()
        delete_start_projects(session, new_folder.id)
        copy_profile_pictures()
        for project_path, project in starter_projects:
            (
                project_name,
                project_description,
                project_is_component,
                updated_at_datetime,
                project_data,
                project_icon,
                project_icon_bg_color,
            ) = get_project_data(project)
            updated_project_data = update_projects_components_with_latest_component_versions(
                project_data, all_types_dict
            )
            updated_project_data = update_edges_with_latest_component_versions(updated_project_data)
            if updated_project_data != project_data:
                project_data = updated_project_data
                # We also need to update the project data in the file

                update_project_file(project_path, project, updated_project_data)
            if project_name and project_data:
                for existing_project in get_all_flows_similar_to_project(session, new_folder.id):
                    session.delete(existing_project)

                create_new_project(
                    session,
                    project_name,
                    project_description,
                    project_is_component,
                    updated_at_datetime,
                    project_data,
                    project_icon,
                    project_icon_bg_color,
                    new_folder.id,
                )


def initialize_super_user_if_needed():
    settings_service = get_settings_service()
    if not settings_service.auth_settings.AUTO_LOGIN:
        return
    username = settings_service.auth_settings.SUPERUSER
    password = settings_service.auth_settings.SUPERUSER_PASSWORD
    if not username or not password:
        raise ValueError("SUPERUSER and SUPERUSER_PASSWORD must be set in the settings if AUTO_LOGIN is true.")

    with session_scope() as session:
        super_user = create_super_user(db=session, username=username, password=password)
        get_variable_service().initialize_user_variables(super_user.id, session)
        create_default_folder_if_it_doesnt_exist(session, super_user.id)
        session.commit()
        logger.info("Super user initialized")
