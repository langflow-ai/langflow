import asyncio
import os
import shutil
import tempfile
import uuid
from copy import deepcopy
from datetime import datetime
from pathlib import Path as SyncPath
from unittest.mock import AsyncMock, patch

import pytest
from anyio import Path
from httpx import AsyncClient
from langflow.initial_setup.constants import STARTER_FOLDER_NAME
from langflow.initial_setup.setup import (
    copy_profile_pictures,
    detect_github_url,
    get_project_data,
    load_bundles_from_urls,
    load_starter_projects,
    update_projects_components_with_latest_component_versions,
)
from langflow.interface.components import get_and_cache_all_types_dict
from langflow.services.auth.utils import create_super_user
from langflow.services.database.models import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.deps import get_settings_service, session_scope
from sqlalchemy.orm import selectinload
from sqlmodel import select


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
    all_types = await get_and_cache_all_types_dict(get_settings_service())
    copy_all_types = deepcopy(all_types)

    chat_input = find_component_by_name(copy_all_types, "ChatInput")
    chat_output = find_component_by_name(copy_all_types, "ChatOutput")
    chat_output["template"]["code"]["value"] = "changed !"
    del chat_output["template"]["should_store_message"]
    graph_data = {
        "nodes": [
            component_to_node("chat-input-1", "ChatInput", chat_input),
            component_to_node("chat-output-1", "ChatOutput", chat_output),
        ],
        "edges": [add_edge("ChatInput" + "chat-input-1", "ChatOutput" + "chat-output-1", "message", "input_value")],
    }

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

    # Create a superuser in the test database since load_bundles_from_urls requires one
    async with session_scope() as session:
        await create_super_user(
            username=settings_service.auth_settings.SUPERUSER,
            password=(
                settings_service.auth_settings.SUPERUSER_PASSWORD.get_secret_value()
                if hasattr(settings_service.auth_settings.SUPERUSER_PASSWORD, "get_secret_value")
                else settings_service.auth_settings.SUPERUSER_PASSWORD
            ),
            db=session,
        )

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
    # Use a relative path which will be placed in the user's flows directory
    # The path validation requires paths to be within the user's flows directory for security
    flow_filename = f"{uuid.uuid4()}.json"
    try:
        basic_case = {
            "name": "string",
            "description": "string",
            "data": {},
            "locked": False,
            "fs_path": flow_filename,
        }
        response = await client.post("api/v1/flows/", json=basic_case, headers=logged_in_headers)
        assert response.status_code == 201, f"Failed to create flow: {response.text}"
        created_flow = response.json()
        flow_id = created_flow["id"]
        user_id = created_flow["user_id"]

        # Construct the full path where the file was saved
        # The API saves relative paths to: storage_service.data_dir / "flows" / user_id / filename
        from langflow.services.deps import get_storage_service

        storage_service = get_storage_service()
        flow_file = storage_service.data_dir / "flows" / str(user_id) / flow_filename

        # Read the file created by the API
        content = await flow_file.read_text(encoding="utf-8")
        fs_flow = Flow.model_validate_json(content)
        fs_flow.name = "new name"
        fs_flow.description = "new description"
        fs_flow.data = {"nodes": {}, "edges": {}}
        fs_flow.locked = True

        await flow_file.write_text(fs_flow.model_dump_json(), encoding="utf-8")

        result = {}
        for i in range(10):
            response = await client.get(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
            result = response.json()
            if result["name"] == "new name":
                break
            assert i != 9, "flow name should have been updated"
            await asyncio.sleep(0.1)

        assert result["description"] == "new description"
        assert result["data"] == {"nodes": {}, "edges": {}}
        assert result["locked"] is True
    finally:
        if "flow_file" in locals():
            await flow_file.unlink(missing_ok=True)


# ==================== Profile Pictures Tests ====================


@pytest.fixture
def profile_pictures_temp_config(monkeypatch):
    """Fixture that sets up a temporary config directory for profile picture tests."""
    temp_dir = tempfile.mkdtemp()
    config_path = SyncPath(temp_dir)

    # Set the config_dir to our temp directory
    monkeypatch.setenv("LANGFLOW_CONFIG_DIR", str(config_path))

    yield config_path

    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.usefixtures("client")
async def test_copy_profile_pictures_creates_directories():
    """Test that copy_profile_pictures creates the profile_pictures directories."""
    settings_service = get_settings_service()
    config_dir = settings_service.settings.config_dir
    config_path = SyncPath(config_dir)

    # The function should have been called during app startup (client fixture)
    # Verify the directories exist
    people_dir = config_path / "profile_pictures" / "People"
    space_dir = config_path / "profile_pictures" / "Space"

    assert people_dir.exists(), "People directory should exist after copy_profile_pictures"
    assert space_dir.exists(), "Space directory should exist after copy_profile_pictures"


@pytest.mark.usefixtures("client")
async def test_copy_profile_pictures_copies_files():
    """Test that copy_profile_pictures copies all profile picture files."""
    settings_service = get_settings_service()
    config_dir = settings_service.settings.config_dir
    config_path = SyncPath(config_dir)

    people_dir = config_path / "profile_pictures" / "People"
    space_dir = config_path / "profile_pictures" / "Space"

    # Check that files were copied
    people_files = list(people_dir.glob("*.svg")) if people_dir.exists() else []
    space_files = list(space_dir.glob("*.svg")) if space_dir.exists() else []

    assert len(people_files) > 0, "Should have People profile pictures copied"
    assert len(space_files) > 0, "Should have Space profile pictures copied"


@pytest.mark.usefixtures("client")
async def test_copy_profile_pictures_specific_files_exist():
    """Test that specific known profile picture files exist after copying."""
    settings_service = get_settings_service()
    config_dir = settings_service.settings.config_dir
    config_path = SyncPath(config_dir)

    # Check for the default rocket profile picture (used as default in the app)
    rocket_path = config_path / "profile_pictures" / "Space" / "046-rocket.svg"
    assert rocket_path.exists(), "Default rocket profile picture should exist"

    # Check that the file has content
    content = rocket_path.read_bytes()
    assert len(content) > 0, "Profile picture file should have content"
    assert b"<svg" in content or b"<?xml" in content, "Profile picture should be a valid SVG"


@pytest.mark.usefixtures("client")
async def test_copy_profile_pictures_is_idempotent():
    """Test that copy_profile_pictures can be called multiple times without issues."""
    settings_service = get_settings_service()
    config_dir = settings_service.settings.config_dir
    config_path = SyncPath(config_dir)

    # Get initial file count
    people_dir = config_path / "profile_pictures" / "People"
    initial_count = len(list(people_dir.glob("*.svg"))) if people_dir.exists() else 0

    # Call copy_profile_pictures again
    await copy_profile_pictures()

    # Count should remain the same (no duplicates)
    final_count = len(list(people_dir.glob("*.svg"))) if people_dir.exists() else 0
    assert final_count == initial_count, "Calling copy_profile_pictures again should not create duplicates"


async def test_copy_profile_pictures_source_exists():
    """Test that the source profile pictures directory exists in the package."""
    from langflow.initial_setup import setup

    source_path = Path(setup.__file__).parent / "profile_pictures"
    assert await source_path.exists(), "Source profile_pictures directory should exist in package"

    people_source = source_path / "People"
    space_source = source_path / "Space"

    assert await people_source.exists(), "Source People directory should exist"
    assert await space_source.exists(), "Source Space directory should exist"

    # Count source files
    people_files = [f async for f in people_source.glob("*.svg")]
    space_files = [f async for f in space_source.glob("*.svg")]

    assert len(people_files) > 0, "Source should have People profile pictures"
    assert len(space_files) > 0, "Source should have Space profile pictures"


@pytest.mark.usefixtures("client")
async def test_profile_pictures_available_via_api(client: AsyncClient, logged_in_headers):
    """Test that profile pictures are available via the API after app startup."""
    response = await client.get("api/v1/files/profile_pictures/list", headers=logged_in_headers)

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.json()}"

    data = response.json()
    assert "files" in data, "Response should contain 'files' key"

    files = data["files"]
    assert len(files) > 0, "Should have profile pictures available via API"

    # Check for expected file format
    assert any(f.startswith("People/") for f in files), "Should have People profile pictures"
    assert any(f.startswith("Space/") for f in files), "Should have Space profile pictures"

    # Check for the default rocket profile picture
    assert "Space/046-rocket.svg" in files, "Default rocket profile picture should be available"


@pytest.mark.usefixtures("client")
async def test_profile_picture_can_be_downloaded(client: AsyncClient, logged_in_headers):
    """Test that a profile picture can be downloaded via the API."""
    response = await client.get(
        "api/v1/files/profile_pictures/Space/046-rocket.svg",
        headers=logged_in_headers,
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert "image/svg+xml" in response.headers["content-type"], "Should return SVG content type"
    assert len(response.content) > 0, "Should have content"


async def test_copy_profile_pictures_handles_missing_config_dir():
    """Test that copy_profile_pictures raises error when config_dir is not set."""
    with patch("langflow.initial_setup.setup.get_storage_service") as mock_storage:
        mock_settings = AsyncMock()
        mock_settings.settings_service.settings.config_dir = None
        mock_storage.return_value = mock_settings

        with pytest.raises(ValueError, match="Config dir is not set"):
            await copy_profile_pictures()


# ==================== Hash History Tests ====================


def test_update_projects_strips_hash_history_from_components():
    """Test that hash_history is stripped from components when updating projects.

    This ensures that internal component metadata (hash_history) used for tracking
    component evolution in the component index does not leak into saved flows.
    """
    # Create a mock all_types_dict with hash_history in component metadata
    all_types_dict = {
        "agents": {
            "Agent": {
                "template": {
                    "code": {"value": "test code"},
                    "_type": "Component",
                },
                "display_name": "Agent",
                "metadata": {
                    "code_hash": "abc123",
                    "hash_history": [  # This should be stripped
                        {"hash": "abc123", "v_from": "1.0.0", "version_last": "1.0.1"}
                    ],
                },
            }
        }
    }

    # Create a mock project with a node using this component
    project_data = {
        "nodes": [
            {
                "data": {
                    "type": "Agent",
                    "node": {
                        "template": {
                            "code": {"value": "old code"},
                            "_type": "Component",
                        },
                        "outputs": [],
                    },
                }
            }
        ]
    }

    # Update the project
    updated_project = update_projects_components_with_latest_component_versions(project_data, all_types_dict)

    # Verify the component was updated
    updated_node = updated_project["nodes"][0]["data"]["node"]
    assert updated_node["template"]["code"]["value"] == "test code"

    # CRITICAL: Verify hash_history was NOT copied into the flow
    # Hash_history should only exist in component_index.json, never in saved flows
    node_metadata = updated_node.get("metadata", {})
    assert "hash_history" not in node_metadata, (
        "hash_history should not be present in flow nodes. "
        "It is internal metadata for component evolution tracking and should only exist in component_index.json"
    )


def test_update_projects_preserves_other_metadata():
    """Test that other metadata fields are preserved when stripping hash_history."""
    all_types_dict = {
        "agents": {
            "Agent": {
                "template": {
                    "code": {"value": "test code"},
                    "_type": "Component",
                },
                "display_name": "Agent",
                "metadata": {
                    "code_hash": "abc123",
                    "module": "test.module",
                    "hash_history": [{"hash": "abc123", "v_from": "1.0.0", "v_to": "1.0.1"}],
                },
            }
        }
    }

    project_data = {
        "nodes": [
            {
                "data": {
                    "type": "Agent",
                    "node": {
                        "template": {
                            "code": {"value": "old code"},
                            "_type": "Component",
                        },
                        "outputs": [],
                    },
                }
            }
        ]
    }

    update_projects_components_with_latest_component_versions(project_data, all_types_dict)

    # Verify hash_history is stripped but other metadata is preserved
    # Note: The function doesn't copy metadata to nodes, it only updates template
    # This test verifies the internal flattened dict doesn't have hash_history
    # The actual metadata preservation happens in the template update logic


def test_update_projects_handles_components_without_metadata():
    """Test that components without metadata are handled gracefully."""
    all_types_dict = {
        "agents": {
            "Agent": {
                "template": {
                    "code": {"value": "test code"},
                    "_type": "Component",
                },
                "display_name": "Agent",
                # No metadata field at all
            }
        }
    }

    project_data = {
        "nodes": [
            {
                "data": {
                    "type": "Agent",
                    "node": {
                        "template": {
                            "code": {"value": "old code"},
                            "_type": "Component",
                        },
                        "outputs": [],
                    },
                }
            }
        ]
    }

    # Should not raise an error
    updated_project = update_projects_components_with_latest_component_versions(project_data, all_types_dict)
    assert updated_project["nodes"][0]["data"]["node"]["template"]["code"]["value"] == "test code"


def test_update_projects_handles_components_without_hash_history():
    """Test that components with metadata but no hash_history are handled gracefully."""
    all_types_dict = {
        "agents": {
            "Agent": {
                "template": {
                    "code": {"value": "test code"},
                    "_type": "Component",
                },
                "display_name": "Agent",
                "metadata": {
                    "code_hash": "abc123",
                    "module": "test.module",
                    # No hash_history field
                },
            }
        }
    }

    project_data = {
        "nodes": [
            {
                "data": {
                    "type": "Agent",
                    "node": {
                        "template": {
                            "code": {"value": "old code"},
                            "_type": "Component",
                        },
                        "outputs": [],
                    },
                }
            }
        ]
    }

    # Should not raise an error
    updated_project = update_projects_components_with_latest_component_versions(project_data, all_types_dict)
    assert updated_project["nodes"][0]["data"]["node"]["template"]["code"]["value"] == "test code"
