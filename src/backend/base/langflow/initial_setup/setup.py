from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import orjson
from emoji import demojize, purely_emoji  # type: ignore
from loguru import logger
from sqlmodel import select

from langflow.base.constants import FIELD_FORMAT_ATTRIBUTES, NODE_FORMAT_ATTRIBUTES
from langflow.interface.types import get_all_components
from langflow.services.database.models.flow.model import Flow, FlowCreate
from langflow.services.deps import get_settings_service, session_scope

STARTER_FOLDER_NAME = "Starter Projects"


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
    log_node_changes(node_changes_log)
    return project_data_copy


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
        f.write(orjson.dumps(project, option=orjson.OPT_INDENT_2).decode())
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
        folder=STARTER_FOLDER_NAME,
    )
    db_flow = Flow.model_validate(new_project, from_attributes=True)
    session.add(db_flow)


def get_all_flows_similar_to_project(session, project_name):
    flows = session.exec(
        select(Flow).where(
            Flow.name == project_name,
            Flow.folder == STARTER_FOLDER_NAME,
        )
    ).all()
    return flows


def delete_start_projects(session):
    flows = session.exec(
        select(Flow).where(
            Flow.folder == STARTER_FOLDER_NAME,
        )
    ).all()
    for flow in flows:
        session.delete(flow)
    session.commit()


def create_or_update_starter_projects():
    components_paths = get_settings_service().settings.COMPONENTS_PATH
    try:
        all_types_dict = get_all_components(components_paths, as_dict=True)
    except Exception as e:
        logger.exception(f"Error loading components: {e}")
        raise e
    with session_scope() as session:
        starter_projects = load_starter_projects()
        delete_start_projects(session)
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
            if updated_project_data != project_data:
                project_data = updated_project_data
                # We also need to update the project data in the file

                update_project_file(project_path, project, updated_project_data)
            if project_name and project_data:
                for existing_project in get_all_flows_similar_to_project(session, project_name):
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
                )
