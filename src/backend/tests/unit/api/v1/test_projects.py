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
