import json
from io import BytesIO

import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.fixture
def basic_case():
    return {
        "name": "New Folder",
        "description": "",
        "flows_list": [],
        "components_list": [],
    }


async def test_create_folder(client: AsyncClient, logged_in_headers, basic_case):
    response = await client.post("api/v1/folders/", json=basic_case, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_201_CREATED
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "name" in result, "The dictionary must contain a key called 'name'"
    assert "description" in result, "The dictionary must contain a key called 'description'"
    assert "id" in result, "The dictionary must contain a key called 'id'"
    assert "parent_id" in result, "The dictionary must contain a key called 'parent_id'"


async def test_read_folders(client: AsyncClient, logged_in_headers):
    response = await client.get("api/v1/folders/", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, list), "The result must be a list"
    assert len(result) > 0, "The list must not be empty"


async def test_read_folder(client: AsyncClient, logged_in_headers, basic_case):
    _response = await client.post("api/v1/folders/", json=basic_case, headers=logged_in_headers)
    _id = _response.json()["id"]
    response = await client.get(f"api/v1/folders/{_id}", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "name" in result, "The dictionary must contain a key called 'name'"
    assert "description" in result, "The dictionary must contain a key called 'description'"
    assert "id" in result, "The dictionary must contain a key called 'id'"
    assert "parent_id" in result, "The dictionary must contain a key called 'parent_id'"


async def test_update_folder(client: AsyncClient, logged_in_headers, basic_case):
    update_case = basic_case.copy()
    update_case["name"] = "Updated Folder"
    _response = await client.post("api/v1/folders/", json=basic_case, headers=logged_in_headers)
    _id = _response.json()["id"]
    response = await client.patch(f"api/v1/folders/{_id}", json=update_case, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "name" in result, "The dictionary must contain a key called 'name'"
    assert "description" in result, "The dictionary must contain a key called 'description'"
    assert "id" in result, "The dictionary must contain a key called 'id'"
    assert "parent_id" in result, "The dictionary must contain a key called 'parent_id'"


async def test_upload_file(client: AsyncClient, logged_in_headers):
    content = {
        "folder_name": "batatinhas",
        "folder_description": "batatinhas",
        "flows": [],
    }
    json_content = json.dumps(content).encode("utf-8")
    json_file = BytesIO(json_content)
    json_file.name = "minimal.json"
    files = {"file": (json_file.name, json_file, "application/json")}

    response = await client.post("api/v1/folders/upload/", files=files, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_201_CREATED
    assert isinstance(result, dict), "The result must be a dictionary"


async def test_download_file(client: AsyncClient, logged_in_headers):
    folder_id = "string"
    response = await client.get(f"api/v1/folders/download/{folder_id}", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "name" in result, "The dictionary must contain a key called 'name'"
    assert "description" in result, "The dictionary must contain a key called 'description'"
    assert "flows" in result, "The dictionary must contain a key called 'id'"


async def test_delete_folder(client: AsyncClient, logged_in_headers):
    folder_id = "string"
    response = await client.delete(f"api/v1/folders/{folder_id}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_204_NO_CONTENT
