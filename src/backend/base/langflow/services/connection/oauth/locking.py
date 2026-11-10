"""Use one database transaction lock for exchange, refresh, revoke and delete."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import update
from sqlmodel import col, select

from langflow.services.database.models.connection import Connection

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


async def lock_connection(session: AsyncSession, connection_id: UUID) -> Connection | None:
    # UPDATE acquires a row lock on Postgres and a write reservation on SQLite.
    # It must be the first statement in a fresh transaction on SQLite: upgrading
    # an existing read snapshot while another worker commits can fail/busy-loop.
    await session.execute(
        update(Connection).where(col(Connection.id) == connection_id).values(updated_at=Connection.updated_at)
    )
    return (
        await session.exec(
            select(Connection).where(col(Connection.id) == connection_id).execution_options(populate_existing=True)
        )
    ).first()
