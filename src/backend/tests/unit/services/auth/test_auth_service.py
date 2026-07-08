from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi import HTTPException, WebSocketException, status
from langflow.services.auth.constants import AUTO_LOGIN_WARNING
from langflow.services.auth.context import (
    AUTH_METHOD_API_KEY,
    clear_current_auth_context,
    get_current_auth_context,
)
from langflow.services.auth.exceptions import (
    InactiveUserError,
    InvalidTokenError,
    MissingCredentialsError,
    TokenExpiredError,
)
from langflow.services.auth.service import AuthService
from langflow.services.database.models.api_key.crud import ApiKeyAuthResult
from langflow.services.database.models.user.model import User
from lfx.services.settings.auth import AuthSettings
from lfx.services.settings.constants import DEFAULT_SUPERUSER, LEGACY_DEFAULT_SUPERUSER_PASSWORD
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
async def test_authenticate_with_credentials_missing_creds_raises(
    auth_service: AuthService,
):
    """Default config (AUTO_LOGIN off, skip_auth_auto_login off) rejects callers with no creds."""
    with pytest.raises(MissingCredentialsError):
        await auth_service.authenticate_with_credentials(token=None, api_key=None, db=AsyncMock())


@pytest.mark.anyio
async def test_authenticate_with_api_key_sets_auth_context(auth_service: AuthService):
    user = _dummy_user(uuid4())
    api_key_id = uuid4()

    with patch(
        "langflow.services.auth.service.authenticate_api_key",
        new=AsyncMock(
            return_value=ApiKeyAuthResult(
                user=user,
                api_key_source="db",  # pragma: allowlist secret
                api_key_id=api_key_id,
            )
        ),
    ):
        try:
            result = await auth_service.authenticate_with_credentials(
                token=None,
                api_key="sk-test-key",  # pragma: allowlist secret
                db=AsyncMock(),
            )
            context = get_current_auth_context()
        finally:
            clear_current_auth_context()

    assert result.id == user.id
    assert context is not None
    assert context.method == AUTH_METHOD_API_KEY
    assert context.api_key_id == api_key_id
    assert context.api_key_source == "db"  # pragma: allowlist secret


@pytest.mark.anyio
async def test_authenticate_with_credentials_auto_login_alone_still_rejects(
    auth_service: AuthService,
    auth_settings: AuthSettings,
):
    """AUTO_LOGIN without skip_auth_auto_login must still require credentials.

    Without this guard the AUTO_LOGIN security-tightening from #8513 would
    silently regress for every ``get_current_user``-protected endpoint.
    """
    auth_settings.AUTO_LOGIN = True
    auth_settings.skip_auth_auto_login = False
    auth_settings.SUPERUSER = "admin"

    with pytest.raises(MissingCredentialsError):
        await auth_service.authenticate_with_credentials(token=None, api_key=None, db=AsyncMock())


@pytest.mark.anyio
async def test_authenticate_with_credentials_auto_login_skip_returns_superuser(
    auth_service: AuthService,
    auth_settings: AuthSettings,
):
    """With AUTO_LOGIN + skip_auth_auto_login, missing creds fall back to the superuser.

    Restores parity with ``api_key_security`` so ``CurrentActiveUser``-protected
    endpoints (e.g. ``GET /api/v1/flows/``) work for ADK/dev environments that
    relied on the v1.7.1 behavior.
    """
    auth_settings.AUTO_LOGIN = True
    auth_settings.skip_auth_auto_login = True
    auth_settings.SUPERUSER = "admin"
    superuser = _dummy_user(uuid4())

    with (
        patch(
            "langflow.services.auth.service.get_user_by_username",
            new=AsyncMock(return_value=superuser),
        ) as mock_lookup,
        patch("langflow.services.auth.service.logger") as mock_logger,
    ):
        result = await auth_service.authenticate_with_credentials(token=None, api_key=None, db=AsyncMock())

    assert result is superuser
    mock_lookup.assert_awaited_once()
    mock_logger.warning.assert_called_once_with(AUTO_LOGIN_WARNING)


@pytest.mark.anyio
async def test_authenticate_with_credentials_auto_login_skip_missing_superuser_raises(
    auth_service: AuthService,
    auth_settings: AuthSettings,
):
    """AUTO_LOGIN + skip_auth_auto_login with no superuser row in the DB rejects.

    Mirrors the safety check inside ``_api_key_security_impl`` when the
    configured superuser is absent from the database.
    """
    auth_settings.AUTO_LOGIN = True
    auth_settings.skip_auth_auto_login = True
    auth_settings.SUPERUSER = "admin"

    from langflow.services.auth.exceptions import InvalidCredentialsError

    with (
        patch(
            "langflow.services.auth.service.get_user_by_username",
            new=AsyncMock(return_value=None),
        ),
        pytest.raises(InvalidCredentialsError),
    ):
        await auth_service.authenticate_with_credentials(token=None, api_key=None, db=AsyncMock())


@pytest.mark.anyio
async def test_auto_login_longterm_token_is_short_lived_with_refresh(
    auth_service: AuthService,
    auth_settings: AuthSettings,
):
    """auto_login must not mint a 365-day superuser token.

    Regression for GHSA-fjgc-vj2f-77hm: create_user_longterm_token
    previously issued a 365-day access token with no refresh token. It must now
    issue a normally-scoped access token (ACCESS_TOKEN_EXPIRE_SECONDS) plus a
    refresh token.
    """
    auth_settings.AUTO_LOGIN = True
    auth_settings.SUPERUSER = "admin"
    superuser = _dummy_user(uuid4())

    with (
        patch("langflow.services.auth.service.get_user_by_username", new=AsyncMock(return_value=superuser)),
        patch("langflow.services.auth.service.update_user_last_login_at", new=AsyncMock()),
    ):
        user_id, tokens = await auth_service.create_user_longterm_token(AsyncMock())

    assert user_id == superuser.id
    # A refresh token is now issued (previously None).
    assert tokens["refresh_token"]

    # The access token lifetime is bounded by ACCESS_TOKEN_EXPIRE_SECONDS (60 in
    # the fixture), nowhere near a year.
    claims = jwt.decode(tokens["access_token"], options={"verify_signature": False})
    lifetime = claims["exp"] - int(datetime.now(timezone.utc).timestamp())
    assert lifetime > 0
    assert lifetime <= auth_settings.ACCESS_TOKEN_EXPIRE_SECONDS + 5
    assert lifetime < 60 * 60 * 24  # far below a day, definitely not 365 days


@pytest.mark.anyio
async def test_authenticate_with_credentials_auto_login_skip_empty_superuser_config_raises():
    """AUTO_LOGIN + skip_auth_auto_login with an empty SUPERUSER config rejects without a DB lookup.

    The ``if not auth_settings.SUPERUSER:`` guard at the top of the bypass branch
    must fire before ``get_user_by_username`` is called. Uses SimpleNamespace to
    bypass Pydantic model validation so SUPERUSER can be set to an empty string.
    """
    from langflow.services.auth.exceptions import InvalidCredentialsError

    settings_service = SimpleNamespace(
        auth_settings=SimpleNamespace(
            AUTO_LOGIN=True,
            skip_auth_auto_login=True,
            SUPERUSER="",
        )
    )
    service = AuthService(settings_service)

    with pytest.raises(InvalidCredentialsError):
        await service.authenticate_with_credentials(token=None, api_key=None, db=AsyncMock())


@pytest.mark.anyio
async def test_authenticate_with_credentials_auto_login_skip_rejects_inactive_superuser(
    auth_service: AuthService,
    auth_settings: AuthSettings,
):
    """AUTO_LOGIN fallback must enforce ``is_active`` like token/API-key paths.

    ``CurrentActiveUser`` re-checks this for HTTP routes, but SSE/websocket
    dependencies delegate directly to ``authenticate_with_credentials``, so
    the active-user guard must live in this method.
    """
    auth_settings.AUTO_LOGIN = True
    auth_settings.skip_auth_auto_login = True
    inactive_superuser = _dummy_user(uuid4(), active=False)

    with (
        patch(
            "langflow.services.auth.service.get_user_by_username",
            new=AsyncMock(return_value=inactive_superuser),
        ),
        pytest.raises(InactiveUserError),
    ):
        await auth_service.authenticate_with_credentials(token=None, api_key=None, db=AsyncMock())


@pytest.mark.anyio
async def test_authenticate_user_rejects_legacy_default_password_in_auto_login(
    auth_service: AuthService,
    auth_settings: AuthSettings,
):
    auth_settings.AUTO_LOGIN = True
    auth_settings.SUPERUSER = DEFAULT_SUPERUSER
    legacy_password = LEGACY_DEFAULT_SUPERUSER_PASSWORD.get_secret_value()
    default_superuser = User(
        id=uuid4(),
        username=DEFAULT_SUPERUSER,
        password=auth_service.get_password_hash(legacy_password),
        is_active=True,
        is_superuser=True,
    )

    with patch("langflow.services.auth.service.get_user_by_username", new=AsyncMock(return_value=default_superuser)):
        result = await auth_service.authenticate_user(DEFAULT_SUPERUSER, legacy_password, AsyncMock())

    assert result is None


@pytest.mark.anyio
async def test_authenticate_user_rejects_legacy_default_password_when_auto_login_false(
    auth_service: AuthService,
    auth_settings: AuthSettings,
):
    auth_settings.AUTO_LOGIN = False
    auth_settings.SUPERUSER = DEFAULT_SUPERUSER
    legacy_password = LEGACY_DEFAULT_SUPERUSER_PASSWORD.get_secret_value()
    default_superuser = User(
        id=uuid4(),
        username=DEFAULT_SUPERUSER,
        password=auth_service.get_password_hash(legacy_password),
        is_active=True,
        is_superuser=True,
    )

    with patch("langflow.services.auth.service.get_user_by_username", new=AsyncMock(return_value=default_superuser)):
        result = await auth_service.authenticate_user(DEFAULT_SUPERUSER, legacy_password, AsyncMock())

    assert result is None


@pytest.mark.anyio
async def test_authenticate_user_rejects_legacy_default_username_after_superuser_override(
    auth_service: AuthService,
    auth_settings: AuthSettings,
):
    auth_settings.AUTO_LOGIN = True
    auth_settings.SUPERUSER = "custom_admin"
    legacy_password = LEGACY_DEFAULT_SUPERUSER_PASSWORD.get_secret_value()
    default_superuser = User(
        id=uuid4(),
        username=DEFAULT_SUPERUSER,
        password=auth_service.get_password_hash(legacy_password),
        is_active=True,
        is_superuser=True,
    )

    with patch("langflow.services.auth.service.get_user_by_username", new=AsyncMock(return_value=default_superuser)):
        result = await auth_service.authenticate_user(DEFAULT_SUPERUSER, legacy_password, AsyncMock())

    assert result is None


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


def test_add_padding_no_extra_chars_when_divisible_by_4():
    """add_base64_padding must not add characters when length is already a multiple of 4."""
    from langflow.services.auth.utils import add_base64_padding

    assert add_base64_padding("ABCD") == "ABCD"
    assert add_base64_padding("ABCDEFGH") == "ABCDEFGH"
    assert add_base64_padding("A" * 44) == "A" * 44


def test_add_padding_pads_correctly():
    """add_base64_padding must add the right number of = characters."""
    from langflow.services.auth.utils import add_base64_padding

    assert add_base64_padding("ABC") == "ABC="
    assert add_base64_padding("AB") == "AB=="
    assert add_base64_padding("A") == "A==="


def test_encrypt_decrypt_roundtrip_with_standard_key(tmp_path):
    """secrets.token_urlsafe(32) produces a 43-char key that must always work."""
    import secrets

    raw_key = secrets.token_urlsafe(32)  # always 43 chars
    assert len(raw_key) == 43

    settings = AuthSettings(CONFIG_DIR=str(tmp_path))
    settings.SECRET_KEY = SecretStr(raw_key)
    settings_service = SimpleNamespace(
        auth_settings=settings,
        settings=SimpleNamespace(config_dir=str(tmp_path)),
    )
    svc = AuthService(settings_service)

    encrypted = svc.encrypt_api_key("sk-test-key-12345")  # pragma: allowlist secret
    assert svc.decrypt_api_key(encrypted) == "sk-test-key-12345"  # pragma: allowlist secret


def test_encrypt_decrypt_roundtrip_with_base64_encoded_32_byte_key(tmp_path):
    """A base64url-encoded 32-byte key (44 chars) must work after padding fix."""
    import base64
    import os

    raw_key = base64.urlsafe_b64encode(os.urandom(32)).decode()  # 44 chars with padding
    assert len(raw_key) == 44

    settings = AuthSettings(CONFIG_DIR=str(tmp_path))
    settings.SECRET_KEY = SecretStr(raw_key)
    settings_service = SimpleNamespace(
        auth_settings=settings,
        settings=SimpleNamespace(config_dir=str(tmp_path)),
    )
    svc = AuthService(settings_service)

    encrypted = svc.encrypt_api_key("sk-test-key-12345")  # pragma: allowlist secret
    assert svc.decrypt_api_key(encrypted) == "sk-test-key-12345"  # pragma: allowlist secret


def test_encrypt_decrypt_roundtrip_with_short_key(tmp_path):
    """Keys shorter than 32 chars use the SHA-256 derivation and must work."""
    raw_key = "short-key"

    settings = AuthSettings(CONFIG_DIR=str(tmp_path))
    settings.SECRET_KEY = SecretStr(raw_key)
    settings_service = SimpleNamespace(
        auth_settings=settings,
        settings=SimpleNamespace(config_dir=str(tmp_path)),
    )
    svc = AuthService(settings_service)

    encrypted = svc.encrypt_api_key("sk-test-key-12345")  # pragma: allowlist secret
    assert svc.decrypt_api_key(encrypted) == "sk-test-key-12345"  # pragma: allowlist secret


def test_decrypt_api_key_returns_empty_on_undecryptable_token(auth_service: AuthService):
    """Decryption of an invalid Fernet token must return empty string, not raise."""
    bad_token = "gAAAAABinvalidtokendata"  # noqa: S105  # pragma: allowlist secret
    result = auth_service.decrypt_api_key(bad_token)
    assert result == ""


def test_decrypt_api_key_returns_plaintext_as_is(auth_service: AuthService):
    """Plaintext keys (not starting with gAAAAA) must be returned as-is."""
    plaintext = "sk-some-plaintext-key"  # pragma: allowlist secret
    assert auth_service.decrypt_api_key(plaintext) == plaintext


def test_decrypt_api_key_returns_empty_for_invalid_input(auth_service: AuthService):
    """Empty or non-string input must return empty string."""
    assert auth_service.decrypt_api_key("") == ""


def test_ensure_fernet_key_with_44_char_key():
    """ensure_fernet_key must handle 44-char keys (len % 4 == 0) correctly."""
    import base64
    import os

    from cryptography.fernet import Fernet
    from langflow.services.auth.utils import ensure_fernet_key

    raw_key = base64.urlsafe_b64encode(os.urandom(32)).decode()  # 44 chars, len % 4 == 0
    assert len(raw_key) == 44

    fernet = Fernet(ensure_fernet_key(raw_key))
    encrypted = fernet.encrypt(b"test-value")
    assert fernet.decrypt(encrypted) == b"test-value"


def test_ensure_fernet_key_short_key_uses_sha256_derivation():
    """Short-key derivation must be the SHA-256 hash, not the old PRNG output.

    Regression for GHSA-jxw3-mjmx-3pqm: the key was previously derived with
    ``random.seed(secret_key)`` + ``random.getrandbits`` — a predictable,
    non-cryptographic PRNG. The guard that catches that regression is the
    SHA-256 equality below: the derived key must equal
    ``base64.urlsafe_b64encode(sha256(secret))``, which the old PRNG path could
    never produce.

    The random-state perturbation between the two calls is only a determinism
    sanity check. On its own it would *not* catch the old bug — the vulnerable
    code re-seeded with the secret on every call, so it was deterministic per
    secret too; the SHA-256 assertion is what proves the path actually changed.
    """
    import base64
    import hashlib
    import random

    from langflow.services.auth.utils import ensure_fernet_key

    raw_key = "short-key"  # < 32 chars -> derivation branch

    random.seed(0)
    key_a = ensure_fernet_key(raw_key)
    random.seed(123456789)
    _ = [random.random() for _ in range(100)]  # noqa: S311  # perturb global PRNG state
    key_b = ensure_fernet_key(raw_key)

    # Determinism sanity check (held under the old impl too — not the regression guard).
    assert key_a == key_b
    # Regression guard: the key must be the SHA-256 derivation, not random.getrandbits output.
    expected = base64.urlsafe_b64encode(hashlib.sha256(raw_key.encode()).digest())
    assert key_a == expected


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


# =============================================================================
# ws_api_key_security Tests
# =============================================================================


@asynccontextmanager
async def _mock_session_scope():
    yield AsyncMock()


@pytest.mark.anyio
async def test_ws_api_key_security_auto_login_skip_rejects_missing_superuser(
    auth_service: AuthService,
    auth_settings: AuthSettings,
):
    """ws_api_key_security must reject with WS_1011 when the superuser row is absent from DB."""
    auth_settings.AUTO_LOGIN = True
    auth_settings.skip_auth_auto_login = True
    auth_settings.SUPERUSER = "admin"

    with (
        patch("langflow.services.auth.service.session_scope", _mock_session_scope),
        patch(
            "langflow.services.auth.service.get_user_by_username",
            new=AsyncMock(return_value=None),
        ),
        pytest.raises(WebSocketException) as exc,
    ):
        await auth_service.ws_api_key_security(api_key=None)

    assert exc.value.code == status.WS_1011_INTERNAL_ERROR


@pytest.mark.anyio
async def test_ws_api_key_security_auto_login_skip_rejects_inactive_superuser(
    auth_service: AuthService,
    auth_settings: AuthSettings,
):
    """ws_api_key_security must enforce is_active in the AUTO_LOGIN + skip_auth bypass path."""
    auth_settings.AUTO_LOGIN = True
    auth_settings.skip_auth_auto_login = True
    auth_settings.SUPERUSER = "admin"
    inactive_superuser = _dummy_user(uuid4(), active=False)

    with (
        patch("langflow.services.auth.service.session_scope", _mock_session_scope),
        patch(
            "langflow.services.auth.service.get_user_by_username",
            new=AsyncMock(return_value=inactive_superuser),
        ),
        pytest.raises(WebSocketException) as exc,
    ):
        await auth_service.ws_api_key_security(api_key=None)

    assert exc.value.code == status.WS_1008_POLICY_VIOLATION


# =============================================================================
# _api_key_security_impl Tests
# =============================================================================


@pytest.mark.anyio
async def test_api_key_security_impl_auto_login_skip_rejects_inactive_superuser(
    auth_service: AuthService,
    auth_settings: AuthSettings,
):
    """_api_key_security_impl must enforce is_active in the AUTO_LOGIN + skip_auth bypass path."""
    auth_settings.AUTO_LOGIN = True
    auth_settings.skip_auth_auto_login = True
    auth_settings.SUPERUSER = "admin"
    inactive_superuser = _dummy_user(uuid4(), active=False)

    with (
        patch(
            "langflow.services.auth.service.get_user_by_username",
            new=AsyncMock(return_value=inactive_superuser),
        ),
        pytest.raises(HTTPException) as exc,
    ):
        await auth_service._api_key_security_impl(
            query_param=None,
            header_param=None,
            db=AsyncMock(),
            settings_service=auth_service.settings,
        )

    assert exc.value.status_code == status.HTTP_403_FORBIDDEN


# =============================================================================
# External-user materialization (F1): email is never erased by an email-less token
# =============================================================================


def _external_jwt(auth_service: AuthService, claims: dict) -> str:
    """Encode a trusted external JWT signed with the service secret.

    A future ``exp`` is always supplied because the trusted-decode path requires
    it (see external._validate_trusted_time_claims).
    """
    secret = auth_service.settings.auth_settings.SECRET_KEY.get_secret_value()
    payload = {"exp": datetime.now(timezone.utc) + timedelta(minutes=5), **claims}
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.mark.anyio
async def test_materialize_external_user_preserves_email_when_token_omits_it(
    auth_service: AuthService,
    auth_settings: AuthSettings,
    async_session,
):
    """A later token without an email claim must not erase the stored email (F1)."""
    from langflow.services.auth.external import identity_from_claims
    from langflow.services.database.models.auth import SSOUserProfile
    from sqlmodel import select

    auth_settings.EXTERNAL_AUTH_ENABLED = True
    auth_settings.EXTERNAL_AUTH_PROVIDER = "external"

    # First login carries an email and provisions the user + profile.
    identity_with_email = identity_from_claims(
        {"sub": "ext-subject-1", "email": "alice@example.com", "preferred_username": "alice"},
        auth_settings,
    )
    user = await auth_service._materialize_external_user(identity_with_email, async_session)
    await async_session.flush()

    profile = (await async_session.exec(select(SSOUserProfile).where(SSOUserProfile.user_id == user.id))).first()
    assert profile is not None
    assert profile.email == "alice@example.com"

    # Second login with the SAME subject but NO email claim must keep the stored email.
    identity_without_email = identity_from_claims(
        {"sub": "ext-subject-1", "preferred_username": "alice"},
        auth_settings,
    )
    assert identity_without_email.email is None

    same_user = await auth_service._materialize_external_user(identity_without_email, async_session)
    await async_session.flush()
    await async_session.refresh(profile)

    assert same_user.id == user.id
    assert profile.email == "alice@example.com"

    # A later token that DOES carry an email still updates it.
    identity_new_email = identity_from_claims(
        {"sub": "ext-subject-1", "email": "alice2@example.com"},
        auth_settings,
    )
    await auth_service._materialize_external_user(identity_new_email, async_session)
    await async_session.flush()
    await async_session.refresh(profile)
    assert profile.email == "alice2@example.com"


# =============================================================================
# External fallback (F2/F14): a valid external credential is tried when native fails
# =============================================================================


@pytest.mark.anyio
async def test_invalid_native_token_falls_back_to_external_credential(
    auth_service: AuthService,
    auth_settings: AuthSettings,
    async_session,
):
    """An invalid native token plus a valid external credential authenticates via external (F2/F14)."""
    from langflow.services.auth.external import identity_from_claims

    auth_settings.EXTERNAL_AUTH_ENABLED = True
    auth_settings.EXTERNAL_AUTH_TRUSTED_JWT_DECODE = True
    auth_settings.EXTERNAL_AUTH_PROVIDER = "external"

    # Pre-provision the external user + profile so the resolver takes the
    # existing-profile branch (no folder/variable service needed).
    identity = identity_from_claims(
        {"sub": "ext-subject-2", "email": "bob@example.com", "preferred_username": "bob"},
        auth_settings,
    )
    user = await auth_service._materialize_external_user(identity, async_session)
    await async_session.flush()

    # A present-but-invalid native token must NOT shadow the valid external one.
    external_token = _external_jwt(
        auth_service, {"sub": "ext-subject-2", "email": "bob@example.com", "preferred_username": "bob"}
    )

    try:
        result = await auth_service.authenticate_with_credentials(
            token="not-a-valid-jwt",  # noqa: S106  # native decode fails
            api_key=None,
            db=async_session,
            external_token=external_token,
        )
    finally:
        clear_current_auth_context()

    assert result.id == user.id


@pytest.mark.anyio
async def test_no_external_token_keeps_native_error(
    auth_service: AuthService,
    auth_settings: AuthSettings,
):
    """With external_token=None, an invalid native token still raises (no behavior change)."""
    auth_settings.EXTERNAL_AUTH_ENABLED = True
    auth_settings.EXTERNAL_AUTH_TRUSTED_JWT_DECODE = True

    with pytest.raises(InvalidTokenError):
        await auth_service.authenticate_with_credentials(
            token="not-a-valid-jwt",  # noqa: S106
            api_key=None,
            db=AsyncMock(),
            external_token=None,
        )


@pytest.mark.anyio
async def test_external_token_only_authenticates_without_native_token(
    auth_service: AuthService,
    auth_settings: AuthSettings,
    async_session,
):
    """When no native token is present, the separately-extracted external token still works."""
    from langflow.services.auth.external import identity_from_claims

    auth_settings.EXTERNAL_AUTH_ENABLED = True
    auth_settings.EXTERNAL_AUTH_TRUSTED_JWT_DECODE = True
    auth_settings.EXTERNAL_AUTH_PROVIDER = "external"

    identity = identity_from_claims(
        {"sub": "ext-subject-3", "preferred_username": "carol"},
        auth_settings,
    )
    user = await auth_service._materialize_external_user(identity, async_session)
    await async_session.flush()

    external_token = _external_jwt(auth_service, {"sub": "ext-subject-3", "preferred_username": "carol"})

    try:
        result = await auth_service.authenticate_with_credentials(
            token=None,
            api_key=None,
            db=async_session,
            external_token=external_token,
        )
    finally:
        clear_current_auth_context()

    assert result.id == user.id


# =============================================================================
# P1: regular HTTP + /session external-credential shadowing
# get_current_user_from_access_token must fall back to a distinct external token
# when the native token is stale/invalid, and accept an external-only credential.
# =============================================================================


@pytest.mark.anyio
async def test_access_token_path_falls_back_to_external_on_invalid_native(
    auth_service: AuthService,
    auth_settings: AuthSettings,
    async_session,
):
    """A stale/invalid native token plus a valid external credential recovers (P1)."""
    from langflow.services.auth.external import identity_from_claims

    auth_settings.EXTERNAL_AUTH_ENABLED = True
    auth_settings.EXTERNAL_AUTH_TRUSTED_JWT_DECODE = True
    auth_settings.EXTERNAL_AUTH_PROVIDER = "external"

    identity = identity_from_claims(
        {"sub": "ext-p1-1", "preferred_username": "dave"},
        auth_settings,
    )
    user = await auth_service._materialize_external_user(identity, async_session)
    await async_session.flush()

    external_token = _external_jwt(auth_service, {"sub": "ext-p1-1", "preferred_username": "dave"})

    try:
        result = await auth_service.get_current_user_from_access_token(
            "not-a-valid-jwt",  # native decode fails
            async_session,
            external_token=external_token,
        )
    finally:
        clear_current_auth_context()

    assert result.id == user.id


@pytest.mark.anyio
async def test_access_token_path_external_only_authenticates(
    auth_service: AuthService,
    auth_settings: AuthSettings,
    async_session,
):
    """No native token but a valid external credential authenticates via /session path (P1)."""
    from langflow.services.auth.external import identity_from_claims

    auth_settings.EXTERNAL_AUTH_ENABLED = True
    auth_settings.EXTERNAL_AUTH_TRUSTED_JWT_DECODE = True
    auth_settings.EXTERNAL_AUTH_PROVIDER = "external"

    identity = identity_from_claims(
        {"sub": "ext-p1-2", "preferred_username": "erin"},
        auth_settings,
    )
    user = await auth_service._materialize_external_user(identity, async_session)
    await async_session.flush()

    external_token = _external_jwt(auth_service, {"sub": "ext-p1-2", "preferred_username": "erin"})

    try:
        result = await auth_service.get_current_user_from_access_token(
            None,
            async_session,
            external_token=external_token,
        )
    finally:
        clear_current_auth_context()

    assert result.id == user.id


@pytest.mark.anyio
async def test_access_token_path_no_external_keeps_native_error(
    auth_service: AuthService,
    auth_settings: AuthSettings,
):
    """With external_token=None, an invalid native token still raises (no behavior change)."""
    auth_settings.EXTERNAL_AUTH_ENABLED = True
    auth_settings.EXTERNAL_AUTH_TRUSTED_JWT_DECODE = True

    with pytest.raises(InvalidTokenError):
        await auth_service.get_current_user_from_access_token(
            "not-a-valid-jwt",
            AsyncMock(),
            external_token=None,
        )


@pytest.mark.anyio
async def test_access_token_path_missing_native_token_still_raises(
    auth_service: AuthService,
):
    """A None native token with no external credential still raises MissingCredentialsError."""
    with pytest.raises(MissingCredentialsError):
        await auth_service.get_current_user_from_access_token(None, AsyncMock())


# =============================================================================
# P2: the external-access ceiling ContextVar is cleared at every auth entrypoint.
# A stale ceiling left over from a prior same-task external auth must not leak
# into a subsequent non-external API-key auth path.
# =============================================================================


@pytest.mark.anyio
async def test_api_key_entrypoint_clears_stale_external_access_ceiling(
    auth_service: AuthService,
    auth_settings: AuthSettings,
):
    """_api_key_security_impl must clear a stale external-access ceiling ContextVar."""
    from langflow.services.auth.external import (
        ExternalAccessContext,
        get_current_external_access_context,
        set_current_external_access_context,
    )

    auth_settings.AUTO_LOGIN = False
    user = _dummy_user(uuid4())

    # Simulate a stale ceiling left in this task by a prior external auth.
    set_current_external_access_context(
        ExternalAccessContext(provider="external", subject="stale-subject", level="viewer")
    )
    assert get_current_external_access_context() is not None

    try:
        with patch(
            "langflow.services.auth.service.authenticate_api_key",
            new=AsyncMock(
                return_value=ApiKeyAuthResult(
                    user=user,
                    api_key_source="db",  # pragma: allowlist secret
                    api_key_id=uuid4(),
                )
            ),
        ):
            result = await auth_service._api_key_security_impl(
                query_param="sk-test-key",  # pragma: allowlist secret
                header_param=None,
                db=AsyncMock(),
                settings_service=auth_service.settings,
            )

        # The stale ceiling must have been cleared by the entrypoint.
        assert get_current_external_access_context() is None
    finally:
        clear_current_auth_context()
        set_current_external_access_context(None)

    assert result.id == user.id
