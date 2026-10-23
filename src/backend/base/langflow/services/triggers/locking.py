"""Serialize lifecycle decisions against the latest persisted trigger state."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlmodel import update

from langflow.services.database.models.trigger.model import Trigger

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


async def lock_trigger(session: AsyncSession, trigger_id: UUID) -> Trigger | None:
    """Reload a trigger while holding its write lock until the transaction ends."""
    if session.get_bind().dialect.name == "sqlite":
        # SQLite ignores FOR UPDATE. Take its write lock before reading the
        # state, using the same no-op update as the dispatcher capacity guard.
        await session.exec(
            update(Trigger)
            .where(Trigger.id == trigger_id)
            .values(updated_at=Trigger.updated_at)
            .execution_options(synchronize_session=False)
        )
    return await session.get(Trigger, trigger_id, populate_existing=True, with_for_update=True)
