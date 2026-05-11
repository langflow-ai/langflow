"""Tests for API key CRUD operations with hash-based lookup."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.services.database.models.api_key.crud import (
    _check_key_from_db,
    create_api_key,
    hash_api_key,
)
from langflow.services.database.models.api_key.model import ApiKey, ApiKeyCreate
from langflow.services.database.models.user.model import User

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
    await async_session.flush()

    result = await _check_key_from_db(async_session, plaintext, mock_settings)
    assert result is not None
    assert result.id == user.id


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

    result = await _check_key_from_db(async_session, plaintext, mock_settings)
    assert result is not None
    assert result.id == user.id


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
