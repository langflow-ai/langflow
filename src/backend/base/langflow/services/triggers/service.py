"""Trigger persistence and lifecycle.

The trigger *row* is authoritative for state, binding, pinning, and identity.
The canvas node is authoritative only for the trigger's own configuration
fields, which reconciliation copies into ``config`` on every flow save (TRG-2's
schedule reconciler). That split is what lets a pinned trigger keep firing the
pinned version while its cron expression still tracks the canvas.

Authorization is deliberately NOT here: triggers ride the flow resource, and the
API layer holds the ``ensure_flow_permission`` calls so every guard is visible
next to the route it protects.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlmodel import col, select

from langflow.services.base import Service
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.trigger.model import Trigger
from langflow.services.database.models.trigger.schemas import (
    TriggerCreate,
    TriggerState,
    TriggerUpdate,
)
from langflow.services.triggers.errors import TriggerNotFoundError

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

#: Only these states are re-armable by ``enable``. ``dead`` is terminal: a dead
#: trigger is re-created, not resurrected, so the audit trail stays truthful.
_ENABLEABLE_STATES = frozenset(
    {
        TriggerState.PENDING.value,
        TriggerState.ACTIVE.value,
        TriggerState.PAUSED.value,
        TriggerState.ERROR.value,
        TriggerState.EXPIRED.value,
        TriggerState.NEEDS_RECONNECT.value,
    }
)


class TriggerService(Service):
    """Data access for the ``trigger`` table."""

    name = "triggers_service"

    def __init__(self) -> None:
        self.set_ready()

    async def get(self, session: AsyncSession, trigger_id: UUID) -> Trigger:
        row = await session.get(Trigger, trigger_id)
        if row is None:
            raise TriggerNotFoundError(str(trigger_id))
        return row

    async def list_for_flows(
        self,
        session: AsyncSession,
        *,
        flow_ids: list[UUID],
        limit: int = 100,
        offset: int = 0,
    ) -> list[Trigger]:
        """List triggers on the given flows, newest first.

        An empty ``flow_ids`` returns an empty list without touching the
        database: a caller with no visible flows must not fall through to an
        unfiltered scan.
        """
        if not flow_ids:
            return []
        statement = (
            select(Trigger)
            .where(col(Trigger.flow_id).in_(flow_ids))
            .order_by(col(Trigger.created_at).desc(), col(Trigger.id).desc())
            .offset(offset)
            .limit(limit)
        )
        return list((await session.exec(statement)).all())

    async def list_active(self, session: AsyncSession, *, kind: str | None = None) -> list[Trigger]:
        """Every armed trigger, optionally narrowed to one kind.

        Used by the schedule tick producer; kept here so the dispatcher never
        writes its own trigger queries.
        """
        statement = select(Trigger).where(Trigger.state == TriggerState.ACTIVE.value)
        if kind is not None:
            statement = statement.where(Trigger.kind == kind)
        return list((await session.exec(statement)).all())

    async def get_by_node(self, session: AsyncSession, *, flow_id: UUID, node_id: str) -> Trigger | None:
        statement = select(Trigger).where(Trigger.flow_id == flow_id, Trigger.node_id == node_id)
        return (await session.exec(statement)).first()

    async def create(self, session: AsyncSession, *, payload: TriggerCreate, owner_id: UUID) -> Trigger:
        row = Trigger(
            flow_id=payload.flow_id,
            user_id=owner_id,
            name=payload.name,
            kind=payload.kind,
            provider=payload.provider,
            node_id=payload.node_id,
            connection_id=payload.connection_id,
            config=payload.config,
            provider_state={},
            state=payload.state.value,
            binding_target=payload.binding_target.value,
            deployment_id=payload.deployment_id,
            flow_version_id=payload.flow_version_id,
            session_policy=payload.session_policy.value,
            concurrency_limit=payload.concurrency_limit,
            max_attempts=payload.max_attempts,
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row

    async def update(self, session: AsyncSession, *, row: Trigger, payload: TriggerUpdate) -> Trigger:
        """Apply a partial update. Unset fields are left alone.

        ``exclude_unset`` (not ``exclude_none``) is the whole point: it is how a
        caller clears ``connection_id`` or unpins ``flow_version_id`` by sending
        an explicit null, without every other omitted field being nulled too.
        """
        changes = payload.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(row, field, value.value if hasattr(value, "value") else value)
        row.updated_at = datetime.now(timezone.utc)
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row

    async def set_state(self, session: AsyncSession, *, row: Trigger, state: TriggerState) -> Trigger:
        row.state = state.value
        if state is not TriggerState.ERROR:
            row.last_error = None
        row.updated_at = datetime.now(timezone.utc)
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row

    async def enable(self, session: AsyncSession, *, row: Trigger) -> Trigger:
        if row.state not in _ENABLEABLE_STATES:
            msg = f"Trigger in state {row.state!r} cannot be enabled."
            raise ValueError(msg)
        # Clear the schedule cursor so the tick producer recomputes the next fire
        # from now rather than replaying every tick missed while paused.
        row.next_fire_at = None
        return await self.set_state(session, row=row, state=TriggerState.ACTIVE)

    async def disable(self, session: AsyncSession, *, row: Trigger) -> Trigger:
        return await self.set_state(session, row=row, state=TriggerState.PAUSED)

    async def pin(self, session: AsyncSession, *, row: Trigger, flow_version_id: UUID | None) -> Trigger:
        """Pin the trigger to a flow version, or unpin with ``None``."""
        row.flow_version_id = flow_version_id
        row.updated_at = datetime.now(timezone.utc)
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row

    async def delete(self, session: AsyncSession, *, row: Trigger) -> None:
        await session.delete(row)
        await session.flush()

    async def record_error(self, session: AsyncSession, *, row: Trigger, message: str) -> Trigger:
        row.last_error = message
        row.state = TriggerState.ERROR.value
        row.updated_at = datetime.now(timezone.utc)
        session.add(row)
        await session.flush()
        return row

    @staticmethod
    async def get_flow(session: AsyncSession, flow_id: UUID) -> Flow | None:
        return await session.get(Flow, flow_id)
