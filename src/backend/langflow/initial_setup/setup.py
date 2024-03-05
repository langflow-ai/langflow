import json
from datetime import datetime
from pathlib import Path

from loguru import logger
from sqlmodel import select

from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import get_session

STARTER_FOLDER_NAME = "Starter Projects"


# In the folder ./starter_projects we have a few JSON files that represent
# starter projects. We want to load these into the database so that users
# can use them as a starting point for their own projects.
def load_starter_projects():
    # Load the starter projects from the JSON files
    # using Pathlib's glob method
    starter_projects = []
    folder = Path(__file__).parent / "starter_projects"
    for file in folder.glob("*.json"):
        with open(file, "r") as f:
            starter_projects.append(json.load(f))
            logger.info(f"Loaded starter project {file}")
    return starter_projects


# We want to load the starter projects into the database
def create_or_update_starter_projects():
    session = next(get_session())
    starter_projects = load_starter_projects()
    for project in starter_projects:
        # Check if the project already exists in the database
        project_name = project.get("name")
        project_description = project.get("description")
        project_is_component = project.get("is_component")
        project_updated_at = project.get("updated_at")
        # 2024-03-05T21:59:59.738081
        updated_at_datetime = datetime.strptime(
            project_updated_at, "%Y-%m-%dT%H:%M:%S.%f"
        )
        project_data = project.get("data")
        if project_name and project_data:
            existing_project = session.exec(
                select(Flow).where(
                    Flow.name == project_name, Flow.folder == STARTER_FOLDER_NAME
                )
            ).first()
            if existing_project:
                logger.info(f"Updating starter project {project_name}")
                existing_project.data = project_data
                existing_project.folder = STARTER_FOLDER_NAME
                existing_project.description = project_description
                existing_project.is_component = project_is_component
                existing_project.updated_at = updated_at_datetime
                # Now we need to update the project in the database
                session.add(existing_project)
            else:
                logger.info(f"Creating starter project {project_name}")
                session.add(
                    Flow(
                        name=project_name,
                        description=project_description,
                        is_component=project_is_component,
                        updated_at=updated_at_datetime,
                        folder=STARTER_FOLDER_NAME,
                        data=project_data,
                    )
                )
    session.commit()
    session.close()
    logger.info("Starter projects loaded into database")
