"""Explicit trigger cascades for databases without foreign-key enforcement."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlmodel import col, delete

from langflow.services.database.models.trigger.model import Trigger, TriggerEvent, TriggerSubscription

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


async def delete_triggers(session: AsyncSession, *, trigger_ids: Sequence[UUID]) -> None:
    """Delete triggers and their children within the caller's transaction.

    SQLite does not enable foreign-key cascades by default. Remove payloads and
    subscriptions explicitly before their triggers so deletion works on both
    SQLite and PostgreSQL. Connection-level listener leases are independent.
    """
    if not trigger_ids:
        return
    await session.exec(delete(TriggerSubscription).where(col(TriggerSubscription.trigger_id).in_(trigger_ids)))
    await session.exec(delete(TriggerEvent).where(col(TriggerEvent.trigger_id).in_(trigger_ids)))
    await session.exec(delete(Trigger).where(col(Trigger.id).in_(trigger_ids)))
