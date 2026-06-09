from uuid import UUID

from lfx.utils.async_helpers import run_until_complete
from sqlalchemy import delete
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.message.model import MessageTable, MessageUpdate
from langflow.services.deps import session_scope


def _messages_for_user_stmt(user_id: UUID):
    # Centralized ownership filter used by read/update flows in monitor API.
    # Joining through Flow is the source of truth for message ownership.
    # MessageTable itself does not store user_id directly.
    return select(MessageTable).join(Flow, MessageTable.flow_id == Flow.id).where(Flow.user_id == user_id)


async def get_message_for_user(session: AsyncSession, user_id: UUID, message_id: UUID) -> MessageTable | None:
    # Single-message lookup constrained by owner.
    stmt = _messages_for_user_stmt(user_id).where(MessageTable.id == message_id)
    return (await session.exec(stmt)).first()


async def get_messages_for_user_by_session(session: AsyncSession, user_id: UUID, session_id: str) -> list[MessageTable]:
    # Bulk lookup by session, still constrained by owner.
    stmt = _messages_for_user_stmt(user_id).where(MessageTable.session_id == session_id)
    return (await session.exec(stmt)).all()


async def get_message_ids_for_user(session: AsyncSession, user_id: UUID, message_ids: list[UUID]) -> list[UUID]:
    if not message_ids:
        return []

    stmt = (
        select(MessageTable.id)
        .join(Flow, MessageTable.flow_id == Flow.id)
        .where(col(MessageTable.id).in_(message_ids))
        .where(Flow.user_id == user_id)
    )
    return (await session.exec(stmt)).all()


async def get_message_ids_for_user_by_session(session: AsyncSession, user_id: UUID, session_id: str) -> list[UUID]:
    stmt = (
        select(MessageTable.id)
        .join(Flow, MessageTable.flow_id == Flow.id)
        .where(col(MessageTable.session_id) == session_id)
        .where(Flow.user_id == user_id)
    )
    return (await session.exec(stmt)).all()


async def delete_messages_for_user(session: AsyncSession, user_id: UUID, message_ids: list[UUID]) -> None:
    # Select owned IDs first so mixed payloads only affect caller-owned rows.
    # This prevents a direct delete(MessageTable.id.in_(...)) from ever touching
    # records the caller should not control.
    owned_message_ids = await get_message_ids_for_user(session, user_id, message_ids)
    if not owned_message_ids:
        # No owned targets: keep delete endpoint behavior as idempotent no-op.
        return

    await session.exec(
        delete(MessageTable)
        .where(col(MessageTable.id).in_(owned_message_ids))
        .execution_options(synchronize_session="fetch")
    )


async def delete_messages_for_user_by_session(session: AsyncSession, user_id: UUID, session_id: str) -> None:
    # Same ownership-first strategy for bulk delete by session_id.
    # Session IDs are not globally trusted identifiers; ownership must be checked.
    owned_message_ids = await get_message_ids_for_user_by_session(session, user_id, session_id)
    if not owned_message_ids:
        # Returning without delete preserves 204 semantics without cross-tenant impact.
        return

    await session.exec(
        delete(MessageTable)
        .where(col(MessageTable.id).in_(owned_message_ids))
        .execution_options(synchronize_session="fetch")
    )


async def _update_message(message_id: UUID | str, message: MessageUpdate | dict):
    if not isinstance(message, MessageUpdate):
        message = MessageUpdate(**message)
    async with session_scope() as session:
        db_message = await session.get(MessageTable, message_id)
        if not db_message:
            msg = "Message not found"
            raise ValueError(msg)
        message_dict = message.model_dump(exclude_unset=True, exclude_none=True)
        db_message.sqlmodel_update(message_dict)
        session.add(db_message)
        await session.flush()
        await session.refresh(db_message)
        return db_message


def update_message(message_id: UUID | str, message: MessageUpdate | dict):
    """DEPRECATED - Kept for backward compatibility. Do not use."""
    return run_until_complete(_update_message(message_id, message))
