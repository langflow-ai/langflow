from datetime import datetime
from pathlib import Path

import pytest
from langflow.custom.directory_reader.utils import build_custom_component_list_from_path
from langflow.initial_setup.setup import (
    STARTER_FOLDER_NAME,
    get_project_data,
    load_starter_projects,
    update_projects_components_with_latest_component_versions,
)
from langflow.interface.types import aget_all_types_dict
from langflow.services.database.models.folder.model import Folder
from langflow.services.deps import session_scope
from sqlmodel import select


def test_load_starter_projects():
    projects = load_starter_projects()
    assert isinstance(projects, list)
    assert all(isinstance(project[1], dict) for project in projects)
    assert all(isinstance(project[0], Path) for project in projects)


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
            project_gradient,
            project_tags,
        ) = get_project_data(project)
        assert isinstance(project_gradient, str) or project_gradient is None
        assert isinstance(project_tags, list)
        assert isinstance(project_name, str)
        assert isinstance(project_description, str)
        assert isinstance(project_is_component, bool)
        assert isinstance(updated_at_datetime, datetime)
        assert isinstance(project_data, dict)
        assert isinstance(project_icon, str) or project_icon is None
        assert isinstance(project_icon_bg_color, str) or project_icon_bg_color is None


@pytest.mark.asyncio
@pytest.mark.usefixtures("client")
async def test_create_or_update_starter_projects():
    with session_scope() as session:
        # Get the number of projects returned by load_starter_projects
        num_projects = len(load_starter_projects())

        # Get the number of projects in the database
        folder = session.exec(select(Folder).where(Folder.name == STARTER_FOLDER_NAME)).first()
        assert folder is not None
        num_db_projects = len(folder.flows)

        # Check that the number of projects in the database is the same as the number of projects returned by load_starter_projects
        assert num_db_projects == num_projects


# Some starter projects require integration
# @pytest.mark.asyncio
# async def test_starter_projects_can_run_successfully(client):
#     with session_scope() as session:
#         # Run the function to create or update projects
#         create_or_update_starter_projects()

#         # Get the number of projects returned by load_starter_projects
#         num_projects = len(load_starter_projects())

#         # Get the number of projects in the database
#         num_db_projects = session.exec(select(func.count(Flow.id)).where(Flow.folder == STARTER_FOLDER_NAME)).one()

#         # Check that the number of projects in the database is the same as the number of projects returned by load_starter_projects
#         assert num_db_projects == num_projects

#         # Get all the starter projects
#         projects = session.exec(select(Flow).where(Flow.folder == STARTER_FOLDER_NAME)).all()
#         graphs: list[tuple[str, Graph]] = []
#         for project in projects:
#             # Add tweaks to make file_path work
#             tweaks = {"path": __file__}
#             graph_data = process_tweaks(project.data, tweaks)
#             graph_object = Graph.from_payload(graph_data, flow_id=project.id)
#             graphs.append((project.name, graph_object))
#         assert len(graphs) == len(projects)
#     for name, graph in graphs:
#         outputs = await graph.arun(
#             inputs={},
#             outputs=[],
#             session_id="test",
#         )
#         assert all(isinstance(output, RunOutputs) for output in outputs), f"Project {name} error: {outputs}"
#         delete_messages(session_id="test")


def find_componeny_by_name(components, name):
    for children in components.values():
        if name in children:
            return children[name]
    msg = f"Component {name} not found in components"
    raise ValueError(msg)


def set_value(component, input_name, value):
    component["template"][input_name]["value"] = value


def component_to_node(id, type, component):
    return {"id": type + id, "data": {"node": component, "type": type, "id": id}}


def add_edge(input, output, from_output, to_input):
    return {
        "source": input,
        "target": output,
        "data": {
            "sourceHandle": {"dataType": "ChatInput", "id": input, "name": from_output, "output_types": ["Message"]},
            "targetHandle": {"fieldName": to_input, "id": output, "inputTypes": ["Message"], "type": "str"},
        },
    }


@pytest.mark.asyncio
async def test_refresh_starter_projects():
    data_path = str(Path(__file__).parent.parent.parent.absolute() / "base" / "langflow" / "components")
    components = build_custom_component_list_from_path(data_path)

    chat_input = find_componeny_by_name(components, "ChatInput")
    chat_output = find_componeny_by_name(components, "ChatOutput")
    chat_output["template"]["code"]["value"] = "changed !"
    del chat_output["template"]["should_store_message"]
    graph_data = {
        "nodes": [
            component_to_node("chat-input-1", "ChatInput", chat_input),
            component_to_node("chat-output-1", "ChatOutput", chat_output),
        ],
        "edges": [add_edge("ChatInput" + "chat-input-1", "ChatOutput" + "chat-output-1", "message", "input_value")],
    }
    all_types = await aget_all_types_dict([data_path])
    new_change = update_projects_components_with_latest_component_versions(graph_data, all_types)
    assert graph_data["nodes"][1]["data"]["node"]["template"]["code"]["value"] == "changed !"
    assert new_change["nodes"][1]["data"]["node"]["template"]["code"]["value"] != "changed !"

    assert "should_store_message" not in graph_data["nodes"][1]["data"]["node"]["template"]
    assert "should_store_message" in new_change["nodes"][1]["data"]["node"]["template"]
