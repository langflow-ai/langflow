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


async def test_delete_api_key_route_unauthorized(client: AsyncClient, logged_in_headers, active_user):
    """Test that users cannot delete API keys belonging to other users."""
    # Import required modules
    from langflow.services.auth.utils import get_password_hash
    from langflow.services.database.models.user.model import User
    from langflow.services.deps import session_scope
    from sqlmodel import select

    # Create first user's API key
    basic_case = {
        "name": "test_key_user1",
        "total_uses": 0,
        "is_active": True,
        "api_key": "string",
        "user_id": str(active_user.id),
    }
    response = await client.post("api/v1/api_key/", json=basic_case, headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    user1_api_key_id = response.json()["id"]

    # Create a second user and get their auth headers
    async with session_scope() as session:
        user2 = User(
            username="testuser2",
            password=get_password_hash("testpassword2"),
            is_active=True,
            is_superuser=False,
        )
        stmt = select(User).where(User.username == user2.username)
        existing_user = (await session.exec(stmt)).first()
        if not existing_user:
            session.add(user2)
            await session.flush()
            await session.refresh(user2)
        else:
            user2 = existing_user

    # Login as second user
    login_data = {"username": "testuser2", "password": "testpassword2"}
    response = await client.post("api/v1/login", data=login_data)
    assert response.status_code == status.HTTP_200_OK
    user2_token = response.json()["access_token"]
    user2_headers = {"Authorization": f"Bearer {user2_token}"}

    # Try to delete first user's API key using second user's credentials
    response = await client.delete(f"api/v1/api_key/{user1_api_key_id}", headers=user2_headers)

    # Should fail with 400 error (API Key not found - we don't reveal it exists)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "API Key not found" in response.json()["detail"]

    # Verify the first user's API key still exists by trying to delete it with correct credentials
    response = await client.delete(f"api/v1/api_key/{user1_api_key_id}", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["detail"] == "API Key deleted"

    # Clean up second user
    async with session_scope() as session:
        user = await session.get(User, user2.id)
        if user:
            await session.delete(user)
