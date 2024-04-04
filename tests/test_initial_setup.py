from datetime import datetime

import pytest
from langflow.graph.graph.base import Graph
from langflow.graph.schema import RunOutputs
from langflow.initial_setup.setup import (
    STARTER_FOLDER_NAME,
    create_or_update_starter_projects,
    get_project_data,
    load_starter_projects,
)
from langflow.memory import delete_messages
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import session_scope
from sqlalchemy import func
from sqlmodel import select


def test_load_starter_projects():
    projects = load_starter_projects()
    assert isinstance(projects, list)
    assert all(isinstance(project, dict) for project in projects)


def test_get_project_data():
    projects = load_starter_projects()
    for _, project in projects:
        (
            project_name,
            project_description,
            project_is_component,
            updated_at_datetime,
            project_data,
            project_icon,
            project_icon_bg_color,
        ) = get_project_data(project)
        assert isinstance(project_name, str)
        assert isinstance(project_description, str)
        assert isinstance(project_is_component, bool)
        assert isinstance(updated_at_datetime, datetime)
        assert isinstance(project_data, dict)
        assert isinstance(project_icon, str) or project_icon is None
        assert isinstance(project_icon_bg_color, str) or project_icon_bg_color is None


def test_create_or_update_starter_projects(client):
    with session_scope() as session:
        # Run the function to create or update projects
        create_or_update_starter_projects()

        # Get the number of projects returned by load_starter_projects
        num_projects = len(load_starter_projects())

        # Get the number of projects in the database
        num_db_projects = session.exec(select(func.count(Flow.id)).where(Flow.folder == STARTER_FOLDER_NAME)).one()

        # Check that the number of projects in the database is the same as the number of projects returned by load_starter_projects
        assert num_db_projects == num_projects


@pytest.mark.asyncio
async def test_starter_project_can_run_successfully(client):
    with session_scope() as session:
        # Run the function to create or update projects
        create_or_update_starter_projects()

        # Get the number of projects returned by load_starter_projects
        num_projects = len(load_starter_projects())

        # Get the number of projects in the database
        num_db_projects = session.exec(select(func.count(Flow.id)).where(Flow.folder == STARTER_FOLDER_NAME)).one()

        # Check that the number of projects in the database is the same as the number of projects returned by load_starter_projects
        assert num_db_projects == num_projects

        # Get all the starter projects
        projects = session.exec(select(Flow).where(Flow.folder == STARTER_FOLDER_NAME)).all()

        graphs: list[tuple[str, Graph]] = [
            (project.name, Graph.from_payload(project.data, flow_id=project.id))
            for project in projects
            if "Document" not in project.name or "RAG" not in project.name
        ]
        assert len(graphs) == len(projects)
    for name, graph in graphs:
        outputs = await graph.arun(
            inputs={},
            outputs=[],
            session_id="test",
        )
        assert all(isinstance(output, RunOutputs) for output in outputs), f"Project {name} error: {outputs}"
        delete_messages(session_id="test")
