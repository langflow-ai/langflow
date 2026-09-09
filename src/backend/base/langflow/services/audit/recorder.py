"""Writing an audit row, without ever costing the write it describes.

Two rules shape this module. A write must never fail because its audit row
failed — the record is worth less than the work it describes. And the allowlist
is enforced *here*, not in each producer: a careless caller must not be able to
put a field value, a graph fragment or a secret into the row.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

from lfx.log import logger
from lfx.services.session import NoopSession

from langflow.services.audit.events import resource_type_of
from langflow.services.database.models.audit_log.model import AuditLog
from langflow.services.deps import get_settings_service, session_scope

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

# The only keys a row may carry. Anything else is dropped before the insert, so
# no producer can widen the contract by accident.
ALLOWED_PAYLOAD_KEYS = frozenset(
    {
        "changes",
        "changes_total",
        "reason",
        "error_class",
        "duration_ms",
        "api_key_id",
        "client_ip",
        "user_agent",
        "version_id",
    }
)


# A refused save records itself in its own transaction, so a burst of refusals
# would otherwise ask the connection pool for one session each — at the exact
# moment the pool is already carrying that burst's own requests. Measured: 120
# simultaneous conflicting saves on one replica exhausted the pool and cost the
# deployment 401s on unrelated requests. This bounds the feature's footprint to
# a handful of connections; a refusal that cannot get a slot quickly drops its
# row rather than delaying the 409 the client is waiting for.
MAX_CONCURRENT_INDEPENDENT_WRITES = 4
INDEPENDENT_WRITE_TIMEOUT_SECONDS = 2.0

_write_slots: asyncio.Semaphore | None = None
_write_slots_loop: asyncio.AbstractEventLoop | None = None


def _slots() -> asyncio.Semaphore:
    """The semaphore for this event loop, rebuilt if the loop changed.

    A module-level semaphore belongs to the loop that created it; a second loop
    (a worker, a test) must not inherit one bound elsewhere.
    """
    global _write_slots, _write_slots_loop  # noqa: PLW0603
    loop = asyncio.get_running_loop()
    if _write_slots is None or _write_slots_loop is not loop:
        _write_slots = asyncio.Semaphore(MAX_CONCURRENT_INDEPENDENT_WRITES)
        _write_slots_loop = loop
    return _write_slots


def is_enabled() -> bool:
    return bool(get_settings_service().settings.audit_enabled)


def _allowed(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    # An operator who turns anonymization on wants who/what/when and nothing
    # else, so the payload is dropped before it is ever built into a row.
    if not payload or get_settings_service().settings.audit_anonymize_payload:
        return None
    kept = {key: value for key, value in payload.items() if key in ALLOWED_PAYLOAD_KEYS and value is not None}
    if not kept:
        return None
    # Proven serialisable here rather than at the caller's flush. A JSON column
    # is encoded when the transaction is written, so a value json cannot handle
    # would raise inside the caller's commit — turning a bad audit payload into
    # a failed user save.
    try:
        json.dumps(kept)
    except (TypeError, ValueError):
        return {"changes_total": kept.get("changes_total")} if isinstance(kept.get("changes_total"), int) else None
    return kept


def _has_database(session: AsyncSession) -> bool:
    """False under ``lfx serve``, which is stateless and has no database.

    Checked explicitly rather than relying on ``NoopSession`` silently absorbing
    the insert: a no-op that happens by accident is one refactor away from
    becoming an exception on a request path.
    """
    return not isinstance(session, NoopSession)


async def record_audit_event_independently(
    *,
    event: str,
    user_id: UUID | None = None,
    resource_id: UUID | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """Record an attempt that is about to fail, in its own transaction.

    A refused save raises, and raising rolls the request's transaction back —
    taking the row describing the refusal with it. The record that matters most
    in an investigation is exactly the one the caller's rollback would erase, so
    it is committed separately.
    """
    if not is_enabled():
        return

    try:
        async with asyncio.timeout(INDEPENDENT_WRITE_TIMEOUT_SECONDS), _slots(), session_scope() as scoped:
            await record_audit_event(
                scoped,
                event=event,
                user_id=user_id,
                resource_id=resource_id,
                payload=payload,
            )
    except Exception as exc:  # noqa: BLE001
        await logger.awarning(
            "op=record_audit_event_independently event=%s resource_id=%s outcome=dropped error=%s",
            event,
            resource_id,
            type(exc).__name__,
        )


async def record_audit_event(
    session: AsyncSession,
    *,
    event: str,
    user_id: UUID | None = None,
    resource_id: UUID | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """Record one attempt, or do nothing at all.

    Never raises: the caller is in the middle of a write that has already been
    accepted, and losing the description of an action must not lose the action.
    """
    if not is_enabled() or not _has_database(session):
        return

    try:
        row = AuditLog(
            event=event,
            user_id=user_id,
            resource_type=resource_type_of(event),
            resource_id=resource_id,
            payload=_allowed(payload),
        )
        # Written inside a savepoint, and flushed now rather than left staged for
        # the caller's commit. ``session.add`` only stages: a row the database
        # rejects would otherwise raise inside the caller's flush and fail the
        # write this row merely describes. The savepoint confines that to itself.
        async with session.begin_nested():
            session.add(row)
            await session.flush()
    except Exception as exc:  # noqa: BLE001
        # Named, because a bare warning here would hide a real defect behind a
        # log line that says only that something went wrong.
        await logger.awarning(
            "op=record_audit_event event=%s resource_id=%s outcome=dropped error=%s",
            event,
            resource_id,
            type(exc).__name__,
        )
