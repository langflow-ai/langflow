from fastapi import status
from httpx import AsyncClient


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


async def test_add_user_signup_refused_when_disabled(client: AsyncClient):
    """Public registration must be refused (403) when ENABLE_SIGNUP is False."""
    from langflow.services.deps import get_settings_service

    auth_settings = get_settings_service().auth_settings
    original_signup = auth_settings.ENABLE_SIGNUP
    original_auto_login = auth_settings.AUTO_LOGIN
    # Pin AUTO_LOGIN to a permissive value so the 403 can only come from ENABLE_SIGNUP=False.
    auth_settings.AUTO_LOGIN = False
    auth_settings.ENABLE_SIGNUP = False
    try:
        response = await client.post("api/v1/users/", json={"username": "signupblocked", "password": "newpassword123"})
        assert response.status_code == status.HTTP_403_FORBIDDEN
    finally:
        auth_settings.ENABLE_SIGNUP = original_signup
        auth_settings.AUTO_LOGIN = original_auto_login


async def test_add_user_signup_refused_when_auto_login(client: AsyncClient):
    """Public registration must be refused (403) when AUTO_LOGIN is enabled."""
    from langflow.services.deps import get_settings_service

    auth_settings = get_settings_service().auth_settings
    original_auto_login = auth_settings.AUTO_LOGIN
    original_signup = auth_settings.ENABLE_SIGNUP
    # Pin ENABLE_SIGNUP to a permissive value so the 403 can only come from AUTO_LOGIN=True.
    auth_settings.ENABLE_SIGNUP = True
    auth_settings.AUTO_LOGIN = True
    try:
        response = await client.post(
            "api/v1/users/", json={"username": "autologinblocked", "password": "newpassword123"}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
    finally:
        auth_settings.AUTO_LOGIN = original_auto_login
        auth_settings.ENABLE_SIGNUP = original_signup


async def test_add_user_superuser_succeeds_when_signup_disabled(client: AsyncClient, logged_in_headers_super_user):
    """An authenticated superuser can still create users when public signup is disabled.

    Disabling public sign up must only block the anonymous path; it must not break the
    admin "add user" flow (AdminPage -> useAddUser -> POST /api/v1/users/).
    """
    from langflow.services.deps import get_settings_service

    auth_settings = get_settings_service().auth_settings
    original_signup = auth_settings.ENABLE_SIGNUP
    original_auto_login = auth_settings.AUTO_LOGIN
    auth_settings.AUTO_LOGIN = False
    auth_settings.ENABLE_SIGNUP = False
    try:
        # Superuser-authenticated request is allowed through despite signup being disabled.
        admin_response = await client.post(
            "api/v1/users/",
            json={"username": "adminmade", "password": "newpassword123"},
            headers=logged_in_headers_super_user,
        )
        assert admin_response.status_code == status.HTTP_201_CREATED

        # The anonymous path is still refused. Clear the cookie jar first: the shared
        # AsyncClient persists the superuser's access_token_lf cookie set by the login
        # fixture, which would otherwise authenticate this "anonymous" request too.
        client.cookies.clear()
        anon_response = await client.post("api/v1/users/", json={"username": "anonmade", "password": "newpassword123"})
        assert anon_response.status_code == status.HTTP_403_FORBIDDEN
    finally:
        auth_settings.ENABLE_SIGNUP = original_signup
        auth_settings.AUTO_LOGIN = original_auto_login


async def test_add_user_non_superuser_refused_when_signup_disabled(client: AsyncClient, logged_in_headers):
    """A regular authenticated (non-superuser) user cannot create users when signup is disabled.

    Only superusers may bypass the gate; being merely authenticated is not enough.
    """
    from langflow.services.deps import get_settings_service

    auth_settings = get_settings_service().auth_settings
    original_signup = auth_settings.ENABLE_SIGNUP
    original_auto_login = auth_settings.AUTO_LOGIN
    auth_settings.AUTO_LOGIN = False
    auth_settings.ENABLE_SIGNUP = False
    try:
        response = await client.post(
            "api/v1/users/",
            json={"username": "regularmade", "password": "newpassword123"},
            headers=logged_in_headers,
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
    finally:
        auth_settings.ENABLE_SIGNUP = original_signup
        auth_settings.AUTO_LOGIN = original_auto_login


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
