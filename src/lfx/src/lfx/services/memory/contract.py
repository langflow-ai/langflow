"""Importable behavioral contract for any ``MemoryService`` implementation.

Every registered memory backend — the in-memory default, the database-backed
service, or a future plugin — must pass this same suite. This is the concrete
anti-divergence mechanism from the two-tier design: **semantics live in the
contract; implementations may differ only in quality attributes (capabilities),
never in observable behavior.** If the builder and a production wiring ever
behaved differently on chat memory, that gap is a missing contract test here,
not an ``if embedded:`` branch in the engine.

Usage (in a test module)::

    class TestInMemoryContract(MemoryServiceContract):
        async def build_memory_service(self):
            return InMemoryMemoryService()

The contract intentionally exercises the **facade** primitives that must be
identical across backends (``astore_message`` / ``aget_messages`` /
``aupdate_messages`` on existing rows / ``adelete_messages`` /
``adelete_message`` / ordering / session scoping). Lower-level behavior that is
legitimately implementation-specific (e.g. ``aupdate_messages`` against a
*missing* id — the in-memory store upserts, the database backend raises) is
deliberately left unspecified here; the facade ``astore_message`` reconciles it
and is what the contract pins.
"""
# This module is a shipped test-support mixin: asserts are the point of the
# contract, so S101 (assert usage) is allowed file-wide.
# ruff: noqa: S101

from __future__ import annotations

import uuid

import pytest

from lfx.schema.message import Message
from lfx.services.memory.base import MemoryService


def _make_message(text: str, session_id: str, sender: str = "User", sender_name: str = "Alice") -> Message:
    """Build a minimal valid Message (session_id/sender/sender_name are required)."""
    return Message(text=text, session_id=session_id, sender=sender, sender_name=sender_name)


class MemoryServiceContract:
    """Mixin of behavioral tests every MemoryService backend must satisfy.

    Subclasses implement ``build_memory_service`` to return a ready service.
    """

    async def build_memory_service(self) -> MemoryService:  # pragma: no cover - overridden
        """Return a ready-to-use memory service instance."""
        raise NotImplementedError

    @pytest.mark.asyncio
    async def test_is_memory_service(self) -> None:
        service = await self.build_memory_service()
        assert isinstance(service, MemoryService)

    @pytest.mark.asyncio
    async def test_store_and_get_roundtrip(self) -> None:
        service = await self.build_memory_service()
        session_id = f"s-{uuid.uuid4()}"
        await service.astore_message(_make_message("hello", session_id))

        got = await service.aget_messages(session_id=session_id)
        assert len(got) == 1
        assert got[0].text == "hello"

    @pytest.mark.asyncio
    async def test_store_requires_core_fields(self) -> None:
        service = await self.build_memory_service()
        bad = Message(text="no session", sender="User", sender_name="Alice")
        with pytest.raises(ValueError, match="session_id"):
            await service.astore_message(bad)

    @pytest.mark.asyncio
    async def test_get_filters_by_sender(self) -> None:
        service = await self.build_memory_service()
        session_id = f"s-{uuid.uuid4()}"
        await service.astore_message(_make_message("from user", session_id, sender="User", sender_name="Alice"))
        await service.astore_message(_make_message("from machine", session_id, sender="Machine", sender_name="Bot"))

        only_user = await service.aget_messages(session_id=session_id, sender="User")
        assert len(only_user) == 1
        assert only_user[0].text == "from user"

    @pytest.mark.asyncio
    async def test_store_existing_id_updates_not_duplicates(self) -> None:
        # Re-storing a message that already has an id updates the row in place
        # rather than inserting a duplicate. We mutate ``sender_name`` (a plain
        # field), not ``text`` — ``text`` is a computed field over
        # ``content_blocks`` and does not round-trip through a serializing store,
        # so asserting on it would test an operation the backends legitimately
        # implement differently rather than a shared contract.
        service = await self.build_memory_service()
        session_id = f"s-{uuid.uuid4()}"
        stored = await service.astore_message(_make_message("hi", session_id, sender_name="Alice"))
        message = stored[0]

        message.sender_name = "Renamed"
        await service.astore_message(message)

        got = await service.aget_messages(session_id=session_id)
        assert len(got) == 1
        assert got[0].sender_name == "Renamed"

    @pytest.mark.asyncio
    async def test_aupdate_existing_message(self) -> None:
        service = await self.build_memory_service()
        session_id = f"s-{uuid.uuid4()}"
        stored = await service.astore_message(_make_message("original", session_id, sender_name="Alice"))
        message = stored[0]

        message.sender_name = "Edited"
        await service.aupdate_messages([message])

        got = await service.aget_messages(session_id=session_id)
        assert got[0].sender_name == "Edited"

    @pytest.mark.asyncio
    async def test_delete_by_session_scopes_correctly(self) -> None:
        service = await self.build_memory_service()
        keep_session = f"keep-{uuid.uuid4()}"
        drop_session = f"drop-{uuid.uuid4()}"
        await service.astore_message(_make_message("keep me", keep_session))
        await service.astore_message(_make_message("drop me", drop_session))

        await service.adelete_messages(session_id=drop_session)

        assert await service.aget_messages(session_id=drop_session) == []
        assert len(await service.aget_messages(session_id=keep_session)) == 1

    @pytest.mark.asyncio
    async def test_delete_single_message(self) -> None:
        service = await self.build_memory_service()
        session_id = f"s-{uuid.uuid4()}"
        stored = await service.astore_message(_make_message("temp", session_id))

        await service.adelete_message(str(stored[0].id))

        assert await service.aget_messages(session_id=session_id) == []

    @pytest.mark.asyncio
    async def test_delete_requires_a_filter(self) -> None:
        service = await self.build_memory_service()
        with pytest.raises(ValueError, match="session_id or context_id"):
            await service.adelete_messages()
