import asyncio
from copy import deepcopy
from uuid import uuid4

import pytest
from langflow.initial_setup.setup import (
    get_or_create_default_folder,
    session_scope,
    update_projects_components_with_latest_component_versions,
)
from langflow.services.database.models.folder.constants import DEFAULT_FOLDER_NAME
from langflow.services.database.models.folder.model import Folder, FolderRead
from sqlmodel import select


@pytest.mark.usefixtures("client")
async def test_get_or_create_default_folder_creation() -> None:
    """Test that a default project is created for a new user.

    This test verifies that when no default project exists for a given user,
    get_or_create_default_folder creates one with the expected name and assigns it an ID.
    """
    test_user_id = uuid4()
    async with session_scope() as session:
        folder = await get_or_create_default_folder(session, test_user_id)
        assert folder.name == DEFAULT_FOLDER_NAME, "The project name should match the default."
        assert hasattr(folder, "id"), "The project should have an 'id' attribute after creation."


@pytest.mark.usefixtures("client")
async def test_get_or_create_default_folder_idempotency() -> None:
    """Test that subsequent calls to get_or_create_default_folder return the same project.

    The function should be idempotent such that if a default project already exists,
    calling the function again does not create a new one.
    """
    test_user_id = uuid4()
    async with session_scope() as session:
        folder_first = await get_or_create_default_folder(session, test_user_id)
        folder_second = await get_or_create_default_folder(session, test_user_id)
        assert folder_first.id == folder_second.id, "Both calls should return the same folder instance."


@pytest.mark.usefixtures("client")
async def test_get_or_create_default_folder_concurrent_calls() -> None:
    """Test concurrent invocations of get_or_create_default_folder.

    This test ensures that when multiple concurrent calls are made for the same user,
    only one default project is created, demonstrating idempotency under concurrent access.
    """
    test_user_id = uuid4()

    async def get_folder() -> FolderRead:
        async with session_scope() as session:
            return await get_or_create_default_folder(session, test_user_id)

    results = await asyncio.gather(get_folder(), get_folder(), get_folder())
    folder_ids = {folder.id for folder in results}
    assert len(folder_ids) == 1, "Concurrent calls must return a single, consistent folder instance."


@pytest.mark.usefixtures("client")
async def test_get_or_create_default_folder_respects_rename() -> None:
    """Regression test: renaming the default folder must persist across calls.

    Reproduces the reported bug where the server would recreate a "Starter Project" folder
    on every login or server restart, even though the user had already renamed it to something
    like "My Flows". After the fix, get_or_create_default_folder must detect the user's existing
    (renamed) folder and return it instead of forcing a new default folder back into the UI.
    """
    test_user_id = uuid4()
    renamed_folder_name = "My Flows"

    # First call creates the default folder.
    async with session_scope() as session:
        folder_first = await get_or_create_default_folder(session, test_user_id)
        assert folder_first.name == DEFAULT_FOLDER_NAME
        original_id = folder_first.id

    # Simulate the user renaming the default folder from the UI.
    async with session_scope() as session:
        stmt = select(Folder).where(Folder.id == original_id)
        folder_row = (await session.exec(stmt)).first()
        assert folder_row is not None
        folder_row.name = renamed_folder_name
        session.add(folder_row)
        await session.flush()

    # Second call (simulating next login / server restart) must honor the rename
    # rather than creating a new "Starter Project" alongside the renamed one.
    async with session_scope() as session:
        folder_second = await get_or_create_default_folder(session, test_user_id)
        assert folder_second.id == original_id, (
            "The renamed folder should be returned instead of creating a new default."
        )
        assert folder_second.name == renamed_folder_name, (
            "The folder's user-assigned name must be preserved across calls."
        )

        # There should still be exactly one folder for this user — no phantom duplicate.
        all_folders_stmt = select(Folder).where(Folder.user_id == test_user_id)
        all_folders = (await session.exec(all_folders_stmt)).all()
        folder_names = sorted(f.name for f in all_folders)
        assert folder_names == [renamed_folder_name], (
            f"Expected only the renamed folder to exist, found: {folder_names}"
        )


@pytest.mark.usefixtures("client")
async def test_get_or_create_default_folder_respects_other_existing_folder() -> None:
    """Respect existing folders when the default folder is absent.

    If the user already has any folder (e.g. they moved everything into 'Ideas' and
    deleted the default), we must not resurrect the default folder on the next call.
    """
    test_user_id = uuid4()
    other_folder_name = "Ideas"

    # Simulate an existing user who has a non-default folder but no "Starter Project".
    async with session_scope() as session:
        session.add(Folder(user_id=test_user_id, name=other_folder_name, description="My ideas"))
        await session.flush()

    async with session_scope() as session:
        returned = await get_or_create_default_folder(session, test_user_id)
        assert returned.name == other_folder_name, (
            "Should return the user's existing folder rather than creating a new default."
        )

        all_folders_stmt = select(Folder).where(Folder.user_id == test_user_id)
        all_folders = (await session.exec(all_folders_stmt)).all()
        folder_names = sorted(f.name for f in all_folders)
        assert folder_names == [other_folder_name], f"No new default folder should be created; found: {folder_names}"


def _make_all_types_dict():
    """Create a minimal all_types_dict for testing shared reference isolation."""
    return {
        "test_category": {
            "TestComponent": {
                "template": {
                    "_type": "Component",
                    "code": {
                        "type": "code",
                        "value": "original_code",
                        "advanced": True,
                    },
                    "field_a": {
                        "type": "str",
                        "value": "original_value",
                        "display_name": "Field A",
                    },
                },
                "outputs": [{"name": "out", "types": ["Message"], "selected": "Message"}],
                "description": "Test",
                "display_name": "Test",
                "beta": False,
                "metadata": {"key": "original_metadata"},
            }
        }
    }


def _make_project_data():
    """Create minimal project data containing a TestComponent node."""
    return {
        "nodes": [
            {
                "id": "TestComponent-abc",
                "data": {
                    "type": "TestComponent",
                    "node": {
                        "template": {
                            "_type": "Component",
                            "code": {
                                "type": "code",
                                "value": "original_code",
                                "advanced": True,
                            },
                            "field_a": {
                                "type": "str",
                                "value": "my_custom_value",
                                "display_name": "Field A",
                            },
                        },
                        "outputs": [{"name": "out", "types": ["Message"], "selected": "Message"}],
                        "tool_mode": False,
                    },
                },
            }
        ],
        "edges": [],
    }


def test_update_components_does_not_mutate_all_types_dict_via_code():
    """Verify that modifying the returned project data's template code does not mutate all_types_dict."""
    all_types_dict = _make_all_types_dict()
    snapshot = deepcopy(all_types_dict)

    result = update_projects_components_with_latest_component_versions(_make_project_data(), all_types_dict)

    # Mutate the returned data
    for node in result["nodes"]:
        node["data"]["node"]["template"]["code"]["value"] = "MUTATED!"

    assert all_types_dict == snapshot, "all_types_dict must not be mutated by modifying the returned project data"


def test_update_components_does_not_mutate_all_types_dict_via_attrs():
    """Verify that modifying returned project data's node attributes does not mutate all_types_dict."""
    all_types_dict = _make_all_types_dict()
    snapshot = deepcopy(all_types_dict)

    result = update_projects_components_with_latest_component_versions(_make_project_data(), all_types_dict)

    # Mutate a NODE_FORMAT_ATTRIBUTE on the returned data
    for node in result["nodes"]:
        node_data = node["data"]["node"]
        if "metadata" in node_data:
            node_data["metadata"]["key"] = "MUTATED!"

    assert all_types_dict == snapshot, "all_types_dict must not be mutated via node format attributes"


def test_update_components_does_not_leak_between_projects():
    """Verify that processing one project does not affect the next project's results."""
    all_types_dict = _make_all_types_dict()

    # Process first project and mutate its result
    result_a = update_projects_components_with_latest_component_versions(_make_project_data(), all_types_dict)
    for node in result_a["nodes"]:
        node["data"]["node"]["template"]["code"]["value"] = "MUTATED_BY_A!"

    # Process second project — should get original values
    result_b = update_projects_components_with_latest_component_versions(_make_project_data(), all_types_dict)
    for node in result_b["nodes"]:
        code_value = node["data"]["node"]["template"]["code"]["value"]
        assert code_value == "original_code", (
            f"Second project got '{code_value}' instead of 'original_code' — "
            "mutation from first project leaked via all_types_dict"
        )


def test_update_components_does_not_mutate_when_type_changes():
    """Verify no shared refs when _type differs and the full template is replaced."""
    all_types_dict = _make_all_types_dict()
    snapshot = deepcopy(all_types_dict)

    # Create project data with a different _type to trigger the full template replacement path
    project_data = _make_project_data()
    project_data["nodes"][0]["data"]["node"]["template"]["_type"] = "OldType"

    result = update_projects_components_with_latest_component_versions(project_data, all_types_dict)

    # Mutate the returned data's template
    for node in result["nodes"]:
        node["data"]["node"]["template"]["code"]["value"] = "MUTATED!"

    assert all_types_dict == snapshot, (
        "all_types_dict must not be mutated when _type differs and full template is replaced"
    )


def test_update_components_does_not_mutate_field_format_attributes():
    """Verify that mutable FIELD_FORMAT_ATTRIBUTES (e.g. input_types) are deepcopied, not shared."""
    all_types_dict = {
        "test_category": {
            "TestComponent": {
                "template": {
                    "_type": "Component",
                    "code": {"type": "code", "value": "original_code", "advanced": True},
                    "field_a": {
                        "type": "str",
                        "value": "original_value",
                        "display_name": "Field A",
                        "input_types": ["Message"],
                    },
                },
                "outputs": [{"name": "out", "types": ["Message"], "selected": "Message"}],
                "description": "Test",
                "display_name": "Test",
                "beta": False,
            }
        }
    }
    snapshot = deepcopy(all_types_dict)

    # Project has a different input_types so the FIELD_FORMAT_ATTRIBUTES path is triggered
    project_data = {
        "nodes": [
            {
                "id": "TestComponent-abc",
                "data": {
                    "type": "TestComponent",
                    "node": {
                        "template": {
                            "_type": "Component",
                            "code": {"type": "code", "value": "original_code", "advanced": True},
                            "field_a": {
                                "type": "str",
                                "value": "my_custom_value",
                                "display_name": "Field A",
                                "input_types": ["Data"],  # differs → triggers attr update at line 192
                            },
                        },
                        "outputs": [{"name": "out", "types": ["Message"], "selected": "Message"}],
                        "tool_mode": False,
                    },
                },
            }
        ],
        "edges": [],
    }

    result = update_projects_components_with_latest_component_versions(project_data, all_types_dict)

    # Mutate the returned mutable field attribute
    for node in result["nodes"]:
        node["data"]["node"]["template"]["field_a"]["input_types"].append("MUTATED!")

    assert all_types_dict == snapshot, (
        "all_types_dict must not be mutated via mutable FIELD_FORMAT_ATTRIBUTES (e.g. input_types)"
    )
