from langflow.services.database.utils import session_getter
from langflow.services.getters import get_db_service
import pytest
from langflow.services.database.models.user import User
from langflow.services.auth.utils import get_password_hash


@pytest.fixture
def test_user():
    return User(
        username="testuser",
        password=get_password_hash(
            "testpassword"
        ),  # Assuming password needs to be hashed
        is_active=True,
        is_superuser=False,
    )


def test_login_successful(client, test_user):
    # Adding the test user to the database
    with session_getter(get_db_service()) as session:
        session.add(test_user)
        session.commit()

    response = client.post(
        "api/v1/login", data={"username": "testuser", "password": "testpassword"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_unsuccessful_wrong_username(client):
    response = client.post(
        "api/v1/login", data={"username": "wrongusername", "password": "testpassword"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"


def test_login_unsuccessful_wrong_password(client, test_user, session):
    # Adding the test user to the database
    session.add(test_user)
    session.commit()

    response = client.post(
        "api/v1/login", data={"username": "testuser", "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"
