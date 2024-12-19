from fastapi import status
from httpx import AsyncClient


async def test_create_folder(client: AsyncClient, logged_in_headers):
    response = await client.get("api/v1/api_key/", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "api_keys" in result, "The dictionary must contain a key called 'api_keys'"
    assert "user_id" in result, "The dictionary must contain a key called 'user_id'"
    assert "total_count" in result, "The dictionary must contain a key called 'total_count'"


async def test_create_api_key_route(client: AsyncClient, logged_in_headers, active_user):
    basic_case = {
        "name": "string",
        "total_uses": 0,
        "is_active": True,
        "api_key": "string",
        "user_id": str(active_user.id),
    }
    response = await client.post("api/v1/api_key/", json=basic_case, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "api_key" in result, "The dictionary must contain a key called 'api_key'"
    assert "id" in result, "The dictionary must contain a key called 'id'"
    assert "is_active" in result, "The dictionary must contain a key called 'is_active'"
    assert "last_used_at" in result, "The dictionary must contain a key called 'last_used_at'"
    assert "name" in result, "The dictionary must contain a key called 'name'"
    assert "total_uses" in result, "The dictionary must contain a key called 'total_uses'"
    assert "user_id" in result, "The dictionary must contain a key called 'user_id'"


async def test_delete_api_key_route(client: AsyncClient, logged_in_headers, active_user):
    basic_case = {
        "name": "string",
        "total_uses": 0,
        "is_active": True,
        "api_key": "string",
        "user_id": str(active_user.id),
    }
    response_ = await client.post("api/v1/api_key/", json=basic_case, headers=logged_in_headers)
    id_ = response_.json()["id"]

    response = await client.delete(f"api/v1/api_key/{id_}", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "detail" in result, "The dictionary must contain a key called 'detail'"


async def test_save_store_api_key(client: AsyncClient, logged_in_headers):
    basic_case = {"api_key": "string"}
    response = await client.post("api/v1/api_key/store", json=basic_case, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "detail" in result, "The dictionary must contain a key called 'detail'"
