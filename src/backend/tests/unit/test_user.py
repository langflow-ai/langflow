from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from langflow.services.auth.utils import create_super_user, get_password_hash
from langflow.services.database.models.user import UserUpdate
from langflow.services.database.models.user.model import User
from langflow.services.database.utils import session_getter
from langflow.services.deps import get_db_service, get_settings_service
from lfx.services.settings.constants import DEFAULT_SUPERUSER
from sqlmodel import select


@pytest.fixture
async def super_user(client):  # noqa: ARG001
    settings_manager = get_settings_service()
    auth_settings = settings_manager.auth_settings
    async with session_getter(get_db_service()) as db:
        return await create_super_user(
            db=db,
            username=auth_settings.SUPERUSER,
            password=(
                auth_settings.SUPERUSER_PASSWORD.get_secret_value()
                if hasattr(auth_settings.SUPERUSER_PASSWORD, "get_secret_value")
                else auth_settings.SUPERUSER_PASSWORD
            ),
        )


@pytest.fixture
async def super_user_headers(
    client: AsyncClient,
    super_user,  # noqa: ARG001
):
    settings_service = get_settings_service()
    auth_settings = settings_service.auth_settings
    login_data = {
        # SUPERUSER may be reset to default depending on AUTO_LOGIN; use constant for stability in tests
        "username": DEFAULT_SUPERUSER if auth_settings.AUTO_LOGIN else auth_settings.SUPERUSER,
        "password": (
            auth_settings.SUPERUSER_PASSWORD.get_secret_value()
            if hasattr(auth_settings.SUPERUSER_PASSWORD, "get_secret_value")
            else auth_settings.SUPERUSER_PASSWORD
        ),
    }
    response = await client.post("api/v1/login", data=login_data)
    assert response.status_code == 200
    tokens = response.json()
    a_token = tokens["access_token"]
    return {"Authorization": f"Bearer {a_token}"}


@pytest.fixture
async def deactivated_user(client):  # noqa: ARG001
    async with session_getter(get_db_service()) as session:
        user = User(
            username="deactivateduser",
            password=get_password_hash("testpassword"),
            is_active=False,
            is_superuser=False,
            last_login_at=datetime.now(tz=timezone.utc),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


async def test_user_waiting_for_approval(client):
    username = "waitingforapproval"
    password = "testpassword"  # noqa: S105

    # Debug: Check if the user already exists
    async with session_getter(get_db_service()) as session:
        stmt = select(User).where(User.username == username)
        existing_user = (await session.exec(stmt)).first()
        if existing_user:
            pytest.fail(
                f"User {username} already exists before the test. Database URL: {get_db_service().database_url}"
            )

    # Create a user that is not active and has never logged in
    async with session_getter(get_db_service()) as session:
        user = User(
            username=username,
            password=get_password_hash(password),
            is_active=False,
            last_login_at=None,
        )
        session.add(user)
        await session.commit()

    login_data = {"username": "waitingforapproval", "password": "testpassword"}
    response = await client.post("api/v1/login", data=login_data)
    assert response.status_code == 400
    assert response.json()["detail"] == "Waiting for approval"

    # Debug: Check if the user still exists after the test
    async with session_getter(get_db_service()) as session:
        stmt = select(User).where(User.username == username)
        existing_user = (await session.exec(stmt)).first()
        if existing_user:
            pass
        else:
            pytest.fail(f"User {username} does not exist after the test. This is unexpected.")


@pytest.mark.api_key_required
async def test_deactivated_user_cannot_login(client: AsyncClient, deactivated_user):
    login_data = {"username": deactivated_user.username, "password": "testpassword"}
    response = await client.post("api/v1/login", data=login_data)
    assert response.status_code == 401, response.json()
    assert response.json()["detail"] == "Inactive user", response.text


@pytest.mark.usefixtures("deactivated_user")
async def test_deactivated_user_cannot_access(client: AsyncClient, logged_in_headers):
    # Assuming the headers for deactivated_user
    response = await client.get("api/v1/users/", headers=logged_in_headers)
    assert response.status_code == 403, response.status_code
    assert response.json()["detail"] == "The user doesn't have enough privileges", response.text


@pytest.mark.api_key_required
async def test_data_consistency_after_update(client: AsyncClient, active_user, logged_in_headers, super_user_headers):
    user_id = active_user.id
    update_data = UserUpdate(is_active=False)

    response = await client.patch(f"/api/v1/users/{user_id}", json=update_data.model_dump(), headers=super_user_headers)
    assert response.status_code == 200, response.json()

    # Fetch the updated user from the database
    response = await client.get("api/v1/users/whoami", headers=logged_in_headers)
    assert response.status_code == 401, response.json()
    assert response.json()["detail"] == "User not found or is inactive."


@pytest.mark.api_key_required
async def test_data_consistency_after_delete(client: AsyncClient, test_user, super_user_headers):
    user_id = test_user.get("id")
    response = await client.delete(f"/api/v1/users/{user_id}", headers=super_user_headers)
    assert response.status_code == 200, response.json()

    # Attempt to fetch the deleted user from the database
    response = await client.get("api/v1/users/", headers=super_user_headers)
    assert response.status_code == 200
    assert all(user["id"] != user_id for user in response.json()["users"])


@pytest.mark.api_key_required
async def test_inactive_user(client: AsyncClient):
    # Create a user that is not active and has a last_login_at value
    async with session_getter(get_db_service()) as session:
        user = User(
            username="inactiveuser",
            password=get_password_hash("testpassword"),
            is_active=False,
            last_login_at=datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        )
        session.add(user)
        await session.commit()

    login_data = {"username": "inactiveuser", "password": "testpassword"}
    response = await client.post("api/v1/login", data=login_data)
    assert response.status_code == 401
    assert response.json()["detail"] == "Inactive user"


@pytest.mark.api_key_required
def test_add_user(test_user):
    assert test_user["username"] == "testuser"


@pytest.mark.api_key_required
async def test_read_all_users(client: AsyncClient, super_user_headers):
    response = await client.get("api/v1/users/", headers=super_user_headers)
    assert response.status_code == 200, response.json()
    assert isinstance(response.json()["users"], list)


@pytest.mark.api_key_required
async def test_normal_user_cant_read_all_users(client: AsyncClient, logged_in_headers):
    response = await client.get("api/v1/users/", headers=logged_in_headers)
    assert response.status_code == 403, response.json()
    assert response.json() == {"detail": "The user doesn't have enough privileges"}


@pytest.mark.api_key_required
async def test_patch_user(client: AsyncClient, active_user, logged_in_headers):
    user_id = active_user.id
    update_data = UserUpdate(
        username="newname",
    )

    response = await client.patch(f"/api/v1/users/{user_id}", json=update_data.model_dump(), headers=logged_in_headers)
    assert response.status_code == 200, response.json()
    update_data = UserUpdate(
        profile_image="new_image",
    )

    response = await client.patch(f"/api/v1/users/{user_id}", json=update_data.model_dump(), headers=logged_in_headers)
    assert response.status_code == 200, response.json()


@pytest.mark.api_key_required
async def test_patch_reset_password(client: AsyncClient, active_user, logged_in_headers):
    user_id = active_user.id
    update_data = UserUpdate(
        password="newpassword",  # noqa: S106
    )

    response = await client.patch(
        f"/api/v1/users/{user_id}/reset-password",
        json=update_data.model_dump(),
        headers=logged_in_headers,
    )
    assert response.status_code == 200, response.json()
    # Now we need to test if the new password works
    login_data = {"username": active_user.username, "password": "newpassword"}
    response = await client.post("api/v1/login", data=login_data)
    assert response.status_code == 200


@pytest.mark.api_key_required
@pytest.mark.usefixtures("active_user")
async def test_patch_user_wrong_id(client: AsyncClient, logged_in_headers):
    user_id = "wrong_id"
    update_data = UserUpdate(
        username="newname",
    )

    response = await client.patch(f"/api/v1/users/{user_id}", json=update_data.model_dump(), headers=logged_in_headers)
    assert response.status_code == 422, response.json()
    json_response = response.json()
    detail = json_response["detail"]
    error = detail[0]
    assert error["loc"] == ["path", "user_id"]
    assert error["type"] == "uuid_parsing"


@pytest.mark.api_key_required
async def test_delete_user(client: AsyncClient, test_user, super_user_headers):
    user_id = test_user["id"]
    response = await client.delete(f"/api/v1/users/{user_id}", headers=super_user_headers)
    assert response.status_code == 200
    assert response.json() == {"detail": "User deleted"}


@pytest.mark.api_key_required
@pytest.mark.usefixtures("test_user")
async def test_delete_user_wrong_id(client: AsyncClient, super_user_headers):
    user_id = "wrong_id"
    response = await client.delete(f"/api/v1/users/{user_id}", headers=super_user_headers)
    assert response.status_code == 422
    json_response = response.json()
    detail = json_response["detail"]
    error = detail[0]
    assert error["loc"] == ["path", "user_id"]
    assert error["type"] == "uuid_parsing"


@pytest.mark.api_key_required
async def test_normal_user_cant_delete_user(client: AsyncClient, test_user, logged_in_headers):
    user_id = test_user["id"]
    response = await client.delete(f"/api/v1/users/{user_id}", headers=logged_in_headers)
    assert response.status_code == 403
    assert response.json() == {"detail": "The user doesn't have enough privileges"}
