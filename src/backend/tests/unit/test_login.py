from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from langflow.services.auth.exceptions import InvalidTokenError
from langflow.services.database.models.auth import SSOUserProfile
from langflow.services.database.models.user import User
from langflow.services.deps import get_auth_service, get_settings_service, session_scope
from lfx.services.settings.constants import DEFAULT_SUPERUSER, LEGACY_DEFAULT_SUPERUSER_PASSWORD
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

_EXTERNAL_TEST_SECRET = "external-test-secret-with-enough-length"  # noqa: S105 # pragma: allowlist secret
_EXTERNAL_AUTH_HEADER = "X-Langflow-External-Auth"
_EXTERNAL_AUTH_COOKIE = "external-session"


def _external_token(**claims) -> str:
    payload = {
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        **claims,
    }
    return jwt.encode(payload, _EXTERNAL_TEST_SECRET, algorithm="HS256")


_EXTERNAL_FIELDS = (
    "EXTERNAL_AUTH_ENABLED",
    "EXTERNAL_AUTH_PROVIDER",
    "EXTERNAL_AUTH_TOKEN_HEADER",
    "EXTERNAL_AUTH_TOKEN_COOKIE",
    "EXTERNAL_AUTH_IDENTITY_RESOLVER",
    "EXTERNAL_AUTH_TRUSTED_JWT_DECODE",
    "EXTERNAL_AUTH_JWKS_URL",
    "EXTERNAL_AUTH_ISSUER",
    "EXTERNAL_AUTH_AUDIENCE",
    "EXTERNAL_AUTH_ALGORITHMS",
    "EXTERNAL_AUTH_SUBJECT_CLAIM",
    "EXTERNAL_AUTH_USERNAME_CLAIM",
    "EXTERNAL_AUTH_EMAIL_CLAIM",
    "EXTERNAL_AUTH_NAME_CLAIM",
    "EXTERNAL_AUTH_ACCESS_CEILING_ENABLED",
    "EXTERNAL_AUTH_ACCESS_CLAIM",
    "EXTERNAL_AUTH_ACCESS_CLAIM_MAPPING",
    "EXTERNAL_AUTH_DEFAULT_ACCESS_LEVEL",
    "EXTERNAL_AUTH_DISABLE_API_KEYS_FOR_EXTERNAL_USERS",
)


@pytest.fixture
async def external_auth_settings(client):  # noqa: ARG001
    auth_settings = get_settings_service().auth_settings
    original = {field: getattr(auth_settings, field) for field in _EXTERNAL_FIELDS}

    auth_settings.EXTERNAL_AUTH_ENABLED = True
    auth_settings.EXTERNAL_AUTH_PROVIDER = "test-provider"
    auth_settings.EXTERNAL_AUTH_TOKEN_HEADER = _EXTERNAL_AUTH_HEADER
    auth_settings.EXTERNAL_AUTH_TOKEN_COOKIE = None
    auth_settings.EXTERNAL_AUTH_IDENTITY_RESOLVER = None
    auth_settings.EXTERNAL_AUTH_TRUSTED_JWT_DECODE = True
    auth_settings.EXTERNAL_AUTH_JWKS_URL = None
    auth_settings.EXTERNAL_AUTH_ISSUER = None
    auth_settings.EXTERNAL_AUTH_AUDIENCE = None
    auth_settings.EXTERNAL_AUTH_ALGORITHMS = "RS256"
    auth_settings.EXTERNAL_AUTH_SUBJECT_CLAIM = "sub"
    auth_settings.EXTERNAL_AUTH_USERNAME_CLAIM = "preferred_username"
    auth_settings.EXTERNAL_AUTH_EMAIL_CLAIM = "email"
    auth_settings.EXTERNAL_AUTH_NAME_CLAIM = "name"
    auth_settings.EXTERNAL_AUTH_ACCESS_CEILING_ENABLED = False
    auth_settings.EXTERNAL_AUTH_ACCESS_CLAIM = None
    auth_settings.EXTERNAL_AUTH_ACCESS_CLAIM_MAPPING = None
    auth_settings.EXTERNAL_AUTH_DEFAULT_ACCESS_LEVEL = "viewer"
    auth_settings.EXTERNAL_AUTH_DISABLE_API_KEYS_FOR_EXTERNAL_USERS = True

    yield auth_settings

    for field, value in original.items():
        setattr(auth_settings, field, value)


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


# ---------------------------------------------------------------------------
# External trusted auth + JIT provisioning
# ---------------------------------------------------------------------------


async def test_session_endpoint_jit_creates_user_for_external_header(client, external_auth_settings):  # noqa: ARG001
    token = _external_token(
        sub="subject-1",
        preferred_username="external-user",
        email="external@example.com",
        name="External User",
    )

    response = await client.get("api/v1/session", headers={_EXTERNAL_AUTH_HEADER: f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is True
    assert data["user"]["username"] == "external-user"
    assert data["user"]["is_active"] is True

    async with session_scope() as session:
        statement = select(SSOUserProfile).where(
            SSOUserProfile.sso_provider == "test-provider",
            SSOUserProfile.sso_user_id == "subject-1",
        )
        profiles = (await session.exec(statement)).all()
        assert len(profiles) == 1
        assert str(profiles[0].user_id) == data["user"]["id"]
        assert profiles[0].email == "external@example.com"

    # Second request reuses the same user.
    second_response = await client.get("api/v1/session", headers={_EXTERNAL_AUTH_HEADER: f"Bearer {token}"})
    assert second_response.status_code == 200
    assert second_response.json()["user"]["id"] == data["user"]["id"]


async def test_session_endpoint_accepts_external_cookie_with_custom_claim_mapping(client, external_auth_settings):
    external_auth_settings.EXTERNAL_AUTH_TOKEN_HEADER = "X-Unused-External-Auth"  # noqa: S105
    external_auth_settings.EXTERNAL_AUTH_TOKEN_COOKIE = _EXTERNAL_AUTH_COOKIE
    external_auth_settings.EXTERNAL_AUTH_USERNAME_CLAIM = "username"
    external_auth_settings.EXTERNAL_AUTH_EMAIL_CLAIM = "username"
    external_auth_settings.EXTERNAL_AUTH_NAME_CLAIM = "display_name"

    token = _external_token(sub="cookie-subject", username="person@example.com", display_name="Person Name")

    response = await client.get("api/v1/session", headers={"Cookie": f"{_EXTERNAL_AUTH_COOKIE}={token}"})

    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is True
    assert data["user"]["username"] == "person@example.com"

    async with session_scope() as session:
        statement = select(SSOUserProfile).where(
            SSOUserProfile.sso_provider == "test-provider",
            SSOUserProfile.sso_user_id == "cookie-subject",
        )
        profile = (await session.exec(statement)).first()
        assert profile is not None
        assert profile.email == "person@example.com"


async def test_session_endpoint_rejects_expired_external_token(client, external_auth_settings):  # noqa: ARG001
    token = jwt.encode(
        {
            "sub": "expired-subject",
            "preferred_username": "expired-user",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        _EXTERNAL_TEST_SECRET,
        algorithm="HS256",
    )

    response = await client.get("api/v1/session", headers={_EXTERNAL_AUTH_HEADER: f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["authenticated"] is False


async def test_external_access_ceiling_filters_effective_permissions(client, external_auth_settings):
    external_auth_settings.EXTERNAL_AUTH_ACCESS_CEILING_ENABLED = True
    external_auth_settings.EXTERNAL_AUTH_ACCESS_CLAIM = "openrag_mode"
    external_auth_settings.EXTERNAL_AUTH_ACCESS_CLAIM_MAPPING = '{"view":"viewer","edit":"editor"}'
    token = _external_token(
        sub="viewer-subject",
        preferred_username="viewer-user",
        openrag_mode="view",
    )

    response = await client.post(
        "api/v1/authz/me/permissions",
        headers={_EXTERNAL_AUTH_HEADER: f"Bearer {token}"},
        json={
            "resource_type": "flow",
            "resource_ids": ["00000000-0000-0000-0000-000000000001"],
            "actions": ["read", "write", "delete"],
        },
    )

    assert response.status_code == 200
    permissions = response.json()["permissions"]
    assert permissions["00000000-0000-0000-0000-000000000001"] == ["read"]


async def test_session_external_recovers_despite_stale_native_cookie(client, external_auth_settings):  # noqa: ARG001
    """A stale/invalid native cookie must not shadow a valid external credential on /session (P1)."""
    token = _external_token(
        sub="recover-subject",
        preferred_username="recover-user",
        email="recover@example.com",
    )

    response = await client.get(
        "api/v1/session",
        headers={
            # A stale/invalid native cookie is present alongside the valid external header.
            "Cookie": "access_token_lf=stale-invalid-native-token",
            _EXTERNAL_AUTH_HEADER: f"Bearer {token}",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is True
    assert data["user"]["username"] == "recover-user"


async def test_get_current_user_external_recovers_despite_stale_native_cookie(client, external_auth_settings):  # noqa: ARG001
    """A get_current_user-protected endpoint accepts a valid external credential despite a stale cookie (P1)."""
    token = _external_token(
        sub="recover-subject-2",
        preferred_username="recover-user-2",
        email="recover2@example.com",
    )

    # /api/v1/users/whoami is guarded by CurrentActiveUser -> get_current_user.
    response = await client.get(
        "api/v1/users/whoami",
        headers={
            "Cookie": "access_token_lf=stale-invalid-native-token",
            _EXTERNAL_AUTH_HEADER: f"Bearer {token}",
        },
    )

    assert response.status_code == 200
    assert response.json()["username"] == "recover-user-2"


async def test_external_access_ceiling_blocks_api_key_creation(client, external_auth_settings):
    external_auth_settings.EXTERNAL_AUTH_ACCESS_CEILING_ENABLED = True
    external_auth_settings.EXTERNAL_AUTH_ACCESS_CLAIM = "openrag_mode"
    token = _external_token(
        sub="viewer-api-key-subject",
        preferred_username="viewer-api-key-user",
        openrag_mode="viewer",
    )

    response = await client.post(
        "api/v1/api_key/",
        headers={_EXTERNAL_AUTH_HEADER: f"Bearer {token}"},
        json={"name": "should-not-work"},
    )

    assert response.status_code == 403
    assert "API key creation is disabled" in response.json()["detail"]
