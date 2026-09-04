"""Tests for API key CRUD operations with hash-based lookup."""

from __future__ import annotations

import hashlib
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import anyio
import pytest
from langflow.services.database.models.api_key.crud import (
    _authenticate_api_key_in_owned_scope,
    _authenticate_api_key_with_session,
    _check_key_from_db,
    _check_key_from_db_with_context,
    create_api_key,
    hash_api_key,
)
from langflow.services.database.models.api_key.model import ApiKey, ApiKeyCreate
from langflow.services.database.models.user.model import User, UserRead
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

_TEST_PASSWORD = "hashed"  # noqa: S105  # pragma: allowlist secret


def _make_user(**kwargs):
    defaults = {
        "id": uuid4(),
        "username": "testuser",
        "password": _TEST_PASSWORD,
        "is_active": True,
        "is_superuser": False,
    }
    defaults.update(kwargs)
    return User(**defaults)


def test_hash_api_key_is_sha256():
    """hash_api_key must return a hex SHA-256 digest."""
    key = "sk-test-key-12345"
    expected = hashlib.sha256(key.encode()).hexdigest()
    assert hash_api_key(key) == expected
    assert len(hash_api_key(key)) == 64


def test_hash_api_key_deterministic():
    """Same input must always produce the same hash."""
    assert hash_api_key("sk-abc") == hash_api_key("sk-abc")


def test_hash_api_key_different_inputs():
    """Different inputs must produce different hashes."""
    assert hash_api_key("sk-abc") != hash_api_key("sk-def")


@pytest.fixture
def mock_settings(monkeypatch):
    """Mock settings service for API key operations."""
    settings = SimpleNamespace(
        auth_settings=SimpleNamespace(
            SECRET_KEY=SimpleNamespace(get_secret_value=lambda: "a" * 43),
            API_KEY_SOURCE="db",  # pragma: allowlist secret
            # Non-optional AuthSettings fields read directly by create_api_key
            # and the external-access-ceiling chokepoint.
            EXTERNAL_AUTH_ACCESS_CEILING_ENABLED=False,
            EXTERNAL_AUTH_DISABLE_API_KEYS_FOR_EXTERNAL_USERS=True,
            EXTERNAL_AUTH_PROVIDER="external",
        ),
        settings=SimpleNamespace(disable_track_apikey_usage=False),
    )
    monkeypatch.setattr(
        "langflow.services.database.models.api_key.crud.get_settings_service",
        lambda: settings,
    )
    return settings


@pytest.mark.anyio
async def test_create_api_key_stores_hash(async_session, mock_settings, monkeypatch):  # noqa: ARG001
    """create_api_key must store both encrypted key and hash."""
    user = _make_user()
    async_session.add(user)
    await async_session.commit()

    monkeypatch.setattr(
        "langflow.services.database.models.api_key.crud.auth_utils.encrypt_api_key",
        lambda key, **_kwargs: f"encrypted-{key}",
    )

    result = await create_api_key(async_session, ApiKeyCreate(name="test"), user.id)
    assert result.api_key.startswith("sk-")

    from sqlmodel import select

    row = (await async_session.exec(select(ApiKey).where(ApiKey.user_id == user.id))).first()
    assert row is not None
    assert row.api_key_hash == hash_api_key(result.api_key)
    assert row.api_key.startswith("encrypted-sk-")


@pytest.mark.anyio
async def test_check_key_finds_by_hash(async_session, mock_settings):
    """check_key must find keys via hash without decrypting."""
    user = _make_user()
    async_session.add(user)
    await async_session.flush()

    plaintext = "sk-test-12345"  # pragma: allowlist secret
    api_key = ApiKey(
        api_key="encrypted-value",  # pragma: allowlist secret
        api_key_hash=hash_api_key(plaintext),
        name="test",
        user_id=user.id,
        created_at=datetime.now(timezone.utc),
    )
    async_session.add(api_key)
    await async_session.commit()

    result = await _check_key_from_db(async_session, plaintext, mock_settings)
    assert result is not None
    assert result.id == user.id


@pytest.mark.anyio
async def test_authenticate_api_key_returns_db_key_metadata(async_session, mock_settings):
    """The richer resolver preserves the DB API-key id for authorization context."""
    user = _make_user()
    async_session.add(user)
    await async_session.flush()

    plaintext = "sk-test-12345"  # pragma: allowlist secret
    api_key = ApiKey(
        api_key="encrypted-value",  # pragma: allowlist secret
        api_key_hash=hash_api_key(plaintext),
        name="test",
        user_id=user.id,
        created_at=datetime.now(timezone.utc),
    )
    async_session.add(api_key)
    await async_session.commit()

    result = await _authenticate_api_key_with_session(async_session, plaintext, mock_settings)

    assert result is not None
    assert result.user.id == user.id
    assert result.api_key_source == "db"  # pragma: allowlist secret
    assert result.api_key_id == api_key.id


@pytest.mark.anyio
async def test_check_key_fallback_for_legacy_keys(async_session, mock_settings, monkeypatch):
    """Legacy keys without hash must still match via decrypt-and-compare."""
    user = _make_user()
    async_session.add(user)
    await async_session.flush()

    plaintext = "sk-legacy-key"
    api_key = ApiKey(
        api_key=plaintext,
        api_key_hash=None,
        name="legacy",
        user_id=user.id,
        created_at=datetime.now(timezone.utc),
    )
    async_session.add(api_key)
    await async_session.flush()

    monkeypatch.setattr(
        "langflow.services.database.models.api_key.crud.auth_utils.decrypt_api_key",
        lambda val, **_kwargs: val,
    )
    compare_digest = MagicMock(wraps=secrets.compare_digest)
    monkeypatch.setattr(
        "langflow.services.database.models.api_key.crud.secrets.compare_digest",
        compare_digest,
    )

    result = await _check_key_from_db(async_session, plaintext, mock_settings)
    assert result is not None
    assert result.id == user.id
    compare_digest.assert_called_once_with(plaintext.encode(), plaintext.encode())


@pytest.mark.anyio
async def test_check_key_fallback_backfills_hash(async_session, mock_settings, monkeypatch):
    """When a legacy key matches, its hash must be backfilled for future lookups."""
    user = _make_user()
    async_session.add(user)
    await async_session.flush()

    plaintext = "sk-legacy-key"
    api_key = ApiKey(
        api_key=plaintext,
        api_key_hash=None,
        name="legacy",
        user_id=user.id,
        created_at=datetime.now(timezone.utc),
    )
    async_session.add(api_key)
    await async_session.flush()

    monkeypatch.setattr(
        "langflow.services.database.models.api_key.crud.auth_utils.decrypt_api_key",
        lambda val, **_kwargs: val,
    )

    await _check_key_from_db(async_session, plaintext, mock_settings)

    await async_session.refresh(api_key)
    assert api_key.api_key_hash == hash_api_key(plaintext)


@pytest.mark.anyio
async def test_check_key_no_match_returns_none(async_session, mock_settings, monkeypatch):
    """Non-existent key must return None."""
    monkeypatch.setattr(
        "langflow.services.database.models.api_key.crud.auth_utils.decrypt_api_key",
        lambda val, **_kwargs: val,
    )

    result = await _check_key_from_db(async_session, "sk-nonexistent", mock_settings)
    assert result is None


@pytest.mark.anyio
async def test_check_key_skips_orphaned_encrypted_keys(async_session, mock_settings, monkeypatch):
    """Orphaned encrypted keys (wrong secret) must not block valid key lookup."""
    user = _make_user()
    async_session.add(user)
    await async_session.flush()

    orphaned = ApiKey(
        api_key="gAAAAABorphaned",  # pragma: allowlist secret
        api_key_hash=None,
        name="orphaned",
        user_id=user.id,
        created_at=datetime.now(timezone.utc),
    )
    plaintext = "sk-valid-key"  # pragma: allowlist secret
    valid = ApiKey(
        api_key="encrypted-valid",  # pragma: allowlist secret
        api_key_hash=hash_api_key(plaintext),
        name="valid",
        user_id=user.id,
        created_at=datetime.now(timezone.utc),
    )
    async_session.add_all([orphaned, valid])
    await async_session.flush()

    monkeypatch.setattr(
        "langflow.services.database.models.api_key.crud.auth_utils.decrypt_api_key",
        lambda val, **_kwargs: "" if val.startswith("gAAAAA") else val,
    )

    result = await _check_key_from_db(async_session, plaintext, mock_settings)
    assert result is not None
    assert result.id == user.id


@pytest.mark.anyio
async def test_check_key_duplicate_hash_fails_closed(async_session, mock_settings):
    """Duplicate hashes must fail closed rather than authenticating an arbitrary user."""
    user1 = _make_user(username="user1")
    user2 = _make_user(username="user2")
    async_session.add_all([user1, user2])
    await async_session.flush()

    # Two keys with the same hash (simulates data corruption)
    shared_hash = hash_api_key("sk-shared")  # pragma: allowlist secret
    key1 = ApiKey(
        api_key="encrypted-1",  # pragma: allowlist secret
        api_key_hash=shared_hash,
        name="key1",
        user_id=user1.id,
        created_at=datetime.now(timezone.utc),
    )
    key2 = ApiKey(
        api_key="encrypted-2",  # pragma: allowlist secret
        api_key_hash=shared_hash,
        name="key2",
        user_id=user2.id,
        created_at=datetime.now(timezone.utc),
    )
    async_session.add_all([key1, key2])
    await async_session.flush()

    result = await _check_key_from_db(async_session, "sk-shared", mock_settings)
    assert result is None


@pytest.mark.anyio
async def test_inactive_key_is_rejected(async_session, mock_settings):
    """Keys with is_active=False must not authenticate."""
    user = _make_user()
    async_session.add(user)
    await async_session.flush()

    plaintext = "sk-inactive-key"  # pragma: allowlist secret
    api_key = ApiKey(
        api_key="encrypted-inactive",  # pragma: allowlist secret
        api_key_hash=hash_api_key(plaintext),
        name="inactive",
        user_id=user.id,
        is_active=False,
        created_at=datetime.now(timezone.utc),
    )
    async_session.add(api_key)
    await async_session.flush()

    result = await _check_key_from_db(async_session, plaintext, mock_settings)
    assert result is None


@pytest.mark.anyio
async def test_expired_key_is_rejected(async_session, mock_settings):
    """Keys with expires_at in the past must not authenticate."""
    from datetime import timedelta

    user = _make_user()
    async_session.add(user)
    await async_session.flush()

    plaintext = "sk-expired-key"  # pragma: allowlist secret
    api_key = ApiKey(
        api_key="encrypted-expired",  # pragma: allowlist secret
        api_key_hash=hash_api_key(plaintext),
        name="expired",
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        created_at=datetime.now(timezone.utc),
    )
    async_session.add(api_key)
    await async_session.flush()

    result = await _check_key_from_db(async_session, plaintext, mock_settings)
    assert result is None


@pytest.mark.anyio
async def test_valid_key_expiry_passes(async_session, mock_settings):
    """Keys with expires_at in the future must still authenticate."""
    from datetime import timedelta

    user = _make_user()
    async_session.add(user)
    await async_session.flush()

    plaintext = "sk-future-expiry"  # pragma: allowlist secret
    api_key = ApiKey(
        api_key="encrypted-future",  # pragma: allowlist secret
        api_key_hash=hash_api_key(plaintext),
        name="future-expiry",
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        created_at=datetime.now(timezone.utc),
    )
    async_session.add(api_key)
    await async_session.flush()

    result = await _check_key_from_db(async_session, plaintext, mock_settings)
    assert result is not None
    assert result.id == user.id


@pytest.mark.anyio
async def test_no_expiry_key_passes(async_session, mock_settings):
    """Keys with expires_at=None (no expiry) must authenticate indefinitely."""
    user = _make_user()
    async_session.add(user)
    await async_session.flush()

    plaintext = "sk-no-expiry"  # pragma: allowlist secret
    api_key = ApiKey(
        api_key="encrypted-no-expiry",  # pragma: allowlist secret
        api_key_hash=hash_api_key(plaintext),
        name="no-expiry",
        user_id=user.id,
        expires_at=None,
        created_at=datetime.now(timezone.utc),
    )
    async_session.add(api_key)
    await async_session.flush()

    result = await _check_key_from_db(async_session, plaintext, mock_settings)
    assert result is not None
    assert result.id == user.id


@pytest.mark.anyio
async def test_create_api_key_stores_expires_at(async_session, mock_settings, monkeypatch):  # noqa: ARG001
    """create_api_key must persist expires_at when provided."""
    from datetime import timedelta

    from sqlmodel import select

    user = _make_user()
    async_session.add(user)
    await async_session.commit()

    monkeypatch.setattr(
        "langflow.services.database.models.api_key.crud.auth_utils.encrypt_api_key",
        lambda key, **_kwargs: f"encrypted-{key}",
    )

    expiry = datetime.now(timezone.utc) + timedelta(days=30)
    result = await create_api_key(async_session, ApiKeyCreate(name="test", expires_at=expiry), user.id)

    row = (await async_session.exec(select(ApiKey).where(ApiKey.user_id == user.id))).first()
    assert row is not None
    assert row.expires_at is not None
    assert abs((row.expires_at.replace(tzinfo=timezone.utc) - expiry).total_seconds()) < 2
    assert result.expires_at is not None


@pytest.mark.anyio
async def test_create_api_key_no_expires_at_is_none(async_session, mock_settings, monkeypatch):  # noqa: ARG001
    """create_api_key must store expires_at=None when not provided."""
    from sqlmodel import select

    user = _make_user()
    async_session.add(user)
    await async_session.commit()

    monkeypatch.setattr(
        "langflow.services.database.models.api_key.crud.auth_utils.encrypt_api_key",
        lambda key, **_kwargs: f"encrypted-{key}",
    )

    result = await create_api_key(async_session, ApiKeyCreate(name="no-expiry"), user.id)

    row = (await async_session.exec(select(ApiKey).where(ApiKey.user_id == user.id))).first()
    assert row is not None
    assert row.expires_at is None
    assert result.expires_at is None


# =============================================================================
# External access ceiling chokepoint (H1): API keys disabled for external users
# =============================================================================


async def _seed_external_user_with_key(async_session, *, provider: str = "external"):
    """Create a user with an external SSO profile and an active API key."""
    from langflow.services.database.models.auth import SSOUserProfile

    user = _make_user(username=f"ext-{uuid4().hex[:8]}")
    async_session.add(user)
    await async_session.flush()

    async_session.add(
        SSOUserProfile(
            user_id=user.id,
            sso_provider=provider,
            sso_user_id=f"subject-{uuid4().hex[:8]}",
        )
    )
    plaintext = f"sk-ext-{uuid4().hex}"  # pragma: allowlist secret
    async_session.add(
        ApiKey(
            api_key="encrypted-ext",  # pragma: allowlist secret
            api_key_hash=hash_api_key(plaintext),
            name="ext-key",
            user_id=user.id,
            created_at=datetime.now(timezone.utc),
        )
    )
    await async_session.commit()
    return user, plaintext


@pytest.mark.anyio
async def test_authenticate_api_key_rejects_external_user_when_ceiling_enabled(async_session, mock_settings):
    """When ceiling + disable-keys are ON, an external user's API key fails at auth time."""
    mock_settings.auth_settings.EXTERNAL_AUTH_ACCESS_CEILING_ENABLED = True
    mock_settings.auth_settings.EXTERNAL_AUTH_DISABLE_API_KEYS_FOR_EXTERNAL_USERS = True

    _user, plaintext = await _seed_external_user_with_key(async_session)

    # authenticate_api_key is the shared chokepoint used by every API-key caller.
    assert await _authenticate_api_key_with_session(async_session, plaintext, mock_settings) is None


@pytest.mark.anyio
async def test_authenticate_api_key_allows_external_user_when_ceiling_disabled(async_session, mock_settings):
    """When the ceiling is OFF, the external user's API key still authenticates (no behavior change)."""
    mock_settings.auth_settings.EXTERNAL_AUTH_ACCESS_CEILING_ENABLED = False
    mock_settings.auth_settings.EXTERNAL_AUTH_DISABLE_API_KEYS_FOR_EXTERNAL_USERS = True

    user, plaintext = await _seed_external_user_with_key(async_session)

    result = await _authenticate_api_key_with_session(async_session, plaintext, mock_settings)
    assert result is not None
    assert result.user.id == user.id


@pytest.mark.anyio
async def test_authenticate_api_key_allows_external_user_when_disable_keys_disabled(async_session, mock_settings):
    """Ceiling ON but disable-keys OFF must not block the external user (feature is opt-in)."""
    mock_settings.auth_settings.EXTERNAL_AUTH_ACCESS_CEILING_ENABLED = True
    mock_settings.auth_settings.EXTERNAL_AUTH_DISABLE_API_KEYS_FOR_EXTERNAL_USERS = False

    user, plaintext = await _seed_external_user_with_key(async_session)

    result = await _authenticate_api_key_with_session(async_session, plaintext, mock_settings)
    assert result is not None
    assert result.user.id == user.id


@pytest.mark.anyio
async def test_authenticate_api_key_allows_non_external_user_when_ceiling_enabled(async_session, mock_settings):
    """A user with no external SSO profile is unaffected even with the ceiling fully enabled."""
    mock_settings.auth_settings.EXTERNAL_AUTH_ACCESS_CEILING_ENABLED = True
    mock_settings.auth_settings.EXTERNAL_AUTH_DISABLE_API_KEYS_FOR_EXTERNAL_USERS = True

    user = _make_user()
    async_session.add(user)
    await async_session.flush()
    plaintext = "sk-native-key"  # pragma: allowlist secret
    async_session.add(
        ApiKey(
            api_key="encrypted-native",  # pragma: allowlist secret
            api_key_hash=hash_api_key(plaintext),
            name="native-key",
            user_id=user.id,
            created_at=datetime.now(timezone.utc),
        )
    )
    await async_session.commit()

    result = await _authenticate_api_key_with_session(async_session, plaintext, mock_settings)
    assert result is not None
    assert result.user.id == user.id


@pytest.mark.anyio
async def test_authenticate_api_key_ignores_profile_for_other_provider(async_session, mock_settings):
    """A profile under a different provider key must not trip the configured-provider block."""
    mock_settings.auth_settings.EXTERNAL_AUTH_ACCESS_CEILING_ENABLED = True
    mock_settings.auth_settings.EXTERNAL_AUTH_DISABLE_API_KEYS_FOR_EXTERNAL_USERS = True
    mock_settings.auth_settings.EXTERNAL_AUTH_PROVIDER = "external"

    # Profile is stored under "some-other-provider", not the configured "external".
    user, plaintext = await _seed_external_user_with_key(async_session, provider="some-other-provider")

    result = await _authenticate_api_key_with_session(async_session, plaintext, mock_settings)
    assert result is not None
    assert result.user.id == user.id


# =============================================================================
# LOW: a DENIED API-key auth must not mutate usage counters (total_uses/last_used_at)
# =============================================================================


@pytest.mark.anyio
async def test_blocked_external_user_key_does_not_increment_usage(async_session, mock_settings):
    """A ceiling-blocked external user's key must NOT bump total_uses / last_used_at (fast hash path)."""
    from sqlmodel import select

    mock_settings.auth_settings.EXTERNAL_AUTH_ACCESS_CEILING_ENABLED = True
    mock_settings.auth_settings.EXTERNAL_AUTH_DISABLE_API_KEYS_FOR_EXTERNAL_USERS = True

    _user, plaintext = await _seed_external_user_with_key(async_session)

    # Denied auth.
    assert await _authenticate_api_key_with_session(async_session, plaintext, mock_settings) is None

    row = (await async_session.exec(select(ApiKey).where(ApiKey.api_key_hash == hash_api_key(plaintext)))).first()
    assert row is not None
    assert row.total_uses == 0
    assert row.last_used_at is None


@pytest.mark.anyio
async def test_blocked_external_user_legacy_key_does_not_increment_usage(async_session, mock_settings, monkeypatch):
    """A ceiling-blocked external user's legacy (hashless) key must NOT bump usage / backfill hash."""
    from langflow.services.database.models.auth import SSOUserProfile
    from sqlmodel import select

    mock_settings.auth_settings.EXTERNAL_AUTH_ACCESS_CEILING_ENABLED = True
    mock_settings.auth_settings.EXTERNAL_AUTH_DISABLE_API_KEYS_FOR_EXTERNAL_USERS = True

    user = _make_user(username=f"ext-{uuid4().hex[:8]}")
    async_session.add(user)
    await async_session.flush()
    async_session.add(
        SSOUserProfile(
            user_id=user.id,
            sso_provider="external",
            sso_user_id=f"subject-{uuid4().hex[:8]}",
        )
    )

    plaintext = "sk-legacy-blocked"  # pragma: allowlist secret
    legacy = ApiKey(
        api_key=plaintext,
        api_key_hash=None,
        name="legacy-blocked",
        user_id=user.id,
        created_at=datetime.now(timezone.utc),
    )
    async_session.add(legacy)
    await async_session.commit()

    monkeypatch.setattr(
        "langflow.services.database.models.api_key.crud.auth_utils.decrypt_api_key",
        lambda val, **_kwargs: val,
    )

    assert await _authenticate_api_key_with_session(async_session, plaintext, mock_settings) is None

    row = (await async_session.exec(select(ApiKey).where(ApiKey.id == legacy.id))).first()
    assert row is not None
    assert row.total_uses == 0
    assert row.last_used_at is None
    # The hash backfill is a success-path side effect and must not run on a denial.
    assert row.api_key_hash is None


@pytest.mark.anyio
async def test_allowed_user_key_still_increments_usage(async_session, mock_settings):
    """Sanity: a non-blocked user's key still records usage (success-path unchanged)."""
    from sqlmodel import select

    user = _make_user()
    async_session.add(user)
    await async_session.flush()
    plaintext = "sk-usage-tracked"  # pragma: allowlist secret
    async_session.add(
        ApiKey(
            api_key="encrypted-tracked",  # pragma: allowlist secret
            api_key_hash=hash_api_key(plaintext),
            name="tracked",
            user_id=user.id,
            created_at=datetime.now(timezone.utc),
        )
    )
    await async_session.commit()

    result = await _authenticate_api_key_with_session(async_session, plaintext, mock_settings)
    assert result is not None

    async_session.expire_all()
    row = (await async_session.exec(select(ApiKey).where(ApiKey.api_key_hash == hash_api_key(plaintext)))).first()
    assert row is not None
    assert row.total_uses == 1
    assert row.last_used_at is not None


@pytest.mark.parametrize("hashed", [True, False])
@pytest.mark.anyio
async def test_inactive_user_key_does_not_mutate_bookkeeping(async_session, mock_settings, *, hashed):
    """Inactive users are rejected before usage tracking or legacy hash backfill."""
    user = _make_user(is_active=False)
    async_session.add(user)
    await async_session.flush()

    plaintext = f"sk-inactive-{'hashed' if hashed else 'legacy'}"  # pragma: allowlist secret
    api_key = ApiKey(
        api_key=plaintext,
        api_key_hash=hash_api_key(plaintext) if hashed else None,
        name="inactive-user-key",
        user_id=user.id,
        created_at=datetime.now(timezone.utc),
    )
    async_session.add(api_key)
    await async_session.commit()

    result = await _authenticate_api_key_with_session(async_session, plaintext, mock_settings)
    assert result is None

    await async_session.refresh(api_key)
    assert api_key.api_key_hash == (hash_api_key(plaintext) if hashed else None)
    assert api_key.total_uses == 0
    assert api_key.last_used_at is None


# =============================================================================
# LE-2097: successful API-key writes must finish their transaction
# =============================================================================


async def _seed_key_for_transaction_test(async_session, *, plaintext: str, hashed: bool) -> ApiKey:
    user = _make_user(username=f"transaction-{uuid4().hex[:8]}")
    async_session.add(user)
    await async_session.flush()

    api_key = ApiKey(
        api_key=plaintext,
        api_key_hash=hash_api_key(plaintext) if hashed else None,
        name="transaction-test",
        user_id=user.id,
        created_at=datetime.now(timezone.utc),
    )
    async_session.add(api_key)
    await async_session.commit()
    return api_key


def _session_scope_factory(engine):
    @asynccontextmanager
    async def owned_scope():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    return owned_scope


@pytest.mark.parametrize(
    ("hashed", "disable_tracking", "expected_uses"),
    [(True, False, 1), (False, True, 0)],
)
@pytest.mark.anyio
async def test_api_key_bookkeeping_commits_only_its_owned_session(
    mock_settings,
    tmp_path,
    *,
    hashed,
    disable_tracking,
    expected_uses,
):
    """Owned auth writes persist without flushing or committing pending caller state."""
    mock_settings.settings.disable_track_apikey_usage = disable_tracking
    plaintext = f"sk-isolated-{'hashed' if hashed else 'legacy'}"  # pragma: allowlist secret
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'api-key-isolation.db'}")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(
                lambda sync_connection: SQLModel.metadata.create_all(
                    sync_connection,
                    tables=[User.__table__, ApiKey.__table__],
                )
            )

        async with AsyncSession(engine, expire_on_commit=False) as caller_session:
            api_key = await _seed_key_for_transaction_test(caller_session, plaintext=plaintext, hashed=hashed)
            api_key_id = api_key.id

            caller_owned_user = _make_user(username=f"caller-owned-{uuid4().hex[:8]}")
            caller_owned_user_id = caller_owned_user.id
            caller_session.add(caller_owned_user)

            result = await _authenticate_api_key_in_owned_scope(plaintext, _session_scope_factory(engine))
            assert result is not None
            assert caller_owned_user in caller_session
            assert result.user.id == api_key.user_id
            assert result.user not in caller_session
            assert UserRead.model_validate(result.user).id == api_key.user_id

            await caller_session.rollback()

        async with AsyncSession(engine, expire_on_commit=False) as verification_session:
            persisted_caller_user = await verification_session.get(User, caller_owned_user_id)
            persisted_api_key = await verification_session.get(ApiKey, api_key_id)
    finally:
        await engine.dispose()

    assert persisted_caller_user is None
    assert persisted_api_key is not None
    assert persisted_api_key.api_key_hash == hash_api_key(plaintext)
    assert persisted_api_key.total_uses == expected_uses
    assert (persisted_api_key.last_used_at is not None) is (expected_uses == 1)


@pytest.mark.anyio
async def test_owned_auth_completes_after_pre_read_releases_only_pool_connection(mock_settings, tmp_path):  # noqa: ARG001
    """Pre-read scopes release the sole connection before owned authentication."""
    plaintext = "sk-single-pool-held"  # pragma: allowlist secret
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'api-key-single-pool.db'}",
        pool_size=1,
        max_overflow=0,
        pool_timeout=0.1,
    )
    try:
        async with engine.begin() as connection:
            await connection.run_sync(
                lambda sync_connection: SQLModel.metadata.create_all(
                    sync_connection,
                    tables=[User.__table__, ApiKey.__table__],
                )
            )

        async with AsyncSession(engine, expire_on_commit=False) as seed_session:
            api_key = await _seed_key_for_transaction_test(seed_session, plaintext=plaintext, hashed=True)
            api_key_id = api_key.id
            user_id = api_key.user_id

        async with AsyncSession(engine, expire_on_commit=False) as pre_read_session, pre_read_session.begin():
            assert await pre_read_session.get(User, user_id) is not None

        with anyio.fail_after(1):
            result = await _authenticate_api_key_in_owned_scope(plaintext, _session_scope_factory(engine))
        assert result is not None
        assert result.user.id == user_id

        async with AsyncSession(engine, expire_on_commit=False) as verification_session:
            persisted_api_key = await verification_session.get(ApiKey, api_key_id)
    finally:
        await engine.dispose()

    assert persisted_api_key is not None
    assert persisted_api_key.total_uses == 1
    assert persisted_api_key.last_used_at is not None


@pytest.mark.parametrize(("hashed", "disable_tracking"), [(True, False), (False, True)])
@pytest.mark.anyio
async def test_single_connection_bookkeeping_never_commits_flushed_caller_state(
    async_session,
    mock_settings,
    *,
    hashed,
    disable_tracking,
):
    """StaticPool bookkeeping stays inside the caller-owned transaction."""
    mock_settings.settings.disable_track_apikey_usage = disable_tracking
    plaintext = f"sk-single-connection-{'hashed' if hashed else 'legacy'}"  # pragma: allowlist secret
    api_key = await _seed_key_for_transaction_test(async_session, plaintext=plaintext, hashed=hashed)
    api_key_id = api_key.id

    caller_owned_user = _make_user(username=f"flushed-caller-{uuid4().hex[:8]}")
    caller_owned_user_id = caller_owned_user.id
    async_session.add(caller_owned_user)
    await async_session.flush()

    result = await _check_key_from_db_with_context(async_session, plaintext, mock_settings)
    assert result is not None

    await async_session.rollback()
    async with AsyncSession(bind=async_session.bind, expire_on_commit=False) as verification_session:
        persisted_caller_user = await verification_session.get(User, caller_owned_user_id)
        persisted_api_key = await verification_session.get(ApiKey, api_key_id)

    assert persisted_caller_user is None
    assert persisted_api_key is not None
    assert persisted_api_key.api_key_hash == (hash_api_key(plaintext) if hashed else None)
    assert persisted_api_key.total_uses == 0
    assert persisted_api_key.last_used_at is None


@pytest.mark.anyio
async def test_connection_bound_bookkeeping_never_commits_flushed_caller_state(mock_settings, tmp_path):
    """A session bound to one connection keeps bookkeeping caller-owned."""
    plaintext = "sk-connection-bound"  # pragma: allowlist secret
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'connection-bound.db'}")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(
                lambda sync_connection: SQLModel.metadata.create_all(
                    sync_connection,
                    tables=[User.__table__, ApiKey.__table__],
                )
            )

        async with AsyncSession(engine, expire_on_commit=False) as seed_session:
            api_key = await _seed_key_for_transaction_test(seed_session, plaintext=plaintext, hashed=True)
            api_key_id = api_key.id

        async with (
            engine.connect() as connection,
            AsyncSession(bind=connection, expire_on_commit=False) as caller_session,
        ):
            caller_owned_user = _make_user(username=f"connection-caller-{uuid4().hex[:8]}")
            caller_owned_user_id = caller_owned_user.id
            caller_session.add(caller_owned_user)
            await caller_session.flush()

            result = await _check_key_from_db_with_context(caller_session, plaintext, mock_settings)
            assert result is not None

            await caller_session.rollback()

        async with AsyncSession(engine, expire_on_commit=False) as verification_session:
            persisted_caller_user = await verification_session.get(User, caller_owned_user_id)
            persisted_api_key = await verification_session.get(ApiKey, api_key_id)
    finally:
        await engine.dispose()

    assert persisted_caller_user is None
    assert persisted_api_key is not None
    assert persisted_api_key.total_uses == 0
    assert persisted_api_key.last_used_at is None
