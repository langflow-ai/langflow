from unittest.mock import AsyncMock, patch

import pytest
from langflow.services.auth.exceptions import InvalidTokenError
from langflow.services.database.models.user import User
from langflow.services.deps import get_auth_service, get_settings_service, session_scope
from lfx.services.settings.constants import DEFAULT_SUPERUSER, LEGACY_DEFAULT_SUPERUSER_PASSWORD
from sqlalchemy.exc import IntegrityError
from sqlmodel import select


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


async def test_login_rejects_legacy_default_superuser_password_when_auto_login_enabled(client):
    settings = get_settings_service()
    original_auto_login = settings.auth_settings.AUTO_LOGIN
    original_superuser = settings.auth_settings.SUPERUSER
    legacy_password = LEGACY_DEFAULT_SUPERUSER_PASSWORD.get_secret_value()
    settings.auth_settings.AUTO_LOGIN = True
    settings.auth_settings.SUPERUSER = DEFAULT_SUPERUSER

    async with session_scope() as session:
        stmt = select(User).where(User.username == DEFAULT_SUPERUSER)
        user = (await session.exec(stmt)).first()
        if user is None:
            user = User(
                username=DEFAULT_SUPERUSER,
                password=get_auth_service().get_password_hash(legacy_password),
                is_active=True,
                is_superuser=True,
            )
            session.add(user)
            await session.commit()
        else:
            user.password = get_auth_service().get_password_hash(legacy_password)
            user.is_active = True
            user.is_superuser = True
            await session.commit()

    try:
        response = await client.post(
            "api/v1/login",
            data={"username": DEFAULT_SUPERUSER, "password": legacy_password},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Incorrect username or password"
    finally:
        settings.auth_settings.AUTO_LOGIN = original_auto_login
        settings.auth_settings.SUPERUSER = original_superuser


async def test_session_endpoint_unauthenticated(client):
    """Test /session endpoint returns authenticated=False for unauthenticated requests."""
    response = await client.get("api/v1/session")
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is False
    assert data["user"] is None
    assert data["store_api_key"] is None


async def test_session_endpoint_invalid_token_returns_unauthenticated(client):
    """Test /session endpoint handles invalid tokens as unauthenticated sessions."""
    auth_service = AsyncMock()
    auth_service.get_current_user_from_access_token.side_effect = InvalidTokenError("Invalid token")

    with patch("langflow.api.v1.login.get_auth_service", return_value=auth_service):
        response = await client.get("api/v1/session", headers={"Authorization": "Bearer invalid-token"})

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
