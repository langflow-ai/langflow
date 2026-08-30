from __future__ import annotations

import asyncio
import hashlib
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import jwt
import pytest
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, WebSocketException, status
from langflow.services.auth.constants import AUTO_LOGIN_ERROR, AUTO_LOGIN_WARNING
from langflow.services.auth.context import (
    AUTH_METHOD_API_KEY,
    AUTH_METHOD_AUTO_LOGIN,
    AUTH_METHOD_EXTERNAL,
    AUTH_METHOD_JWT,
    AuthCredentialContext,
    clear_current_auth_context,
    get_current_auth_context,
    set_current_auth_context,
)
from langflow.services.auth.exceptions import (
    InactiveUserError,
    InvalidCredentialsError,
    InvalidTokenError,
    MissingCredentialsError,
    TokenExpiredError,
)
from langflow.services.auth.service import AuthService
from langflow.services.database.models.api_key.crud import ApiKeyAuthResult, hash_api_key
from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.database.models.user.model import User
from lfx.services.settings.auth import AuthSettings
from lfx.services.settings.constants import DEFAULT_SUPERUSER, LEGACY_DEFAULT_SUPERUSER_PASSWORD
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.fixture
def auth_settings(tmp_path) -> AuthSettings:
    settings = AuthSettings(CONFIG_DIR=str(tmp_path))
    settings.SECRET_KEY = SecretStr("MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")  # pragma: allowlist secret
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
async def test_inactive_user_api_key_rejection_does_not_persist_usage(
    auth_service: AuthService,
    tmp_path,
    monkeypatch,
):
    """A rejected inactive-user credential must not record a successful API-key use."""
    plaintext = "sk-inactive-user"  # pragma: allowlist secret
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'inactive-user-api-key.db'}")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(
                lambda sync_connection: SQLModel.metadata.create_all(
                    sync_connection,
                    tables=[User.__table__, ApiKey.__table__],
                )
            )

        inactive_user = _dummy_user(uuid4(), active=False)
        inactive_user.username = "inactive-api-key-user"
        api_key = ApiKey(
            api_key="encrypted-inactive-user",  # pragma: allowlist secret
            api_key_hash=hash_api_key(plaintext),
            name="inactive-user",
            user_id=inactive_user.id,
            created_at=datetime.now(timezone.utc),
        )
        async with AsyncSession(engine, expire_on_commit=False) as seed_session:
            seed_session.add(inactive_user)
            seed_session.add(api_key)
            await seed_session.commit()
            api_key_id = api_key.id

        auth_service.settings.settings.disable_track_apikey_usage = False
        monkeypatch.setattr(
            "langflow.services.database.models.api_key.crud.get_settings_service",
            lambda: auth_service.settings,
        )

        @asynccontextmanager
        async def owned_auth_scope():
            async with AsyncSession(engine, expire_on_commit=False) as auth_session:
                try:
                    yield auth_session
                    await auth_session.commit()
                except Exception:
                    await auth_session.rollback()
                    raise

        monkeypatch.setattr(
            "langflow.services.database.models.api_key.crud.session_scope",
            owned_auth_scope,
        )
        async with AsyncSession(engine, expire_on_commit=False) as caller_session:
            with pytest.raises(InvalidCredentialsError):
                await auth_service.authenticate_with_credentials(
                    token=None,
                    api_key=plaintext,
                    db=caller_session,
                )
            await caller_session.rollback()

        async with AsyncSession(engine, expire_on_commit=False) as verification_session:
            persisted_api_key = await verification_session.get(ApiKey, api_key_id)
    finally:
        await engine.dispose()

    assert persisted_api_key is not None
    assert persisted_api_key.total_uses == 0
    assert persisted_api_key.last_used_at is None


@pytest.mark.anyio
@pytest.mark.parametrize("token", [None, "native-token"], ids=["external-only", "native-and-external"])
async def test_api_key_fallback_rolls_back_failed_token_and_external_state(
    auth_service: AuthService,
    async_session,
    monkeypatch,
    token,
):
    """API-key fallback discards state flushed by every earlier credential attempt."""
    from sqlmodel import select

    api_user = _dummy_user(uuid4())
    api_user.username = "api-key-user"
    plaintext = "sk-valid-fallback-key"  # pragma: allowlist secret
    api_key = ApiKey(
        api_key="encrypted-value",  # pragma: allowlist secret
        api_key_hash=hash_api_key(plaintext),
        name="fallback",
        user_id=api_user.id,
        created_at=datetime.now(timezone.utc),
    )
    async_session.add(api_user)
    async_session.add(api_key)
    await async_session.commit()
    api_user_id = api_user.id

    auth_service.settings.settings.disable_track_apikey_usage = False
    monkeypatch.setattr(
        "langflow.services.database.models.api_key.crud.get_settings_service",
        lambda: auth_service.settings,
    )

    @asynccontextmanager
    async def owned_auth_scope():
        async with AsyncSession(bind=async_session.bind, expire_on_commit=False) as auth_session:
            try:
                yield auth_session
                await auth_session.commit()
            except Exception:
                await auth_session.rollback()
                raise

    monkeypatch.setattr(
        "langflow.services.database.models.api_key.crud.session_scope",
        owned_auth_scope,
    )

    failed_token_user = _dummy_user(uuid4())
    failed_token_user.username = "failed-token-user"
    failed_external_user = _dummy_user(uuid4())
    failed_external_user.username = "failed-external-user"

    async def stage_user_then_fail(_token: str, db) -> None:
        db.add(failed_token_user)
        await db.flush()
        msg = "external reconciliation failed"
        raise RuntimeError(msg)

    async def stage_user_then_decline(_token: str, db) -> None:
        db.add(failed_external_user)
        await db.flush()

    with (
        patch.object(auth_service, "_authenticate_with_token", new=stage_user_then_fail),
        patch.object(auth_service, "_authenticate_with_external_token", new=stage_user_then_decline),
    ):
        result = await auth_service.authenticate_with_credentials(
            token=token,
            api_key=plaintext,
            db=async_session,
            external_token="external-token",  # noqa: S106
        )

    persisted_failed_token_user = (
        await async_session.exec(select(User).where(User.id == failed_token_user.id))
    ).first()
    persisted_failed_external_user = (
        await async_session.exec(select(User).where(User.id == failed_external_user.id))
    ).first()
    await async_session.refresh(api_key)

    assert result.id == api_user_id
    assert persisted_failed_token_user is None
    assert persisted_failed_external_user is None
    assert api_key.total_uses == 1


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


def test_short_key_decrypts_legacy_ciphertext_without_using_legacy_key_for_new_writes(tmp_path):
    """Short-key upgrades retain read compatibility without regressing new encryption.

    Before 1.10.1, ``shortkey123`` produced the fixed Fernet key below via
    ``random.seed(secret)`` and 32 calls to ``random.getrandbits(8)``. The
    current SHA-256 key must decrypt that legacy ciphertext as a fallback, but
    encryption must continue to use the SHA-256-derived primary key.
    """
    from langflow.services.auth.utils import ensure_fernet_key

    raw_key = "shortkey123"  # pragma: allowlist secret
    legacy_key = b"qeA9wdDv6i0_4s4YpmYkg7mByqBIVqF5L8On7wINNmo="  # pragma: allowlist secret
    plaintext = "credential-written-before-1.10.1"  # pragma: allowlist secret

    settings = AuthSettings(CONFIG_DIR=str(tmp_path))
    settings.SECRET_KEY = SecretStr(raw_key)
    settings_service = SimpleNamespace(
        auth_settings=settings,
        settings=SimpleNamespace(config_dir=str(tmp_path)),
    )
    svc = AuthService(settings_service)

    legacy_ciphertext = Fernet(legacy_key).encrypt(plaintext.encode()).decode()
    assert svc.decrypt_api_key(legacy_ciphertext) == plaintext

    with patch("langflow.services.auth.utils._ensure_legacy_fernet_key") as mock_legacy_derivation:
        current_ciphertext = svc.encrypt_api_key(plaintext)

    mock_legacy_derivation.assert_not_called()
    assert Fernet(ensure_fernet_key(raw_key)).decrypt(current_ciphertext.encode()).decode() == plaintext
    with pytest.raises(InvalidToken):
        Fernet(legacy_key).decrypt(current_ciphertext.encode())


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
# Verified external-group reconciliation
# =============================================================================


class _DirectoryAuthorizationStub:
    """Authorization seam double for verified external-group reconciliation."""

    def __init__(
        self,
        *,
        result,
        claim_name: str | None = "groups",
        claim_path: tuple[str, ...] | None = None,
        supports_incomplete: bool = True,
    ) -> None:
        self.external_groups_claim = AsyncMock(return_value=claim_name)
        self.external_groups_claim_path = AsyncMock(
            return_value=claim_path if claim_path is not None else ((claim_name,) if claim_name else None)
        )
        self.ingest_directory_membership_snapshot = AsyncMock(return_value=result)
        self.directory_membership_committed = AsyncMock()
        self.supports_incomplete_directory_membership_snapshots = AsyncMock(return_value=supports_incomplete)


def _external_identity(claims: dict):
    from langflow.services.auth.external import ExternalIdentity

    return ExternalIdentity(
        provider="customer-idp",
        subject="external-subject",
        username="external-user",
        claims=claims,
    )


@pytest.mark.anyio
async def test_external_group_reconciliation_normalizes_commits_and_audits(auth_service: AuthService):
    from lfx.services.authorization import DirectoryMembershipIngestResult

    user = _dummy_user(uuid4())
    db = AsyncMock()
    authz = _DirectoryAuthorizationStub(result=DirectoryMembershipIngestResult(changed=True, added=2, removed=1))
    audit = AsyncMock()
    identity = _external_identity(
        {
            "iss": " https://issuer.example ",
            "aud": ["langflow-api"],
            "groups": [" reviewers ", "engineering", "reviewers"],
        }
    )

    with (
        patch("langflow.services.deps.get_authorization_service", return_value=authz),
        patch("langflow.services.authorization.audit.audit_decision", new=audit),
    ):
        await auth_service._reconcile_verified_external_groups(identity=identity, user=user, db=db)

    snapshot = authz.ingest_directory_membership_snapshot.await_args.kwargs["snapshot"]
    assert snapshot.provider_id == "customer-idp"
    assert snapshot.provider_user_id == "external-subject"
    assert snapshot.user_id == user.id
    assert snapshot.memberships == ("engineering", "reviewers")
    assert snapshot.authoritative is True
    assert snapshot.complete is True
    assert snapshot.claim_state is None
    assert snapshot.claim_path == ("groups",)
    db.commit.assert_awaited_once()
    authz.directory_membership_committed.assert_awaited_once_with(user_id=user.id, changed=True)

    audit_details = audit.await_args.kwargs
    assert audit_details["action"] == "directory_membership:reconcile"
    assert audit_details["obj"] == f"user:{user.id}"
    assert audit_details["result"] == "allow"
    assert audit_details["details"] == {
        "provider_id": "customer-idp",
        "issuer": "https://issuer.example",
        "subject": "external-subject",
        "audience": ["langflow-api"],
        "source": "external_bearer",
        "membership_count": 2,
        "membership_sha256": hashlib.sha256(b"engineering\0reviewers").hexdigest(),
        "changed": True,
        "added": 2,
        "removed": 1,
        "authoritative": True,
        "complete": True,
    }


@pytest.mark.anyio
async def test_external_group_reconciliation_accepts_present_empty_claim(auth_service: AuthService):
    from lfx.services.authorization import DirectoryMembershipClaimState, DirectoryMembershipIngestResult

    user = _dummy_user(uuid4())
    db = AsyncMock()
    authz = _DirectoryAuthorizationStub(result=DirectoryMembershipIngestResult())

    with (
        patch("langflow.services.deps.get_authorization_service", return_value=authz),
        patch("langflow.services.authorization.audit.audit_decision", new=AsyncMock()),
    ):
        await auth_service._reconcile_verified_external_groups(
            identity=_external_identity({"groups": []}),
            user=user,
            db=db,
        )

    snapshot = authz.ingest_directory_membership_snapshot.await_args.kwargs["snapshot"]
    assert snapshot.memberships == ()
    assert snapshot.claim_state is DirectoryMembershipClaimState.EMPTY
    db.commit.assert_awaited_once()
    authz.directory_membership_committed.assert_awaited_once_with(user_id=user.id, changed=False)


@pytest.mark.anyio
async def test_external_group_reconciliation_resolves_nested_claim_path(auth_service: AuthService):
    from lfx.services.authorization import DirectoryMembershipIngestResult

    user = _dummy_user(uuid4())
    db = AsyncMock()
    authz = _DirectoryAuthorizationStub(
        result=DirectoryMembershipIngestResult(),
        claim_path=("realm_access", "groups"),
    )

    with (
        patch("langflow.services.deps.get_authorization_service", return_value=authz),
        patch("langflow.services.authorization.audit.audit_decision", new=AsyncMock()),
    ):
        await auth_service._reconcile_verified_external_groups(
            identity=_external_identity({"realm_access": {"groups": [" engineering "]}}),
            user=user,
            db=db,
        )

    snapshot = authz.ingest_directory_membership_snapshot.await_args.kwargs["snapshot"]
    assert snapshot.memberships == ("engineering",)
    assert snapshot.claim_path == ("realm_access", "groups")
    authz.external_groups_claim.assert_not_awaited()


@pytest.mark.anyio
async def test_nested_claim_path_does_not_collide_with_literal_dotted_overage_name(auth_service: AuthService):
    from lfx.services.authorization import DirectoryMembershipIngestResult

    user = _dummy_user(uuid4())
    db = AsyncMock()
    authz = _DirectoryAuthorizationStub(
        result=DirectoryMembershipIngestResult(),
        claim_path=("realm_access", "groups"),
    )

    with (
        patch("langflow.services.deps.get_authorization_service", return_value=authz),
        patch("langflow.services.authorization.audit.audit_decision", new=AsyncMock()),
    ):
        await auth_service._reconcile_verified_external_groups(
            identity=_external_identity(
                {
                    "_claim_names": {"realm_access.groups": "src1"},
                    "realm_access": {"groups": ["engineering"]},
                }
            ),
            user=user,
            db=db,
        )

    snapshot = authz.ingest_directory_membership_snapshot.await_args.kwargs["snapshot"]
    assert snapshot.memberships == ("engineering",)
    assert snapshot.claim_state is None


@pytest.mark.anyio
async def test_nested_claim_path_detects_top_level_parent_overage(auth_service: AuthService):
    from lfx.services.authorization import DirectoryMembershipClaimState, DirectoryMembershipIngestResult

    user = _dummy_user(uuid4())
    db = AsyncMock()
    authz = _DirectoryAuthorizationStub(
        result=DirectoryMembershipIngestResult(),
        claim_path=("realm_access", "groups"),
    )

    with (
        patch("langflow.services.deps.get_authorization_service", return_value=authz),
        patch("langflow.services.authorization.audit.audit_decision", new=AsyncMock()),
    ):
        await auth_service._reconcile_verified_external_groups(
            identity=_external_identity({"_claim_names": {"realm_access": "src1"}}),
            user=user,
            db=db,
        )

    snapshot = authz.ingest_directory_membership_snapshot.await_args.kwargs["snapshot"]
    assert snapshot.memberships == ()
    assert snapshot.claim_state is DirectoryMembershipClaimState.OVERAGE


@pytest.mark.anyio
async def test_external_group_reconciliation_marks_invalid_nested_container_malformed(auth_service: AuthService):
    from lfx.services.authorization import DirectoryMembershipClaimState, DirectoryMembershipIngestResult

    user = _dummy_user(uuid4())
    db = AsyncMock()
    authz = _DirectoryAuthorizationStub(
        result=DirectoryMembershipIngestResult(),
        claim_path=("realm_access", "groups"),
    )

    with (
        patch("langflow.services.deps.get_authorization_service", return_value=authz),
        patch("langflow.services.authorization.audit.audit_decision", new=AsyncMock()),
    ):
        await auth_service._reconcile_verified_external_groups(
            identity=_external_identity({"realm_access": "not-an-object"}),
            user=user,
            db=db,
        )

    snapshot = authz.ingest_directory_membership_snapshot.await_args.kwargs["snapshot"]
    assert snapshot.claim_state is DirectoryMembershipClaimState.MALFORMED
    assert snapshot.authoritative is False
    assert snapshot.complete is False


@pytest.mark.parametrize(
    ("claims", "expected_reason"),
    [
        ({"iss": "https://issuer.example"}, "absent"),
        (
            {"_claim_names": {"groups": "src1"}, "_claim_sources": {"src1": {"endpoint": "https://graph"}}},
            "overage",
        ),
        ({"groups": {"unexpected": "mapping"}}, "malformed"),
        ({"groups": ["engineering", 7]}, "malformed"),
        ({"groups": ["   "]}, "malformed"),
        ({"groups": ["x" * 257]}, "malformed"),
        ({"groups": [f"group-{index}" for index in range(501)]}, "too_many"),
    ],
    ids=["absent", "entra-overage", "invalid-type", "non-string", "blank", "overlong", "too-many"],
)
@pytest.mark.anyio
async def test_incomplete_external_group_claim_skips_authoritative_reconciliation(
    auth_service: AuthService,
    claims: dict,
    expected_reason: str,
):
    from lfx.services.authorization import DirectoryMembershipClaimState, DirectoryMembershipIngestResult

    user = _dummy_user(uuid4())
    db = AsyncMock()
    authz = _DirectoryAuthorizationStub(result=DirectoryMembershipIngestResult(changed=True))
    events: list[str] = []
    db.commit.side_effect = lambda: events.append("commit")
    audit = AsyncMock(side_effect=lambda **_kwargs: events.append("audit"))

    with (
        patch("langflow.services.deps.get_authorization_service", return_value=authz),
        patch("langflow.services.authorization.audit.audit_decision", new=audit),
    ):
        await auth_service._reconcile_verified_external_groups(
            identity=_external_identity(claims),
            user=user,
            db=db,
        )

    snapshot = authz.ingest_directory_membership_snapshot.await_args.kwargs["snapshot"]
    assert snapshot.memberships == ()
    assert snapshot.authoritative is False
    assert snapshot.complete is False
    assert snapshot.claim_state is DirectoryMembershipClaimState(expected_reason)
    assert snapshot.claim_path == ("groups",)
    db.commit.assert_awaited_once()
    authz.directory_membership_committed.assert_awaited_once_with(user_id=user.id, changed=True)
    audit.assert_awaited_once()
    assert events == ["commit", "audit"]
    audit_call = audit.await_args.kwargs
    assert audit_call["action"] == "directory_membership:reconcile"
    assert audit_call["obj"] == f"user:{user.id}"
    assert audit_call["result"] == "skip"
    assert audit_call["details"] == {
        "provider_id": "customer-idp",
        "issuer": claims.get("iss"),
        "subject": "external-subject",
        "audience": None,
        "source": "external_bearer",
        "claim_name": "groups",
        "reason": expected_reason,
        "authoritative": False,
        "complete": False,
    }


@pytest.mark.anyio
async def test_incomplete_external_group_claim_reaches_plugin_before_commit(auth_service: AuthService):
    from lfx.services.authorization import AuthorizationMutationRejected

    user = _dummy_user(uuid4())
    db = AsyncMock()
    authz = _DirectoryAuthorizationStub(result=None)
    authz.ingest_directory_membership_snapshot.side_effect = AuthorizationMutationRejected("Group claim required")

    with (
        patch("langflow.services.deps.get_authorization_service", return_value=authz),
        patch("langflow.services.authorization.audit.audit_decision", new=AsyncMock()) as audit,
        pytest.raises(InvalidTokenError, match="Group claim required") as exc_info,
    ):
        await auth_service._reconcile_verified_external_groups(
            identity=_external_identity({}),
            user=user,
            db=db,
        )

    authz.ingest_directory_membership_snapshot.assert_awaited_once()
    db.commit.assert_not_awaited()
    audit.assert_not_awaited()
    assert isinstance(exc_info.value.__cause__, AuthorizationMutationRejected)


@pytest.mark.anyio
async def test_incomplete_external_group_claim_preserves_legacy_complete_only_plugin_contract(
    auth_service: AuthService,
):
    from lfx.services.authorization import DirectoryMembershipIngestResult

    user = _dummy_user(uuid4())
    db = AsyncMock()
    authz = _DirectoryAuthorizationStub(
        result=DirectoryMembershipIngestResult(changed=True),
        supports_incomplete=False,
    )
    audit = AsyncMock()

    with (
        patch("langflow.services.deps.get_authorization_service", return_value=authz),
        patch("langflow.services.authorization.audit.audit_decision", new=audit),
    ):
        await auth_service._reconcile_verified_external_groups(
            identity=_external_identity({}),
            user=user,
            db=db,
        )

    authz.supports_incomplete_directory_membership_snapshots.assert_awaited_once_with()
    authz.ingest_directory_membership_snapshot.assert_not_awaited()
    authz.directory_membership_committed.assert_not_awaited()
    db.commit.assert_awaited_once()
    assert audit.await_args.kwargs["result"] == "skip"
    assert audit.await_args.kwargs["details"]["reason"] == "absent"


@pytest.mark.anyio
async def test_incomplete_external_group_claim_preserves_duck_typed_legacy_plugin_contract(
    auth_service: AuthService,
):
    """A plugin predating the capability method never receives ambiguous empty membership."""
    from lfx.services.authorization import DirectoryMembershipIngestResult

    user = _dummy_user(uuid4())
    db = AsyncMock()
    authz = _DirectoryAuthorizationStub(result=DirectoryMembershipIngestResult(changed=True))
    del authz.supports_incomplete_directory_membership_snapshots
    audit = AsyncMock()

    with (
        patch("langflow.services.deps.get_authorization_service", return_value=authz),
        patch("langflow.services.authorization.audit.audit_decision", new=audit),
    ):
        await auth_service._reconcile_verified_external_groups(
            identity=_external_identity({}),
            user=user,
            db=db,
        )

    authz.ingest_directory_membership_snapshot.assert_not_awaited()
    authz.directory_membership_committed.assert_not_awaited()
    db.commit.assert_awaited_once()
    assert audit.await_args.kwargs["result"] == "skip"
    assert audit.await_args.kwargs["details"]["reason"] == "absent"


@pytest.mark.anyio
async def test_external_group_reconciliation_plugin_opt_out_is_not_a_skip(auth_service: AuthService):
    from lfx.services.authorization import DirectoryMembershipIngestResult

    user = _dummy_user(uuid4())
    db = AsyncMock()
    authz = _DirectoryAuthorizationStub(
        result=DirectoryMembershipIngestResult(changed=True),
        claim_name=None,
    )
    audit = AsyncMock()

    with (
        patch("langflow.services.deps.get_authorization_service", return_value=authz),
        patch("langflow.services.authorization.audit.audit_decision", new=audit),
    ):
        await auth_service._reconcile_verified_external_groups(
            identity=_external_identity({}),
            user=user,
            db=db,
        )

    authz.ingest_directory_membership_snapshot.assert_not_awaited()
    db.commit.assert_not_awaited()
    audit.assert_not_awaited()


@pytest.mark.parametrize(
    "legacy_result",
    [None, SimpleNamespace(changed=True)],
    ids=["none", "changed-only"],
)
@pytest.mark.anyio
async def test_legacy_directory_ingest_result_invalidates_conservatively(
    auth_service: AuthService,
    legacy_result,
):
    user = _dummy_user(uuid4())
    db = AsyncMock()
    authz = _DirectoryAuthorizationStub(result=legacy_result)

    with (
        patch("langflow.services.deps.get_authorization_service", return_value=authz),
        patch("langflow.services.authorization.audit.audit_decision", new=AsyncMock()),
    ):
        await auth_service._reconcile_verified_external_groups(
            identity=_external_identity({"groups": ["engineering"]}),
            user=user,
            db=db,
        )

    db.commit.assert_awaited_once()
    authz.directory_membership_committed.assert_awaited_once_with(user_id=user.id, changed=True)


@pytest.mark.anyio
async def test_directory_post_commit_failure_does_not_fail_authentication(auth_service: AuthService):
    from lfx.services.authorization import DirectoryMembershipIngestResult

    user = _dummy_user(uuid4())
    db = AsyncMock()
    authz = _DirectoryAuthorizationStub(result=DirectoryMembershipIngestResult(changed=True, added=1))
    authz.directory_membership_committed.side_effect = RuntimeError("replica unavailable")

    with (
        patch("langflow.services.deps.get_authorization_service", return_value=authz),
        patch("langflow.services.authorization.audit.audit_decision", new=AsyncMock()),
    ):
        await auth_service._reconcile_verified_external_groups(
            identity=_external_identity({"groups": ["engineering"]}),
            user=user,
            db=db,
        )

    db.commit.assert_awaited_once()
    authz.directory_membership_committed.assert_awaited_once_with(user_id=user.id, changed=True)


@pytest.mark.anyio
async def test_directory_post_commit_audit_failure_does_not_fail_authentication(auth_service: AuthService):
    from lfx.services.authorization import DirectoryMembershipIngestResult

    user = _dummy_user(uuid4())
    db = AsyncMock()
    authz = _DirectoryAuthorizationStub(result=DirectoryMembershipIngestResult(changed=True, added=1))
    audit = AsyncMock(side_effect=RuntimeError("audit settings unavailable"))

    with (
        patch("langflow.services.deps.get_authorization_service", return_value=authz),
        patch("langflow.services.authorization.audit.audit_decision", new=audit),
    ):
        await auth_service._reconcile_verified_external_groups(
            identity=_external_identity({"groups": ["engineering"]}),
            user=user,
            db=db,
        )

    db.commit.assert_awaited_once()
    audit.assert_awaited_once()
    authz.directory_membership_committed.assert_awaited_once_with(user_id=user.id, changed=True)


@pytest.mark.anyio
async def test_directory_skip_audit_failure_does_not_fail_authentication(auth_service: AuthService):
    from lfx.services.authorization import DirectoryMembershipIngestResult

    user = _dummy_user(uuid4())
    db = AsyncMock()
    authz = _DirectoryAuthorizationStub(result=DirectoryMembershipIngestResult(changed=True))
    audit = AsyncMock(side_effect=RuntimeError("audit settings unavailable"))

    with (
        patch("langflow.services.deps.get_authorization_service", return_value=authz),
        patch("langflow.services.authorization.audit.audit_decision", new=audit),
    ):
        await auth_service._reconcile_verified_external_groups(
            identity=_external_identity({}),
            user=user,
            db=db,
        )

    authz.ingest_directory_membership_snapshot.assert_awaited_once()
    db.commit.assert_awaited_once()
    audit.assert_awaited_once()
    authz.directory_membership_committed.assert_awaited_once_with(user_id=user.id, changed=True)


# =============================================================================
# LE-2109: bearer tokens arrive on every request, so an unchanged directory
# state must not be reconciled (and audited) again on every one of them.
# =============================================================================


@pytest.mark.anyio
async def test_unchanged_directory_state_reconciles_once_per_interval(
    auth_service: AuthService,
    auth_settings: AuthSettings,
):
    from lfx.services.authorization import DirectoryMembershipIngestResult

    auth_settings.EXTERNAL_AUTH_GROUP_RECONCILE_INTERVAL_SECONDS = 60
    user = _dummy_user(uuid4())
    db = AsyncMock()
    authz = _DirectoryAuthorizationStub(result=DirectoryMembershipIngestResult(changed=False))
    audit = AsyncMock()
    identity = _external_identity({"groups": ["engineering", "reviewers"]})

    with (
        patch("langflow.services.deps.get_authorization_service", return_value=authz),
        patch("langflow.services.authorization.audit.audit_decision", new=audit),
    ):
        for _ in range(5):
            await auth_service._reconcile_verified_external_groups(identity=identity, user=user, db=db)

    # One reconciliation and one audit row for five authenticated requests,
    # while the JIT/profile bookkeeping of every request is still committed.
    authz.ingest_directory_membership_snapshot.assert_awaited_once()
    assert audit.await_count == 1
    assert db.commit.await_count == 5


@pytest.mark.anyio
async def test_changed_group_claim_reconciles_immediately(
    auth_service: AuthService,
    auth_settings: AuthSettings,
):
    from lfx.services.authorization import DirectoryMembershipIngestResult

    auth_settings.EXTERNAL_AUTH_GROUP_RECONCILE_INTERVAL_SECONDS = 3600
    user = _dummy_user(uuid4())
    db = AsyncMock()
    authz = _DirectoryAuthorizationStub(result=DirectoryMembershipIngestResult(changed=False))
    audit = AsyncMock()

    with (
        patch("langflow.services.deps.get_authorization_service", return_value=authz),
        patch("langflow.services.authorization.audit.audit_decision", new=audit),
    ):
        await auth_service._reconcile_verified_external_groups(
            identity=_external_identity({"groups": ["engineering"]}),
            user=user,
            db=db,
        )
        await auth_service._reconcile_verified_external_groups(
            identity=_external_identity({"groups": ["engineering", "reviewers"]}),
            user=user,
            db=db,
        )

    assert authz.ingest_directory_membership_snapshot.await_count == 2
    memberships = [
        call.kwargs["snapshot"].memberships for call in authz.ingest_directory_membership_snapshot.await_args_list
    ]
    assert memberships == [("engineering",), ("engineering", "reviewers")]


@pytest.mark.anyio
async def test_reconciliation_that_changed_state_is_confirmed_before_it_is_cached(
    auth_service: AuthService,
    auth_settings: AuthSettings,
):
    """A pass that wrote something must not hide the next request's retry."""
    from lfx.services.authorization import DirectoryMembershipIngestResult

    auth_settings.EXTERNAL_AUTH_GROUP_RECONCILE_INTERVAL_SECONDS = 3600
    user = _dummy_user(uuid4())
    db = AsyncMock()
    authz = _DirectoryAuthorizationStub(result=DirectoryMembershipIngestResult(changed=True, added=1))
    audit = AsyncMock()
    identity = _external_identity({"groups": ["engineering"]})

    with (
        patch("langflow.services.deps.get_authorization_service", return_value=authz),
        patch("langflow.services.authorization.audit.audit_decision", new=audit),
    ):
        await auth_service._reconcile_verified_external_groups(identity=identity, user=user, db=db)
        authz.ingest_directory_membership_snapshot.return_value = DirectoryMembershipIngestResult(changed=False)
        await auth_service._reconcile_verified_external_groups(identity=identity, user=user, db=db)
        await auth_service._reconcile_verified_external_groups(identity=identity, user=user, db=db)

    assert authz.ingest_directory_membership_snapshot.await_count == 2


@pytest.mark.anyio
async def test_zero_reconcile_interval_reconciles_every_request(
    auth_service: AuthService,
    auth_settings: AuthSettings,
):
    from lfx.services.authorization import DirectoryMembershipIngestResult

    auth_settings.EXTERNAL_AUTH_GROUP_RECONCILE_INTERVAL_SECONDS = 0
    user = _dummy_user(uuid4())
    db = AsyncMock()
    authz = _DirectoryAuthorizationStub(result=DirectoryMembershipIngestResult(changed=False))
    audit = AsyncMock()
    identity = _external_identity({"groups": ["engineering"]})

    with (
        patch("langflow.services.deps.get_authorization_service", return_value=authz),
        patch("langflow.services.authorization.audit.audit_decision", new=audit),
    ):
        for _ in range(3):
            await auth_service._reconcile_verified_external_groups(identity=identity, user=user, db=db)

    assert authz.ingest_directory_membership_snapshot.await_count == 3


@pytest.mark.anyio
async def test_incomplete_claim_skip_is_not_audited_on_every_request(
    auth_service: AuthService,
    auth_settings: AuthSettings,
):
    from lfx.services.authorization import DirectoryMembershipIngestResult

    auth_settings.EXTERNAL_AUTH_GROUP_RECONCILE_INTERVAL_SECONDS = 60
    user = _dummy_user(uuid4())
    db = AsyncMock()
    authz = _DirectoryAuthorizationStub(
        result=DirectoryMembershipIngestResult(),
        supports_incomplete=False,
    )
    audit = AsyncMock()
    identity = _external_identity({})

    with (
        patch("langflow.services.deps.get_authorization_service", return_value=authz),
        patch("langflow.services.authorization.audit.audit_decision", new=audit),
    ):
        for _ in range(4):
            await auth_service._reconcile_verified_external_groups(identity=identity, user=user, db=db)

    authz.ingest_directory_membership_snapshot.assert_not_awaited()
    assert audit.await_count == 1
    assert db.commit.await_count == 4


@pytest.mark.anyio
async def test_group_revoked_after_promotion_reconciles_immediately(
    auth_service: AuthService,
    auth_settings: AuthSettings,
):
    """A group set the user moved past must not be served from an earlier cache entry.

    LE-2099 QA follow-up: ``[devs]`` reconciled and cached, then a promotion to
    ``[admins, devs]``, then the IdP revokes ``admins``. The claim now differs
    from the last reconciled state, so it must reconcile on the next request
    rather than after the interval expires - privilege removal is the case
    that must not be delayed.
    """
    from lfx.services.authorization import DirectoryMembershipIngestResult

    auth_settings.EXTERNAL_AUTH_GROUP_RECONCILE_INTERVAL_SECONDS = 3600
    user = _dummy_user(uuid4())
    db = AsyncMock()
    authz = _DirectoryAuthorizationStub(result=DirectoryMembershipIngestResult(changed=True, added=1))
    audit = AsyncMock()
    developer = _external_identity({"groups": ["lf-devs"]})
    promoted = _external_identity({"groups": ["lf-admins", "lf-devs"]})
    ingest = authz.ingest_directory_membership_snapshot

    async def reconcile(identity, *, changed: bool) -> None:
        ingest.return_value = DirectoryMembershipIngestResult(changed=changed, added=int(changed))
        await auth_service._reconcile_verified_external_groups(identity=identity, user=user, db=db)

    def memberships_seen() -> list[tuple[str, ...]]:
        return [call.kwargs["snapshot"].memberships for call in ingest.await_args_list]

    with (
        patch("langflow.services.deps.get_authorization_service", return_value=authz),
        patch("langflow.services.authorization.audit.audit_decision", new=audit),
    ):
        # 1) first login grants developer, 2) the confirming pass caches [devs]
        await reconcile(developer, changed=True)
        await reconcile(developer, changed=False)
        await reconcile(developer, changed=False)
        assert ingest.await_count == 2, "the confirming pass must be cached"

        # 3) promotion: a group set never seen before reconciles at once
        await reconcile(promoted, changed=True)
        assert ingest.await_count == 3

        # 4) revocation back to the earlier group set must reconcile immediately,
        #    even though [devs] was cached in step 2 and its TTL has not expired.
        await reconcile(developer, changed=True)
        assert ingest.await_count == 4, "a revoked group kept its role from a stale cache entry"
        assert memberships_seen()[-1] == ("lf-devs",)

        # The confirming pass caches the reconciled state again and later
        # identical requests are still skipped: the cache keeps working.
        await reconcile(developer, changed=False)
        await reconcile(developer, changed=False)
        await reconcile(developer, changed=False)
        assert ingest.await_count == 5

        # A later promotion is again a change from the last reconciled state.
        await reconcile(promoted, changed=True)
        assert ingest.await_count == 6

    assert memberships_seen() == [
        ("lf-devs",),
        ("lf-devs",),
        ("lf-admins", "lf-devs"),
        ("lf-devs",),
        ("lf-devs",),
        ("lf-admins", "lf-devs"),
    ]


@pytest.mark.anyio
async def test_revocation_reconciles_even_after_the_promotion_was_confirmed_and_cached(
    auth_service: AuthService,
    auth_settings: AuthSettings,
):
    """Both the promoted and the earlier state were cached; the older one must not win."""
    from lfx.services.authorization import DirectoryMembershipIngestResult

    auth_settings.EXTERNAL_AUTH_GROUP_RECONCILE_INTERVAL_SECONDS = 3600
    user = _dummy_user(uuid4())
    db = AsyncMock()
    authz = _DirectoryAuthorizationStub(result=DirectoryMembershipIngestResult(changed=False))
    audit = AsyncMock()
    developer = _external_identity({"groups": ["lf-devs"]})
    promoted = _external_identity({"groups": ["lf-admins", "lf-devs"]})
    ingest = authz.ingest_directory_membership_snapshot

    with (
        patch("langflow.services.deps.get_authorization_service", return_value=authz),
        patch("langflow.services.authorization.audit.audit_decision", new=audit),
    ):
        await auth_service._reconcile_verified_external_groups(identity=developer, user=user, db=db)
        ingest.return_value = DirectoryMembershipIngestResult(changed=True, added=1)
        await auth_service._reconcile_verified_external_groups(identity=promoted, user=user, db=db)
        ingest.return_value = DirectoryMembershipIngestResult(changed=False)
        await auth_service._reconcile_verified_external_groups(identity=promoted, user=user, db=db)
        assert ingest.await_count == 3

        # Revocation: [devs] is the state cached first, [admins, devs] the one
        # cached last. Neither may hide the change.
        ingest.return_value = DirectoryMembershipIngestResult(changed=True, removed=1)
        await auth_service._reconcile_verified_external_groups(identity=developer, user=user, db=db)

    assert ingest.await_count == 4
    assert ingest.await_args_list[-1].kwargs["snapshot"].memberships == ("lf-devs",)


@pytest.mark.anyio
async def test_reconcile_cache_is_scoped_per_user(
    auth_service: AuthService,
    auth_settings: AuthSettings,
):
    """Remembering one user's state must not evict or leak into another user's entry."""
    from lfx.services.authorization import DirectoryMembershipIngestResult

    auth_settings.EXTERNAL_AUTH_GROUP_RECONCILE_INTERVAL_SECONDS = 3600
    first_user = _dummy_user(uuid4())
    second_user = _dummy_user(uuid4())
    db = AsyncMock()
    authz = _DirectoryAuthorizationStub(result=DirectoryMembershipIngestResult(changed=False))
    audit = AsyncMock()
    identity = _external_identity({"groups": ["engineering"]})

    with (
        patch("langflow.services.deps.get_authorization_service", return_value=authz),
        patch("langflow.services.authorization.audit.audit_decision", new=audit),
    ):
        await auth_service._reconcile_verified_external_groups(identity=identity, user=first_user, db=db)
        await auth_service._reconcile_verified_external_groups(identity=identity, user=second_user, db=db)
        await auth_service._reconcile_verified_external_groups(identity=identity, user=first_user, db=db)
        await auth_service._reconcile_verified_external_groups(identity=identity, user=second_user, db=db)

    assert authz.ingest_directory_membership_snapshot.await_count == 2


@pytest.mark.anyio
async def test_change_landing_after_a_concurrent_noop_pass_evicts_its_entry(
    auth_service: AuthService,
    auth_settings: AuthSettings,
):
    """An old-token no-op pass must not keep serving once an overlapping pass changed the state.

    The promotion pass begins first and is held inside the plugin. Meanwhile
    the old token's ``[devs]`` pass verifies the still-unchanged state and is
    remembered. When the promotion commits, that entry must be evicted, or
    the next ``[devs]`` request would be skipped while the user holds admin.
    """
    from lfx.services.authorization import DirectoryMembershipIngestResult

    auth_settings.EXTERNAL_AUTH_GROUP_RECONCILE_INTERVAL_SECONDS = 3600
    user = _dummy_user(uuid4())
    db = AsyncMock()
    audit = AsyncMock()
    developer = _external_identity({"groups": ["lf-devs"]})
    promoted = _external_identity({"groups": ["lf-admins", "lf-devs"]})
    promotion_in_plugin = asyncio.Event()
    release_promotion = asyncio.Event()

    async def ingest(*, session, snapshot):  # noqa: ARG001
        if snapshot.memberships == ("lf-admins", "lf-devs"):
            promotion_in_plugin.set()
            await release_promotion.wait()
            return DirectoryMembershipIngestResult(changed=True, added=1)
        return DirectoryMembershipIngestResult(changed=False)

    authz = _DirectoryAuthorizationStub(result=None)
    authz.ingest_directory_membership_snapshot = AsyncMock(side_effect=ingest)

    with (
        patch("langflow.services.deps.get_authorization_service", return_value=authz),
        patch("langflow.services.authorization.audit.audit_decision", new=audit),
    ):
        promotion = asyncio.create_task(
            auth_service._reconcile_verified_external_groups(identity=promoted, user=user, db=db)
        )
        await promotion_in_plugin.wait()
        await auth_service._reconcile_verified_external_groups(identity=developer, user=user, db=db)
        assert authz.ingest_directory_membership_snapshot.await_count == 2
        release_promotion.set()
        await promotion

        await auth_service._reconcile_verified_external_groups(identity=developer, user=user, db=db)

    assert authz.ingest_directory_membership_snapshot.await_count == 3, (
        "the [devs] verdict cached before the promotion landed was served after it"
    )
    assert authz.ingest_directory_membership_snapshot.await_args_list[-1].kwargs["snapshot"].memberships == ("lf-devs",)


@pytest.mark.anyio
async def test_noop_pass_that_verified_a_superseded_state_is_not_remembered(
    auth_service: AuthService,
    auth_settings: AuthSettings,
):
    """A no-op verdict reached before a change landed must be discarded, not cached after it.

    The old token's ``[devs]`` pass verifies the state and is held at commit.
    The promotion then begins, changes the state and commits. When the held
    pass resumes and tries to remember ``[devs]``, its verdict describes a
    state the user has moved past and must be dropped.
    """
    from lfx.services.authorization import DirectoryMembershipIngestResult

    auth_settings.EXTERNAL_AUTH_GROUP_RECONCILE_INTERVAL_SECONDS = 3600
    user = _dummy_user(uuid4())
    audit = AsyncMock()
    developer = _external_identity({"groups": ["lf-devs"]})
    promoted = _external_identity({"groups": ["lf-admins", "lf-devs"]})
    developer_at_commit = asyncio.Event()
    release_developer = asyncio.Event()

    async def held_commit() -> None:
        developer_at_commit.set()
        await release_developer.wait()

    held_db = AsyncMock()
    held_db.commit = AsyncMock(side_effect=held_commit)
    db = AsyncMock()

    async def ingest(*, session, snapshot):  # noqa: ARG001
        if snapshot.memberships == ("lf-admins", "lf-devs"):
            return DirectoryMembershipIngestResult(changed=True, added=1)
        return DirectoryMembershipIngestResult(changed=False)

    authz = _DirectoryAuthorizationStub(result=None)
    authz.ingest_directory_membership_snapshot = AsyncMock(side_effect=ingest)

    with (
        patch("langflow.services.deps.get_authorization_service", return_value=authz),
        patch("langflow.services.authorization.audit.audit_decision", new=audit),
    ):
        held = asyncio.create_task(
            auth_service._reconcile_verified_external_groups(identity=developer, user=user, db=held_db)
        )
        await developer_at_commit.wait()
        await auth_service._reconcile_verified_external_groups(identity=promoted, user=user, db=db)
        assert authz.ingest_directory_membership_snapshot.await_count == 2
        release_developer.set()
        await held

        await auth_service._reconcile_verified_external_groups(identity=developer, user=user, db=db)

    assert authz.ingest_directory_membership_snapshot.await_count == 3, (
        "a stale [devs] verdict was cached after the promotion had already landed"
    )


# =============================================================================
# LE-2099 / BUG-02: a backend outage is not a credential verdict
# =============================================================================


@pytest.mark.anyio
async def test_transient_database_failure_is_not_reported_as_an_authentication_failure(
    auth_service: AuthService,
    auth_settings: AuthSettings,
):
    """A deadlock victim never judged the token, so it must not answer 401."""
    from langflow.services.auth.exceptions import AuthBackendUnavailableError
    from sqlalchemy.exc import DBAPIError

    class _DeadlockDetectedError(Exception):
        """Stand-in for psycopg's DeadlockDetected (SQLSTATE 40P01)."""

        sqlstate = "40P01"

    auth_settings.EXTERNAL_AUTH_ENABLED = True
    identity = _external_identity({"groups": ["engineering"]})
    deadlock = DBAPIError(
        "SELECT pg_advisory_xact_lock(%(lock_key)s::BIGINT)",
        {},
        _DeadlockDetectedError("deadlock detected"),
    )
    db = AsyncMock()

    with (
        patch("langflow.services.auth.service.resolve_external_identity", AsyncMock(return_value=identity)),
        patch.object(auth_service, "_materialize_external_user", AsyncMock(return_value=_dummy_user(uuid4()))),
        patch.object(
            auth_service,
            "_reconcile_verified_external_groups",
            AsyncMock(side_effect=deadlock),
        ),
        pytest.raises(AuthBackendUnavailableError) as exc_info,
    ):
        await auth_service._authenticate_with_external_token("external-token", db)

    assert exc_info.value.error_code == "auth_backend_unavailable"
    assert exc_info.value.__cause__ is deadlock


@pytest.mark.anyio
async def test_backend_unavailable_short_circuits_the_remaining_credentials(auth_service: AuthService):
    """A backend outage must not be retried against every other credential."""
    from langflow.services.auth.exceptions import AuthBackendUnavailableError

    db = AsyncMock()
    outage = AuthBackendUnavailableError()

    with (
        patch.object(auth_service, "_authenticate_with_token", side_effect=outage),
        patch.object(auth_service, "_authenticate_with_external_token", new=AsyncMock()) as external,
        patch.object(auth_service, "_authenticate_with_api_key", new=AsyncMock()) as api_key,
        pytest.raises(AuthBackendUnavailableError) as exc_info,
    ):
        await auth_service.authenticate_with_credentials(
            token="native-token",  # noqa: S106  # pragma: allowlist secret
            api_key="an-api-key",  # pragma: allowlist secret
            db=db,
            external_token="external-token",  # noqa: S106  # pragma: allowlist secret
        )

    assert exc_info.value is outage
    external.assert_not_awaited()
    api_key.assert_not_awaited()


def test_backend_unavailable_maps_to_a_retryable_503():
    from fastapi import status
    from langflow.services.auth.exceptions import AuthBackendUnavailableError
    from langflow.services.auth.utils import _auth_error_to_http

    http_error = _auth_error_to_http(AuthBackendUnavailableError())

    assert http_error.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert http_error.headers == {"Retry-After": "1"}


@pytest.mark.anyio
async def test_a_deadlocked_attempt_is_replayed_before_it_is_reported(
    auth_service: AuthService,
    auth_settings: AuthSettings,
):
    """The victim transaction rolled back, so replaying it is the fix."""
    from sqlalchemy.exc import DBAPIError

    class _DeadlockDetectedError(Exception):
        sqlstate = "40P01"

    auth_settings.EXTERNAL_AUTH_ENABLED = True
    identity = _external_identity({"groups": ["engineering"]})
    reconcile = AsyncMock(side_effect=[DBAPIError("stmt", {}, _DeadlockDetectedError("deadlock detected")), None])
    user = _dummy_user(uuid4())
    db = AsyncMock()

    with (
        patch("langflow.services.auth.service.resolve_external_identity", AsyncMock(return_value=identity)),
        patch.object(auth_service, "_materialize_external_user", AsyncMock(return_value=user)),
        patch.object(auth_service, "_reconcile_verified_external_groups", reconcile),
    ):
        resolved = await auth_service._authenticate_with_external_token("external-token", db)

    assert resolved is user
    assert reconcile.await_count == 2
    db.rollback.assert_awaited_once()


@pytest.mark.anyio
async def test_a_concurrent_assignment_race_is_replayed_not_rejected(
    auth_service: AuthService,
    auth_settings: AuthSettings,
):
    """Two logins racing to create one effective assignment converge on replay."""
    from sqlalchemy.exc import IntegrityError

    auth_settings.EXTERNAL_AUTH_ENABLED = True
    identity = _external_identity({"groups": ["engineering"]})
    race = IntegrityError("INSERT INTO authz_role_assignment ...", {}, Exception("UNIQUE constraint failed"))
    reconcile = AsyncMock(side_effect=[race, None])
    user = _dummy_user(uuid4())
    db = AsyncMock()

    with (
        patch("langflow.services.auth.service.resolve_external_identity", AsyncMock(return_value=identity)),
        patch.object(auth_service, "_materialize_external_user", AsyncMock(return_value=user)),
        patch.object(auth_service, "_reconcile_verified_external_groups", reconcile),
    ):
        resolved = await auth_service._authenticate_with_external_token("external-token", db)

    assert resolved is user
    assert reconcile.await_count == 2


def test_only_rolled_back_backend_failures_count_as_retryable():
    """A constraint violation is a real verdict; a deadlock victim is not."""
    from langflow.services.auth.service import _is_retryable_backend_failure
    from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError

    class _OrigError(Exception):
        def __init__(self, sqlstate: str) -> None:
            super().__init__(sqlstate)
            self.sqlstate = sqlstate

    assert _is_retryable_backend_failure(DBAPIError("stmt", {}, _OrigError("40P01"))) is True
    assert _is_retryable_backend_failure(DBAPIError("stmt", {}, _OrigError("40001"))) is True
    assert _is_retryable_backend_failure(OperationalError("stmt", {}, _OrigError("57P01"))) is True
    assert _is_retryable_backend_failure(IntegrityError("stmt", {}, _OrigError("23505"))) is False
    assert _is_retryable_backend_failure(ValueError("unrelated")) is False

    # A transient failure re-raised behind an application error still counts.
    wrapped = RuntimeError("reconciliation failed")
    wrapped.__cause__ = DBAPIError("stmt", {}, _OrigError("40P01"))
    assert _is_retryable_backend_failure(wrapped) is True


def test_credential_errors_keep_their_existing_status_codes():
    from fastapi import status
    from langflow.services.auth.exceptions import InvalidCredentialsError
    from langflow.services.auth.utils import _auth_error_to_http

    assert _auth_error_to_http(InvalidCredentialsError()).status_code == status.HTTP_403_FORBIDDEN
    assert _auth_error_to_http(InvalidTokenError("nope")).status_code == status.HTTP_401_UNAUTHORIZED


# =============================================================================
# External fallback (F2/F14): a valid external credential is tried when native fails
# =============================================================================


@pytest.mark.parametrize("native_token", [None, "native-token"], ids=["external-only", "distinct-fallback"])
@pytest.mark.anyio
async def test_external_group_policy_rejection_preserves_public_auth_error_across_credential_paths(
    auth_service: AuthService,
    native_token: str | None,
):
    """Typed plugin rejection remains an actionable auth error on every external path."""
    group_error = InvalidTokenError("Group claim required")
    native_error = InvalidTokenError("Native token rejected")
    external_credential = "external-token"
    db = AsyncMock()

    with (
        patch.object(auth_service, "_authenticate_with_token", side_effect=native_error) as authenticate_native,
        patch.object(
            auth_service,
            "_authenticate_with_external_token",
            side_effect=group_error,
        ) as authenticate_external,
        pytest.raises(InvalidTokenError, match="Group claim required") as exc_info,
    ):
        await auth_service.authenticate_with_credentials(
            token=native_token,
            api_key=None,
            db=db,
            external_token=external_credential,
        )

    assert exc_info.value is group_error
    if native_token is None:
        authenticate_native.assert_not_awaited()
    else:
        authenticate_native.assert_awaited_once_with(native_token, db)
    authenticate_external.assert_awaited_once_with(external_credential, db)


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
    # This fixture represents state that predates the request. Persist it so the
    # credential-boundary rollback below cannot correctly discard the setup.
    await async_session.commit()

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


@pytest.mark.parametrize(
    ("entrypoint", "failure_type"),
    [
        ("credentials", RuntimeError),
        ("credentials", InvalidTokenError),
        ("access-token", InvalidTokenError),
    ],
    ids=["credentials-unexpected-error", "credentials-policy-rejection", "access-token-policy-rejection"],
)
@pytest.mark.anyio
async def test_distinct_external_fallback_rolls_back_and_replaces_failed_native_state(
    auth_service: AuthService,
    auth_settings: AuthSettings,
    async_session,
    entrypoint: str,
    failure_type: type[Exception],
):
    """A successful distinct external fallback starts after a clean native-auth boundary."""
    from langflow.services.auth.external import (
        ExternalAccessContext,
        get_current_external_access_context,
        identity_from_claims,
        set_current_external_access_context,
    )
    from sqlmodel import select

    auth_settings.EXTERNAL_AUTH_ENABLED = True
    auth_settings.EXTERNAL_AUTH_TRUSTED_JWT_DECODE = True
    auth_settings.EXTERNAL_AUTH_PROVIDER = "external"
    auth_settings.EXTERNAL_AUTH_ACCESS_CEILING_ENABLED = True
    auth_settings.EXTERNAL_AUTH_ACCESS_CLAIM = "access"

    external_claims = {
        "sub": "external-boundary-subject",
        "preferred_username": "external-boundary-user",
        "access": "editor",
    }
    identity = identity_from_claims(external_claims, auth_settings)
    external_user = await auth_service._materialize_external_user(identity, async_session)
    await async_session.commit()

    failed_native_user = _dummy_user(uuid4())
    failed_native_user.username = "failed-native-boundary-user"

    async def stage_native_state_then_fail(_token: str, db) -> None:
        db.add(failed_native_user)
        await db.flush()
        set_current_auth_context(AuthCredentialContext(method=AUTH_METHOD_JWT))
        set_current_external_access_context(
            ExternalAccessContext(provider="stale-native", subject="stale-subject", level="viewer")
        )
        msg = "native authentication failed after staging state"
        raise failure_type(msg)

    real_external_auth = auth_service._authenticate_with_external_token

    async def authenticate_external_from_clean_boundary(token: str, db):
        assert get_current_auth_context() is None
        assert get_current_external_access_context() is None
        return await real_external_auth(token, db)

    external_token = _external_jwt(auth_service, external_claims)

    try:
        with (
            patch.object(auth_service, "_authenticate_with_token", new=stage_native_state_then_fail),
            patch.object(
                auth_service,
                "_authenticate_with_external_token",
                new=authenticate_external_from_clean_boundary,
            ),
        ):
            if entrypoint == "credentials":
                result = await auth_service.authenticate_with_credentials(
                    token="native-token",  # noqa: S106
                    api_key=None,
                    db=async_session,
                    external_token=external_token,
                )
            else:
                result = await auth_service.get_current_user_from_access_token(
                    "native-token",
                    async_session,
                    external_token=external_token,
                )

        await async_session.commit()
        persisted_failed_native_user = (
            await async_session.exec(select(User).where(User.id == failed_native_user.id))
        ).first()
        auth_context = get_current_auth_context()
        external_context = get_current_external_access_context()

        assert result.id == external_user.id
        assert persisted_failed_native_user is None
        assert auth_context == AuthCredentialContext(method=AUTH_METHOD_EXTERNAL, external_provider="external")
        assert external_context is not None
        assert external_context.provider == "external"
        assert external_context.subject == "external-boundary-subject"
        assert external_context.level == "editor"
    finally:
        clear_current_auth_context()
        set_current_external_access_context(None)


def _foreign_external_jwt(claims: dict) -> str:
    """Encode an IdP-style JWT the native decoder cannot verify.

    Signed with a key that is not the service secret so native JWT decoding
    fails and ``_authenticate_with_token`` falls through to the external
    resolver, while the trusted external decode path
    (EXTERNAL_AUTH_TRUSTED_JWT_DECODE) accepts it without signature checks.
    """
    payload = {"exp": datetime.now(timezone.utc) + timedelta(minutes=5), **claims}
    return jwt.encode(payload, "not-the-service-secret-at-least-32-bytes", algorithm="HS256")


@pytest.mark.parametrize("entrypoint", ["credentials", "access-token"])
@pytest.mark.anyio
async def test_single_credential_policy_rejection_exits_with_clean_session_and_context(
    auth_service: AuthService,
    auth_settings: AuthSettings,
    async_session,
    entrypoint: str,
):
    """A policy-rejected identity must not survive an exceptional auth exit (LE-2109).

    With ``token == external_token`` the distinct-credential fallback never
    runs, so the exceptional exit itself must roll back the staged JIT rows and
    clear the identity contexts: callers that swallow auth errors
    (``get_optional_user``) let the request complete, and the request-scoped
    session auto-commits at teardown.
    """
    from langflow.services.auth.external import get_current_external_access_context
    from langflow.services.database.models.auth import SSOUserProfile
    from lfx.services.authorization import AuthorizationMutationRejected
    from sqlmodel import select

    auth_settings.EXTERNAL_AUTH_ENABLED = True
    auth_settings.EXTERNAL_AUTH_TRUSTED_JWT_DECODE = True
    auth_settings.EXTERNAL_AUTH_PROVIDER = "external"

    token = _foreign_external_jwt(
        {"sub": "rejected-subject", "preferred_username": "rejected-user", "groups": ["blocked-group"]}
    )
    authz = _DirectoryAuthorizationStub(result=None)
    authz.ingest_directory_membership_snapshot = AsyncMock(
        side_effect=AuthorizationMutationRejected("Group membership rejected")
    )

    with (
        patch("langflow.services.deps.get_authorization_service", return_value=authz),
        patch.object(auth_service, "_initialize_jit_user_defaults", new=AsyncMock()),
    ):
        if entrypoint == "credentials":
            attempt = auth_service.authenticate_with_credentials(
                token=token,
                api_key=None,
                db=async_session,
                external_token=token,
            )
        else:
            attempt = auth_service.get_current_user_from_access_token(token, async_session, external_token=token)
        with pytest.raises(InvalidTokenError, match="Group membership rejected"):
            await attempt

    # What the request-scoped session_scope teardown does when a caller
    # swallowed the auth error and the request completed cleanly.
    await async_session.commit()

    persisted_profile = (
        await async_session.exec(select(SSOUserProfile).where(SSOUserProfile.sso_user_id == "rejected-subject"))
    ).first()
    assert persisted_profile is None
    assert get_current_auth_context() is None
    assert get_current_external_access_context() is None


@pytest.mark.anyio
async def test_get_optional_user_swallowed_policy_rejection_stages_nothing_for_commit(
    auth_service: AuthService,
    auth_settings: AuthSettings,
    async_session,
):
    """A swallowed policy rejection must leave nothing for the teardown auto-commit."""
    from langflow.services.auth.external import get_current_external_access_context
    from langflow.services.auth.utils import get_optional_user
    from langflow.services.database.models.auth import SSOUserProfile
    from lfx.services.authorization import AuthorizationMutationRejected
    from sqlmodel import select

    auth_settings.EXTERNAL_AUTH_ENABLED = True
    auth_settings.EXTERNAL_AUTH_TRUSTED_JWT_DECODE = True
    auth_settings.EXTERNAL_AUTH_PROVIDER = "external"

    token = _foreign_external_jwt(
        {"sub": "optional-rejected-subject", "preferred_username": "optional-rejected-user", "groups": ["g"]}
    )
    authz = _DirectoryAuthorizationStub(result=None)
    authz.ingest_directory_membership_snapshot = AsyncMock(
        side_effect=AuthorizationMutationRejected("Group membership rejected")
    )

    with (
        patch("langflow.services.deps.get_authorization_service", return_value=authz),
        patch.object(auth_service, "_initialize_jit_user_defaults", new=AsyncMock()),
        patch("langflow.services.auth.utils._auth_service", return_value=auth_service),
    ):
        user = await get_optional_user(token, None, None, db=async_session)

    assert user is None
    # The request completed cleanly as anonymous, so the request-scoped
    # session_scope teardown auto-commits.
    await async_session.commit()

    persisted_profile = (
        await async_session.exec(
            select(SSOUserProfile).where(SSOUserProfile.sso_user_id == "optional-rejected-subject")
        )
    ).first()
    assert persisted_profile is None
    assert get_current_auth_context() is None
    assert get_current_external_access_context() is None


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
    # Model preexisting state; the fallback rollback must not erase this setup.
    await async_session.commit()

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


# =============================================================================
# get_current_user_mcp Tests — AUTO_LOGIN parity with the non-MCP entrypoints
# =============================================================================


@pytest.mark.anyio
async def test_get_current_user_mcp_auto_login_alone_still_rejects(
    auth_service: AuthService,
    auth_settings: AuthSettings,
):
    """MCP credential resolution must honour skip_auth_auto_login like every other entrypoint.

    With the default configuration (AUTO_LOGIN on, skip_auth_auto_login off) a caller
    that presents no token and no API key must be rejected. Without this guard the MCP
    transport endpoints resolve an anonymous request to the configured superuser while
    every other authenticated route returns 403.
    """
    auth_settings.AUTO_LOGIN = True
    auth_settings.skip_auth_auto_login = False
    auth_settings.SUPERUSER = "admin"
    superuser = _dummy_user(uuid4())

    with (
        patch(
            "langflow.services.auth.service.get_user_by_username",
            new=AsyncMock(return_value=superuser),
        ) as mock_lookup,
        pytest.raises(HTTPException) as exc,
    ):
        await auth_service.get_current_user_mcp(
            token=None,
            query_param=None,
            header_param=None,
            db=AsyncMock(),
        )

    assert exc.value.status_code == status.HTTP_403_FORBIDDEN
    assert exc.value.detail == AUTO_LOGIN_ERROR
    mock_lookup.assert_not_awaited()


@pytest.mark.anyio
async def test_get_current_user_mcp_auto_login_skip_returns_superuser(
    auth_service: AuthService,
    auth_settings: AuthSettings,
):
    """AUTO_LOGIN + skip_auth_auto_login keeps the documented single-user MCP fallback."""
    auth_settings.AUTO_LOGIN = True
    auth_settings.skip_auth_auto_login = True
    auth_settings.SUPERUSER = "admin"
    superuser = _dummy_user(uuid4())

    try:
        with (
            patch(
                "langflow.services.auth.service.get_user_by_username",
                new=AsyncMock(return_value=superuser),
            ) as mock_lookup,
            patch("langflow.services.auth.service.logger") as mock_logger,
        ):
            result = await auth_service.get_current_user_mcp(
                token=None,
                query_param=None,
                header_param=None,
                db=AsyncMock(),
            )

        assert result is superuser
        mock_lookup.assert_awaited_once()
        mock_logger.warning.assert_called_once_with(AUTO_LOGIN_WARNING)
        assert get_current_auth_context().method == AUTH_METHOD_AUTO_LOGIN
    finally:
        clear_current_auth_context()


@pytest.mark.anyio
async def test_get_current_user_mcp_auto_login_skip_missing_superuser_rejects(
    auth_service: AuthService,
    auth_settings: AuthSettings,
):
    """AUTO_LOGIN + skip_auth_auto_login with no superuser row must not fall through to allow."""
    auth_settings.AUTO_LOGIN = True
    auth_settings.skip_auth_auto_login = True
    auth_settings.SUPERUSER = "admin"

    with (
        patch(
            "langflow.services.auth.service.get_user_by_username",
            new=AsyncMock(return_value=None),
        ),
        pytest.raises(HTTPException) as exc,
    ):
        await auth_service.get_current_user_mcp(
            token=None,
            query_param=None,
            header_param=None,
            db=AsyncMock(),
        )

    assert exc.value.status_code == status.HTTP_403_FORBIDDEN
