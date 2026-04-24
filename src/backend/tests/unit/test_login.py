import pytest
from langflow.services.database.models.user import User
from langflow.services.deps import get_auth_service, session_scope
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def test_user():
    return User(
        username="testuser",
        password=get_auth_service().get_password_hash("testpassword"),  # Assuming password needs to be hashed
        is_active=True,
        is_superuser=False,
    )


async def test_login_successful(client, test_user):
    # Adding the test user to the database
    try:
        async with session_scope() as session:
            session.add(test_user)
            await session.commit()
    except IntegrityError:
        pass

    response = await client.post("api/v1/login", data={"username": "testuser", "password": "testpassword"})
    assert response.status_code == 200
    assert "access_token" in response.json()


async def test_login_unsuccessful_wrong_username(client):
    response = await client.post("api/v1/login", data={"username": "wrongusername", "password": "testpassword"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"


async def test_login_unsuccessful_wrong_password(client, test_user, async_session):
    # Adding the test user to the database
    async_session.add(test_user)
    await async_session.commit()

    response = await client.post("api/v1/login", data={"username": "testuser", "password": "wrongpassword"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"


async def test_session_endpoint_unauthenticated(client):
    """Test /session endpoint returns authenticated=False for unauthenticated requests."""
    response = await client.get("api/v1/session")
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is False
    assert data["user"] is None
    assert data["store_api_key"] is None


async def test_session_endpoint_authenticated(client, logged_in_headers):
    """Test /session endpoint returns user info for authenticated requests."""
    response = await client.get("api/v1/session", headers=logged_in_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is True
    assert data["user"] is not None
    assert data["user"]["username"] == "activeuser"
    assert data["user"]["is_active"] is True


async def test_session_endpoint_no_api_key_in_response(client, logged_in_headers):
    """Test /session endpoint does not return store_api_key in response body.

    This is a security check to ensure API keys are not exposed in HTTP response bodies,
    even to authenticated users. API keys should only be stored in httponly cookies.
    """
    response = await client.get("api/v1/session", headers=logged_in_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is True
    # Verify store_api_key field is None or not present in response
    assert data.get("store_api_key") is None
