"""A context owns at most one reference to each server's pooled MCP session.

MCP clients call ``get_session`` before every tool call, while ``disconnect``
releases the context once. Each leak below kept a session (stdio subprocess or
HTTP connection) alive until the idle sweep; each early release tore one down
while another run could still be using it.
"""

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from lfx.base.mcp.util import MCPSessionManager


async def _keep_alive(stopping: asyncio.Event, stop_gate: asyncio.Event | None) -> None:
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        stopping.set()
        # A real transport takes a while to shut down (process exit, HTTP DELETE).
        if stop_gate is not None:
            await stop_gate.wait()
        raise


class _FakeTransport:
    """Stands in for the stdio transport: a live task per session, no subprocess."""

    def __init__(self) -> None:
        self.created: list[tuple[object, asyncio.Task[Any]]] = []
        self.stopping = asyncio.Event()
        self.stop_gate: asyncio.Event | None = None

    async def create(self, session_id: str, connection_params: object) -> tuple[object, asyncio.Task[Any]]:
        del session_id, connection_params
        session = object()
        task = asyncio.create_task(_keep_alive(self.stopping, self.stop_gate))
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


def _pair(manager: MCPSessionManager, context_id: str, command: str) -> tuple[str, str]:
    server_key = manager._get_server_key(_params(command), "stdio")
    return server_key, manager._context_to_session[context_id][server_key]


def _live_sessions(manager: MCPSessionManager) -> int:
    return sum(len(manager._sessions_for(key)) for key in list(manager.sessions_by_server))


async def test_should_keep_one_reference_when_same_context_reacquires_its_session(manager):
    first = await manager.get_session("ctx", _params("server-a"), "stdio")
    second = await manager.get_session("ctx", _params("server-a"), "stdio")
    third = await manager.get_session("ctx", _params("server-a"), "stdio")

    assert first is second is third
    assert manager._session_refcount[_pair(manager, "ctx", "server-a")] == 1


async def test_should_release_session_when_context_disconnects_after_repeated_acquisition(manager, transport):
    for _ in range(3):
        await manager.get_session("ctx", _params("server-a"), "stdio")
    pair = _pair(manager, "ctx", "server-a")
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
    pair = _pair(manager, "ctx-1", "server-a")
    assert manager._session_refcount[pair] == 2

    await manager._cleanup_session("ctx-1")
    assert manager._session_refcount[pair] == 1
    assert _live_sessions(manager) == 1

    await manager._cleanup_session("ctx-2")
    assert pair not in manager._session_refcount
    assert _live_sessions(manager) == 0


async def test_should_keep_each_server_session_when_context_uses_several_servers(manager, transport):
    await manager.get_session("ctx", _params("server-a"), "stdio")
    await manager.get_session("ctx", _params("server-b"), "stdio")
    await manager.get_session("ctx", _params("server-a"), "stdio")

    # A call may still be running on server A's session while the context
    # also uses server B, so neither is torn down.
    assert len(transport.created) == 2
    assert not any(task.done() for _, task in transport.created)
    assert sorted(manager._session_refcount.values()) == [1, 1]

    await manager._cleanup_session("ctx")

    assert manager._context_to_session == {}
    assert manager._session_refcount == {}
    assert _live_sessions(manager) == 0
    assert all(task.cancelled() for _, task in transport.created)


async def test_should_not_count_dead_session_when_context_gets_a_replacement(manager, transport):
    await manager.get_session("ctx", _params("server-a"), "stdio")
    dead_pair = _pair(manager, "ctx", "server-a")
    _, dead_task = transport.created[0]
    dead_task.cancel()
    await asyncio.sleep(0)

    await manager.get_session("ctx", _params("server-a"), "stdio")
    live_pair = _pair(manager, "ctx", "server-a")

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


async def test_should_release_once_when_the_same_context_disconnects_twice_concurrently(manager):
    await manager.get_session("ctx-1", _params("server-a"), "stdio")
    await manager.get_session("ctx-2", _params("server-a"), "stdio")
    pair = _pair(manager, "ctx-1", "server-a")

    await asyncio.gather(manager._cleanup_session("ctx-1"), manager._cleanup_session("ctx-1"))

    assert manager._session_refcount[pair] == 1
    assert _live_sessions(manager) == 1


async def test_should_keep_new_server_when_it_is_bound_during_a_disconnect(manager):
    await manager.get_session("ctx", _params("server-a"), "stdio")
    server_a, _ = _pair(manager, "ctx", "server-a")

    # The disconnect waits on server A's lock while the context starts using
    # server B; that later use is not part of the disconnect.
    async with manager._server_lock(server_a):
        disconnect = asyncio.create_task(manager._cleanup_session("ctx"))
        await asyncio.sleep(0)
        await manager.get_session("ctx", _params("server-b"), "stdio")
    await disconnect

    server_b, session_b = _pair(manager, "ctx", "server-b")
    assert manager._context_to_session == {"ctx": {server_b: session_b}}
    assert manager._session_refcount == {(server_b, session_b): 1}
    assert _live_sessions(manager) == 1


async def test_should_keep_replacement_when_another_run_discards_the_dead_session(manager, transport):
    dead = await manager.get_session("ctx-1", _params("server-a"), "stdio")
    await manager.get_session("ctx-2", _params("server-a"), "stdio")
    server_key, _ = _pair(manager, "ctx-1", "server-a")

    # Both runs saw the session die; the first replaces it before the second reacts.
    await manager.discard_session(server_key, dead)
    replacement = await manager.get_session("ctx-1", _params("server-a"), "stdio")
    await manager.discard_session(server_key, dead)

    _, replacement_task = transport.created[1]
    assert await manager.get_session("ctx-2", _params("server-a"), "stdio") is replacement
    assert not replacement_task.done()
    assert manager._session_refcount == {_pair(manager, "ctx-1", "server-a"): 2}


async def test_should_pool_session_started_while_the_server_is_invalidated(manager, transport):
    transport.stop_gate = asyncio.Event()
    await manager.get_session("ctx-1", _params("server-a"), "stdio")
    server_key, _ = _pair(manager, "ctx-1", "server-a")

    invalidation = asyncio.create_task(manager.invalidate_server_key(server_key))
    await transport.stopping.wait()
    starting = asyncio.create_task(manager.get_session("ctx-2", _params("server-a"), "stdio"))
    await asyncio.sleep(0.05)
    transport.stop_gate.set()
    await invalidation
    session = await starting

    # Out of the pool, its transport would run on with nothing left to stop it.
    assert [info["session"] for info in manager._sessions_for(server_key).values()] == [session]
