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
from langflow.services.database.models.folder.model import FolderRead


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
