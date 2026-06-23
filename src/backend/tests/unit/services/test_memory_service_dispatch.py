"""Tests for langflow's MEMORY_SERVICE backend resolution.

LangflowMemoryService resolves its backend once, on first use, from the registered
database service: a real DB routes to ``langflow.memory`` (MessageTable), while a
NoopDatabaseService falls back to lfx's round-tripping in-memory store (no silent
no-op inserts). The decision is cached, not re-evaluated per call.
"""

import pytest
from langflow.services.memory.service import LangflowMemoryService
from lfx.schema.message import Message
from lfx.services.database.service import NoopDatabaseService
from lfx.services.memory.service import InMemoryMemoryService


def _msg(text, session_id="s1"):
    return Message(text=text, sender="AI", sender_name="Bot", session_id=session_id)


@pytest.mark.asyncio
async def test_noop_db_resolves_in_memory_not_silent_noop(monkeypatch):
    """With a NoopDatabaseService, store/read round-trip via the in-memory fallback."""
    monkeypatch.setattr("lfx.services.deps.get_db_service", lambda: NoopDatabaseService())

    # Guard: if the fallback were wrong and it hit langflow.memory, fail loudly.
    import langflow.memory as langflow_memory

    def _boom(*_args, **_kwargs):
        msg = "langflow.memory must not be used under a NoopDatabaseService"
        raise AssertionError(msg)

    monkeypatch.setattr(langflow_memory, "astore_message", _boom)

    svc = LangflowMemoryService()
    await svc.astore_message(_msg("hello", session_id="noop"))
    got = await svc.aget_messages(session_id="noop")

    assert isinstance(svc._backend_impl(), InMemoryMemoryService)
    assert [m.text for m in got] == ["hello"]


@pytest.mark.asyncio
async def test_real_db_resolves_langflow_memory(monkeypatch):
    """With a real (non-noop) DB, store/read route to langflow.memory."""

    class _FakeRealDbService:
        """Non-noop stand-in."""

    monkeypatch.setattr("lfx.services.deps.get_db_service", lambda: _FakeRealDbService())

    import langflow.memory as langflow_memory

    calls = {}

    async def _fake_store(message, flow_id=None, run_id=None):  # noqa: ARG001
        calls["store"] = message
        return [message]

    async def _fake_get(**kwargs):
        calls["get"] = kwargs
        return ["sentinel"]

    monkeypatch.setattr(langflow_memory, "astore_message", _fake_store)
    monkeypatch.setattr(langflow_memory, "aget_messages", _fake_get)

    svc = LangflowMemoryService()
    msg = _msg("hi", session_id="real")
    await svc.astore_message(msg)
    got = await svc.aget_messages(session_id="real")

    assert svc._backend_impl() is langflow_memory
    assert calls["store"] is msg
    assert got == ["sentinel"]


@pytest.mark.asyncio
async def test_backend_resolved_once_and_cached(monkeypatch):
    """Once resolved, flipping the DB state does not change the backend."""
    monkeypatch.setattr("lfx.services.deps.get_db_service", lambda: NoopDatabaseService())

    svc = LangflowMemoryService()
    # First use under noop DB -> in-memory.
    await svc.astore_message(_msg("first", session_id="cache"))
    assert isinstance(svc._backend_impl(), InMemoryMemoryService)

    # Now a real DB appears; the cached backend must not switch.
    class _FakeRealDbService:
        pass

    monkeypatch.setattr("lfx.services.deps.get_db_service", lambda: _FakeRealDbService())
    assert isinstance(svc._backend_impl(), InMemoryMemoryService)

    # And it still round-trips through the same in-memory backend.
    got = await svc.aget_messages(session_id="cache")
    assert [m.text for m in got] == ["first"]


def test_get_memory_service_returns_langflow_service():
    """In a langflow process the registered MEMORY_SERVICE is LangflowMemoryService."""
    from langflow.services.utils import register_all_service_factories
    from lfx.services.deps import get_memory_service

    register_all_service_factories()
    svc = get_memory_service()
    assert isinstance(svc, LangflowMemoryService)
