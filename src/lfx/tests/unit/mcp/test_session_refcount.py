"""A context owns at most one reference to a pooled MCP session.

MCP clients call ``get_session`` before every tool call, while ``disconnect``
releases the context once. Each case below leaked a session (stdio subprocess
or HTTP connection) that only the idle sweep would ever reclaim.
"""

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from lfx.base.mcp.util import MCPSessionManager


class _FakeTransport:
    """Stands in for the stdio transport: a live task per session, no subprocess."""

    def __init__(self) -> None:
        self.created: list[tuple[object, asyncio.Task[Any]]] = []

    async def create(self, session_id: str, connection_params: object) -> tuple[object, asyncio.Task[Any]]:
        del session_id, connection_params
        session = object()
        task = asyncio.create_task(asyncio.Event().wait())
        self.created.append((session, task))
        return session, task


@pytest.fixture
def transport() -> _FakeTransport:
    return _FakeTransport()


@pytest.fixture
async def manager(transport, monkeypatch):
    session_manager = MCPSessionManager()
    monkeypatch.setattr(session_manager, "_create_stdio_session", transport.create)
    yield session_manager
    await session_manager.cleanup_all()


def _params(command: str) -> SimpleNamespace:
    return SimpleNamespace(command=command, args=[], env={})


async def _settle(manager: MCPSessionManager) -> None:
    pending = [task for task in manager._background_tasks if not task.done() and task is not manager._cleanup_task]
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    await asyncio.sleep(0)


def _live_sessions(manager: MCPSessionManager) -> int:
    return sum(len(manager._sessions_for(key)) for key in list(manager.sessions_by_server))


async def test_should_keep_one_reference_when_same_context_reacquires_its_session(manager):
    first = await manager.get_session("ctx", _params("server-a"), "stdio")
    second = await manager.get_session("ctx", _params("server-a"), "stdio")
    third = await manager.get_session("ctx", _params("server-a"), "stdio")

    pair = manager._context_to_session["ctx"]
    assert first is second is third
    assert manager._session_refcount[pair] == 1


async def test_should_release_session_when_context_disconnects_after_repeated_acquisition(manager, transport):
    for _ in range(3):
        await manager.get_session("ctx", _params("server-a"), "stdio")
    pair = manager._context_to_session["ctx"]
    _, task = transport.created[0]

    await manager._cleanup_session("ctx")

    assert "ctx" not in manager._context_to_session
    assert pair not in manager._session_refcount
    assert _live_sessions(manager) == 0
    assert task.cancelled()


async def test_should_keep_shared_session_until_last_context_disconnects(manager):
    await manager.get_session("ctx-1", _params("server-a"), "stdio")
    await manager.get_session("ctx-1", _params("server-a"), "stdio")
    await manager.get_session("ctx-2", _params("server-a"), "stdio")
    pair = manager._context_to_session["ctx-1"]
    assert manager._session_refcount[pair] == 2

    await manager._cleanup_session("ctx-1")
    assert manager._session_refcount[pair] == 1
    assert _live_sessions(manager) == 1

    await manager._cleanup_session("ctx-2")
    assert pair not in manager._session_refcount
    assert _live_sessions(manager) == 0


async def test_should_release_previous_session_when_context_switches_server(manager):
    await manager.get_session("ctx", _params("server-a"), "stdio")
    await manager.get_session("ctx", _params("server-b"), "stdio")
    await manager.get_session("ctx", _params("server-a"), "stdio")
    await _settle(manager)

    assert list(manager._session_refcount.values()) == [1]
    assert _live_sessions(manager) == 1

    await manager._cleanup_session("ctx")
    await _settle(manager)

    assert manager._context_to_session == {}
    assert manager._session_refcount == {}
    assert _live_sessions(manager) == 0


async def test_should_keep_previous_session_when_another_context_still_uses_it(manager):
    await manager.get_session("ctx-1", _params("server-a"), "stdio")
    await manager.get_session("ctx-2", _params("server-a"), "stdio")
    pair_a = manager._context_to_session["ctx-1"]

    await manager.get_session("ctx-1", _params("server-b"), "stdio")
    await _settle(manager)

    assert manager._session_refcount[pair_a] == 1
    assert pair_a[1] in manager._sessions_for(pair_a[0])


async def test_should_not_count_dead_session_when_context_gets_a_replacement(manager, transport):
    await manager.get_session("ctx", _params("server-a"), "stdio")
    dead_pair = manager._context_to_session["ctx"]
    _, dead_task = transport.created[0]
    dead_task.cancel()
    await asyncio.sleep(0)

    await manager.get_session("ctx", _params("server-a"), "stdio")
    await _settle(manager)
    live_pair = manager._context_to_session["ctx"]

    assert live_pair != dead_pair
    assert manager._session_refcount == {live_pair: 1}

    await manager._cleanup_session("ctx")
    assert manager._session_refcount == {}
    assert _live_sessions(manager) == 0


async def test_should_drop_stale_references_when_idle_sweep_removes_session(manager, monkeypatch):
    await manager.get_session("ctx", _params("server-a"), "stdio")
    monkeypatch.setattr("lfx.base.mcp.util.get_session_idle_timeout", lambda: -1)

    await manager._cleanup_idle_sessions()

    assert manager._context_to_session == {}
    assert manager._session_refcount == {}


async def test_should_not_release_twice_when_disconnect_races_a_server_switch(manager):
    await manager.get_session("ctx-1", _params("server-a"), "stdio")
    await manager.get_session("ctx-2", _params("server-a"), "stdio")
    pair_a = manager._context_to_session["ctx-1"]

    # The disconnect waits on server A's lock while ctx-1 moves to server B,
    # which already releases ctx-1's reference to A.
    async with manager._server_lock(pair_a[0]):
        disconnect = asyncio.create_task(manager._cleanup_session("ctx-1"))
        await asyncio.sleep(0)
        await manager.get_session("ctx-1", _params("server-b"), "stdio")
    await disconnect
    await _settle(manager)

    assert manager._session_refcount[pair_a] == 1
    assert pair_a[1] in manager._sessions_for(pair_a[0])
    assert manager._context_to_session["ctx-1"][0] != pair_a[0]
