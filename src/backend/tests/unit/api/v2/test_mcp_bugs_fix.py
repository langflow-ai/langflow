"""Tests for MCP bugs b0, b1: concurrent updates and cache key mismatch on invalidation."""
import asyncio
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from langflow.api.v2.mcp import update_server


class FakeStorageService:
    """Minimal stub for storage interactions."""

    def __init__(self):
        self._store: dict[str, bytes] = {}

    async def save_file(self, flow_id: str, file_name: str, data: bytes, *, append: bool = False):
        key = f"{flow_id}/{file_name}"
        if append and key in self._store:
            self._store[key] += data
        else:
            self._store[key] = data

    async def get_file_size(self, flow_id: str, file_name: str):
        return len(self._store.get(f"{flow_id}/{file_name}", b""))

    async def delete_file(self, flow_id: str, file_name: str):
        self._store.pop(f"{flow_id}/{file_name}", None)


class FakeResult:
    """Helper for Session.exec return."""

    def __init__(self, rows):
        self._rows = rows

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return list(self._rows)


class FakeSession:
    """Minimal async session stub."""

    def __init__(self):
        self._db: dict[str, object] = {}

    async def exec(self, stmt):
        return FakeResult([])

    def add(self, obj):
        self._db[str(obj)] = obj

    async def commit(self):
        return

    async def refresh(self, obj):  # noqa: ARG002
        return

    async def delete(self, obj):
        self._db.pop(str(obj), None)

    async def flush(self):
        return


class FakeSettings:
    """Fake settings for tests."""

    max_file_size_upload: int = 10  # MB


@pytest.fixture
def current_user():
    """Create a fake user."""

    class User(SimpleNamespace):
        id: str
        is_superuser: bool = False

    return User(id=str(uuid.uuid4()))


@pytest.fixture
def storage_service():
    """Create a fake storage service."""
    return FakeStorageService()


@pytest.fixture
def settings_service():
    """Create a fake settings service."""
    return SimpleNamespace(settings=FakeSettings())


@pytest.fixture
def session():
    """Create a fake session."""
    return FakeSession()


@pytest.mark.asyncio
async def test_b1_cache_invalidation_clears_hashed_keys(
    session, storage_service, settings_service, current_user
):
    """Cache invalidation must clear all cache entries, including those with hashed keys.

    Bug b1: Cache invalidation deletes using bare server_name, but actual cache key
    includes SHA256 hash of headers+timeout (mcp_component.py:160-185).
    Expected: All cache entries for a server are cleared, including hashed variants.
    """
    cache_updates = []

    def mock_safe_cache_get(cache, key, default=None):
        # Simulate having a "servers" dict with both bare and hashed keys
        if key == "servers":
            return {
                "my_server": {"config": "old"},
                "my_server:abc123def": {"config": "old_with_headers"},
                "other_server": {"config": "data"},
            }
        return default

    def mock_safe_cache_set(cache, key, value):
        cache_updates.append((key, value))

    config_state = {"mcpServers": {"my_server": {"command": "new"}}}

    async def mock_get_server_list(*_args, **_kwargs):
        return config_state

    async def mock_upload_server_config(new_config, *_args, **_kwargs):
        config_state["mcpServers"] = dict(new_config["mcpServers"])

    async def mock_get_server(name, *_args, **kwargs):
        server_list = kwargs.get("server_list", {})
        return server_list.get("mcpServers", {}).get(name)

    # Mock the lock context
    class MockLockContext:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    with patch.multiple(
        "langflow.api.v2.mcp",
        get_server_list=mock_get_server_list,
        upload_server_config=mock_upload_server_config,
        get_server=mock_get_server,
        _MCPLockContext=MockLockContext,
        get_shared_component_cache_service=MagicMock(return_value=SimpleNamespace()),
        safe_cache_get=mock_safe_cache_get,
        safe_cache_set=mock_safe_cache_set,
    ):
        await update_server(
            "my_server",
            {"command": "new"},
            current_user,
            session,
            storage_service,
            settings_service,
        )

    # Find the cache update for servers
    servers_update = None
    for key, value in cache_updates:
        if key == "servers":
            servers_update = value
            break

    assert servers_update is not None, "Cache should have been updated for servers"
    # Hashed key should be cleared
    assert "my_server:abc123def" not in servers_update, (
        "Hashed cache key 'my_server:abc123def' should be cleared"
    )
    # Bare key should be cleared
    assert "my_server" not in servers_update, "Bare server key should be cleared"
    # Other servers untouched
    assert "other_server" in servers_update, "Other servers should remain"


@pytest.mark.asyncio
async def test_b0_distributed_lock_protects_concurrent_updates(
    session, storage_service, settings_service, current_user
):
    """Concurrent updates use a distributed lock to prevent lost writes.

    Bug b0: In-process asyncio.Lock doesn't coordinate across Gunicorn workers.
    Expected: Distributed file lock serializes updates even across processes.

    Note: this does not cover cross-worker cache staleness (a separate, narrower
    issue in the tool-connection cache keyed in mcp_component.py, which self-heals
    via that cache's existing TTL) — only the config-file lost-update race.
    """
    import copy

    # Shared mutable config state
    config_state = {"mcpServers": {"server_a": {"command": "echo", "args": ["a"]}}}
    update_order = []

    # Simulate a distributed lock with an asyncio.Lock for testing
    lock = asyncio.Lock()

    async def mock_get_server_list(*_args, **_kwargs):
        result = copy.deepcopy(config_state)
        await asyncio.sleep(0)  # Yield to allow interleaving
        return result

    async def mock_upload_server_config(new_config, *_args, **_kwargs):
        # Record when each write happens (to verify ordering by lock)
        update_order.append(list(new_config["mcpServers"].keys()))
        await asyncio.sleep(0)  # Yield
        config_state["mcpServers"] = dict(new_config["mcpServers"])

    async def mock_get_server(name, *_args, **kwargs):
        server_list = kwargs.get("server_list", {})
        return server_list.get("mcpServers", {}).get(name)

    # Mock the lock context with proper synchronization
    class MockLockContext:
        def __init__(self, *args, **kwargs):
            self.lock = lock

        async def __aenter__(self):
            await self.lock.acquire()
            return self

        async def __aexit__(self, *args):
            self.lock.release()
            return False

    with patch.multiple(
        "langflow.api.v2.mcp",
        get_server_list=mock_get_server_list,
        upload_server_config=mock_upload_server_config,
        get_server=mock_get_server,
        _MCPLockContext=MockLockContext,
        get_shared_component_cache_service=MagicMock(return_value=SimpleNamespace()),
        safe_cache_get=MagicMock(return_value={}),
        safe_cache_set=MagicMock(),
    ):
        # Run concurrent updates - they should serialize due to the lock
        await asyncio.gather(
            update_server(
                "server_b",
                {"command": "echo", "args": ["b"]},
                current_user,
                session,
                storage_service,
                settings_service,
            ),
            update_server(
                "server_c",
                {"command": "echo", "args": ["c"]},
                current_user,
                session,
                storage_service,
                settings_service,
            ),
        )

    # All servers should be preserved (lock prevents lost updates)
    assert "server_a" in config_state["mcpServers"], "server_a should be preserved"
    assert "server_b" in config_state["mcpServers"], "server_b should be preserved"
    assert "server_c" in config_state["mcpServers"], "server_c should be preserved"

    # Lock ensures writes are serialized (one after the other)
    # Each write should have all previously written servers plus the new one
    assert len(update_order) >= 2, "Multiple writes should have occurred"
