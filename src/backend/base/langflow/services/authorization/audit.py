"""Batched audit pipeline for authorization decisions.

An earlier revision did ``asyncio.create_task(_write())`` per authorization
decision, with each write opening its own ``session_scope()``. That works on
light traffic, but on a real workload (every authenticated request emits at
least one audit row) it turns into a connection-pool storm.

This module routes every decision through a bounded queue drained by a
single long-lived writer task. The writer batches up to ``_AUDIT_BATCH_MAX``
rows per ``session_scope()`` and commits them in one INSERT.
``audit_decision`` stays a non-blocking ``put_nowait``: if the queue is
saturated the row is dropped (with time-based warning) so the request path
is never gated on the audit DB.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from uuid import UUID

from lfx.log.logger import logger

from langflow.services.deps import get_settings_service

# Shared audit result vocabulary.
AUDIT_ALLOW = "allow"
AUDIT_DENY = "deny"
AUDIT_OWNER_OVERRIDE = "owner_override"

_AUDIT_QUEUE_MAX = 10_000
_AUDIT_BATCH_MAX = 100

# Minimum seconds between drop warnings while saturation persists.
_AUDIT_DROP_WARN_INTERVAL = 10.0


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


class _AuditEntry:
    """One pending audit row.

    A plain class (not a dataclass) so it can be instantiated cheaply from the
    request path without dataclass overhead. The fields mirror
    ``AuthzAuditLog`` columns plus the raw ``obj`` string — the writer splits
    ``obj`` into ``(resource_type, resource_id)`` once per batch.
    """

    __slots__ = ("action", "details", "obj", "result", "user_id")

    def __init__(
        self,
        *,
        user_id: UUID | None,
        action: str,
        obj: str,
        result: str,
        details: dict[str, Any] | None,
    ) -> None:
        self.user_id = user_id
        self.action = action
        self.obj = obj
        self.result = result
        self.details = details


# Module-level state. Bound to whichever event loop is running when the first
# ``audit_decision`` call happens. ``_audit_queue_loop`` lets us detect a fresh
# loop (e.g. between pytest test cases) and restart the writer in the new loop
# instead of writing to a queue tied to a dead loop.
_audit_queue: asyncio.Queue[_AuditEntry] | None = None
_audit_queue_loop: asyncio.AbstractEventLoop | None = None
_audit_writer_task: asyncio.Task[None] | None = None
_audit_dropped_count: int = 0
_audit_last_drop_warn: float = 0.0
# Kept as a vestigial public name for backward compatibility with downstream
# callers (and the existing drain helper). The new pipeline tracks the single
# writer task here so ``drain_pending_audit_writes`` can await it.
_pending_audit_tasks: set[asyncio.Task[None]] = set()


def _ensure_audit_writer_started() -> asyncio.Queue[_AuditEntry] | None:
    """Lazily start the audit writer task in the current event loop.

    Returns the queue, or ``None`` if no event loop is running (audit is
    skipped entirely in that case — there's no place to schedule the writer).
    """
    global _audit_queue, _audit_queue_loop, _audit_writer_task  # noqa: PLW0603

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return None

    # A fresh event loop replaces the previous queue+writer. Without this,
    # a subsequent ``audit_decision`` call (e.g. in a new pytest test) would
    # ``put_nowait`` into a queue that no live task is consuming.
    if _audit_queue_loop is not loop:
        _audit_queue = asyncio.Queue(maxsize=_AUDIT_QUEUE_MAX)
        _audit_queue_loop = loop
        _audit_writer_task = None
        _pending_audit_tasks.clear()

    if _audit_writer_task is None or _audit_writer_task.done():
        _audit_writer_task = loop.create_task(_audit_writer_loop())
        _pending_audit_tasks.add(_audit_writer_task)
        _audit_writer_task.add_done_callback(_pending_audit_tasks.discard)

    return _audit_queue


async def _audit_writer_loop() -> None:
    """Drain the audit queue and write batches to the DB.

    Loops until cancelled. Each iteration blocks on the first row, then greedily
    pulls everything else already enqueued up to ``_AUDIT_BATCH_MAX`` and
    commits them as a single batch insert. DB exceptions are logged and
    swallowed — an audit-table outage must never crash the request path that
    triggered the row.
    """
    while True:
        queue = _audit_queue
        if queue is None:
            return
        try:
            first = await queue.get()
        except asyncio.CancelledError:
            return

        batch: list[_AuditEntry] = [first]
        try:
            while len(batch) < _AUDIT_BATCH_MAX:
                batch.append(queue.get_nowait())
        except asyncio.QueueEmpty:
            pass

        try:
            await _flush_audit_batch(batch)
        except Exception:  # noqa: BLE001 — never let the writer die quietly
            logger.exception("Authz audit writer batch flush failed for %d row(s)", len(batch))
        finally:
            for _ in batch:
                queue.task_done()


async def _flush_audit_batch(batch: list[_AuditEntry]) -> None:
    """Insert a batch of ``_AuditEntry`` rows in a single session."""
    if not batch:
        return
    # Imported lazily so the request path doesn't pull DB modules until the
    # writer first runs (matches the lazy import in the old per-row path).
    from langflow.services.database.models.auth import AuthzAuditLog
    from langflow.services.deps import session_scope

    async with session_scope() as session:
        for entry in batch:
            resource_type, resource_id = _split_obj(entry.obj)
            session.add(
                AuthzAuditLog(
                    user_id=entry.user_id,
                    action=entry.action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    result=entry.result,
                    details=entry.details,
                )
            )


async def drain_pending_audit_writes(timeout: float = 5.0) -> None:
    """Flush the audit queue and stop the writer (bounded by ``timeout``).

    Safe to call multiple times; safe to call when no audit traffic has run.
    Splits the timeout between draining the queue and awaiting writer
    cancellation so neither side can hang shutdown indefinitely.
    """
    global _audit_writer_task  # noqa: PLW0603

    queue = _audit_queue
    writer = _audit_writer_task
    if queue is None or writer is None:
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

        with suppress(asyncio.CancelledError):
            await asyncio.wait_for(writer, timeout=cancel_budget)

    _pending_audit_tasks.discard(writer)
    _audit_writer_task = None


async def audit_decision(
    *,
    user_id: UUID | None,
    action: str,
    obj: str,
    result: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Enqueue an AuthzAuditLog row for batched background insertion.

    Non-blocking from the caller's perspective. When the queue is saturated the
    row is dropped and a time-bounded warning is emitted so a stuck pipeline is
    operator-visible without flooding the log. Audit is fully bypassed when
    ``AUTHZ_AUDIT_ENABLED=False`` (the default).
    """
    global _audit_dropped_count, _audit_last_drop_warn  # noqa: PLW0603

    settings = get_settings_service()
    auth_settings = settings.auth_settings
    # Audit is independent of enforcement. ``AuthSettings.AUTHZ_AUDIT_ENABLED``
    # defaults to ``False`` (see lfx/services/settings/auth.py) because the
    # background writer still consumes a DB connection; operators opt in.
    if not getattr(auth_settings, "AUTHZ_AUDIT_ENABLED", False):
        return

    queue = _ensure_audit_writer_started()
    if queue is None:
        # No running event loop — nothing to schedule against. The caller is
        # likely outside an async context (e.g. a sync test); silently skip.
        return

    entry = _AuditEntry(
        user_id=user_id,
        action=action,
        obj=obj,
        result=result,
        details=details,
    )
    try:
        queue.put_nowait(entry)
    except asyncio.QueueFull:
        _audit_dropped_count += 1
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
