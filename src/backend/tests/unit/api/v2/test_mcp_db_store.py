"""Proof that the DB-backed MCP store fixes both multi-replica bugs.

This file previously reproduced the two bugs against the file-based implementation
(Bug 1: storage divergence; Bug 2: cross-pod lost updates — 1/30 servers survived).
`update_server` / `get_server_list` / `get_server` are now backed by the
`mcp_server` table (one row per server, unique on `(user_id, name)`, no in-process
lock), so those bugs are structurally impossible. These tests assert the fix using
the real functions against a real SQLite DB.

Run:  uv run pytest src/backend/tests/unit/api/v2/test_mcp_db_store.py -v -s
"""

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import langflow.services.database.models  # noqa: F401  (register SQLModel tables)
import pytest
from langflow.api.v2.mcp import get_server, get_server_list, update_server
from langflow.services.database.models import MCPServer
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.pool import StaticPool

# _clear_server_cache() calls the shared component cache service, which isn't booted
# in a bare unit test; no-op it (orthogonal to the store under test).
CACHE_PATCH = {
    "get_shared_component_cache_service": MagicMock(return_value=SimpleNamespace()),
    "safe_cache_get": MagicMock(return_value={}),
    "safe_cache_set": MagicMock(),
}


async def _memory_engine():
    """Single shared in-memory DB (one connection) — for sequential tests."""
    engine = create_async_engine("sqlite+aiosqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine


async def _file_engine(db_path):
    """File-backed DB so each session gets its own connection (WAL) — models concurrent pods."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", connect_args={"timeout": 30})

    @event.listens_for(engine.sync_engine, "connect")
    def _pragmas(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine


# ---------------------------------------------------------------------------
# Bug 2 — cross-pod lost update: FIXED
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_bug2_fixed_30_concurrent_adds_all_survive(tmp_path):
    """30 concurrent same-user adds across independent sessions — all must survive.

    File-based multi-pod result was 1/30 (29 lost). Per-row upsert → 30/30.
    """
    engine = await _file_engine(tmp_path / "mcp.db")
    user_id = uuid.uuid4()

    async def add_one(i: int):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            await update_server(
                f"server_{i}", {"command": "echo", "args": [str(i)]}, SimpleNamespace(id=user_id), session, None, None
            )

    with patch.multiple("langflow.api.v2.mcp", **CACHE_PATCH):
        await asyncio.gather(*[add_one(i) for i in range(30)])
        async with AsyncSession(engine, expire_on_commit=False) as session:
            final = await get_server_list(SimpleNamespace(id=user_id), session, None, None)

    await engine.dispose()
    survivors = final["mcpServers"]
    # File-based multi-pod result was 1/30; per-row upsert keeps all 30.
    assert len(survivors) == 30, f"expected all 30, got {sorted(survivors)}"


@pytest.mark.asyncio
async def test_bug2_fixed_interleaved_writes_no_loss():
    """Interleaved read/read/write/write (which dropped a server on the file store) now keeps all servers."""
    engine = await _memory_engine()
    user = SimpleNamespace(id=uuid.uuid4())

    with patch.multiple("langflow.api.v2.mcp", **CACHE_PATCH):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            await update_server("server_a", {"command": "echo", "args": ["a"]}, user, session, None, None)
            # Two "pods" add different servers; on the file store the second clobbered the first.
            await update_server("server_b", {"command": "echo", "args": ["b"]}, user, session, None, None)
            await update_server("server_c", {"command": "echo", "args": ["c"]}, user, session, None, None)
            final = await get_server_list(user, session, None, None)

    await engine.dispose()
    assert set(final["mcpServers"]) == {"server_a", "server_b", "server_c"}


@pytest.mark.asyncio
async def test_concurrent_same_name_no_crash(tmp_path):
    """Concurrent adds of the same name are absorbed by the unique constraint, leaving exactly one row."""
    engine = await _file_engine(tmp_path / "mcp.db")
    user_id = uuid.uuid4()

    async def add_same(i: int):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            await update_server(
                "dup", {"command": "echo", "args": [str(i)]}, SimpleNamespace(id=user_id), session, None, None
            )

    with patch.multiple("langflow.api.v2.mcp", **CACHE_PATCH):
        # return_exceptions so a raced IntegrityError (if any slips) is visible, not swallowed
        results = await asyncio.gather(*[add_same(i) for i in range(10)], return_exceptions=True)
        async with AsyncSession(engine, expire_on_commit=False) as session:
            rows = (await session.exec(select(MCPServer).where(MCPServer.user_id == user_id))).all()

    await engine.dispose()
    errors = [r for r in results if isinstance(r, Exception)]
    assert not errors, f"same-name races raised: {errors}"
    assert len(rows) == 1, f"expected exactly one 'dup' row, got {len(rows)}"


# ---------------------------------------------------------------------------
# Bug 1 — storage divergence: FIXED (no file/storage at all)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_bug1_fixed_no_storage_divergence(tmp_path):
    """Two 'pods' (two sessions, no storage service) read identical servers from the shared DB — nothing diverges."""
    engine = await _file_engine(tmp_path / "mcp.db")
    user = SimpleNamespace(id=uuid.uuid4())

    with patch.multiple("langflow.api.v2.mcp", **CACHE_PATCH):
        async with AsyncSession(engine, expire_on_commit=False) as pod_a:
            await update_server("weather", {"command": "uvx", "args": ["mcp-server-weather"]}, user, pod_a, None, None)
        async with AsyncSession(engine, expire_on_commit=False) as pod_b:
            list_b = await get_server_list(user, pod_b, None, None)

    await engine.dispose()
    assert "weather" in list_b["mcpServers"], "pod B must see what pod A wrote (shared DB, no storage)"


# ---------------------------------------------------------------------------
# Drop-in contract — same signatures, same {"mcpServers": {...}} shape
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_drop_in_crud_roundtrip():
    engine = await _memory_engine()
    user = SimpleNamespace(id=uuid.uuid4())

    with patch.multiple("langflow.api.v2.mcp", **CACHE_PATCH):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            cfg = {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-everything"]}
            await update_server("everything", cfg, user, session, None, None)

            listed = await get_server_list(user, session, None, None)
            assert set(listed.keys()) == {"mcpServers"}
            assert listed["mcpServers"]["everything"]["command"] == "npx"

            one = await get_server("everything", user, session, None, None)
            assert one["args"][0] == "-y"
            assert await get_server("missing", user, session, None, None) is None

            # add_server semantics: creating an existing name is rejected
            with pytest.raises(Exception):  # noqa: B017, PT011  (HTTPException 500)
                await update_server("everything", cfg, user, session, None, None, check_existing=True)

            # delete
            await update_server("everything", {}, user, session, None, None, delete=True)
            assert (await get_server_list(user, session, None, None))["mcpServers"] == {}

    await engine.dispose()


# ---------------------------------------------------------------------------
# Secrets encrypted at rest (needs the auth service → depends on `client`)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_secrets_encrypted_at_rest(client):  # noqa: ARG001  (boots services incl. auth)
    engine = await _memory_engine()
    user = SimpleNamespace(id=uuid.uuid4())

    with patch.multiple("langflow.api.v2.mcp", **CACHE_PATCH):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            await update_server(
                "secure",
                {"url": "https://mcp.example.com", "headers": {"Authorization": "Bearer SECRET-TOKEN"}},
                user,
                session,
                None,
                None,
            )
            # Raw row: the secret must be ciphertext at rest.
            row = (await session.exec(select(MCPServer).where(MCPServer.user_id == user.id))).first()
            stored = row.config["headers"]["Authorization"]
            assert stored != "Bearer SECRET-TOKEN", "header stored in plaintext!"
            assert stored.startswith("gAAAAA"), f"expected Fernet ciphertext, got {stored[:12]}"

            # Read path decrypts back to a runnable value.
            got = await get_server("secure", user, session, None, None)
            assert got["headers"]["Authorization"] == "Bearer SECRET-TOKEN"

    await engine.dispose()


# ---------------------------------------------------------------------------
# Backward compat — existing file-based users are migrated into the table
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_backfill_from_legacy_file(client, active_user):  # noqa: ARG001  (boots services)
    """A user's legacy _mcp_servers file is imported into mcp_server (secrets encrypted); re-running is a no-op."""
    from langflow.api.utils.mcp.backfill import backfill_mcp_servers_from_files
    from langflow.api.v2.mcp import upload_server_config
    from langflow.services.deps import get_settings_service, get_storage_service, session_scope

    user = SimpleNamespace(id=active_user.id)
    legacy = {
        "mcpServers": {
            "weather": {"command": "uvx", "args": ["mcp-server-weather"]},
            "auth": {"url": "https://mcp.example.com", "headers": {"Authorization": "Bearer LEGACY-TOKEN"}},
        }
    }

    with patch.multiple("langflow.api.v2.mcp", **CACHE_PATCH):
        # Seed the legacy file through the real storage service (local or S3).
        async with session_scope() as session:
            await upload_server_config(legacy, user, session, get_storage_service(), get_settings_service())
            await session.commit()

        # First run imports both servers.
        async with session_scope() as session:
            summary = await backfill_mcp_servers_from_files(session)
        assert summary["imported"] >= 2

        async with session_scope() as session:
            servers = (await get_server_list(user, session, None, None))["mcpServers"]
        assert "weather" in servers
        assert servers["auth"]["headers"]["Authorization"] == "Bearer LEGACY-TOKEN"  # plaintext legacy → decrypted

        # Second run is idempotent — nothing new imported.
        async with session_scope() as session:
            again = await backfill_mcp_servers_from_files(session)
        assert again["imported"] == 0, f"backfill not idempotent: {again}"


# ---------------------------------------------------------------------------
# Cache invalidation — updating a server must drop its hashed cache variants
# ---------------------------------------------------------------------------
def test_clear_server_cache_removes_hashed_variants():
    """Updating a server clears the bare name AND every ``{name}:{hash}`` cache variant (else stale config)."""
    from langflow.api.v2.mcp import _clear_server_cache

    cache = {"servers": {"weather": 1, "weather:abc123": 2, "weather:def456": 3, "other": 4, "other:xyz": 5}}

    def fake_get(_svc, key, default=None):
        return cache.get(key, default)

    def fake_set(_svc, key, value):
        cache[key] = value

    with patch.multiple(
        "langflow.api.v2.mcp",
        get_shared_component_cache_service=MagicMock(return_value=SimpleNamespace()),
        safe_cache_get=fake_get,
        safe_cache_set=fake_set,
    ):
        _clear_server_cache("weather")

    assert cache["servers"] == {"other": 4, "other:xyz": 5}


@pytest.mark.asyncio
async def test_concurrent_check_existing_create_does_not_overwrite_winner(tmp_path):
    """Concurrent check_existing creates for one name: exactly one wins (fallback must not overwrite the winner)."""
    engine = await _file_engine(tmp_path / "mcp.db")
    user_id = uuid.uuid4()

    async def create(i: int):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            await update_server(
                "dup",
                {"command": "echo", "args": [str(i)]},
                SimpleNamespace(id=user_id),
                session,
                None,
                None,
                check_existing=True,
            )

    with patch.multiple("langflow.api.v2.mcp", **CACHE_PATCH):
        results = await asyncio.gather(*[create(i) for i in range(10)], return_exceptions=True)
        async with AsyncSession(engine, expire_on_commit=False) as session:
            rows = (
                await session.exec(select(MCPServer).where(MCPServer.user_id == user_id, MCPServer.name == "dup"))
            ).all()

    await engine.dispose()
    successes = [r for r in results if not isinstance(r, Exception)]
    assert len(rows) == 1, f"expected exactly one row, got {len(rows)}"
    assert len(successes) == 1, f"expected exactly one create to win, got {len(successes)}"


@pytest.mark.asyncio
async def test_get_server_list_preserves_insertion_order():
    """get_server_list orders by created_at so the starter project stays first, not sorted by name."""
    from datetime import datetime, timedelta, timezone

    engine = await _memory_engine()
    user_id = uuid.uuid4()
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    # Insert out of alphabetical order, with increasing created_at.
    names = ["lf-starter_project", "aaa_added_later", "zzz_added_last"]
    async with AsyncSession(engine, expire_on_commit=False) as session:
        for i, name in enumerate(names):
            session.add(MCPServer(user_id=user_id, name=name, config={}, created_at=base + timedelta(seconds=i)))
        await session.commit()

    with patch.multiple("langflow.api.v2.mcp", **CACHE_PATCH):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            servers = (await get_server_list(SimpleNamespace(id=user_id), session, None, None))["mcpServers"]

    await engine.dispose()
    assert list(servers.keys()) == names, f"expected insertion order {names}, got {list(servers.keys())}"


@pytest.mark.asyncio
async def test_concurrent_merge_patches_preserve_all_fields(tmp_path):
    """Concurrent merge PATCHes to the SAME server each set a distinct field; the version lock keeps all of them.

    Without the version-guarded retry, all writers read the same base config and the last
    commit wins, silently dropping the other fields (the gap flagged in review of #13976).
    """
    engine = await _file_engine(tmp_path / "mcp.db")
    user = SimpleNamespace(id=uuid.uuid4())

    with patch.multiple("langflow.api.v2.mcp", **CACHE_PATCH):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            await update_server("svc", {"url": "https://x", "k0": "base"}, user, session, None, None)

        async def patch_field(i: int):
            async with AsyncSession(engine, expire_on_commit=False) as session:
                await update_server("svc", {f"k{i}": str(i)}, user, session, None, None, merge_existing=True)

        results = await asyncio.gather(*[patch_field(i) for i in range(1, 9)], return_exceptions=True)
        async with AsyncSession(engine, expire_on_commit=False) as session:
            final = await get_server("svc", user, session, None, None)

    await engine.dispose()
    errors = [r for r in results if isinstance(r, Exception)]
    assert not errors, f"concurrent PATCHes raised: {errors}"
    assert final["url"] == "https://x"
    for i in range(1, 9):
        assert final.get(f"k{i}") == str(i), f"lost concurrently-patched field k{i}; final={final}"


@pytest.mark.asyncio
async def test_concurrent_patch_and_delete_never_raises_raw_db_error(tmp_path):
    """A merge PATCH racing a DELETE of the same server must fail cleanly (HTTPException), never a raw DB error."""
    from fastapi import HTTPException

    engine = await _file_engine(tmp_path / "mcp.db")
    user = SimpleNamespace(id=uuid.uuid4())

    async def create():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            await update_server("svc", {"url": "https://x", "a": "1"}, user, session, None, None)

    async def patch_it():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            await update_server("svc", {"b": "2"}, user, session, None, None, merge_existing=True)

    async def delete_it():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            await update_server("svc", {}, user, session, None, None, delete=True)

    with patch.multiple("langflow.api.v2.mcp", **CACHE_PATCH):
        # Many rounds to make the "deleted between the PATCH's read and its guarded write" window likely.
        for _ in range(15):
            await create()
            results = await asyncio.gather(patch_it(), delete_it(), return_exceptions=True)
            raw = [r for r in results if isinstance(r, Exception) and not isinstance(r, HTTPException)]
            assert not raw, f"PATCH/DELETE race raised a raw DB error: {[type(r).__name__ for r in raw]}"

    await engine.dispose()
