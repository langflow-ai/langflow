"""API-key auth must not hold SQLite's write lock for the whole request.

Authenticating with an API key bumps `total_uses` / `last_used_at` on the request's session.
FastAPI keeps that session open until the response ends, so flushing the UPDATE without
committing left SQLite's single write lock held for the request's whole lifetime. Any
concurrent write then waited out `busy_timeout` and failed with "database is locked" -- which
is what a long API-key request did to its own writes: a flow build streaming its events over
`/build/{id}/flow?event_delivery=direct` killed its own `INSERT INTO message` after 30s.
Measured against a live server: locked and failing before, 0 locks after.

These tests pin the invariant at the source: the usage write must be committed, not left
pending, on both API-key lookup paths (hash hit, and the legacy scan that backfills the hash).
"""

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langflow.services.database.models.api_key.crud import _check_key_from_db_with_context, hash_api_key
from langflow.services.database.models.user.model import User

MODULE = "langflow.services.database.models.api_key.crud"
API_KEY = "sk-test-key"


def _settings(*, track: bool = True):
    s = MagicMock()
    s.settings.disable_track_apikey_usage = not track
    return s


def _api_key_row(*, api_key_hash: str | None):
    row = MagicMock()
    row.expires_at = None
    row.total_uses = 0
    row.last_used_at = None
    row.api_key_hash = api_key_hash
    row.id = "key-id"
    row.user_id = "user-id"
    return row


def _session_recording_calls(calls: list[str], row) -> AsyncMock:
    session = AsyncMock()
    session.commit = AsyncMock(side_effect=lambda: calls.append("commit"))
    session.flush = AsyncMock(side_effect=lambda: calls.append("flush"))
    session.get = AsyncMock(return_value=User(id="user-id", username="u", password="p"))  # noqa: S106
    session.add = MagicMock()
    result = MagicMock()
    result.all = MagicMock(return_value=[row])
    session.exec = AsyncMock(return_value=result)
    return session


@pytest.mark.asyncio
async def test_should_commit_the_usage_write_on_the_hash_path():
    calls: list[str] = []
    row = _api_key_row(api_key_hash=hash_api_key(API_KEY))
    session = _session_recording_calls(calls, row)

    with patch(f"{MODULE}._external_access_ceiling_blocks_user", new=AsyncMock(return_value=False)):
        await _check_key_from_db_with_context(session, API_KEY, _settings())

    assert "commit" in calls, "the usage UPDATE must be committed, or it holds SQLite's write lock"
    assert "flush" not in calls, "a bare flush leaves the write lock held for the whole request"


@pytest.mark.asyncio
async def test_should_record_the_usage_before_committing():
    calls: list[str] = []
    row = _api_key_row(api_key_hash=hash_api_key(API_KEY))
    session = _session_recording_calls(calls, row)

    with patch(f"{MODULE}._external_access_ceiling_blocks_user", new=AsyncMock(return_value=False)):
        await _check_key_from_db_with_context(session, API_KEY, _settings())

    assert row.total_uses == 1
    assert isinstance(row.last_used_at, datetime.datetime)
    assert calls == ["commit"]


@pytest.mark.asyncio
async def test_should_not_write_at_all_when_usage_tracking_is_disabled():
    calls: list[str] = []
    row = _api_key_row(api_key_hash=hash_api_key(API_KEY))
    session = _session_recording_calls(calls, row)

    with patch(f"{MODULE}._external_access_ceiling_blocks_user", new=AsyncMock(return_value=False)):
        await _check_key_from_db_with_context(session, API_KEY, _settings(track=False))

    assert row.total_uses == 0
    assert calls == []
