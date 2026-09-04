"""Batched audit pipeline for authorization decisions.

An earlier revision did ``asyncio.create_task(_write())`` per authorization
decision, with each write opening its own ``session_scope()``. That works on
light traffic, but on a real workload (every authenticated request emits at
least one audit row) it turns into a connection-pool storm.

This module routes every decision through a bounded queue drained by a
single long-lived writer task. The writer batches up to ``_AUDIT_BATCH_MAX``
rows per ``session_scope()`` and commits them in one INSERT. By default,
``audit_decision`` remains best effort and non-blocking. Operators that need
delivery guarantees can opt into durable mode: the bounded queue then applies
backpressure and the call returns only after its row's batch commits.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from lfx.log.logger import logger

from langflow.services.auth.context import (
    AUTH_METHOD_API_KEY,
    current_auth_context_for_audit,
    get_current_auth_context,
)
from langflow.services.deps import get_settings_service

if TYPE_CHECKING:
    from lfx.services.authorization import AuthorizationPrincipal
    from sqlmodel.ext.asyncio.session import AsyncSession

# Shared audit result vocabulary.
AUDIT_ALLOW = "allow"
AUDIT_DENY = "deny"
AUDIT_OWNER_OVERRIDE = "owner_override"
AUDIT_SKIP = "skip"

AUDIT_ACTOR_API_KEY = "api_key"  # pragma: allowlist secret
AUDIT_ACTOR_UNKNOWN = "unknown"
AUDIT_ACTOR_USER = "user"

# ``details["event"]`` discriminates the two row classes that share this table.
# Guards emit a row for every authorization *decision* they make; routes emit a
# second row after the effect is durable. Both used to be written under the same
# action name (``share:create`` for the check and for the created share), so a
# check and a real mutation were indistinguishable downstream. Readers that need
# "what actually happened" filter on ``AUDIT_EVENT_MUTATION``.
AUDIT_EVENT_DECISION = "authorization_decision"
AUDIT_EVENT_MUTATION = "mutation"
# Two further classes exist so that *every* row can be classified. Without them
# a reader filtering on ``event`` silently drops the untagged rows: reading the
# audit log itself, and the reconcile the server runs at startup with no user
# behind it. ``access`` is something a user did that changed nothing; ``system``
# is something the server did on its own.
AUDIT_EVENT_ACCESS = "access"
AUDIT_EVENT_SYSTEM = "system"

_AUDIT_QUEUE_MAX = 10_000
_AUDIT_BATCH_MAX = 100

# Minimum seconds between drop warnings while saturation persists.
_AUDIT_DROP_WARN_INTERVAL = 10.0


class AuditPersistenceError(RuntimeError):
    """A durable audit decision could not be committed to the database.

    The message is deliberately fixed so database errors and credentials are
    never reflected into an API response. Operators can use the bounded
    producer-health failure code for diagnosis.
    """

    def __init__(self) -> None:
        super().__init__("Durable authorization audit persistence failed")


def _split_obj(obj: str) -> tuple[str | None, UUID | None]:
    """Parse an authz obj key like 'flow:abc' into (resource_type, resource_id).

    Wildcards (``flow:*``) and unparseable ids return None for ``resource_id``
    so audit rows are still written with the right ``resource_type``.
    """
    if ":" not in obj:
        return None, None
    resource_type, _, suffix = obj.partition(":")
    if not suffix or suffix == "*":
        return resource_type, None
    try:
        return resource_type, UUID(suffix)
    except (ValueError, TypeError):
        return resource_type, None


def _coerce_uuid(value: Any) -> UUID | None:
    """Return a UUID for trusted or string-like input without raising."""
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def _resolve_actor(
    user_id: UUID | None,
    principal: AuthorizationPrincipal | None = None,
) -> tuple[UUID | None, str, UUID | None]:
    """Derive durable actor identity from the request credential and owner user."""
    if principal is not None:
        return _coerce_uuid(principal.user_id), principal.actor_type, _coerce_uuid(principal.actor_id)
    resolved_user_id = _coerce_uuid(user_id)
    auth_context = get_current_auth_context()
    if resolved_user_id is not None and auth_context is not None and auth_context.method == AUTH_METHOD_API_KEY:
        return resolved_user_id, AUDIT_ACTOR_API_KEY, _coerce_uuid(auth_context.api_key_id)
    if resolved_user_id is not None:
        return resolved_user_id, AUDIT_ACTOR_USER, resolved_user_id
    return None, AUDIT_ACTOR_UNKNOWN, None


def _merge_audit_details(
    details: dict[str, Any] | None,
    *,
    include_credential: bool,
) -> dict[str, Any] | None:
    """Merge request credential metadata centrally while preserving caller details."""
    credential_details = current_auth_context_for_audit() if include_credential else {}
    if details is None and not credential_details:
        return details
    merged = {**(details or {}), **credential_details}
    # These names are reserved for the first-class columns. Keeping caller
    # values in JSON as well would create a second, spoofable actor identity.
    merged.pop("actor_type", None)
    merged.pop("actor_id", None)
    return merged


class _AuditEntry:
    """One pending audit row.

    A plain class (not a dataclass) so it can be instantiated cheaply from the
    request path without dataclass overhead. The fields mirror
    ``AuthzAuditLog`` columns plus the raw ``obj`` string — the writer splits
    ``obj`` into ``(resource_type, resource_id)`` once per batch.
    """

    __slots__ = (
        "action",
        "actor_id",
        "actor_type",
        "details",
        "event_id",
        "obj",
        "occurred_at",
        "result",
        "user_id",
    )

    def __init__(
        self,
        *,
        user_id: UUID | None,
        actor_type: str,
        actor_id: UUID | None,
        action: str,
        obj: str,
        result: str,
        details: dict[str, Any] | None,
        event_id: UUID | None = None,
        occurred_at: datetime | None = None,
    ) -> None:
        self.user_id = user_id
        self.actor_type = actor_type
        self.actor_id = actor_id
        self.action = action
        self.obj = obj
        self.result = result
        self.details = details
        # Identity and event time are assigned before enqueue. This makes a
        # queued decision stable across batching delays and provides the seam
        # needed for idempotent downstream delivery.
        self.event_id = event_id or uuid4()
        self.occurred_at = occurred_at or datetime.now(timezone.utc)


class _AuditEnvelope:
    """Queue item with an optional durable commit acknowledgement."""

    __slots__ = ("ack", "entry", "terminal")

    def __init__(self, entry: _AuditEntry, ack: asyncio.Future[None] | None = None) -> None:
        self.entry = entry
        self.ack = ack
        self.terminal = False


# Module-level state. Bound to whichever event loop is running when the first
# ``audit_decision`` call happens. ``_audit_queue_loop`` lets us detect a fresh
# loop (e.g. between pytest test cases) and restart the writer in the new loop
# instead of writing to a queue tied to a dead loop.
_audit_queue: asyncio.Queue[_AuditEnvelope] | None = None
_audit_queue_loop: asyncio.AbstractEventLoop | None = None
_audit_writer_task: asyncio.Task[None] | None = None
_audit_inflight: tuple[_AuditEnvelope, ...] = ()
_audit_accepting: bool = True
_audit_capacity_waiters: set[asyncio.Future[None]] = set()
_audit_dropped_count: int = 0
_audit_last_drop_warn: float = 0.0
_audit_submitted_count: int = 0
_audit_persisted_count: int = 0
_audit_failed_count: int = 0
_audit_last_failure_code: str | None = None
# Kept as a vestigial public name for backward compatibility with downstream
# callers (and the existing drain helper). The new pipeline tracks the single
# writer task here so ``drain_pending_audit_writes`` can await it.
_pending_audit_tasks: set[asyncio.Task[None]] = set()


def _consume_ack_exception(future: asyncio.Future[None]) -> None:
    """Retrieve a detached acknowledgement exception after caller cancellation."""
    if not future.cancelled():
        future.exception()


def _complete_persisted(batch: list[_AuditEnvelope]) -> None:
    """Mark each previously accepted envelope durably committed exactly once."""
    global _audit_persisted_count, _audit_last_failure_code  # noqa: PLW0603

    for envelope in batch:
        if envelope.terminal:
            continue
        envelope.terminal = True
        _audit_persisted_count += 1
        if envelope.ack is not None and not envelope.ack.done():
            envelope.ack.set_result(None)
    _audit_last_failure_code = None


def _complete_failed(batch: list[_AuditEnvelope] | tuple[_AuditEnvelope, ...], code: str) -> None:
    """Give accepted envelopes a terminal, sanitized persistence failure."""
    global _audit_failed_count, _audit_last_failure_code  # noqa: PLW0603

    safe_code = code[:64]
    failed_any = False
    for envelope in batch:
        if envelope.terminal:
            continue
        envelope.terminal = True
        failed_any = True
        _audit_failed_count += 1
        if envelope.ack is not None and not envelope.ack.done():
            envelope.ack.set_exception(AuditPersistenceError())
    if failed_any:
        _audit_last_failure_code = safe_code


def _release_capacity_waiters() -> None:
    """Wake blocked durable producers after the writer frees queue capacity."""
    for waiter in tuple(_audit_capacity_waiters):
        if not waiter.done():
            waiter.set_result(None)


def _fail_capacity_waiters(code: str) -> None:
    """Give every producer blocked before admission a sanitized terminal error."""
    global _audit_last_failure_code  # noqa: PLW0603

    failed_any = False
    for waiter in tuple(_audit_capacity_waiters):
        if not waiter.done():
            failed_any = True
            waiter.set_exception(AuditPersistenceError())
    if failed_any:
        _audit_last_failure_code = code[:64]


def _discard_closed_loop_pipeline() -> None:
    """Drop unreachable state after its owning event loop has closed.

    Futures owned by a closed loop cannot be completed safely. No caller can
    still make progress on that loop, so account for accepted work as failed,
    discard references, and let the next live loop build a fresh pipeline.
    """
    global _audit_accepting, _audit_failed_count, _audit_inflight  # noqa: PLW0603
    global _audit_last_failure_code, _audit_queue, _audit_queue_loop, _audit_writer_task  # noqa: PLW0603

    abandoned = sum(not envelope.terminal for envelope in _audit_inflight)
    if _audit_queue is not None:
        abandoned += _audit_queue.qsize()
    if abandoned:
        _audit_failed_count += abandoned
        _audit_last_failure_code = "loop_replaced"
    _audit_queue = None
    _audit_queue_loop = None
    _audit_writer_task = None
    _audit_inflight = ()
    _audit_accepting = False
    _audit_capacity_waiters.clear()
    _pending_audit_tasks.clear()


def _fail_queued_entries(queue: asyncio.Queue[_AuditEnvelope], code: str) -> None:
    """Remove and terminally fail all entries left behind by a stopped writer."""
    while True:
        try:
            envelope = queue.get_nowait()
        except asyncio.QueueEmpty:
            return
        _complete_failed([envelope], code)
        queue.task_done()


def _audit_writer_finished(task: asyncio.Task[None]) -> None:
    """Fail accepted work if the writer exits outside the controlled shutdown path."""
    _pending_audit_tasks.discard(task)
    if task is not _audit_writer_task or not _audit_accepting:
        return

    code = "writer_stopped"
    if not task.cancelled():
        error = task.exception()
        if error is not None:
            code = type(error).__name__
    _complete_failed(_audit_inflight, code)
    if _audit_queue is not None:
        _fail_queued_entries(_audit_queue, code)
    _fail_capacity_waiters(code)


async def _admit_durable(queue: asyncio.Queue[_AuditEnvelope], envelope: _AuditEnvelope) -> None:
    """Atomically admit one durable entry or reject it when shutdown closes admission."""
    global _audit_last_failure_code, _audit_submitted_count  # noqa: PLW0603

    loop = asyncio.get_running_loop()
    while True:
        writer = _audit_writer_task
        if not _audit_accepting or writer is None or writer.done():
            _audit_last_failure_code = "writer_stopped"
            raise AuditPersistenceError
        try:
            # There is no await between the admission check and put_nowait, so
            # shutdown cannot interleave on this event loop and sweep too soon.
            queue.put_nowait(envelope)
        except asyncio.QueueFull:
            waiter: asyncio.Future[None] = loop.create_future()
            waiter.add_done_callback(_consume_ack_exception)
            _audit_capacity_waiters.add(waiter)
            try:
                await waiter
            finally:
                _audit_capacity_waiters.discard(waiter)
            continue
        _audit_submitted_count += 1
        return


def _ensure_audit_writer_started() -> asyncio.Queue[_AuditEnvelope] | None:
    """Lazily start the audit writer task in the current event loop.

    Returns the queue, or ``None`` if no event loop is running (audit is
    skipped entirely in that case — there's no place to schedule the writer).
    """
    global _audit_accepting, _audit_inflight, _audit_queue, _audit_queue_loop, _audit_writer_task  # noqa: PLW0603

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return None

    if _audit_queue_loop is not None and _audit_queue_loop is not loop:
        if not _audit_queue_loop.is_closed():
            # The module-level producer is intentionally single-loop. Refuse a
            # concurrent second loop without mutating the live owner's state.
            global _audit_last_failure_code  # noqa: PLW0603

            _audit_last_failure_code = "loop_mismatch"
            return None
        _discard_closed_loop_pipeline()

    # A fresh event loop replaces the previous queue+writer. Without this,
    # a subsequent ``audit_decision`` call (e.g. in a new pytest test) would
    # ``put_nowait`` into a queue that no live task is consuming.
    if _audit_queue_loop is not loop:
        _audit_queue = asyncio.Queue(maxsize=_AUDIT_QUEUE_MAX)
        _audit_queue_loop = loop
        _audit_writer_task = None
        _audit_inflight = ()
        _audit_accepting = True
        _audit_capacity_waiters.clear()
        _pending_audit_tasks.clear()

    if _audit_writer_task is None or _audit_writer_task.done():
        _audit_writer_task = loop.create_task(_audit_writer_loop())
        _pending_audit_tasks.add(_audit_writer_task)
        _audit_writer_task.add_done_callback(_audit_writer_finished)

    return _audit_queue


async def _audit_writer_loop() -> None:
    """Drain the audit queue and write batches to the DB.

    Loops until cancelled. Each iteration blocks on the first row, then greedily
    pulls everything else already enqueued up to ``_AUDIT_BATCH_MAX`` and
    commits them as a single batch insert. In best-effort mode DB exceptions
    remain asynchronous; in durable mode the affected callers receive a fixed,
    sanitized ``AuditPersistenceError``.
    """
    global _audit_inflight  # noqa: PLW0603

    while True:
        queue = _audit_queue
        if queue is None:
            return
        try:
            first = await queue.get()
        except asyncio.CancelledError:
            return

        batch: list[_AuditEnvelope] = [first]
        try:
            while len(batch) < _AUDIT_BATCH_MAX:
                batch.append(queue.get_nowait())
        except asyncio.QueueEmpty:
            pass
        _release_capacity_waiters()

        try:
            _audit_inflight = tuple(batch)
            await _flush_audit_batch([envelope.entry for envelope in batch])
        except asyncio.CancelledError:
            _complete_failed(batch, "writer_stopped")
            return
        except Exception as exc:  # noqa: BLE001 — never let the writer die quietly
            # Never log the exception value: database URLs and driver errors
            # can contain credentials. The class name is enough for a bounded
            # operator signal and is safe to expose through producer health.
            failure_code = type(exc).__name__
            logger.error(
                "Authz audit writer batch flush failed for %d row(s) (%s)",
                len(batch),
                failure_code,
            )
            _complete_failed(batch, failure_code)
        except BaseException as exc:
            # System-level task termination is re-raised after accepted work
            # receives a terminal failure. The done callback then fails work
            # that was still queued behind this batch.
            _complete_failed(batch, type(exc).__name__)
            raise
        else:
            _complete_persisted(batch)
        finally:
            for _ in batch:
                queue.task_done()
            _audit_inflight = ()


async def _flush_audit_batch(batch: list[_AuditEntry]) -> None:
    """Insert a batch of ``_AuditEntry`` rows in a single session."""
    if not batch:
        return
    from langflow.services.deps import session_scope

    async with session_scope() as session:
        _stage_audit_entries(session, batch)


def _stage_audit_entries(session: AsyncSession, entries: list[_AuditEntry]) -> None:
    """Add audit rows and plugin events to an existing transaction."""
    # Imported lazily so callers with auditing disabled do not pull DB models.
    from lfx.services.authorization import AuthorizationAuditEvent

    from langflow.services.database.models.auth import AuthzAuditLog
    from langflow.services.deps import get_authorization_service

    events: list[AuthorizationAuditEvent] = []
    for entry in entries:
        resource_type, resource_id = _split_obj(entry.obj)
        session.add(
            AuthzAuditLog(
                id=entry.event_id,
                timestamp=entry.occurred_at,
                user_id=entry.user_id,
                actor_type=entry.actor_type,
                actor_id=entry.actor_id,
                action=entry.action,
                resource_type=resource_type,
                resource_id=resource_id,
                result=entry.result,
                details=entry.details,
            )
        )
        events.append(
            AuthorizationAuditEvent(
                event_id=entry.event_id,
                occurred_at=entry.occurred_at,
            )
        )
    get_authorization_service().stage_audit_events(session=session, events=tuple(events))


def stage_audit_decision(
    *,
    session: AsyncSession,
    user_id: UUID | None,
    principal: AuthorizationPrincipal | None = None,
    action: str,
    obj: str,
    result: str,
    details: dict[str, Any] | None = None,
) -> bool:
    """Stage a durable audit row in a caller-owned mutation transaction.

    Returns ``True`` when the row was staged. Best-effort mode returns ``False``
    so the caller can submit through the asynchronous audit pipeline after its
    mutation commits.
    """
    auth_settings = get_settings_service().auth_settings
    if not getattr(auth_settings, "AUTHZ_AUDIT_ENABLED", False) or not getattr(
        auth_settings, "AUTHZ_AUDIT_DURABLE", False
    ):
        return False

    resolved_user_id, actor_type, actor_id = _resolve_actor(user_id, principal)
    entry = _AuditEntry(
        user_id=resolved_user_id,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        obj=obj,
        result=result,
        details=_merge_audit_details(details, include_credential=resolved_user_id is not None),
    )
    _stage_audit_entries(session, [entry])
    return True


async def drain_pending_audit_writes(timeout: float = 5.0) -> None:
    """Flush the audit queue and stop the writer (bounded by ``timeout``).

    Safe to call multiple times; safe to call when no audit traffic has run.
    Splits the timeout between draining the queue and awaiting writer
    cancellation so neither side can hang shutdown indefinitely.
    """
    global _audit_accepting, _audit_queue_loop, _audit_writer_task  # noqa: PLW0603

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if _audit_queue_loop is not None and _audit_queue_loop is not loop:
        if _audit_queue_loop.is_closed():
            _discard_closed_loop_pipeline()
        else:
            global _audit_last_failure_code  # noqa: PLW0603

            _audit_last_failure_code = "loop_mismatch"
        return

    _audit_accepting = False
    _fail_capacity_waiters("writer_stopped")

    queue = _audit_queue
    writer = _audit_writer_task
    if queue is None:
        # Closing admission must be owned by this loop even when lazy startup
        # never created a queue. The same-loop durable guard can then keep the
        # idle pipeline terminal while a later, genuinely new loop replaces it.
        _audit_queue_loop = loop
        return
    if writer is None:
        _fail_queued_entries(queue, "writer_stopped")
        return

    drain_budget = max(0.1, timeout * 0.8)
    cancel_budget = max(0.1, timeout - drain_budget)

    try:
        await asyncio.wait_for(queue.join(), timeout=drain_budget)
    except asyncio.TimeoutError:
        logger.warning(
            "drain_pending_audit_writes timed out after %.2fs with %d row(s) pending",
            drain_budget,
            queue.qsize(),
        )

    if not writer.done():
        writer.cancel()
        from contextlib import suppress

        with suppress(asyncio.CancelledError, asyncio.TimeoutError):
            await asyncio.wait_for(writer, timeout=cancel_budget)

    _complete_failed(_audit_inflight, "writer_stopped")
    _fail_queued_entries(queue, "writer_stopped")
    _fail_capacity_waiters("writer_stopped")

    _pending_audit_tasks.discard(writer)
    _audit_writer_task = None


async def audit_decision(
    *,
    user_id: UUID | None,
    principal: AuthorizationPrincipal | None = None,
    action: str,
    obj: str,
    result: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Submit an AuthzAuditLog row to the batched database writer.

    Legacy mode is best effort and non-blocking: saturation drops the row with
    a time-bounded warning. With ``AUTHZ_AUDIT_DURABLE=True``, bounded queue
    capacity backpressures the caller and return means the database batch has
    committed. Audit is fully bypassed when ``AUTHZ_AUDIT_ENABLED=False``.
    """
    global _audit_dropped_count, _audit_last_drop_warn, _audit_last_failure_code, _audit_submitted_count  # noqa: PLW0603

    settings = get_settings_service()
    auth_settings = settings.auth_settings
    # Audit is independent of enforcement. ``AuthSettings.AUTHZ_AUDIT_ENABLED``
    # defaults to ``False`` (see lfx/services/settings/auth.py) because the
    # background writer still consumes a DB connection; operators opt in.
    if not getattr(auth_settings, "AUTHZ_AUDIT_ENABLED", False):
        return

    durable = bool(getattr(auth_settings, "AUTHZ_AUDIT_DURABLE", False))
    # A completed same-loop drain is terminal. Reject before the lazy starter
    # can create an idle replacement writer; a genuinely new event loop still
    # flows through ``_ensure_audit_writer_started`` and replaces the closed
    # loop's pipeline below.
    if durable and _audit_queue_loop is asyncio.get_running_loop() and not _audit_accepting:
        _audit_last_failure_code = "writer_stopped"
        raise AuditPersistenceError
    queue = _ensure_audit_writer_started()
    if queue is None:
        if durable:
            _audit_last_failure_code = "writer_unavailable"
            raise AuditPersistenceError
        return
    if durable and not _audit_accepting:
        _audit_last_failure_code = "writer_stopped"
        raise AuditPersistenceError

    resolved_user_id, actor_type, actor_id = _resolve_actor(user_id, principal)
    entry = _AuditEntry(
        user_id=resolved_user_id,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        obj=obj,
        result=result,
        details=_merge_audit_details(details, include_credential=resolved_user_id is not None),
    )
    if durable:
        loop = asyncio.get_running_loop()
        ack: asyncio.Future[None] = loop.create_future()
        # A timed-out request no longer awaits this future, so consume any
        # eventual failure to avoid an unhandled-future warning. ``shield``
        # below ensures cancellation does not cancel the persistence itself.
        ack.add_done_callback(_consume_ack_exception)
        await _admit_durable(queue, _AuditEnvelope(entry, ack))
        await asyncio.shield(ack)
        return

    try:
        queue.put_nowait(_AuditEnvelope(entry))
        _audit_submitted_count += 1
    except asyncio.QueueFull:
        _audit_dropped_count += 1
        _audit_last_failure_code = "queue_full"
        # Time-based: always log the first drop, then at most once per
        # ``_AUDIT_DROP_WARN_INTERVAL`` while saturation persists. Cheaper to
        # reason about for operators than the previous every-1000th heuristic
        # (which could go minutes without a log line at low drop rates).
        now = time.monotonic()
        if _audit_dropped_count == 1 or (now - _audit_last_drop_warn) >= _AUDIT_DROP_WARN_INTERVAL:
            _audit_last_drop_warn = now
            logger.warning(
                "AuthzAuditLog queue full (%d/%d); dropped %d row(s) total. DB writer is likely behind or stalled.",
                queue.qsize(),
                _AUDIT_QUEUE_MAX,
                _audit_dropped_count,
            )


def get_audit_producer_health() -> dict[str, bool | int | str | None]:
    """Return a bounded, credential-free snapshot of the local audit producer."""
    auth_settings = get_settings_service().auth_settings
    queue = _audit_queue
    writer = _audit_writer_task
    return {
        "enabled": bool(getattr(auth_settings, "AUTHZ_AUDIT_ENABLED", False)),
        "durable": bool(getattr(auth_settings, "AUTHZ_AUDIT_DURABLE", False)),
        "active": writer is not None and not writer.done(),
        "healthy": _audit_last_failure_code is None,
        "queue_depth": queue.qsize() if queue is not None else 0,
        "queue_capacity": _AUDIT_QUEUE_MAX,
        "submitted_count": _audit_submitted_count,
        "persisted_count": _audit_persisted_count,
        "failed_count": _audit_failed_count,
        "dropped_count": _audit_dropped_count,
        "last_failure_code": _audit_last_failure_code,
    }
