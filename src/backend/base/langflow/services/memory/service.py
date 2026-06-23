"""Langflow's MEMORY_SERVICE: real DB-backed memory, with an in-memory fallback.

The backend is resolved **once, on first use**, from the registered database
service: a real (non-noop) DB routes to ``langflow.memory`` (the MessageTable
implementation), while a ``NoopDatabaseService`` falls back to lfx's round-tripping
in-memory store. Resolving on first use — rather than at construction — defers the
decision past service registration (the database service is registered at langflow
startup, before any flow runs and thus before the first memory operation), so the
service never locks in the wrong backend.

This intentionally does *not* call ``has_langflow_db_backend()``: inside langflow,
langflow is always importable, so the only honest question is "is a real DB wired",
answered directly by inspecting the database service.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.services.memory.base import MemoryService
from lfx.services.memory.service import InMemoryMemoryService

if TYPE_CHECKING:
    from uuid import UUID

    from lfx.schema.message import Message


class LangflowMemoryService(MemoryService):
    """Memory service that delegates to the DB-backed implementation when available."""

    name = "memory_service"

    def __init__(self) -> None:
        super().__init__()
        self._backend: object | None = None
        self.set_ready()

    def _backend_impl(self):
        """Resolve and memoize the concrete backend on first use."""
        if self._backend is None:
            from lfx.services.database.service import NoopDatabaseService
            from lfx.services.deps import get_db_service

            if isinstance(get_db_service(), NoopDatabaseService):
                self._backend = InMemoryMemoryService()
            else:
                from langflow import memory as langflow_memory

                self._backend = langflow_memory
        return self._backend

    async def astore_message(
        self,
        message: Message,
        flow_id: str | UUID | None = None,
        run_id: str | UUID | None = None,
    ) -> list[Message]:
        return await self._backend_impl().astore_message(message, flow_id=flow_id, run_id=run_id)

    async def aget_messages(
        self,
        sender: str | None = None,
        sender_name: str | None = None,
        session_id: str | UUID | None = None,
        context_id: str | UUID | None = None,
        order_by: str | None = "timestamp",
        order: str | None = "DESC",
        flow_id: UUID | None = None,
        limit: int | None = None,
    ) -> list[Message]:
        return await self._backend_impl().aget_messages(
            sender=sender,
            sender_name=sender_name,
            session_id=session_id,
            context_id=context_id,
            order_by=order_by,
            order=order,
            flow_id=flow_id,
            limit=limit,
        )

    async def aupdate_messages(self, messages: Message | list[Message]) -> list[Message]:
        return await self._backend_impl().aupdate_messages(messages)

    async def adelete_messages(self, session_id: str | None = None, context_id: str | None = None) -> None:
        return await self._backend_impl().adelete_messages(session_id=session_id, context_id=context_id)

    async def adelete_message(self, id_: str) -> None:
        backend = self._backend_impl()
        # langflow.memory exposes ``delete_message``; InMemoryMemoryService exposes
        # ``adelete_message``.
        if isinstance(backend, InMemoryMemoryService):
            return await backend.adelete_message(id_)
        return await backend.delete_message(id_)

    async def aadd_messages(self, messages: Message | list[Message]) -> list[Message]:
        return await self._backend_impl().aadd_messages(messages)

    async def aadd_messagetables(self, messages: Message | list[Message]) -> list[Message]:
        backend = self._backend_impl()
        # langflow.memory.aadd_messagetables has a different (session-taking)
        # signature; aadd_messages is the equivalent public batch entrypoint.
        if isinstance(backend, InMemoryMemoryService):
            return await backend.aadd_messagetables(messages)
        return await backend.aadd_messages(messages)

    async def teardown(self) -> None:
        if isinstance(self._backend, InMemoryMemoryService):
            await self._backend.teardown()
