"""Tests for the pluggable MEMORY_SERVICE and its lean in-memory default.

Bare lfx previously had no round-tripping chat memory: the stub wrote through a
NoopDatabaseService and reads returned ``[]``. These tests verify the in-memory
default genuinely round-trips, supports filtering/sorting/limiting, exposes the
inherited batch/sync helpers, and is overridable through the service manager.
"""

import asyncio

import lfx.services.manager as manager_mod
import pytest
from lfx.schema.message import Message
from lfx.services.factory import ServiceFactory
from lfx.services.manager import ServiceManager
from lfx.services.memory.base import MemoryService
from lfx.services.memory.factory import MemoryServiceFactory
from lfx.services.memory.service import InMemoryMemoryService
from lfx.services.schema import ServiceType


@pytest.fixture
def fresh_service_manager(monkeypatch):
    """Swap the global service manager for a fresh one (auto-restored)."""
    new_manager = ServiceManager()
    monkeypatch.setattr(manager_mod, "_service_manager", new_manager)
    yield new_manager
    asyncio.run(new_manager.teardown())


def _msg(text, sender="AI", sender_name="Bot", session_id="s1", **kwargs):
    return Message(text=text, sender=sender, sender_name=sender_name, session_id=session_id, **kwargs)


def test_factory_metadata():
    """The memory default is no-deps and (under a noop DB) yields the in-memory backend."""
    factory = MemoryServiceFactory()
    assert factory.service_class is InMemoryMemoryService
    assert factory.dependencies == []
    # With no real DB registered, create() resolves to the in-memory backend.
    assert isinstance(factory.create(), InMemoryMemoryService)


def test_get_memory_service_is_in_memory_default_and_cached(fresh_service_manager):
    """In a process without langflow, the deps helper returns a cached in-memory service."""
    from lfx.services.deps import get_memory_service
    from lfx.services.initialize import initialize_services

    initialize_services()

    svc = get_memory_service()
    assert isinstance(svc, InMemoryMemoryService)
    # Resolves through the (isolated) global manager and is cached.
    assert fresh_service_manager.get(ServiceType.MEMORY_SERVICE) is svc
    assert get_memory_service() is svc


@pytest.mark.asyncio
async def test_store_and_read_round_trip(fresh_service_manager):  # noqa: ARG001
    """Store a message and read it back through get_memory_service() — not []."""
    from lfx.services.deps import get_memory_service
    from lfx.services.initialize import initialize_services

    initialize_services()
    svc = get_memory_service()

    await svc.astore_message(_msg("hello", session_id="round-trip"))
    got = await svc.aget_messages(session_id="round-trip")

    assert [m.text for m in got] == ["hello"]


@pytest.mark.asyncio
async def test_top_level_memory_module_round_trips(fresh_service_manager):  # noqa: ARG001
    """The lfx.memory module proxies route through the registered service and round-trip."""
    from lfx.memory import aget_messages, astore_message
    from lfx.services.initialize import initialize_services

    initialize_services()

    await astore_message(_msg("via-module", session_id="mod"))
    got = await aget_messages(session_id="mod")

    assert [m.text for m in got] == ["via-module"]


@pytest.mark.asyncio
async def test_filter_sort_limit():
    """aget_messages filters by sender/session, sorts by order, and applies limit."""
    svc = InMemoryMemoryService()

    await svc.astore_message(_msg("a", sender="AI", session_id="s1", timestamp="2024-01-01 00:00:00 UTC"))
    await svc.astore_message(_msg("b", sender="User", session_id="s1", timestamp="2024-01-02 00:00:00 UTC"))
    await svc.astore_message(_msg("c", sender="AI", session_id="s2", timestamp="2024-01-03 00:00:00 UTC"))

    # sender filter
    ai = await svc.aget_messages(sender="AI")
    assert {m.text for m in ai} == {"a", "c"}

    # session filter
    s1 = await svc.aget_messages(session_id="s1")
    assert {m.text for m in s1} == {"a", "b"}

    # order DESC (default) vs ASC by timestamp
    desc = await svc.aget_messages(session_id="s1", order="DESC")
    assert [m.text for m in desc] == ["b", "a"]
    asc = await svc.aget_messages(session_id="s1", order="ASC")
    assert [m.text for m in asc] == ["a", "b"]

    # limit
    limited = await svc.aget_messages(limit=1)
    assert len(limited) == 1


@pytest.mark.asyncio
async def test_aadd_messages_loops_astore():
    """The inherited batch helper stores each message and returns them all."""
    svc = InMemoryMemoryService()

    result = await svc.aadd_messages([_msg("one", session_id="b"), _msg("two", session_id="b")])

    assert {m.text for m in result} == {"one", "two"}
    assert {m.text for m in await svc.aget_messages(session_id="b")} == {"one", "two"}


@pytest.mark.asyncio
async def test_aupdate_messages_upserts_without_not_found_raise():
    """Update upserts by id rather than raising 'not found' (NoopSession regression)."""
    svc = InMemoryMemoryService()
    [stored] = await svc.astore_message(_msg("orig", session_id="u"))

    stored.text = "edited"
    [updated] = await svc.aupdate_messages(stored)
    assert updated.text == "edited"

    # Updating a never-stored (but id-bearing) message upserts, no exception.
    fresh = _msg("brand-new", session_id="u")
    fresh.id = "00000000-0000-0000-0000-000000000001"
    [up] = await svc.aupdate_messages(fresh)
    assert up.text == "brand-new"


@pytest.mark.asyncio
async def test_delete_paths():
    """adelete_message and adelete_messages remove the right entries."""
    svc = InMemoryMemoryService()
    await svc.astore_message(_msg("keep", session_id="x"))
    [m2] = await svc.astore_message(_msg("drop", session_id="y"))

    await svc.adelete_message(m2.id)
    assert {m.text for m in await svc.aget_messages()} == {"keep"}

    await svc.adelete_messages(session_id="x")
    assert await svc.aget_messages() == []

    with pytest.raises(ValueError, match="Either session_id or context_id"):
        await svc.adelete_messages()


def test_sync_wrappers_on_base_round_trip():
    """The deprecated sync wrappers (concrete on the ABC) round-trip."""
    svc = InMemoryMemoryService()

    svc.store_message(_msg("sync", session_id="z"))
    got = svc.get_messages(session_id="z")

    assert [m.text for m in got] == ["sync"]


def test_astore_message_requires_identity_fields():
    """Missing session_id/sender/sender_name raises (validation preserved from stubs)."""
    svc = InMemoryMemoryService()
    bad = Message(text="x", sender="AI", sender_name="Bot", session_id="")
    with pytest.raises(ValueError, match="session_id, sender, and sender_name"):
        asyncio.run(svc.astore_message(bad))


def test_alternate_factory_overrides_default(fresh_service_manager):
    """A different memory factory registered through the manager wins."""
    from lfx.services.initialize import initialize_services

    initialize_services()

    class CustomMemoryService(MemoryService):
        name = "memory_service"

        def __init__(self) -> None:
            super().__init__()
            self.set_ready()

        async def astore_message(self, message, flow_id=None, run_id=None):  # noqa: ARG002
            return [message]

        async def aget_messages(self, **kwargs):  # noqa: ARG002
            return []

        async def aupdate_messages(self, messages):
            return messages if isinstance(messages, list) else [messages]

        async def adelete_messages(self, session_id=None, context_id=None):  # noqa: ARG002
            return None

        async def adelete_message(self, id_):  # noqa: ARG002
            return None

    class CustomMemoryFactory(ServiceFactory):
        def __init__(self) -> None:
            super().__init__()
            self.service_class = CustomMemoryService
            self.dependencies = []

        def create(self):
            return CustomMemoryService()

    fresh_service_manager.register_factory(CustomMemoryFactory())

    service = fresh_service_manager.get(ServiceType.MEMORY_SERVICE)
    assert isinstance(service, CustomMemoryService)
    assert not isinstance(service, InMemoryMemoryService)
