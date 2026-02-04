from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi import HTTPException, status
from langflow.services.auth.exceptions import (
    InactiveUserError,
    InvalidTokenError,
    TokenExpiredError,
)
from langflow.services.auth.service import AuthService
from langflow.services.database.models.user.model import User
from lfx.services.settings.auth import AuthSettings
from pydantic import SecretStr


@pytest.fixture
def auth_settings(tmp_path) -> AuthSettings:
    settings = AuthSettings(CONFIG_DIR=str(tmp_path))
    settings.SECRET_KEY = SecretStr("unit-test-secret")
    settings.AUTO_LOGIN = False
    settings.WEBHOOK_AUTH_ENABLE = False
    settings.ACCESS_TOKEN_EXPIRE_SECONDS = 60
    settings.REFRESH_TOKEN_EXPIRE_SECONDS = 120
    return settings


@pytest.fixture
def auth_service(auth_settings, tmp_path) -> AuthService:
    settings_service = SimpleNamespace(
        auth_settings=auth_settings,
        settings=SimpleNamespace(config_dir=str(tmp_path)),
    )
    return AuthService(settings_service)


def _dummy_user(user_id: UUID, *, active: bool = True) -> User:
    return User(
        id=user_id,
        username="tester",
        password="hashed",  # noqa: S106 - test fixture data  # pragma: allowlist secret
        is_active=active,
        is_superuser=False,
    )


@pytest.mark.anyio
async def test_get_current_user_from_access_token_returns_active_user(auth_service: AuthService):
    user_id = uuid4()
    db = AsyncMock()
    token = auth_service.create_token({"sub": str(user_id), "type": "access"}, timedelta(minutes=5))
    fake_user = _dummy_user(user_id)

    with patch("langflow.services.auth.service.get_user_by_id", new=AsyncMock(return_value=fake_user)) as mock_get_user:
        result = await auth_service.get_current_user_from_access_token(token, db)

    assert result is fake_user
    mock_get_user.assert_awaited_once_with(db, str(user_id))


@pytest.mark.anyio
async def test_get_current_user_from_access_token_rejects_expired(
    auth_service: AuthService,
    auth_settings: AuthSettings,
):
    expired = datetime.now(timezone.utc) - timedelta(minutes=1)
    token = jwt.encode(
        {"sub": str(uuid4()), "type": "access", "exp": int(expired.timestamp())},
        auth_settings.SECRET_KEY.get_secret_value(),
        algorithm=auth_settings.ALGORITHM,
    )

    with pytest.raises(TokenExpiredError):
        await auth_service.get_current_user_from_access_token(token, AsyncMock())


@pytest.mark.anyio
async def test_get_current_user_from_access_token_rejects_malformed_token(auth_service: AuthService):
    """CT-010: Malformed Bearer token must raise InvalidTokenError; jwt.decode rejects invalid tokens."""
    db = AsyncMock()
    malformed_tokens = [
        "invalid.token.here",  # invalid signature / not a valid JWT
        "not-a-jwt",  # not 3 segments, jwt.decode raises
    ]
    for token in malformed_tokens:
        with pytest.raises(InvalidTokenError):
            await auth_service.get_current_user_from_access_token(token, db)


@pytest.mark.anyio
async def test_get_current_user_from_access_token_requires_active_user(auth_service: AuthService):
    user_id = uuid4()
    db = AsyncMock()
    token = auth_service.create_token({"sub": str(user_id), "type": "access"}, timedelta(minutes=5))
    inactive_user = _dummy_user(user_id, active=False)

    with (
        patch("langflow.services.auth.service.get_user_by_id", new=AsyncMock(return_value=inactive_user)),
        pytest.raises(InactiveUserError),
    ):
        await auth_service.get_current_user_from_access_token(token, db)


@pytest.mark.anyio
async def test_create_refresh_token_requires_refresh_type(auth_service: AuthService):
    invalid_refresh = auth_service.create_token({"sub": str(uuid4()), "type": "access"}, timedelta(minutes=1))

    with pytest.raises(HTTPException) as exc:
        await auth_service.create_refresh_token(invalid_refresh, AsyncMock())

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_encrypt_and_decrypt_api_key_roundtrip(auth_service: AuthService):
    api_key = "super-secret-api-key"  # pragma: allowlist secret

    encrypted = auth_service.encrypt_api_key(api_key)
    assert encrypted != api_key

    decrypted = auth_service.decrypt_api_key(encrypted)
    assert decrypted == api_key


def test_password_helpers_roundtrip(auth_service: AuthService):
    password = "Str0ngP@ssword"  # noqa: S105  # pragma: allowlist secret

    hashed = auth_service.get_password_hash(password)
    assert hashed != password
    assert auth_service.verify_password(password, hashed)


# =============================================================================
# Token Creation Tests
# =============================================================================


def test_create_token_contains_expected_claims(auth_service: AuthService):
    """Test that created tokens contain the expected claims."""
    user_id = uuid4()
    token = auth_service.create_token(
        {"sub": str(user_id), "type": "access", "custom": "value"},
        timedelta(minutes=5),
    )

    # Decode without verification to check claims
    claims = jwt.decode(token, options={"verify_signature": False})
    assert claims["sub"] == str(user_id)
    assert claims["type"] == "access"
    assert claims["custom"] == "value"
    assert "exp" in claims


def test_get_user_id_from_token_valid(auth_service: AuthService):
    """Test extracting user ID from a valid token."""
    user_id = uuid4()
    token = auth_service.create_token({"sub": str(user_id), "type": "access"}, timedelta(minutes=5))

    result = auth_service.get_user_id_from_token(token)
    assert result == user_id


def test_get_user_id_from_token_invalid_returns_zero_uuid(auth_service: AuthService):
    """Test that invalid token returns zero UUID."""
    result = auth_service.get_user_id_from_token("invalid-token")
    assert result == UUID(int=0)


def test_create_user_api_key(auth_service: AuthService):
    """Test API key creation for a user."""
    user_id = uuid4()
    result = auth_service.create_user_api_key(user_id)

    assert "api_key" in result
    # Verify the token contains expected claims
    claims = jwt.decode(result["api_key"], options={"verify_signature": False})
    assert claims["sub"] == str(user_id)
    assert claims["type"] == "api_key"


@pytest.mark.anyio
async def test_create_user_tokens(auth_service: AuthService):
    """Test creating access and refresh tokens."""
    user_id = uuid4()
    db = AsyncMock()

    result = await auth_service.create_user_tokens(user_id, db, update_last_login=False)

    assert "access_token" in result
    assert "refresh_token" in result
    assert result["token_type"] == "bearer"  # noqa: S105 - not a password

    # Verify access token claims
    access_claims = jwt.decode(result["access_token"], options={"verify_signature": False})
    assert access_claims["sub"] == str(user_id)
    assert access_claims["type"] == "access"

    # Verify refresh token claims
    refresh_claims = jwt.decode(result["refresh_token"], options={"verify_signature": False})
    assert refresh_claims["sub"] == str(user_id)
    assert refresh_claims["type"] == "refresh"


@pytest.mark.anyio
async def test_create_user_tokens_updates_last_login(auth_service: AuthService):
    """Test that create_user_tokens updates last login when requested."""
    user_id = uuid4()
    db = AsyncMock()

    with patch("langflow.services.auth.service.update_user_last_login_at", new=AsyncMock()) as mock_update:
        await auth_service.create_user_tokens(user_id, db, update_last_login=True)
        mock_update.assert_awaited_once_with(user_id, db)


@pytest.mark.anyio
async def test_create_refresh_token_valid(auth_service: AuthService):
    """Test creating new tokens from a valid refresh token."""
    user_id = uuid4()
    db = AsyncMock()
    refresh_token = auth_service.create_token({"sub": str(user_id), "type": "refresh"}, timedelta(minutes=5))
    fake_user = _dummy_user(user_id)

    with patch("langflow.services.auth.service.get_user_by_id", new=AsyncMock(return_value=fake_user)):
        result = await auth_service.create_refresh_token(refresh_token, db)

    assert "access_token" in result
    assert "refresh_token" in result


@pytest.mark.anyio
async def test_create_refresh_token_user_not_found(auth_service: AuthService):
    """Test refresh token fails when user doesn't exist."""
    user_id = uuid4()
    db = AsyncMock()
    refresh_token = auth_service.create_token({"sub": str(user_id), "type": "refresh"}, timedelta(minutes=5))

    with (
        patch("langflow.services.auth.service.get_user_by_id", new=AsyncMock(return_value=None)),
        pytest.raises(HTTPException) as exc,
    ):
        await auth_service.create_refresh_token(refresh_token, db)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.anyio
async def test_create_refresh_token_inactive_user(auth_service: AuthService):
    """Test refresh token fails for inactive user."""
    user_id = uuid4()
    db = AsyncMock()
    refresh_token = auth_service.create_token({"sub": str(user_id), "type": "refresh"}, timedelta(minutes=5))
    inactive_user = _dummy_user(user_id, active=False)

    with (
        patch("langflow.services.auth.service.get_user_by_id", new=AsyncMock(return_value=inactive_user)),
        pytest.raises(HTTPException) as exc,
    ):
        await auth_service.create_refresh_token(refresh_token, db)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "inactive" in exc.value.detail.lower()


# =============================================================================
# User Validation Tests
# =============================================================================


@pytest.mark.anyio
async def test_get_current_active_user_active(auth_service: AuthService):
    """Test active user passes validation."""
    user = _dummy_user(uuid4(), active=True)
    result = await auth_service.get_current_active_user(user)
    assert result is user


@pytest.mark.anyio
async def test_get_current_active_user_inactive(auth_service: AuthService):
    """Test inactive user returns None."""
    user = _dummy_user(uuid4(), active=False)

    result = await auth_service.get_current_active_user(user)
    assert result is None


@pytest.mark.anyio
async def test_get_current_active_superuser_valid(auth_service: AuthService):
    """Test active superuser passes validation."""
    user = User(
        id=uuid4(),
        username="admin",
        password="hashed",  # noqa: S106 # pragma: allowlist secret
        is_active=True,
        is_superuser=True,
    )
    result = await auth_service.get_current_active_superuser(user)
    assert result is user


@pytest.mark.anyio
async def test_get_current_active_superuser_inactive(auth_service: AuthService):
    """Test inactive superuser returns None."""
    user = User(
        id=uuid4(),
        username="admin",
        password="hashed",  # noqa: S106 # pragma: allowlist secret
        is_active=False,
        is_superuser=True,
    )

    result = await auth_service.get_current_active_superuser(user)
    assert result is None


@pytest.mark.anyio
async def test_get_current_active_superuser_not_superuser(auth_service: AuthService):
    """Test non-superuser returns None."""
    user = _dummy_user(uuid4(), active=True)  # is_superuser=False by default

    result = await auth_service.get_current_active_superuser(user)
    assert result is None


# =============================================================================
# Authenticate User Tests
# =============================================================================


@pytest.mark.anyio
async def test_authenticate_user_success(auth_service: AuthService):
    """Test successful authentication."""
    user_id = uuid4()
    password = "correct_password"  # noqa: S105  # pragma: allowlist secret
    hashed = auth_service.get_password_hash(password)
    user = User(
        id=user_id,
        username="testuser",
        password=hashed,  # pragma: allowlist secret
        is_active=True,
        is_superuser=False,
    )
    db = AsyncMock()

    with patch("langflow.services.auth.service.get_user_by_username", new=AsyncMock(return_value=user)):
        result = await auth_service.authenticate_user("testuser", password, db)

    assert result is user


@pytest.mark.anyio
async def test_authenticate_user_wrong_password(auth_service: AuthService):
    """Test authentication fails with wrong password."""
    user_id = uuid4()
    hashed = auth_service.get_password_hash("correct_password")
    user = User(
        id=user_id,
        username="testuser",
        password=hashed,  # pragma: allowlist secret
        is_active=True,
        is_superuser=False,
    )
    db = AsyncMock()

    with patch("langflow.services.auth.service.get_user_by_username", new=AsyncMock(return_value=user)):
        result = await auth_service.authenticate_user("testuser", "wrong_password", db)

    assert result is None


@pytest.mark.anyio
async def test_authenticate_user_not_found(auth_service: AuthService):
    """Test authentication returns None for non-existent user."""
    db = AsyncMock()

    with patch("langflow.services.auth.service.get_user_by_username", new=AsyncMock(return_value=None)):
        result = await auth_service.authenticate_user("nonexistent", "password", db)

    assert result is None


@pytest.mark.anyio
async def test_authenticate_user_inactive_never_logged_in(auth_service: AuthService):
    """Test inactive user who never logged in gets 'waiting for approval'."""
    user = User(
        id=uuid4(),
        username="testuser",
        password=auth_service.get_password_hash("password"),  # pragma: allowlist secret
        is_active=False,
        is_superuser=False,
        last_login_at=None,
    )
    db = AsyncMock()

    with (
        patch("langflow.services.auth.service.get_user_by_username", new=AsyncMock(return_value=user)),
        pytest.raises(HTTPException) as exc,
    ):
        await auth_service.authenticate_user("testuser", "password", db)

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "approval" in exc.value.detail.lower()


@pytest.mark.anyio
async def test_authenticate_user_inactive_previously_logged_in(auth_service: AuthService):
    """Test inactive user who previously logged in gets 'inactive user'."""
    user = User(
        id=uuid4(),
        username="testuser",
        password=auth_service.get_password_hash("password"),  # pragma: allowlist secret
        is_active=False,
        is_superuser=False,
        last_login_at=datetime.now(timezone.utc),
    )
    db = AsyncMock()

    with (
        patch("langflow.services.auth.service.get_user_by_username", new=AsyncMock(return_value=user)),
        pytest.raises(HTTPException) as exc,
    ):
        await auth_service.authenticate_user("testuser", "password", db)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "inactive" in exc.value.detail.lower()


# =============================================================================
# MCP Authentication Tests
# =============================================================================


@pytest.mark.anyio
async def test_get_current_active_user_mcp_active(auth_service: AuthService):
    """Test MCP active user validation passes."""
    user = _dummy_user(uuid4(), active=True)
    result = await auth_service.get_current_active_user_mcp(user)
    assert result is user


@pytest.mark.anyio
async def test_get_current_active_user_mcp_inactive(auth_service: AuthService):
    """Test MCP inactive user validation fails."""
    user = _dummy_user(uuid4(), active=False)

    with pytest.raises(HTTPException) as exc:
        await auth_service.get_current_active_user_mcp(user)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
