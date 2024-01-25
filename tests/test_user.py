from datetime import datetime

import pytest
from langflow.services.auth.utils import create_super_user, get_password_hash
from langflow.services.database.models.user import UserUpdate
from langflow.services.database.models.user.model import User
from langflow.services.database.utils import session_getter
from langflow.services.deps import get_db_service, get_settings_service


@pytest.fixture
def super_user(client):
    settings_manager = get_settings_service()
    auth_settings = settings_manager.auth_settings
    with session_getter(get_db_service()) as session:
        return create_super_user(
            db=session,
            username=auth_settings.SUPERUSER,
            password=auth_settings.SUPERUSER_PASSWORD,
        )


@pytest.fixture
def super_user_headers(client, super_user):
    settings_service = get_settings_service()
    auth_settings = settings_service.auth_settings
    login_data = {
        "username": auth_settings.SUPERUSER,
        "password": auth_settings.SUPERUSER_PASSWORD,
    }
    response = client.post("/api/v1/login", data=login_data)
    assert response.status_code == 200
    tokens = response.json()
    a_token = tokens["access_token"]
    return {"Authorization": f"Bearer {a_token}"}


@pytest.fixture
def deactivated_user():
    with session_getter(get_db_service()) as session:
        user = User(
            username="deactivateduser",
            password=get_password_hash("testpassword"),
            is_active=False,
            is_superuser=False,
            last_login_at=datetime.now(),
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


def test_user_waiting_for_approval(
    client,
):
    # Create a user that is not active and has never logged in
    with session_getter(get_db_service()) as session:
        user = User(
            username="waitingforapproval",
            password=get_password_hash("testpassword"),
            is_active=False,
            last_login_at=None,
        )
        session.add(user)
        session.commit()

    login_data = {"username": "waitingforapproval", "password": "testpassword"}
    response = client.post("/api/v1/login", data=login_data)
    assert response.status_code == 400
    assert response.json()["detail"] == "Waiting for approval"


def test_deactivated_user_cannot_login(client, deactivated_user):
    login_data = {"username": deactivated_user.username, "password": "testpassword"}
    response = client.post("/api/v1/login", data=login_data)
    assert response.status_code == 400, response.json()
    assert response.json()["detail"] == "Inactive user"


def test_deactivated_user_cannot_access(client, deactivated_user, logged_in_headers):
    # Assuming the headers for deactivated_user
    response = client.get("/api/v1/users", headers=logged_in_headers)
    assert response.status_code == 400, response.json()
    assert response.json()["detail"] == "The user doesn't have enough privileges"


def test_data_consistency_after_update(client, active_user, logged_in_headers, super_user_headers):
    user_id = active_user.id
    update_data = UserUpdate(is_active=False)

    response = client.patch(f"/api/v1/users/{user_id}", json=update_data.dict(), headers=super_user_headers)
    assert response.status_code == 200, response.json()

    # Fetch the updated user from the database
    response = client.get("/api/v1/users/whoami", headers=logged_in_headers)
    assert response.status_code == 401, response.json()
    assert response.json()["detail"] == "Could not validate credentials"


def test_data_consistency_after_delete(client, test_user, super_user_headers):
    user_id = test_user.get("id")
    response = client.delete(f"/api/v1/users/{user_id}", headers=super_user_headers)
    assert response.status_code == 200, response.json()

    # Attempt to fetch the deleted user from the database
    response = client.get("/api/v1/users", headers=super_user_headers)
    assert response.status_code == 200
    assert all(user["id"] != user_id for user in response.json()["users"])


def test_inactive_user(client):
    # Create a user that is not active and has a last_login_at value
    with session_getter(get_db_service()) as session:
        user = User(
            username="inactiveuser",
            password=get_password_hash("testpassword"),
            is_active=False,
            last_login_at=datetime(2023, 1, 1, 0, 0, 0),
        )
        session.add(user)
        session.commit()

    login_data = {"username": "inactiveuser", "password": "testpassword"}
    response = client.post("/api/v1/login", data=login_data)
    assert response.status_code == 400
    assert response.json()["detail"] == "Inactive user"


def test_add_user(client, test_user):
    assert test_user["username"] == "testuser"


# This is not used in the Frontend at the moment
# def test_read_current_user(client: TestClient, active_user):
#     # First we need to login to get the access token
#     login_data = {"username": "testuser", "password": "testpassword"}
#     response = client.post("/api/v1/login", data=login_data)
#     assert response.status_code == 200

#     headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

#     response = client.get("/api/v1/user", headers=headers)
#     assert response.status_code == 200, response.json()
#     assert response.json()["username"] == "testuser"


def test_read_all_users(client, super_user_headers):
    response = client.get("/api/v1/users", headers=super_user_headers)
    assert response.status_code == 200, response.json()
    assert isinstance(response.json()["users"], list)


def test_normal_user_cant_read_all_users(client, logged_in_headers):
    response = client.get("/api/v1/users", headers=logged_in_headers)
    assert response.status_code == 400, response.json()
    assert response.json() == {"detail": "The user doesn't have enough privileges"}


def test_patch_user(client, active_user, logged_in_headers):
    user_id = active_user.id
    update_data = UserUpdate(
        username="newname",
    )

    response = client.patch(f"/api/v1/users/{user_id}", json=update_data.dict(), headers=logged_in_headers)
    assert response.status_code == 200, response.json()
    update_data = UserUpdate(
        profile_image="new_image",
    )

    response = client.patch(f"/api/v1/users/{user_id}", json=update_data.dict(), headers=logged_in_headers)
    assert response.status_code == 200, response.json()


def test_patch_reset_password(client, active_user, logged_in_headers):
    user_id = active_user.id
    update_data = UserUpdate(
        password="newpassword",
    )

    response = client.patch(
        f"/api/v1/users/{user_id}/reset-password",
        json=update_data.dict(),
        headers=logged_in_headers,
    )
    assert response.status_code == 200, response.json()
    # Now we need to test if the new password works
    login_data = {"username": active_user.username, "password": "newpassword"}
    response = client.post("/api/v1/login", data=login_data)
    assert response.status_code == 200


def test_patch_user_wrong_id(client, active_user, logged_in_headers):
    user_id = "wrong_id"
    update_data = UserUpdate(
        username="newname",
    )

    response = client.patch(f"/api/v1/users/{user_id}", json=update_data.dict(), headers=logged_in_headers)
    assert response.status_code == 422, response.json()
    json_response = response.json()
    detail = json_response["detail"]
    error = detail[0]
    assert error["loc"] == ["path", "user_id"]
    assert error["type"] == "uuid_parsing"


def test_delete_user(client, test_user, super_user_headers):
    user_id = test_user["id"]
    response = client.delete(f"/api/v1/users/{user_id}", headers=super_user_headers)
    assert response.status_code == 200
    assert response.json() == {"detail": "User deleted"}


def test_delete_user_wrong_id(client, test_user, super_user_headers):
    user_id = "wrong_id"
    response = client.delete(f"/api/v1/users/{user_id}", headers=super_user_headers)
    assert response.status_code == 422
    json_response = response.json()
    detail = json_response["detail"]
    error = detail[0]
    assert error["loc"] == ["path", "user_id"]
    assert error["type"] == "uuid_parsing"


def test_normal_user_cant_delete_user(client, test_user, logged_in_headers):
    user_id = test_user["id"]
    response = client.delete(f"/api/v1/users/{user_id}", headers=logged_in_headers)
    assert response.status_code == 400
    assert response.json() == {"detail": "The user doesn't have enough privileges"}
