"""In-memory chat-message memory backend — the no-deps lean default for bare lfx.

Stores ``Message`` objects in a process-local dict so that store/read genuinely
round-trips without any database. This is the default registered by
``lfx.services.initialize`` and is also used as the fallback when langflow runs
with a ``NoopDatabaseService`` (no silent no-op inserts).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from lfx.log.logger import logger
from lfx.services.memory.base import MemoryService

if TYPE_CHECKING:
    from lfx.schema.message import Message


class InMemoryMemoryService(MemoryService):
    """Round-tripping in-memory memory backend (no database, no dependencies)."""

    name = "memory_service"

    def __init__(self) -> None:
        super().__init__()
        self._messages: dict[str, Message] = {}
        self.set_ready()
        logger.debug("In-memory memory service initialized")

    async def astore_message(
        self,
        message: Message,
        flow_id: str | UUID | None = None,
        run_id: str | UUID | None = None,
    ) -> list[Message]:
        """Store a single message in the in-memory dict and return it."""
        if not message:
            logger.warning("No message provided.")
            return []

        if not message.session_id or not message.sender or not message.sender_name:
            msg = (
                f"All of session_id, sender, and sender_name must be provided. Session ID: {message.session_id},"
                f" Sender: {message.sender}, Sender Name: {message.sender_name}"
            )
            raise ValueError(msg)

        # Normalize flow_id/run_id. Be tolerant of non-UUID flow_ids (synthetic IDs
        # from tests or string identifiers); UUID parsing only normalizes format.
        if flow_id:
            if isinstance(flow_id, str):
                try:
                    flow_id = UUID(flow_id)
                except ValueError:
                    logger.warning(
                        f"flow_id {flow_id!r} is not a valid UUID; preserving verbatim. "
                        "Downstream code that expects a UUID may surface a confusing error."
                    )
            message.flow_id = str(flow_id)
        if run_id:
            if isinstance(run_id, UUID):
                run_id = str(run_id)
            message.run_id = str(run_id)

        if not getattr(message, "id", None):
            try:
                import nanoid

                message.id = nanoid.generate()
            except ImportError:
                import uuid

                message.id = str(uuid.uuid4())

        self._messages[str(message.id)] = message
        logger.debug(f"Message stored with ID: {message.id}")
        return [message]

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
        """Filter, sort, and limit the in-memory messages."""
        results = list(self._messages.values())

        if sender is not None:
            results = [m for m in results if m.sender == sender]
        if sender_name is not None:
            results = [m for m in results if m.sender_name == sender_name]
        # session_id/context_id/flow_id may be UUID or str depending on caller;
        # compare as strings so a UUID filter still matches a str-stored value.
        if session_id is not None:
            results = [m for m in results if str(getattr(m, "session_id", None)) == str(session_id)]
        if context_id is not None:
            results = [m for m in results if str(getattr(m, "context_id", None)) == str(context_id)]
        if flow_id is not None:
            results = [m for m in results if str(getattr(m, "flow_id", None)) == str(flow_id)]

        if order_by:
            results.sort(
                key=lambda m: getattr(m, order_by, None) or "",
                reverse=(order or "DESC").upper() == "DESC",
            )

        if limit is not None:
            results = results[:limit]

        logger.debug(f"Retrieved {len(results)} messages")
        return results

    async def aupdate_messages(self, messages: Message | list[Message]) -> list[Message]:
        """Upsert messages by id.

        Unlike langflow's DB backend we do not raise when a message id is absent
        from the store — we upsert. This deliberately avoids the strict
        existence check that surfaced "Message with id X not found" against a
        NoopSession.
        """
        if not isinstance(messages, list):
            messages = [messages]

        updated: list[Message] = []
        for message in messages:
            if not getattr(message, "id", None):
                error_message = f"Message without ID cannot be updated: {message}"
                logger.warning(error_message)
                raise ValueError(error_message)
            if message.flow_id and isinstance(message.flow_id, UUID):
                message.flow_id = str(message.flow_id)
            self._messages[str(message.id)] = message
            updated.append(message)
            logger.debug(f"Message updated: {message.id}")
        return updated

    async def adelete_messages(self, session_id: str | None = None, context_id: str | None = None) -> None:
        """Delete all messages matching the given session id or context id."""
        if not session_id and not context_id:
            msg = "Either session_id or context_id must be provided to delete messages."
            raise ValueError(msg)

        target = str(session_id) if session_id else str(context_id)
        field = "session_id" if session_id else "context_id"
        to_drop = [mid for mid, m in self._messages.items() if str(getattr(m, field, None)) == target]
        for mid in to_drop:
            del self._messages[mid]
        logger.debug(f"Deleted {len(to_drop)} messages for {field}: {target}")

    async def adelete_message(self, id_: str) -> None:
        """Delete a single message by id (no-op if absent)."""
        self._messages.pop(str(id_), None)
        logger.debug(f"Message deleted: {id_}")

    async def teardown(self) -> None:
        """Clear the in-memory store."""
        self._messages.clear()
        logger.debug("In-memory memory service teardown")
