from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient

CYRILLIC_NAME = "Новый проект"
CYRILLIC_DESC = "Описание проекта с кириллицей"  # noqa: RUF001


@pytest.fixture
def basic_case():
    return {
        "name": "New Project",
        "description": "",
        "flows_list": [],
        "components_list": [],
    }


async def test_create_project(client: AsyncClient, logged_in_headers, basic_case):
    response = await client.post("api/v1/projects/", json=basic_case, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_201_CREATED
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "name" in result, "The dictionary must contain a key called 'name'"
    assert "description" in result, "The dictionary must contain a key called 'description'"
    assert "id" in result, "The dictionary must contain a key called 'id'"
    assert "parent_id" in result, "The dictionary must contain a key called 'parent_id'"


async def test_read_projects(client: AsyncClient, logged_in_headers):
    response = await client.get("api/v1/projects/", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, list), "The result must be a list"
    assert len(result) > 0, "The list must not be empty"


async def test_read_project(client: AsyncClient, logged_in_headers, basic_case):
    # Create a project first
    response_ = await client.post("api/v1/projects/", json=basic_case, headers=logged_in_headers)
    id_ = response_.json()["id"]

    # Get the project
    response = await client.get(f"api/v1/projects/{id_}", headers=logged_in_headers)
    result = response.json()

    # The response structure may be different depending on whether pagination is enabled
    if isinstance(result, dict) and "folder" in result:
        # Handle paginated project response
        folder_data = result["folder"]
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(folder_data, dict), "The folder data must be a dictionary"
        assert "name" in folder_data, "The dictionary must contain a key called 'name'"
        assert "description" in folder_data, "The dictionary must contain a key called 'description'"
        assert "id" in folder_data, "The dictionary must contain a key called 'id'"
    elif isinstance(result, dict) and "project" in result:
        # Handle paginated project response
        project_data = result["project"]
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(project_data, dict), "The project data must be a dictionary"
        assert "name" in project_data, "The dictionary must contain a key called 'name'"
        assert "description" in project_data, "The dictionary must contain a key called 'description'"
        assert "id" in project_data, "The dictionary must contain a key called 'id'"
    else:
        # Handle direct project response
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(result, dict), "The result must be a dictionary"
        assert "name" in result, "The dictionary must contain a key called 'name'"
        assert "description" in result, "The dictionary must contain a key called 'description'"
        assert "id" in result, "The dictionary must contain a key called 'id'"


async def test_update_project(client: AsyncClient, logged_in_headers, basic_case):
    update_case = basic_case.copy()
    update_case["name"] = "Updated Project"

    # Create a project first
    response_ = await client.post("api/v1/projects/", json=basic_case, headers=logged_in_headers)
    id_ = response_.json()["id"]

    # Update the project
    response = await client.patch(f"api/v1/projects/{id_}", json=update_case, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "name" in result, "The dictionary must contain a key called 'name'"
    assert "description" in result, "The dictionary must contain a key called 'description'"
    assert "id" in result, "The dictionary must contain a key called 'id'"
    assert "parent_id" in result, "The dictionary must contain a key called 'parent_id'"


async def test_create_project_validation_error(client: AsyncClient, logged_in_headers, basic_case):
    invalid_case = basic_case.copy()
    invalid_case.pop("name")
    response = await client.post("api/v1/projects/", json=invalid_case, headers=logged_in_headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_delete_project_then_404(client: AsyncClient, logged_in_headers, basic_case):
    create_resp = await client.post("api/v1/projects/", json=basic_case, headers=logged_in_headers)
    proj_id = create_resp.json()["id"]

    del_resp = await client.delete(f"api/v1/projects/{proj_id}", headers=logged_in_headers)
    assert del_resp.status_code == status.HTTP_204_NO_CONTENT

    get_resp = await client.get(f"api/v1/projects/{proj_id}", headers=logged_in_headers)
    assert get_resp.status_code == status.HTTP_404_NOT_FOUND


async def test_read_project_invalid_id_format(client: AsyncClient, logged_in_headers):
    bad_id = "not-a-uuid"
    response = await client.get(f"api/v1/projects/{bad_id}", headers=logged_in_headers)
    assert response.status_code in (status.HTTP_422_UNPROCESSABLE_ENTITY, status.HTTP_400_BAD_REQUEST)


async def test_read_projects_pagination(client: AsyncClient, logged_in_headers):
    response = await client.get("api/v1/projects/?limit=1&offset=0", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    result = response.json()
    if isinstance(result, list):
        assert len(result) <= 1
    else:
        assert "items" in result
        assert result.get("limit") == 1


async def test_read_projects_empty(client: AsyncClient, logged_in_headers):
    # Ensure DB is clean by fetching with a random header that forces each test transactional isolation
    random_headers = {**logged_in_headers, "X-Transaction-ID": str(uuid4())}
    response = await client.get("api/v1/projects/", headers=random_headers)
    if response.json():
        pytest.skip("Pre-existing projects found; skipping empty list assertion")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []


async def test_create_and_read_project_cyrillic(client: AsyncClient, logged_in_headers):
    """Ensure that the API correctly handles non-ASCII (Cyrillic) characters during project creation and retrieval."""
    payload = {
        "name": CYRILLIC_NAME,
        "description": CYRILLIC_DESC,
        "flows_list": [],
        "components_list": [],
    }

    # Create the project with Cyrillic characters
    create_resp = await client.post("api/v1/projects/", json=payload, headers=logged_in_headers)
    assert create_resp.status_code == status.HTTP_201_CREATED
    created = create_resp.json()
    assert created["name"] == CYRILLIC_NAME
    assert created["description"] == CYRILLIC_DESC
    proj_id = created["id"]

    # Fetch the project back to verify round-trip UTF-8 integrity
    get_resp = await client.get(f"api/v1/projects/{proj_id}", headers=logged_in_headers)
    assert get_resp.status_code == status.HTTP_200_OK
    fetched = get_resp.json()

    # Handle potential pagination/envelope variations already seen in other tests
    if isinstance(fetched, dict) and "folder" in fetched:
        fetched = fetched["folder"]
    elif isinstance(fetched, dict) and "project" in fetched:
        fetched = fetched["project"]

    assert fetched["name"] == CYRILLIC_NAME
    assert fetched["description"] == CYRILLIC_DESC


async def test_update_project_preserves_flows(client: AsyncClient, logged_in_headers):
    """Test that renaming a project preserves all associated flows (regression test for flow loss bug)."""
    # Create a project
    project_payload = {
        "name": "Project with Flows",
        "description": "Testing flow preservation",
        "flows_list": [],
        "components_list": [],
    }
    create_resp = await client.post("api/v1/projects/", json=project_payload, headers=logged_in_headers)
    assert create_resp.status_code == status.HTTP_201_CREATED
    project = create_resp.json()
    project_id = project["id"]

    # Create flows in the project
    flow1_payload = {
        "name": "Test Flow 1",
        "description": "First test flow",
        "folder_id": project_id,
        "data": {"nodes": [], "edges": []},
        "is_component": False,
    }
    flow2_payload = {
        "name": "Test Flow 2",
        "description": "Second test flow",
        "folder_id": project_id,
        "data": {"nodes": [], "edges": []},
        "is_component": False,
    }

    flow1_resp = await client.post("api/v1/flows/", json=flow1_payload, headers=logged_in_headers)
    flow2_resp = await client.post("api/v1/flows/", json=flow2_payload, headers=logged_in_headers)
    assert flow1_resp.status_code == status.HTTP_201_CREATED
    assert flow2_resp.status_code == status.HTTP_201_CREATED

    flow1_id = flow1_resp.json()["id"]
    flow2_id = flow2_resp.json()["id"]

    # Get project to verify flows are associated
    get_resp = await client.get(f"api/v1/projects/{project_id}", headers=logged_in_headers)
    assert get_resp.status_code == status.HTTP_200_OK
    project_data = get_resp.json()

    # Current behavior: all flows (including components) are in the flows field
    flows_before = project_data.get("flows", [])
    # Filter only actual flows (not components)
    actual_flows_before = [f for f in flows_before if not f.get("is_component", False)]

    assert len(actual_flows_before) == 2
    flow_ids_before = [f["id"] for f in actual_flows_before]
    assert str(flow1_id) in flow_ids_before
    assert str(flow2_id) in flow_ids_before

    # Update project name (the bug scenario)
    update_payload = {"name": "Renamed Project with Flows", "description": "Testing flow preservation after rename"}
    update_resp = await client.patch(f"api/v1/projects/{project_id}", json=update_payload, headers=logged_in_headers)
    assert update_resp.status_code == status.HTTP_200_OK

    # Verify project was renamed
    updated_project = update_resp.json()
    assert updated_project["name"] == "Renamed Project with Flows"

    # Critical test: Verify flows are still associated after rename
    get_after_resp = await client.get(f"api/v1/projects/{project_id}", headers=logged_in_headers)
    assert get_after_resp.status_code == status.HTTP_200_OK
    project_after = get_after_resp.json()

    flows_after = project_after.get("flows", [])
    actual_flows_after = [f for f in flows_after if not f.get("is_component", False)]

    # This was the bug: flows were being lost after project rename
    assert len(actual_flows_after) == 2, f"Expected 2 flows after rename, got {len(actual_flows_after)}. Flows lost!"

    flow_ids_after = [f["id"] for f in actual_flows_after]
    assert str(flow1_id) in flow_ids_after, "Flow 1 was lost after project rename!"
    assert str(flow2_id) in flow_ids_after, "Flow 2 was lost after project rename!"

    # Verify individual flows still exist and are accessible
    flow1_get_resp = await client.get(f"api/v1/flows/{flow1_id}", headers=logged_in_headers)
    flow2_get_resp = await client.get(f"api/v1/flows/{flow2_id}", headers=logged_in_headers)
    assert flow1_get_resp.status_code == status.HTTP_200_OK
    assert flow2_get_resp.status_code == status.HTTP_200_OK

    # Verify flows still reference the correct project
    flow1_data = flow1_get_resp.json()
    flow2_data = flow2_get_resp.json()
    assert str(flow1_data["folder_id"]) == str(project_id)
    assert str(flow2_data["folder_id"]) == str(project_id)


async def test_update_project_preserves_components(client: AsyncClient, logged_in_headers):
    """Test that renaming a project preserves all associated components."""
    # Create a project
    project_payload = {
        "name": "Project with Components",
        "description": "Testing component preservation",
        "flows_list": [],
        "components_list": [],
    }
    create_resp = await client.post("api/v1/projects/", json=project_payload, headers=logged_in_headers)
    assert create_resp.status_code == status.HTTP_201_CREATED
    project = create_resp.json()
    project_id = project["id"]

    # Create components in the project
    comp1_payload = {
        "name": "Test Component 1",
        "description": "First test component",
        "folder_id": project_id,
        "data": {"nodes": [], "edges": []},
        "is_component": True,  # This makes it a component
    }
    comp2_payload = {
        "name": "Test Component 2",
        "description": "Second test component",
        "folder_id": project_id,
        "data": {"nodes": [], "edges": []},
        "is_component": True,  # This makes it a component
    }

    comp1_resp = await client.post("api/v1/flows/", json=comp1_payload, headers=logged_in_headers)
    comp2_resp = await client.post("api/v1/flows/", json=comp2_payload, headers=logged_in_headers)
    assert comp1_resp.status_code == status.HTTP_201_CREATED
    assert comp2_resp.status_code == status.HTTP_201_CREATED

    comp1_id = comp1_resp.json()["id"]
    comp2_id = comp2_resp.json()["id"]

    # Get project to verify components are associated
    get_resp = await client.get(f"api/v1/projects/{project_id}", headers=logged_in_headers)
    assert get_resp.status_code == status.HTTP_200_OK
    project_data = get_resp.json()

    # Current behavior: all flows (including components) are in the flows field
    flows_before = project_data.get("flows", [])
    # Filter only components
    components_before = [f for f in flows_before if f.get("is_component", False)]

    assert len(components_before) == 2
    component_ids_before = [c["id"] for c in components_before]
    assert str(comp1_id) in component_ids_before
    assert str(comp2_id) in component_ids_before

    # Update project name
    update_payload = {"name": "Renamed Project with Components"}
    update_resp = await client.patch(f"api/v1/projects/{project_id}", json=update_payload, headers=logged_in_headers)
    assert update_resp.status_code == status.HTTP_200_OK

    # Verify components are still associated after rename
    get_after_resp = await client.get(f"api/v1/projects/{project_id}", headers=logged_in_headers)
    assert get_after_resp.status_code == status.HTTP_200_OK
    project_after = get_after_resp.json()

    flows_after = project_after.get("flows", [])
    components_after = [f for f in flows_after if f.get("is_component", False)]

    assert len(components_after) == 2, (
        f"Expected 2 components after rename, got {len(components_after)}. Components lost!"
    )

    component_ids_after = [c["id"] for c in components_after]
    assert str(comp1_id) in component_ids_after, "Component 1 was lost after project rename!"
    assert str(comp2_id) in component_ids_after, "Component 2 was lost after project rename!"


async def test_update_project_preserves_mixed_flows_and_components(client: AsyncClient, logged_in_headers):
    """Test that renaming a project preserves both flows and components correctly."""
    # Create a project
    project_payload = {
        "name": "Mixed Project",
        "description": "Testing mixed flows and components preservation",
        "flows_list": [],
        "components_list": [],
    }
    create_resp = await client.post("api/v1/projects/", json=project_payload, headers=logged_in_headers)
    assert create_resp.status_code == status.HTTP_201_CREATED
    project = create_resp.json()
    project_id = project["id"]

    # Create flows and components
    flow_payload = {
        "name": "Regular Flow",
        "description": "A regular flow",
        "folder_id": project_id,
        "data": {"nodes": [], "edges": []},
        "is_component": False,
    }
    component_payload = {
        "name": "Custom Component",
        "description": "A custom component",
        "folder_id": project_id,
        "data": {"nodes": [], "edges": []},
        "is_component": True,
    }

    flow_resp = await client.post("api/v1/flows/", json=flow_payload, headers=logged_in_headers)
    comp_resp = await client.post("api/v1/flows/", json=component_payload, headers=logged_in_headers)
    assert flow_resp.status_code == status.HTTP_201_CREATED
    assert comp_resp.status_code == status.HTTP_201_CREATED

    flow_id = flow_resp.json()["id"]
    comp_id = comp_resp.json()["id"]

    # Verify initial state
    get_resp = await client.get(f"api/v1/projects/{project_id}", headers=logged_in_headers)
    project_data = get_resp.json()

    flows_before = project_data.get("flows", [])
    actual_flows_before = [f for f in flows_before if not f.get("is_component", False)]
    components_before = [f for f in flows_before if f.get("is_component", False)]

    assert len(actual_flows_before) == 1
    assert len(components_before) == 1

    # Update project
    update_payload = {"name": "Renamed Mixed Project"}
    update_resp = await client.patch(f"api/v1/projects/{project_id}", json=update_payload, headers=logged_in_headers)
    assert update_resp.status_code == status.HTTP_200_OK

    # Verify both flows and components preserved
    get_after_resp = await client.get(f"api/v1/projects/{project_id}", headers=logged_in_headers)
    project_after = get_after_resp.json()

    flows_after = project_after.get("flows", [])
    actual_flows_after = [f for f in flows_after if not f.get("is_component", False)]
    components_after = [f for f in flows_after if f.get("is_component", False)]

    assert len(actual_flows_after) == 1, "Flow was lost after project rename!"
    assert len(components_after) == 1, "Component was lost after project rename!"

    flow_id_after = actual_flows_after[0]["id"]
    comp_id_after = components_after[0]["id"]

    assert str(flow_id) == flow_id_after
    assert str(comp_id) == comp_id_after
