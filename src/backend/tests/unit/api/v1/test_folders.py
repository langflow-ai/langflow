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
    assert "name" in result.keys(), "The dictionary must contain a key called 'name'"
    assert "description" in result.keys(), "The dictionary must contain a key called 'description'"
    assert "id" in result.keys(), "The dictionary must contain a key called 'id'"
    assert "parent_id" in result.keys(), "The dictionary must contain a key called 'parent_id'"


async def test_read_folders(client: AsyncClient, logged_in_headers, basic_case):
    _response = await client.post("api/v1/folders/", json=basic_case, headers=logged_in_headers)
    _id = _response.json()["id"]
    response = await client.get(f"api/v1/folders/{_id}", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "name" in result.keys(), "The dictionary must contain a key called 'name'"
    assert "description" in result.keys(), "The dictionary must contain a key called 'description'"
    assert "id" in result.keys(), "The dictionary must contain a key called 'id'"
    assert "parent_id" in result.keys(), "The dictionary must contain a key called 'parent_id'"
