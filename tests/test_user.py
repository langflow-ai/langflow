from datetime import datetime
from langflow.services.auth.utils import create_super_user, get_password_hash

from langflow.services.database.models.user.user import User
from langflow.services.utils import get_settings_manager
import pytest
from langflow.services.database.models.user import UserUpdate


@pytest.fixture
def super_user(client, session):
    settings_manager = get_settings_manager()
    auth_settings = settings_manager.auth_settings
    return create_super_user(
        db=session,
        username=auth_settings.FIRST_SUPERUSER,
        password=auth_settings.FIRST_SUPERUSER_PASSWORD,
    )


@pytest.fixture
def super_user_headers(client, super_user):
    settings_manager = get_settings_manager()
    auth_settings = settings_manager.auth_settings
    login_data = {
        "username": auth_settings.FIRST_SUPERUSER,
        "password": auth_settings.FIRST_SUPERUSER_PASSWORD,
    }
    response = client.post("/api/v1/login", data=login_data)
    assert response.status_code == 200
    tokens = response.json()
    a_token = tokens["access_token"]
    return {"Authorization": f"Bearer {a_token}"}


@pytest.fixture
def deactivated_user(session):
    user = User(
        username="deactivateduser",
        password=get_password_hash("testpassword"),
        is_active=False,
        is_superuser=False,
        last_login_at=datetime.now(),
    )
    session.add(user)
    session.commit()
    return user


def test_user_waiting_for_approval(client, session):
    # Create a user that is not active and has never logged in
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


def test_data_consistency_after_update(client, active_user, logged_in_headers):
    user_id = active_user.id
    update_data = UserUpdate(username="newname")

    response = client.patch(
        f"/api/v1/user/{user_id}", json=update_data.dict(), headers=logged_in_headers
    )
    assert response.status_code == 200

    # Fetch the updated user from the database
    response = client.get("/api/v1/user", headers=logged_in_headers)
    assert response.json()["username"] == "newname", response.json()


def test_data_consistency_after_delete(client, test_user, super_user_headers):
    user_id = test_user["id"]
    response = client.delete(f"/api/v1/user/{user_id}", headers=super_user_headers)
    assert response.status_code == 200

    # Attempt to fetch the deleted user from the database
    response = client.get("/api/v1/users", headers=super_user_headers)
    assert response.status_code == 200
    assert all(user["id"] != user_id for user in response.json()["users"])


def test_inactive_user(client, session):
    # Create a user that is not active and has a last_login_at value
    user = User(
        username="inactiveuser",
        password=get_password_hash("testpassword"),
        is_active=False,
        last_login_at="2023-01-01T00:00:00",  # Set to a valid datetime string
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

    response = client.patch(
        f"/api/v1/user/{user_id}", json=update_data.dict(), headers=logged_in_headers
    )
    assert response.status_code == 200, response.json()


def test_patch_user_wrong_id(client, active_user, logged_in_headers):
    user_id = "wrong_id"
    update_data = UserUpdate(
        username="newname",
    )

    response = client.patch(
        f"/api/v1/user/{user_id}", json=update_data.dict(), headers=logged_in_headers
    )
    assert response.status_code == 422, response.json()
    assert response.json() == {
        "detail": [
            {
                "loc": ["path", "user_id"],
                "msg": "value is not a valid uuid",
                "type": "type_error.uuid",
            }
        ]
    }


def test_delete_user(client, test_user, super_user_headers):
    user_id = test_user["id"]
    response = client.delete(f"/api/v1/user/{user_id}", headers=super_user_headers)
    assert response.status_code == 200
    assert response.json() == {"detail": "User deleted"}


def test_delete_user_wrong_id(client, test_user, super_user_headers):
    user_id = "wrong_id"
    response = client.delete(f"/api/v1/user/{user_id}", headers=super_user_headers)
    assert response.status_code == 422
    assert response.json() == {
        "detail": [
            {
                "loc": ["path", "user_id"],
                "msg": "value is not a valid uuid",
                "type": "type_error.uuid",
            }
        ]
    }


def test_normal_user_cant_delete_user(client, test_user, logged_in_headers):
    user_id = test_user["id"]
    response = client.delete(f"/api/v1/user/{user_id}", headers=logged_in_headers)
    assert response.status_code == 400
    assert response.json() == {"detail": "The user doesn't have enough privileges"}


# If you still want to test the superuser endpoint
def test_add_super_user_for_testing_purposes_delete_me_before_merge_into_dev(client):
    response = client.post("/api/v1/super_user")
    assert response.status_code == 200
    assert response.json()["username"] == "superuser"
