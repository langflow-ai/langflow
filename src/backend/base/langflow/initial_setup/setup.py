import copy
import json
import shutil
import time
from collections import defaultdict
from collections.abc import Awaitable
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import orjson
from emoji import demojize, purely_emoji
from loguru import logger
from sqlalchemy.exc import NoResultFound
from sqlmodel import select

from langflow.base.constants import (
    FIELD_FORMAT_ATTRIBUTES,
    NODE_FORMAT_ATTRIBUTES,
    ORJSON_OPTIONS,
)
from langflow.graph.graph.base import Graph
from langflow.services.auth.utils import create_super_user
from langflow.services.database.models.flow.model import Flow, FlowCreate
from langflow.services.database.models.folder.model import Folder, FolderCreate
from langflow.services.database.models.folder.utils import (
    create_default_folder_if_it_doesnt_exist,
    get_default_folder_id,
)
from langflow.services.database.models.user.crud import get_user_by_username
from langflow.services.deps import (
    get_settings_service,
    get_storage_service,
    get_variable_service,
    session_scope,
)
from langflow.template.field.prompt import DEFAULT_PROMPT_INTUT_TYPES
from langflow.utils.util import escape_json_dump

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
    all_types_dict_flat = {}
    for category in all_types_dict.values():
        for component in category.values():
            all_types_dict_flat[component["display_name"]] = component
    node_changes_log = defaultdict(list)
    project_data_copy = deepcopy(project_data)
    for node in project_data_copy.get("nodes", []):
        node_data = node.get("data").get("node")
        if node_data.get("display_name") in all_types_dict_flat:
            latest_node = all_types_dict_flat.get(node_data.get("display_name"))
            latest_template = latest_node.get("template")
            node_data["template"]["code"] = latest_template["code"]

            if "outputs" in latest_node:
                node_data["outputs"] = latest_node["outputs"]
            if node_data["template"]["_type"] != latest_template["_type"]:
                node_data["template"]["_type"] = latest_template["_type"]
                if node_data.get("display_name") != "Prompt":
                    node_data["template"] = latest_template
                else:
                    for key, value in latest_template.items():
                        if key not in node_data["template"]:
                            node_changes_log[node_data["display_name"]].append(
                                {
                                    "attr": key,
                                    "old_value": None,
                                    "new_value": value,
                                }
                            )
                            node_data["template"][key] = value
                        elif isinstance(value, dict) and value.get("value"):
                            node_changes_log[node_data["display_name"]].append(
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
                node_changes_log[node_data["display_name"]].append(
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
                        node_data["template"][field_name] = field_dict
                        continue
                    # The idea here is to update some attributes of the field
                    to_check_attributes = FIELD_FORMAT_ATTRIBUTES
                    for attr in to_check_attributes:
                        if (
                            attr in field_dict
                            and attr in node_data["template"].get(field_name)
                            # Check if it needs to be updated
                            and field_dict[attr] != node_data["template"][field_name][attr]
                        ):
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


def scape_json_parse(json_string: str) -> dict:
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
            _id = new_source_handle["id"]
            source_node_index = next((index for (index, d) in enumerate(nodes) if d["id"] == _id), -1)
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
    edge_changes_log = defaultdict(list)
    project_data_copy = deepcopy(project_data)
    for edge in project_data_copy.get("edges", []):
        source_handle = edge.get("data").get("sourceHandle")
        source_handle = scape_json_parse(source_handle)
        target_handle = edge.get("data").get("targetHandle")
        target_handle = scape_json_parse(target_handle)
        # Now find the source and target nodes in the nodes list
        source_node = next(
            (node for node in project_data.get("nodes", []) if node.get("id") == edge.get("source")),
            None,
        )
        target_node = next(
            (node for node in project_data.get("nodes", []) if node.get("id") == edge.get("target")),
            None,
        )
        if source_node and target_node:
            source_node_data = source_node.get("data").get("node")
            target_node_data = target_node.get("data").get("node")
            output_data = next(
                (output for output in source_node_data.get("outputs", []) if output["name"] == source_handle["name"]),
                None,
            )
            if not output_data:
                output_data = next(
                    (
                        output
                        for output in source_node_data.get("outputs", [])
                        if output["display_name"] == source_handle["name"]
                    ),
                    None,
                )
                if output_data:
                    source_handle["name"] = output_data["name"]
            if output_data:
                if len(output_data.get("types")) == 1:
                    new_output_types = output_data.get("types")
                elif output_data.get("selected"):
                    new_output_types = [output_data.get("selected")]
                else:
                    new_output_types = []
            else:
                new_output_types = []

            if source_handle["output_types"] != new_output_types:
                edge_changes_log[source_node_data["display_name"]].append(
                    {
                        "attr": "output_types",
                        "old_value": source_handle["output_types"],
                        "new_value": new_output_types,
                    }
                )
                source_handle["output_types"] = new_output_types

            field_name = target_handle.get("fieldName")
            if field_name in target_node_data.get("template") and target_handle["inputTypes"] != target_node_data.get(
                "template"
            ).get(field_name).get("input_types"):
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
            try:
                old_escape_source_handle = escape_json_dump(json.loads(edge["sourceHandle"]))

            except json.JSONDecodeError:
                old_escape_source_handle = edge["sourceHandle"]

            try:
                old_escape_target_handle = escape_json_dump(json.loads(edge["targetHandle"]))
            except json.JSONDecodeError:
                old_escape_target_handle = edge["targetHandle"]
            if old_escape_source_handle != escaped_source_handle:
                edge_changes_log[source_node_data["display_name"]].append(
                    {
                        "attr": "sourceHandle",
                        "old_value": old_escape_source_handle,
                        "new_value": escaped_source_handle,
                    }
                )
                edge["sourceHandle"] = escaped_source_handle
            if old_escape_target_handle != escaped_target_handle:
                edge_changes_log[target_node_data["display_name"]].append(
                    {
                        "attr": "targetHandle",
                        "old_value": old_escape_target_handle,
                        "new_value": escaped_target_handle,
                    }
                )
                edge["targetHandle"] = escaped_target_handle

        else:
            logger.error(f"Source or target node not found for edge: {edge}")
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


def load_starter_projects(retries=3, delay=1) -> list[tuple[Path, dict]]:
    starter_projects = []
    folder = Path(__file__).parent / "starter_projects"
    for file in folder.glob("*.json"):
        attempt = 0
        while attempt < retries:
            content = file.read_text(encoding="utf-8")
            try:
                project = orjson.loads(content)
                starter_projects.append((file, project))
                logger.info(f"Loaded starter project {file}")
                break  # Break if load is successful
            except orjson.JSONDecodeError as e:
                attempt += 1
                if attempt >= retries:
                    msg = f"Error loading starter project {file}: {e}"
                    raise ValueError(msg) from e
                time.sleep(delay)  # Wait before retrying
    return starter_projects


def copy_profile_pictures() -> None:
    config_dir = get_storage_service().settings_service.settings.config_dir
    if config_dir is None:
        msg = "Config dir is not set in the settings"
        raise ValueError(msg)
    origin = Path(__file__).parent / "profile_pictures"
    target = Path(config_dir) / "profile_pictures"

    if not origin.exists():
        msg = f"The source folder '{origin}' does not exist."
        raise ValueError(msg)

    if not target.exists():
        target.mkdir(parents=True)

    try:
        shutil.copytree(origin, target, dirs_exist_ok=True)
        logger.debug(f"Folder copied from '{origin}' to '{target}'")

    except Exception:  # noqa: BLE001
        logger.exception("Error copying the folder")


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


def update_project_file(project_path: Path, project: dict, updated_project_data) -> None:
    project["data"] = updated_project_data
    project_path.write_text(orjson.dumps(project, option=ORJSON_OPTIONS).decode(), encoding="utf-8")
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
        gradient=project_gradient,
        tags=project_tags,
    )
    db_flow = Flow.model_validate(new_project, from_attributes=True)
    session.add(db_flow)


def get_all_flows_similar_to_project(session, folder_id):
    return session.exec(select(Folder).where(Folder.id == folder_id)).first().flows


def delete_start_projects(session, folder_id) -> None:
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
    return session.exec(select(Folder).where(Folder.name == STARTER_FOLDER_NAME)).first()


def _is_valid_uuid(val):
    try:
        uuid_obj = UUID(val)
    except ValueError:
        return False
    return str(uuid_obj) == val


def load_flows_from_directory() -> None:
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

    with session_scope() as session:
        user = get_user_by_username(session, settings_service.auth_settings.SUPERUSER)
        if user is None:
            msg = "Superuser not found in the database"
            raise NoResultFound(msg)
        user_id = user.id
        _flows_path = Path(flows_path)
        files = [f for f in _flows_path.iterdir() if f.is_file()]
        for f in files:
            if f.suffix != ".json":
                continue
            logger.info(f"Loading flow from file: {f.name}")
            content = f.read_text(encoding="utf-8")
            flow = orjson.loads(content)
            no_json_name = f.stem
            flow_endpoint_name = flow.get("endpoint_name")
            if _is_valid_uuid(no_json_name):
                flow["id"] = no_json_name
            flow_id = flow.get("id")

            existing = find_existing_flow(session, flow_id, flow_endpoint_name)
            if existing:
                logger.debug(f"Found existing flow: {existing.name}")
                logger.info(f"Updating existing flow: {flow_id} with endpoint name {flow_endpoint_name}")
                for key, value in flow.items():
                    if hasattr(existing, key):
                        # flow dict from json and db representation are not 100% the same
                        setattr(existing, key, value)
                existing.updated_at = datetime.now(tz=timezone.utc).astimezone()
                existing.user_id = user_id

                # Generally, folder_id should not be None, but we must check this due to the previous
                # behavior where flows could be added and folder_id was None, orphaning
                # them within Langflow.
                if existing.folder_id is None:
                    folder_id = get_default_folder_id(session, user_id)
                    existing.folder_id = folder_id

                session.add(existing)
            else:
                logger.info(f"Creating new flow: {flow_id} with endpoint name {flow_endpoint_name}")

                # Current behavior loads all new flows into default folder
                folder_id = get_default_folder_id(session, user_id)

                flow["user_id"] = user_id
                flow["folder_id"] = folder_id
                flow = Flow.model_validate(flow, from_attributes=True)
                flow.updated_at = datetime.now(tz=timezone.utc).astimezone()
                session.add(flow)


def find_existing_flow(session, flow_id, flow_endpoint_name):
    if flow_endpoint_name:
        logger.debug(f"flow_endpoint_name: {flow_endpoint_name}")
        stmt = select(Flow).where(Flow.endpoint_name == flow_endpoint_name)
        if existing := session.exec(stmt).first():
            logger.debug(f"Found existing flow by endpoint name: {existing.name}")
            return existing
    stmt = select(Flow).where(Flow.id == flow_id)
    if existing := session.exec(stmt).first():
        logger.debug(f"Found existing flow by id: {flow_id}")
        return existing
    return None


async def create_or_update_starter_projects(get_all_components_coro: Awaitable[dict]) -> None:
    try:
        all_types_dict = await get_all_components_coro
    except Exception:
        logger.exception("Error loading components")
        raise
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
                project_gradient,
                project_tags,
            ) = get_project_data(project)
            updated_project_data = update_projects_components_with_latest_component_versions(
                project_data.copy(), all_types_dict
            )
            updated_project_data = update_edges_with_latest_component_versions(updated_project_data)
            try:
                Graph.from_payload(updated_project_data)
            except Exception:  # noqa: BLE001
                logger.exception(f"Error loading project {project_name}")
            if updated_project_data != project_data:
                project_data = updated_project_data
                # We also need to update the project data in the file

                update_project_file(project_path, project, updated_project_data)
            if project_name and project_data:
                for existing_project in get_all_flows_similar_to_project(session, new_folder.id):
                    session.delete(existing_project)

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


def initialize_super_user_if_needed() -> None:
    settings_service = get_settings_service()
    if not settings_service.auth_settings.AUTO_LOGIN:
        return
    username = settings_service.auth_settings.SUPERUSER
    password = settings_service.auth_settings.SUPERUSER_PASSWORD
    if not username or not password:
        msg = "SUPERUSER and SUPERUSER_PASSWORD must be set in the settings if AUTO_LOGIN is true."
        raise ValueError(msg)

    with session_scope() as session:
        super_user = create_super_user(db=session, username=username, password=password)
        get_variable_service().initialize_user_variables(super_user.id, session)
        create_default_folder_if_it_doesnt_exist(session, super_user.id)
        logger.info("Super user initialized")
