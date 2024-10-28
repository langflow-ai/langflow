from fastapi import status
from httpx import AsyncClient


async def test_add_user(client: AsyncClient):
    basic_case = {"username": "string", "password": "string"}
    response = await client.post("api/v1/users/", json=basic_case)
    result = response.json()

    assert response.status_code == status.HTTP_201_CREATED
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "id" in result, "The result must have an 'id' key"
    assert "is_active" in result, "The result must have an 'is_active' key"
    assert "is_superuser" in result, "The result must have an 'is_superuser' key"
    assert "last_login_at" in result, "The result must have an 'last_login_at' key"
    assert "profile_image" in result, "The result must have an 'profile_image' key"
    assert "store_api_key" in result, "The result must have an 'store_api_key' key"
    assert "updated_at" in result, "The result must have an 'updated_at' key"
    assert "username" in result, "The result must have an 'username' key"


async def test_read_current_user(client: AsyncClient, logged_in_headers):
    response = await client.get("api/v1/users/whoami", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "id" in result, "The result must have an 'id' key"
    assert "is_active" in result, "The result must have an 'is_active' key"
    assert "is_superuser" in result, "The result must have an 'is_superuser' key"
    assert "last_login_at" in result, "The result must have an 'last_login_at' key"
    assert "profile_image" in result, "The result must have an 'profile_image' key"
    assert "store_api_key" in result, "The result must have an 'store_api_key' key"
    assert "updated_at" in result, "The result must have an 'updated_at' key"
    assert "username" in result, "The result must have an 'username' key"


async def test_read_all_users(client: AsyncClient, logged_in_headers_super_user):
    response = await client.get("api/v1/users/", headers=logged_in_headers_super_user)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "total_count" in result, "The result must have an 'total_count' key"
    assert "users" in result, "The result must have an 'users' key"


async def test_patch_user(client: AsyncClient, logged_in_headers_super_user):
    name = "string"
    updated_name = "string2"
    basic_case = {"username": name, "password": "string"}
    _response = await client.post("api/v1/users/", json=basic_case)
    _id = _response.json()["id"]
    basic_case["username"] = updated_name
    response = await client.patch(f"api/v1/users/{_id}", json=basic_case, headers=logged_in_headers_super_user)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "id" in result, "The result must have an 'id' key"
    assert "is_active" in result, "The result must have an 'is_active' key"
    assert "is_superuser" in result, "The result must have an 'is_superuser' key"
    assert "last_login_at" in result, "The result must have an 'last_login_at' key"
    assert "profile_image" in result, "The result must have an 'profile_image' key"
    assert "store_api_key" in result, "The result must have an 'store_api_key' key"
    assert "updated_at" in result, "The result must have an 'updated_at' key"
    assert "username" in result, "The result must have an 'username' key"
    assert result["username"] == updated_name, "The username must be updated"


async def test_reset_password(client: AsyncClient, logged_in_headers, active_user):
    _id = str(active_user.id)
    basic_case = {"username": "string", "password": "new_password"}
    response = await client.patch(f"api/v1/users/{_id}/reset-password", json=basic_case, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "id" in result, "The result must have an 'id' key"
    assert "is_active" in result, "The result must have an 'is_active' key"
    assert "is_superuser" in result, "The result must have an 'is_superuser' key"
    assert "last_login_at" in result, "The result must have an 'last_login_at' key"
    assert "profile_image" in result, "The result must have an 'profile_image' key"
    assert "store_api_key" in result, "The result must have an 'store_api_key' key"
    assert "updated_at" in result, "The result must have an 'updated_at' key"
    assert "username" in result, "The result must have an 'username' key"


async def test_delete_user(client: AsyncClient, logged_in_headers_super_user):
    basic_case = {"username": "string", "password": "string"}
    _response = await client.post("api/v1/users/", json=basic_case)
    _id = _response.json()["id"]
    response = await client.delete(f"api/v1/users/{_id}", headers=logged_in_headers_super_user)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "detail" in result, "The result must have an 'detail' key"
