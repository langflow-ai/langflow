"""Keep long trigger operations owned, and cancel work when ownership is lost."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import TYPE_CHECKING, TypeVar

from sqlmodel import update

from langflow.services.database.models.trigger.model import TriggerLease
from langflow.services.deps import session_scope
from langflow.services.triggers import leases

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

T = TypeVar("T")


class LeaseLostError(RuntimeError):
    """The operation must stop before making any more durable changes."""


async def run_guarded(
    work: Awaitable[T],
    *,
    name: str,
    owner: str,
    ttl_s: float,
    heartbeat: Callable[..., Awaitable[None]] | None = None,
) -> T:
    """Run under an already-acquired lease, renewing it independently of work.

    Renewal never re-acquires an expired lease. A stalled database or changed
    owner cancels the work, including its open database transaction.
    """

    async def renew():
        async with session_scope() as session:
            now = leases._now()  # noqa: SLF001 - share the lease clock
            result = await session.exec(
                update(TriggerLease)
                .where(TriggerLease.name == name, TriggerLease.owner == owner, TriggerLease.expires_at > now)
                .values(heartbeat_at=now, expires_at=now + timedelta(seconds=ttl_s))
            )
            if result.rowcount != 1:
                msg = "Trigger operation lost its lease."
                raise LeaseLostError(msg)
            if heartbeat is not None:
                await heartbeat(session, now=now, ttl_s=ttl_s)

    task = asyncio.ensure_future(work)
    interval = ttl_s / 3
    try:
        while True:
            done, _ = await asyncio.wait({task}, timeout=interval)
            if done:
                return task.result()
            try:
                await asyncio.wait_for(renew(), timeout=interval)
            except LeaseLostError:
                raise
            except Exception as exc:
                msg = "Trigger operation could not renew its lease."
                raise LeaseLostError(msg) from exc
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
