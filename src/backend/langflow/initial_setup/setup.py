from datetime import datetime
from pathlib import Path

import orjson
from loguru import logger
from sqlmodel import select

from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import session_scope

STARTER_FOLDER_NAME = "Starter Projects"


# In the folder ./starter_projects we have a few JSON files that represent
# starter projects. We want to load these into the database so that users
# can use them as a starting point for their own projects.


def load_starter_projects():
    starter_projects = []
    folder = Path(__file__).parent / "starter_projects"
    for file in folder.glob("*.json"):
        project = orjson.loads(file.read_text())
        starter_projects.append(project)
        logger.info(f"Loaded starter project {file}")
    return starter_projects


def get_project_data(project):
    project_name = project.get("name")
    project_description = project.get("description")
    project_is_component = project.get("is_component")
    project_updated_at = project.get("updated_at")
    updated_at_datetime = datetime.strptime(project_updated_at, "%Y-%m-%dT%H:%M:%S.%f")
    project_data = project.get("data")
    project_icon = project.get("icon")
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
    logger.info(f"Creating starter project {project_name}")
    new_project = Flow(
        name=project_name,
        description=project_description,
        is_component=project_is_component,
        updated_at=updated_at_datetime,
        folder=STARTER_FOLDER_NAME,
        data=project_data,
        icon=project_icon,
        icon_bg_color=project_icon_bg_color,
    )
    session.add(new_project)


def create_or_update_starter_projects():
    with session_scope() as session:
        starter_projects = load_starter_projects()
        for project in starter_projects:
            (
                project_name,
                project_description,
                project_is_component,
                updated_at_datetime,
                project_data,
                project_icon,
                project_icon_bg_color,
            ) = get_project_data(project)
            if project_name and project_data:
                existing_project = session.exec(
                    select(Flow).where(
                        Flow.name == project_name, Flow.folder == STARTER_FOLDER_NAME
                    )
                ).first()
                if existing_project:
                    update_existing_project(
                        existing_project,
                        project_name,
                        project_description,
                        project_is_component,
                        updated_at_datetime,
                        project_data,
                        project_icon,
                        project_icon_bg_color,
                    )
                else:
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
