"""Serialize lifecycle decisions against the latest persisted trigger state."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

from lfx.integrations.models import ConnectionRef
from sqlalchemy import false
from sqlmodel import select, update

from langflow.services.database.models.connection.model import Connection
from langflow.services.database.models.trigger.model import Trigger
from langflow.services.triggers.ownership import TriggerConnectionNotOwnedError
from langflow.services.triggers.source_errors import SourceConfigurationError

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


async def lock_trigger_for_admission(session: AsyncSession, trigger_id: UUID) -> tuple[Trigger | None, frozenset[UUID]]:
    """Lock connection parents before a trigger may insert subscription children.

    Both the persisted binding and the canvas handle can name a parent. Discover
    them before taking the trigger lock, then reject a concurrent rebind rather
    than acquiring a new parent while already holding its child. Operator resume
    uses the same order before checking eligibility; repeated acquisition in
    enable is safe because a resolved handle's locked parent cannot be replaced.
    """
    from langflow.services.connection.oauth.locking import lock_connection

    if session.get_bind().dialect.name == "sqlite":
        # Reserve SQLite's writer without locking/mutating an individual child
        # before discovering its parents. PostgreSQL needs no equivalent write.
        await session.exec(
            update(Connection)
            .where(false())
            .values(updated_at=Connection.updated_at)
            .execution_options(synchronize_session=False)
        )
    snapshot = (
        await session.exec(
            select(
                Trigger.connection_id, Trigger.flow_id, Trigger.user_id, Trigger.kind, Trigger.provider, Trigger.config
            ).where(Trigger.id == trigger_id)
        )
    ).first()
    if snapshot is None:
        return None, frozenset()
    expected = (*snapshot[:-1], deepcopy(snapshot.config or {}))
    connection_ids = {snapshot.connection_id} if snapshot.connection_id is not None else set()
    if "." in snapshot.kind:
        try:
            ref = ConnectionRef.parse((snapshot.config or {}).get("connection"))
        except ValueError:
            pass  # The source validator retains its existing configuration error.
        else:
            identifier = (
                await session.exec(
                    select(Connection.id).where(
                        Connection.ownership_mode == "user",
                        Connection.owner_id == snapshot.user_id,
                        Connection.provider_key == ref.provider,
                        Connection.name == ref.name,
                    )
                )
            ).first()
            if identifier is None:
                raise TriggerConnectionNotOwnedError
            connection_ids.add(identifier)
    locked = set()
    for identifier in sorted(connection_ids, key=str):
        if await lock_connection(session, identifier) is not None:
            locked.add(identifier)
    current = await lock_trigger(session, trigger_id)
    if (
        current is not None
        and (
            current.connection_id,
            current.flow_id,
            current.user_id,
            current.kind,
            current.provider,
            current.config or {},
        )
        != expected
    ):
        msg = "The source settings or connection changed while enabling. Try again."
        raise SourceConfigurationError(msg)
    return current, frozenset(locked)
