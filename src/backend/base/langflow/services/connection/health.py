"""Persist provider credential rejection without overwriting a concurrent reconnect."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from langflow.services.connection.oauth.locking import lock_connection
from langflow.services.database.models.connection.schemas import ConnectionHealth, PersistedConnectionStatus

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


async def mark_credential_rejected(
    session: AsyncSession, *, connection_id: UUID, observed_updated_at: datetime | None
) -> bool:
    """Expire only the connection generation whose credential the provider rejected."""
    row = await lock_connection(session, connection_id)

    def utc(value: datetime | None) -> datetime | None:
        return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value

    if row is None or observed_updated_at is None or utc(row.updated_at) != utc(observed_updated_at):
        return False
    if row.status != PersistedConnectionStatus.READY.value:
        return False
    row.status = PersistedConnectionStatus.EXPIRED.value
    row.status_reason = None
    row.health = ConnectionHealth.UNHEALTHY.value
    row.health_checked_at = datetime.now(timezone.utc)
    session.add(row)
    await session.flush()
    return True
