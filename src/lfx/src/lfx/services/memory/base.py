"""Base class for the pluggable chat-message memory service.

The memory service models the store/read/update/delete surface that the
``lfx.memory`` module exposes for chat ``Message`` objects. Backends implement a
small set of async *primitives*; the batch helpers and the deprecated sync
wrappers are concrete on this base class so every backend inherits them (this is
why those wrappers do not need to live in ``lfx.memory.__init__``).

This base class is also the override seam for richer backends: langflow swaps in
a DB-backed implementation, and a future ``DatabaseBackedMemoryService`` for LFX
executors (Postgres) registers through the same service manager.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from lfx.services.base import Service
from lfx.utils.async_helpers import run_until_complete

if TYPE_CHECKING:
    from uuid import UUID

    from lfx.schema.message import Message


class MemoryService(Service):
    """Abstract base class for chat-message memory backends.

    Abstract primitives (each backend implements):
        - ``astore_message`` — persist a single message.
        - ``aget_messages`` — query/filter messages.
        - ``aupdate_messages`` — update existing messages.
        - ``adelete_messages`` — delete by session/context id.
        - ``adelete_message`` — delete a single message by id.

    Concrete derived/convenience methods (inherited; may be overridden):
        - ``aadd_messages`` / ``aadd_messagetables`` — batch over ``astore_message``.
        - ``store_message`` / ``get_messages`` / ``delete_messages`` / ``add_messages``
          — deprecated sync wrappers via ``run_until_complete``.
    """

    name = "memory_service"

    # --- Abstract primitives -------------------------------------------------

    @abstractmethod
    async def astore_message(
        self,
        message: Message,
        flow_id: str | UUID | None = None,
        run_id: str | UUID | None = None,
    ) -> list[Message]:
        """Store a single message and return it as a one-element list."""

    @abstractmethod
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
        """Retrieve messages matching the provided filters."""

    @abstractmethod
    async def aupdate_messages(self, messages: Message | list[Message]) -> list[Message]:
        """Update stored messages and return the updated list."""

    @abstractmethod
    async def adelete_messages(self, session_id: str | None = None, context_id: str | None = None) -> None:
        """Delete messages by session id or context id."""

    @abstractmethod
    async def adelete_message(self, id_: str) -> None:
        """Delete a single message by id."""

    # --- Concrete derived methods -------------------------------------------

    async def aadd_messages(self, messages: Message | list[Message]) -> list[Message]:
        """Add one or more messages by delegating to ``astore_message``."""
        if not isinstance(messages, list):
            messages = [messages]
        result: list[Message] = []
        for message in messages:
            result.extend(await self.astore_message(message))
        return result

    async def aadd_messagetables(self, messages: Message | list[Message]) -> list[Message]:
        """Alias for ``aadd_messages`` kept for backwards compatibility."""
        return await self.aadd_messages(messages)

    # --- Deprecated sync wrappers -------------------------------------------

    def store_message(
        self,
        message: Message,
        flow_id: str | UUID | None = None,
        run_id: str | UUID | None = None,
    ) -> list[Message]:
        """DEPRECATED: use ``astore_message`` instead."""
        return run_until_complete(self.astore_message(message, flow_id=flow_id, run_id=run_id))

    def get_messages(
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
        """DEPRECATED: use ``aget_messages`` instead."""
        return run_until_complete(
            self.aget_messages(
                sender=sender,
                sender_name=sender_name,
                session_id=session_id,
                context_id=context_id,
                order_by=order_by,
                order=order,
                flow_id=flow_id,
                limit=limit,
            )
        )

    def delete_messages(self, session_id: str | None = None, context_id: str | None = None) -> None:
        """DEPRECATED: use ``adelete_messages`` instead."""
        return run_until_complete(self.adelete_messages(session_id=session_id, context_id=context_id))

    def add_messages(self, messages: Message | list[Message]) -> list[Message]:
        """DEPRECATED: use ``aadd_messages`` instead."""
        return run_until_complete(self.aadd_messages(messages))

    async def teardown(self) -> None:
        """Teardown the memory service. Backends with state should override."""
