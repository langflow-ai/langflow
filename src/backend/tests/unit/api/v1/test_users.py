from datetime import timedelta
from uuid import uuid4

from fastapi import status
from httpx import AsyncClient
from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_auth_service, get_settings_service, session_scope


async def test_add_user_public_signup(client: AsyncClient):
    """Test public user registration (sign up) without authentication."""
    basic_case = {"username": "newuser", "password": "newpassword123"}
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
    assert result["username"] == "newuser", "The username must match"
    assert result["is_superuser"] is False, "New users should not be superusers"


async def test_add_user_public_signup_disabled_blocks_anonymous(client: AsyncClient, monkeypatch):
    """When public signup is disabled, anonymous callers cannot create users."""
    monkeypatch.setattr(get_settings_service().auth_settings, "ENABLE_PUBLIC_SIGNUP", False)

    response = await client.post(
        "api/v1/users/",
        json={"username": "blocked_public_signup", "password": "newpassword123"},
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"] == "Public user registration is disabled."


async def test_add_user_public_signup_disabled_ignores_auto_login_fallback(client: AsyncClient, monkeypatch):
    """AUTO_LOGIN fallback without request credentials must not bypass disabled public signup."""
    auth_settings = get_settings_service().auth_settings
    monkeypatch.setattr(auth_settings, "ENABLE_PUBLIC_SIGNUP", False)
    monkeypatch.setattr(auth_settings, "AUTO_LOGIN", True)
    monkeypatch.setattr(auth_settings, "skip_auth_auto_login", True)

    response = await client.post(
        "api/v1/users/",
        json={"username": "blocked_auto_login_fallback", "password": "newpassword123"},
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"] == "Public user registration is disabled."


async def test_add_user_public_signup_disabled_blocks_invalid_credentials(client: AsyncClient, monkeypatch):
    """Invalid credentials must not count as authorization to create users."""
    monkeypatch.setattr(get_settings_service().auth_settings, "ENABLE_PUBLIC_SIGNUP", False)

    response = await client.post(
        "api/v1/users/",
        json={"username": "blocked_invalid_token", "password": "newpassword123"},
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"] == "Public user registration is disabled."


async def test_add_user_public_signup_disabled_blocks_normal_user(client: AsyncClient, logged_in_headers, monkeypatch):
    """Disabling public signup should not let a non-superuser create more users."""
    monkeypatch.setattr(get_settings_service().auth_settings, "ENABLE_PUBLIC_SIGNUP", False)

    response = await client.post(
        "api/v1/users/",
        json={"username": "blocked_by_normal_user", "password": "newpassword123"},
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"] == "Public user registration is disabled."


async def test_add_user_public_signup_disabled_blocks_inactive_superuser(client: AsyncClient, monkeypatch):
    """An inactive superuser token must not authorize user creation."""
    monkeypatch.setattr(get_settings_service().auth_settings, "ENABLE_PUBLIC_SIGNUP", False)
    user_id = uuid4()
    inactive_superuser = User(
        id=user_id,
        username=f"inactive_superuser_{user_id}",
        password=get_auth_service().get_password_hash("testpassword"),
        is_active=False,
        is_superuser=True,
    )

    async with session_scope() as session:
        session.add(inactive_superuser)
        await session.flush()
        await session.refresh(inactive_superuser)

    token = get_auth_service().create_token(
        data={"sub": str(user_id), "type": "access"},
        expires_delta=timedelta(hours=1),
    )
    try:
        response = await client.post(
            "api/v1/users/",
            json={"username": "blocked_inactive_superuser", "password": "newpassword123"},
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        async with session_scope() as session:
            if db_user := await session.get(User, user_id):
                await session.delete(db_user)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"] == "Public user registration is disabled."


async def test_add_user_public_signup_disabled_allows_superuser(
    client: AsyncClient, logged_in_headers_super_user, monkeypatch
):
    """Superusers can still provision accounts when anonymous signup is disabled."""
    monkeypatch.setattr(get_settings_service().auth_settings, "ENABLE_PUBLIC_SIGNUP", False)

    response = await client.post(
        "api/v1/users/",
        json={"username": "created_by_superuser", "password": "newpassword123"},
        headers=logged_in_headers_super_user,
    )
    result = response.json()

    assert response.status_code == status.HTTP_201_CREATED
    assert result["username"] == "created_by_superuser"
    assert result["is_superuser"] is False


async def test_add_user_public_signup_disabled_allows_superuser_cookie(
    client: AsyncClient, logged_in_headers_super_user, monkeypatch
):
    """Cookie-authenticated superusers can still provision accounts when public signup is disabled."""
    monkeypatch.setattr(get_settings_service().auth_settings, "ENABLE_PUBLIC_SIGNUP", False)
    token = logged_in_headers_super_user["Authorization"].removeprefix("Bearer ")

    response = await client.post(
        "api/v1/users/",
        json={"username": "created_by_superuser_cookie", "password": "newpassword123"},
        cookies={"access_token_lf": token},
    )
    result = response.json()

    assert response.status_code == status.HTTP_201_CREATED
    assert result["username"] == "created_by_superuser_cookie"
    assert result["is_superuser"] is False


async def test_add_user_public_signup_disabled_allows_superuser_api_key_header_and_query(
    client: AsyncClient, active_super_user, monkeypatch
):
    """API-key-authenticated superusers can still provision accounts when public signup is disabled."""
    monkeypatch.setattr(get_settings_service().auth_settings, "ENABLE_PUBLIC_SIGNUP", False)
    raw_key = f"superuser-key-{active_super_user.id}"
    api_key = ApiKey(
        name="superuser_signup_key",
        user_id=active_super_user.id,
        api_key=raw_key,
        hashed_api_key=get_auth_service().get_password_hash(raw_key),
    )

    async with session_scope() as session:
        session.add(api_key)
        await session.flush()
        await session.refresh(api_key)

    try:
        header_response = await client.post(
            "api/v1/users/",
            json={"username": "created_by_superuser_api_key_header", "password": "newpassword123"},
            headers={"x-api-key": raw_key},
        )
        query_response = await client.post(
            "api/v1/users/",
            json={"username": "created_by_superuser_api_key_query", "password": "newpassword123"},
            params={"x-api-key": raw_key},
        )
    finally:
        async with session_scope() as session:
            if db_key := await session.get(ApiKey, api_key.id):
                await session.delete(db_key)

    header_result = header_response.json()
    query_result = query_response.json()

    assert header_response.status_code == status.HTTP_201_CREATED
    assert header_result["username"] == "created_by_superuser_api_key_header"
    assert header_result["is_superuser"] is False
    assert query_response.status_code == status.HTTP_201_CREATED
    assert query_result["username"] == "created_by_superuser_api_key_query"
    assert query_result["is_superuser"] is False


async def test_add_user_openapi_schema_stays_public(client: AsyncClient):
    """The signup route advertises optional auth while public signup remains supported."""
    response = await client.get("/openapi.json")
    assert response.status_code == status.HTTP_200_OK

    users_post_schema = response.json()["paths"]["/api/v1/users/"]["post"]
    assert users_post_schema["security"] == [
        {},
        {"OAuth2PasswordBearerCookie": []},
        {"API key query": []},
        {"API key header": []},
    ]


async def test_add_user_duplicate_username(client: AsyncClient):
    """Test that duplicate usernames are rejected."""
    basic_case = {"username": "duplicateuser", "password": "password123"}
    # Create first user
    response1 = await client.post("api/v1/users/", json=basic_case)
    assert response1.status_code == status.HTTP_201_CREATED

    # Try to create second user with same username
    response2 = await client.post("api/v1/users/", json=basic_case)
    assert response2.status_code == status.HTTP_400_BAD_REQUEST
    assert "unavailable" in response2.json()["detail"].lower()


async def test_add_user(client: AsyncClient, logged_in_headers_super_user):
    basic_case = {"username": "string", "password": "string"}
    response = await client.post("api/v1/users/", json=basic_case, headers=logged_in_headers_super_user)
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
    response_ = await client.post("api/v1/users/", json=basic_case, headers=logged_in_headers_super_user)
    id_ = response_.json()["id"]
    basic_case["username"] = updated_name
    response = await client.patch(f"api/v1/users/{id_}", json=basic_case, headers=logged_in_headers_super_user)
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
    id_ = str(active_user.id)
    basic_case = {"username": "string", "password": "new_password"}
    response = await client.patch(f"api/v1/users/{id_}/reset-password", json=basic_case, headers=logged_in_headers)
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
    response_ = await client.post("api/v1/users/", json=basic_case, headers=logged_in_headers_super_user)
    id_ = response_.json()["id"]
    response = await client.delete(f"api/v1/users/{id_}", headers=logged_in_headers_super_user)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "detail" in result, "The result must have an 'detail' key"


async def test_patch_user_self_deactivation_forbidden(client: AsyncClient, logged_in_headers, active_user):
    """Test that a user cannot deactivate their own account."""
    user_id = str(active_user.id)
    response = await client.patch(
        f"api/v1/users/{user_id}",
        json={"is_active": False},
        headers=logged_in_headers,
    )
    result = response.json()

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "can't deactivate your own user account" in result["detail"]


async def test_patch_user_self_deactivation_forbidden_superuser(
    client: AsyncClient, logged_in_headers_super_user, active_super_user
):
    """Test that even a superuser cannot deactivate their own account."""
    user_id = str(active_super_user.id)
    response = await client.patch(
        f"api/v1/users/{user_id}",
        json={"is_active": False},
        headers=logged_in_headers_super_user,
    )
    result = response.json()

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "can't deactivate your own user account" in result["detail"]


async def test_read_all_users_search(client: AsyncClient, logged_in_headers_super_user):
    """Test that the search parameter filters users by username across all pages."""
    # Create several users with distinct usernames
    usernames = ["alice_search", "bob_search", "charlie_search"]
    created_ids = []
    for username in usernames:
        response = await client.post(
            "api/v1/users/",
            json={"username": username, "password": "password123"},
            headers=logged_in_headers_super_user,
        )
        assert response.status_code == status.HTTP_201_CREATED
        created_ids.append(response.json()["id"])

    # Search for "alice" — should return exactly one match
    response = await client.get(
        "api/v1/users/?search=alice",
        headers=logged_in_headers_super_user,
    )
    assert response.status_code == status.HTTP_200_OK
    result = response.json()
    assert result["total_count"] == 1
    assert result["users"][0]["username"] == "alice_search"

    # Search for "_search" — should match all three created users
    response = await client.get(
        "api/v1/users/?search=_search",
        headers=logged_in_headers_super_user,
    )
    assert response.status_code == status.HTTP_200_OK
    result = response.json()
    assert result["total_count"] == 3
    returned_usernames = {u["username"] for u in result["users"]}
    assert returned_usernames == set(usernames)

    # Search for a non-existent username — should return zero results
    response = await client.get(
        "api/v1/users/?search=nonexistentuser",
        headers=logged_in_headers_super_user,
    )
    assert response.status_code == status.HTTP_200_OK
    result = response.json()
    assert result["total_count"] == 0
    assert result["users"] == []

    # Search is case-insensitive
    response = await client.get(
        "api/v1/users/?search=ALICE",
        headers=logged_in_headers_super_user,
    )
    assert response.status_code == status.HTTP_200_OK
    result = response.json()
    assert result["total_count"] == 1
    assert result["users"][0]["username"] == "alice_search"

    # Search combined with pagination: limit=1 should return 1 user but total_count=3
    response = await client.get(
        "api/v1/users/?search=_search&limit=1",
        headers=logged_in_headers_super_user,
    )
    assert response.status_code == status.HTTP_200_OK
    result = response.json()
    assert result["total_count"] == 3
    assert len(result["users"]) == 1

    # Clean up
    for user_id in created_ids:
        await client.delete(f"api/v1/users/{user_id}", headers=logged_in_headers_super_user)


async def test_patch_user_deactivate_other_user_allowed(client: AsyncClient, logged_in_headers_super_user):
    """Test that a superuser can deactivate another user's account."""
    # Create a new user
    basic_case = {"username": "user_to_deactivate", "password": "password123"}
    create_response = await client.post("api/v1/users/", json=basic_case, headers=logged_in_headers_super_user)
    assert create_response.status_code == status.HTTP_201_CREATED
    user_id = create_response.json()["id"]

    # Deactivate the other user
    response = await client.patch(
        f"api/v1/users/{user_id}",
        json={"is_active": False},
        headers=logged_in_headers_super_user,
    )
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert result["is_active"] is False
