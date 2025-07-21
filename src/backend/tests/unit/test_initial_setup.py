import asyncio
import os
import tempfile
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from anyio import Path
from httpx import AsyncClient
from langflow.initial_setup.constants import STARTER_FOLDER_NAME
from langflow.initial_setup.setup import (
    detect_github_url,
    get_project_data,
    load_bundles_from_urls,
    load_starter_projects,
    update_projects_components_with_latest_component_versions,
)
from langflow.interface.components import aget_all_types_dict
from langflow.services.database.models import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.deps import get_settings_service, session_scope
from sqlalchemy.orm import selectinload
from sqlmodel import select

from lfx.custom.directory_reader.utils import abuild_custom_component_list_from_path


async def test_load_starter_projects():
    projects = await load_starter_projects()
    assert isinstance(projects, list)
    assert all(isinstance(project[1], dict) for project in projects)
    assert all(isinstance(project[0], Path) for project in projects)


async def test_get_project_data():
    projects = await load_starter_projects()
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
        assert isinstance(project_tags, list), f"Project {project_name} has no tags"
        assert isinstance(project_name, str), f"Project {project_name} has no name"
        assert isinstance(project_description, str), f"Project {project_name} has no description"
        assert isinstance(project_is_component, bool), f"Project {project_name} has no is_component"
        assert isinstance(updated_at_datetime, datetime), f"Project {project_name} has no updated_at_datetime"
        assert isinstance(project_data, dict), f"Project {project_name} has no data"
        assert isinstance(project_icon, str) or project_icon is None, f"Project {project_name} has no icon"
        assert isinstance(project_icon_bg_color, str) or project_icon_bg_color is None, (
            f"Project {project_name} has no icon_bg_color"
        )


@pytest.mark.usefixtures("client")
async def test_create_or_update_starter_projects():
    async with session_scope() as session:
        # Get the number of projects returned by load_starter_projects
        num_projects = len(await load_starter_projects())

        # Get the number of projects in the database
        stmt = select(Folder).options(selectinload(Folder.flows)).where(Folder.name == STARTER_FOLDER_NAME)
        folder = (await session.exec(stmt)).first()
        assert folder is not None
        num_db_projects = len(folder.flows)

        # Check that the number of projects in the database is the same as the number of projects returned by
        # load_starter_projects
        assert num_db_projects == num_projects


# Some starter projects require integration
# async def test_starter_projects_can_run_successfully(client):
#     with session_scope() as session:
#         # Run the function to create or update projects
#         create_or_update_starter_projects()

#         # Get the number of projects returned by load_starter_projects
#         num_projects = len(load_starter_projects())

#         # Get the number of projects in the database
#         num_db_projects = session.exec(select(func.count(Flow.id)).where(Flow.folder == STARTER_FOLDER_NAME)).one()

#         # Check that the number of projects in the database is the same as the number of projects returned by
#         # load_starter_projects
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


def find_component_by_name(components, name):
    for children in components.values():
        if name in children:
            return children[name]
    msg = f"Component {name} not found in components"
    raise ValueError(msg)


def set_value(component, input_name, value):
    component["template"][input_name]["value"] = value


def component_to_node(node_id, node_type, component):
    return {"id": node_type + node_id, "data": {"node": component, "type": node_type, "id": node_id}}


def add_edge(source, target, from_output, to_input):
    return {
        "source": source,
        "target": target,
        "data": {
            "sourceHandle": {"dataType": "ChatInput", "id": source, "name": from_output, "output_types": ["Message"]},
            "targetHandle": {"fieldName": to_input, "id": target, "inputTypes": ["Message"], "type": "str"},
        },
    }


async def test_refresh_starter_projects():
    data_path = str(await Path(__file__).parent.parent.parent.absolute() / "base" / "langflow" / "components")
    components = await abuild_custom_component_list_from_path(data_path)

    chat_input = find_component_by_name(components, "ChatInput")
    chat_output = find_component_by_name(components, "ChatOutput")
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


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://github.com/langflow-ai/langflow-bundles",
            "https://github.com/langflow-ai/langflow-bundles/archive/refs/heads/main.zip",
        ),
        (
            "https://github.com/langflow-ai/langflow-bundles/",
            "https://github.com/langflow-ai/langflow-bundles/archive/refs/heads/main.zip",
        ),
        (
            "https://github.com/langflow-ai/langflow-bundles.git",
            "https://github.com/langflow-ai/langflow-bundles/archive/refs/heads/main.zip",
        ),
        (
            "https://github.com/langflow-ai/langflow-bundles/tree/some.branch-0_1",
            "https://github.com/langflow-ai/langflow-bundles/archive/refs/heads/some.branch-0_1.zip",
        ),
        (
            "https://github.com/langflow-ai/langflow-bundles/tree/some/branch",
            "https://github.com/langflow-ai/langflow-bundles/archive/refs/heads/some/branch.zip",
        ),
        (
            "https://github.com/langflow-ai/langflow-bundles/tree/some/branch/",
            "https://github.com/langflow-ai/langflow-bundles/archive/refs/heads/some/branch.zip",
        ),
        (
            "https://github.com/langflow-ai/langflow-bundles/releases/tag/v1.0.0-0_1",
            "https://github.com/langflow-ai/langflow-bundles/archive/refs/tags/v1.0.0-0_1.zip",
        ),
        (
            "https://github.com/langflow-ai/langflow-bundles/releases/tag/foo/v1.0.0",
            "https://github.com/langflow-ai/langflow-bundles/archive/refs/tags/foo/v1.0.0.zip",
        ),
        (
            "https://github.com/langflow-ai/langflow-bundles/releases/tag/foo/v1.0.0/",
            "https://github.com/langflow-ai/langflow-bundles/archive/refs/tags/foo/v1.0.0.zip",
        ),
        (
            "https://github.com/langflow-ai/langflow-bundles/commit/68428ce16729a385fe1bcc0f1ec91fd5f5f420b9",
            "https://github.com/langflow-ai/langflow-bundles/archive/68428ce16729a385fe1bcc0f1ec91fd5f5f420b9.zip",
        ),
        (
            "https://github.com/langflow-ai/langflow-bundles/commit/68428ce16729a385fe1bcc0f1ec91fd5f5f420b9/",
            "https://github.com/langflow-ai/langflow-bundles/archive/68428ce16729a385fe1bcc0f1ec91fd5f5f420b9.zip",
        ),
        ("https://example.com/myzip.zip", "https://example.com/myzip.zip"),
    ],
)
async def test_detect_github_url(url, expected):
    # Mock the GitHub API response for the default branch case
    mock_response = AsyncMock()
    mock_response.json = lambda: {"default_branch": "main"}  # Not async, just returns a dict
    mock_response.raise_for_status.return_value = None

    with patch("httpx.AsyncClient.get", return_value=mock_response) as mock_get:
        result = await detect_github_url(url)
        assert result == expected

        # Verify the API call was only made for GitHub repo URLs
        if "github.com" in url and not any(x in url for x in ["/tree/", "/releases/", "/commit/"]):
            mock_get.assert_called_once()
        else:
            mock_get.assert_not_called()


@pytest.mark.usefixtures("client")
async def test_load_bundles_from_urls():
    settings_service = get_settings_service()
    settings_service.settings.bundle_urls = [
        "https://github.com/langflow-ai/langflow-bundles/commit/68428ce16729a385fe1bcc0f1ec91fd5f5f420b9"
    ]
    settings_service.auth_settings.AUTO_LOGIN = True

    temp_dirs, components_paths = await load_bundles_from_urls()

    try:
        assert len(components_paths) == 1
        assert "langflow-bundles-68428ce16729a385fe1bcc0f1ec91fd5f5f420b9/components" in components_paths[0]

        content = await (Path(components_paths[0]) / "embeddings" / "openai2.py").read_text(encoding="utf-8")
        assert "OpenAIEmbeddings2Component" in content

        assert len(temp_dirs) == 1

        async with session_scope() as session:
            stmt = select(Flow).where(Flow.id == uuid.UUID("c54f9130-f2fa-4a3e-b22a-3856d946351b"))
            flow = (await session.exec(stmt)).first()
            assert flow is not None
    finally:
        for temp_dir in temp_dirs:
            await asyncio.to_thread(temp_dir.cleanup)


@pytest.fixture
def set_fs_flows_polling_interval():
    os.environ["LANGFLOW_FS_FLOWS_POLLING_INTERVAL"] = "100"
    yield
    os.unsetenv("LANGFLOW_FS_FLOWS_POLLING_INTERVAL")


@pytest.mark.usefixtures("set_fs_flows_polling_interval")
async def test_sync_flows_from_fs(client: AsyncClient, logged_in_headers):
    flow_file = Path(tempfile.tempdir) / f"{uuid.uuid4()}.json"
    try:
        basic_case = {
            "name": "string",
            "description": "string",
            "data": {},
            "locked": False,
            "fs_path": str(flow_file),
        }
        await client.post("api/v1/flows/", json=basic_case, headers=logged_in_headers)

        content = await flow_file.read_text(encoding="utf-8")
        fs_flow = Flow.model_validate_json(content)
        fs_flow.name = "new name"
        fs_flow.description = "new description"
        fs_flow.data = {"nodes": {}, "edges": {}}
        fs_flow.locked = True

        await flow_file.write_text(fs_flow.model_dump_json(), encoding="utf-8")

        result = {}
        for i in range(10):
            response = await client.get(f"api/v1/flows/{fs_flow.id}", headers=logged_in_headers)
            result = response.json()
            if result["name"] == "new name":
                break
            assert i != 9, "flow name should have been updated"
            await asyncio.sleep(0.1)

        assert result["description"] == "new description"
        assert result["data"] == {"nodes": {}, "edges": {}}
        assert result["locked"] is True
    finally:
        await flow_file.unlink(missing_ok=True)
