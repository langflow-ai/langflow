"""Database-backed chat-message memory — the reference Tier 2 service.

This is the canonical example of the two-tier pluggable-service design:

- It is **Tier 2 (composed)**: it owns the store/read/update/delete *behavior*
  over the lfx-owned ``message`` model, but it does not talk to a database
  directly. It **requires** the Tier 1 ``DATABASE_SERVICE`` and delegates every
  commit/read to it.
- It uses **Option B (explicit injection)**: the database service is passed into
  ``__init__`` (resolved and validated by the service manager from the
  ``requires`` declaration) rather than fetched from a module-level global. The
  service calls ``self.database_service.session_scope()`` — the promoted Tier 1
  port method.

Persistence is inherited from whatever database service is wired underneath:
langflow's engine, ``lfx serve`` sqlite/Postgres, etc. The *same class* runs in
the builder and in the production worker-plane; only the Tier 1 service beneath
it changes. That is the convergence the two-tier model is designed to reach —
langflow selects this lfx implementation instead of authoring its own.

The CRUD logic here is a faithful port of the historical ``langflow.memory``
module (which already operated on the lfx ``MessageTable`` through a
langflow→lfx ``session_scope`` shim); the only change is that the session comes
from the injected Tier 1 service.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, ClassVar
from uuid import UUID

from sqlalchemy import delete
from sqlmodel import col, select

from lfx.log.logger import logger
from lfx.schema.message import Message
from lfx.services.capabilities import Capability, Requires
from lfx.services.database.models.message import MessageRead, MessageTable
from lfx.services.memory.base import MemoryService
from lfx.services.schema import ServiceType

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from lfx.services.interfaces import DatabaseServiceProtocol


def _as_uuid(value):
    """Coerce a value to UUID when possible (MessageTable.id is a UUID column).

    A bare str primary key fails SQLAlchemy's UUID bind processor, so ids that
    arrive as strings (e.g. ``str(message.id)`` from a caller) are normalized
    here. Non-UUID strings are returned unchanged so lookups simply miss rather
    than raising.
    """
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return value


def _build_messages_query(
    sender: str | None = None,
    sender_name: str | None = None,
    session_id: str | UUID | None = None,
    context_id: str | None = None,
    order_by: str | None = "timestamp",
    order: str | None = "DESC",
    flow_id: UUID | None = None,
    limit: int | None = None,
):
    """Build the filtered/ordered SELECT over ``MessageTable`` (error rows excluded)."""
    stmt = select(MessageTable).where(MessageTable.error == False)  # noqa: E712
    if sender:
        stmt = stmt.where(MessageTable.sender == sender)
    if sender_name:
        stmt = stmt.where(MessageTable.sender_name == sender_name)
    if session_id:
        stmt = stmt.where(MessageTable.session_id == session_id)
    if context_id:
        stmt = stmt.where(MessageTable.context_id == context_id)
    if flow_id:
        stmt = stmt.where(MessageTable.flow_id == flow_id)
    if order_by:
        ordering = getattr(MessageTable, order_by).desc() if order == "DESC" else getattr(MessageTable, order_by).asc()
        stmt = stmt.order_by(ordering)
    if limit:
        stmt = stmt.limit(limit)
    return stmt


class DatabaseMemoryService(MemoryService):
    """Chat-message memory backed by the injected Tier 1 database service."""

    name = "memory_service"

    # Wired over a real (persistent) database, this backend persists and is
    # queryable. SHARED is inherited from the underlying database in practice;
    # the static declaration is the conservative {QUERYABLE, PERSISTENT}.
    capabilities: ClassVar[frozenset[Capability]] = frozenset({Capability.QUERYABLE, Capability.PERSISTENT})

    # Requires the database service to be *present* (decision: presence, not
    # PERSISTENT — so this backend can also be wired over an ephemeral database
    # without failing validate_wiring). The injected instance decides whether
    # writes actually survive a restart.
    requires: ClassVar[tuple[Requires, ...]] = (Requires(ServiceType.DATABASE_SERVICE),)

    def __init__(self, database_service: DatabaseServiceProtocol) -> None:
        super().__init__()
        # Option B: the Tier 1 dependency is injected by the manager, not fetched
        # from a global. All persistence goes through this handle.
        self.database_service = database_service
        self.set_ready()
        logger.debug("Database-backed memory service initialized")

    def _session_scope(self):
        """Write session scope from the injected Tier 1 database service."""
        return self.database_service.session_scope()

    async def astore_message(
        self,
        message: Message,
        flow_id: str | UUID | None = None,
        run_id: str | UUID | None = None,
    ) -> list[Message]:
        """Store a single message. Updates in place when it already has an id."""
        if not message:
            await logger.awarning("No message provided.")
            return []

        if not message.session_id or not message.sender or not message.sender_name:
            msg = (
                f"All of session_id, sender, and sender_name must be provided. Session ID: {message.session_id},"
                f" Sender: {message.sender}, Sender Name: {message.sender_name}"
            )
            raise ValueError(msg)

        if getattr(message, "id", None):
            # Has an id: update it if present, otherwise fall through to insert.
            try:
                return await self.aupdate_messages([message])
            except ValueError as e:
                await logger.aerror(e)
        if flow_id and not isinstance(flow_id, UUID):
            flow_id = UUID(flow_id)
        return await self.aadd_messages([message], flow_id=flow_id, run_id=run_id)

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
        """Retrieve messages matching the filters, newest-first by default."""
        async with self.database_service.session_scope_readonly() as session:
            stmt = _build_messages_query(sender, sender_name, session_id, context_id, order_by, order, flow_id, limit)
            messages = await session.exec(stmt)
            return [await Message.create(**d.model_dump()) for d in messages]

    async def aupdate_messages(self, messages: Message | list[Message]) -> list[Message]:
        """Update existing messages by id. Raises if a message id is not found."""
        if not isinstance(messages, list):
            messages = [messages]

        async with self._session_scope() as session:
            updated_messages: list[MessageTable] = []
            for message in messages:
                msg = await session.get(MessageTable, _as_uuid(message.id))
                if msg:
                    msg = msg.sqlmodel_update(message.model_dump(exclude_unset=True, exclude_none=True))
                    # Convert flow_id to UUID if it's a string, preventing a save error.
                    if msg.flow_id and isinstance(msg.flow_id, str):
                        msg.flow_id = UUID(msg.flow_id)
                    result = session.add(msg)
                    if asyncio.iscoroutine(result):
                        await result
                    updated_messages.append(msg)
                else:
                    error_message = f"Message with id {message.id} not found"
                    await logger.awarning(error_message)
                    raise ValueError(error_message)

            return [MessageRead.model_validate(m, from_attributes=True) for m in updated_messages]

    async def aadd_messages(
        self,
        messages: Message | list[Message],
        flow_id: str | UUID | None = None,
        run_id: str | UUID | None = None,
    ) -> list[Message]:
        """Batch-insert messages in a single session."""
        if not isinstance(messages, list):
            messages = [messages]

        for message in messages:
            is_valid_message = isinstance(message, Message) or (
                hasattr(message, "__class__") and message.__class__.__name__ in ["Message", "ErrorMessage"]
            )
            if not is_valid_message:
                types = ", ".join([str(type(msg)) for msg in messages])
                msg = f"The messages must be instances of Message. Found: {types}"
                raise ValueError(msg)

        try:
            message_models = [MessageTable.from_message(m, flow_id=flow_id, run_id=run_id) for m in messages]
            async with self._session_scope() as session:
                message_models = await self._aadd_messagetables(message_models, session)
            return [await Message.create(**m.model_dump()) for m in message_models]
        except Exception as e:
            await logger.aexception(e)
            raise

    async def aadd_messagetables(self, messages: Message | list[Message]) -> list[Message]:
        """Public batch entrypoint — same contract as ``aadd_messages``."""
        return await self.aadd_messages(messages)

    async def _aadd_messagetables(
        self,
        messages: list[MessageTable],
        session: AsyncSession,
        retry_count: int = 0,
    ) -> list[MessageRead]:
        """Add message rows with bounded retry on CancelledError, then normalize."""
        max_retries = 3
        try:
            try:
                for message in messages:
                    result = session.add(message)
                    if asyncio.iscoroutine(result):
                        await result
                await session.commit()
            except asyncio.CancelledError:
                # build_public_tmp can raise CancelledError at commit where
                # build_flow does not; retry a bounded number of times.
                await session.rollback()
                if retry_count >= max_retries:
                    await logger.awarning(
                        f"Max retries ({max_retries}) reached for _aadd_messagetables due to CancelledError"
                    )
                    error_msg = "Add Message operation cancelled after multiple retries"
                    raise ValueError(error_msg) from None
                return await self._aadd_messagetables(messages, session, retry_count + 1)
            for message in messages:
                await session.refresh(message)
        except asyncio.CancelledError as e:
            await logger.aexception(e)
            error_msg = "Operation cancelled"
            raise ValueError(error_msg) from e
        except Exception as e:
            await logger.aexception(e)
            raise

        new_messages = []
        for msg in messages:
            msg.properties = json.loads(msg.properties) if isinstance(msg.properties, str) else msg.properties  # type: ignore[arg-type]
            msg.content_blocks = [json.loads(j) if isinstance(j, str) else j for j in msg.content_blocks]  # type: ignore[arg-type]
            msg.category = msg.category or ""
            new_messages.append(msg)

        return [MessageRead.model_validate(m, from_attributes=True) for m in new_messages]

    async def adelete_messages(self, session_id: str | None = None, context_id: str | None = None) -> None:
        """Delete all messages for a session id or context id."""
        if not session_id and not context_id:
            msg = "Either session_id or context_id must be provided to delete messages."
            raise ValueError(msg)

        async with self._session_scope() as session:
            filter_column = MessageTable.context_id if context_id else MessageTable.session_id
            filter_value = context_id if context_id else session_id
            stmt = (
                delete(MessageTable)
                .where(col(filter_column) == filter_value)
                .execution_options(synchronize_session="fetch")
            )
            await session.exec(stmt)

    async def adelete_message(self, id_: str) -> None:
        """Delete a single message by id (no-op if absent)."""
        async with self._session_scope() as session:
            message = await session.get(MessageTable, _as_uuid(id_))
            if message:
                await session.delete(message)

    async def teardown(self) -> None:
        """No owned resources — the Tier 1 database service owns the engine."""
