import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.fixture
def basic_case():
    return {
        "name": "New Project",
        "description": "",
        "flows_list": [],
        "components_list": [],
    }


async def test_create_folder(client: AsyncClient, logged_in_headers, basic_case):
    # Configure client to follow redirects
    client.follow_redirects = True

    response = await client.post("api/v1/folders/", json=basic_case, headers=logged_in_headers)
    result = response.json()

    # Check that we're getting a valid response from the projects endpoint
    assert response.status_code == status.HTTP_201_CREATED
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "name" in result, "The dictionary must contain a key called 'name'"
    assert "description" in result, "The dictionary must contain a key called 'description'"
    assert "id" in result, "The dictionary must contain a key called 'id'"
    assert "parent_id" in result, "The dictionary must contain a key called 'parent_id'"


async def test_read_folders(client: AsyncClient, logged_in_headers):
    # Configure client to follow redirects
    client.follow_redirects = True

    response = await client.get("api/v1/folders/", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, list), "The result must be a list"
    assert len(result) > 0, "The list must not be empty"


async def test_read_folder(client: AsyncClient, logged_in_headers, basic_case):
    # Configure client to follow redirects
    client.follow_redirects = True

    # Create a folder first
    response_ = await client.post("api/v1/folders/", json=basic_case, headers=logged_in_headers)
    id_ = response_.json()["id"]

    # Get the folder
    response = await client.get(f"api/v1/folders/{id_}", headers=logged_in_headers)
    result = response.json()

    # The response structure may be different depending on whether pagination is enabled
    if "folder" in result:
        # Handle paginated project response
        folder_data = result["folder"]
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(folder_data, dict), "The folder data must be a dictionary"
        assert "name" in folder_data, "The dictionary must contain a key called 'name'"
        assert "description" in folder_data, "The dictionary must contain a key called 'description'"
        assert "id" in folder_data, "The dictionary must contain a key called 'id'"
    elif "project" in result:
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


async def test_update_folder(client: AsyncClient, logged_in_headers, basic_case):
    # Configure client to follow redirects
    client.follow_redirects = True

    update_case = basic_case.copy()
    update_case["name"] = "Updated Folder"

    # Create a folder first
    response_ = await client.post("api/v1/folders/", json=basic_case, headers=logged_in_headers)
    id_ = response_.json()["id"]

    # Update the folder
    response = await client.patch(f"api/v1/folders/{id_}", json=update_case, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "name" in result, "The dictionary must contain a key called 'name'"
    assert "description" in result, "The dictionary must contain a key called 'description'"
    assert "id" in result, "The dictionary must contain a key called 'id'"
    assert "parent_id" in result, "The dictionary must contain a key called 'parent_id'"
