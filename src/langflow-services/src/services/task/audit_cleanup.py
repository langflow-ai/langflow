"""Recurring retention sweep for the ``authz_audit_log`` table.

The retention helper :func:`langflow.services.utils.clean_authz_audit_log` is
invoked once at startup inside ``initialize_services``. That single boot-time
sweep leaves a long-running instance to accumulate audit rows without bound
between restarts. This module wires the same helper to a background worker that
prunes on a fixed interval (daily by default), modelled on the sibling
:class:`langflow.services.task.temp_flow_cleanup.CleanupWorker`.

The worker is intentionally best-effort: every sweep opens its own
``session_scope`` and the helper logs-and-swallows database errors, so a
transient outage never kills the loop or blocks the event loop / request path.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

from lfx.log.logger import logger

from services.deps import get_settings_service, session_scope
from services.providers import require_hook

if TYPE_CHECKING:
    from lfx.services.settings.auth import AuthSettings

# Placeholder cadence used only until ``start()`` resolves the real value from
# AUTHZ_AUDIT_CLEANUP_INTERVAL. Covers the window where a worker is constructed
# but not yet started (the module-level singleton below, or a worker in tests),
# so ``_interval`` is always a valid float. Daily, matching the setting default.
DEFAULT_CLEANUP_INTERVAL_SECONDS = 86400


class AuditLogCleanupWorker:
    """Periodically prune ``authz_audit_log`` rows past the retention window.

    The worker is a no-op unless ``AUTHZ_AUDIT_ENABLED`` is True and
    ``AUTHZ_AUDIT_RETENTION_DAYS`` is greater than 0 — both gates are evaluated
    in :meth:`start`, so a disabled deployment never schedules a task. The
    unconditional startup sweep in ``initialize_services`` still handles
    boot-time pruning (including cleaning up leftover rows after auditing is
    turned off), so this worker only has to cover the steady state.

    Args:
        interval: Optional override (seconds) for the sweep cadence. When None
            the cadence is read from ``AUTHZ_AUDIT_CLEANUP_INTERVAL`` at start.
            Primarily a testing seam so the schedule can be exercised quickly
            without mutating global settings.
    """

    def __init__(self, *, interval: float | None = None) -> None:
        self._interval_override = interval
        self._interval: float = float(interval) if interval is not None else DEFAULT_CLEANUP_INTERVAL_SECONDS
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None

    def _resolve_interval(self, auth_settings: AuthSettings) -> float:
        """Resolve the sweep interval, preferring the constructor override.

        Otherwise reads AUTHZ_AUDIT_CLEANUP_INTERVAL directly: it is a pydantic
        field guaranteed present and ``>= 300`` (see AuthSettings), so no
        defaulting or type-coercion guard is needed here.
        """
        if self._interval_override is not None:
            return float(self._interval_override)
        return float(auth_settings.AUTHZ_AUDIT_CLEANUP_INTERVAL)

    async def start(self) -> None:
        """Start the periodic cleanup task, honouring the audit/retention gates."""
        if self._task is not None:
            await logger.awarning("Audit-log cleanup worker is already running")
            return

        auth_settings = get_settings_service().auth_settings

        if not getattr(auth_settings, "AUTHZ_AUDIT_ENABLED", False):
            await logger.adebug("Audit-log cleanup worker not started: AUTHZ_AUDIT_ENABLED is False")
            return

        try:
            retention_days = int(getattr(auth_settings, "AUTHZ_AUDIT_RETENTION_DAYS", 90))
        except (TypeError, ValueError):
            retention_days = 90
        if retention_days <= 0:
            await logger.adebug(
                "Audit-log cleanup worker not started: retention disabled (AUTHZ_AUDIT_RETENTION_DAYS=%s)",
                retention_days,
            )
            return

        self._interval = self._resolve_interval(auth_settings)
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="authz-audit-cleanup")
        await logger.adebug(
            "Started authz_audit_log cleanup worker (interval=%ss, retention=%sd)",
            self._interval,
            retention_days,
        )

    async def stop(self) -> None:
        """Stop the cleanup task gracefully, waiting for the current sweep to end."""
        if self._task is None:
            # Common path when auditing is disabled — nothing was ever scheduled.
            await logger.adebug("Audit-log cleanup worker is not running")
            return

        await logger.adebug("Stopping authz_audit_log cleanup worker...")
        self._stop_event.set()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None
        await logger.adebug("authz_audit_log cleanup worker stopped")

    async def _run(self) -> None:
        """Prune the audit log every interval until stopped.

        Sleep-first: the unconditional startup sweep already pruned at boot, so
        the first scheduled pass waits one interval to avoid an immediate,
        redundant delete right after startup.
        """
        while not self._stop_event.is_set():
            if await self._sleep_or_stop(self._interval):
                break
            await self._run_once()

    async def _sleep_or_stop(self, delay: float) -> bool:
        """Wait ``delay`` seconds or until stop is requested.

        Returns True if a stop was requested during the wait (the caller should
        break out of the loop), False if the full delay elapsed.
        """
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
        except asyncio.TimeoutError:
            return False
        return True

    async def _run_once(self) -> int:
        """Run a single retention sweep in its own session.

        Best-effort: ``clean_authz_audit_log`` already swallows SQLAlchemy and
        timeout errors; this outer guard additionally protects the loop from
        session/connection failures so the worker survives a transient outage.
        Returns the number of rows deleted (``-1`` when unavailable).
        """
        settings_service = get_settings_service()
        try:
            async with session_scope() as session:
                return await clean_authz_audit_log(settings_service, session)
        except Exception as exc:  # noqa: BLE001 — best-effort; never kill the loop
            await logger.aerror(f"Scheduled authz_audit_log cleanup failed: {exc}")
            return -1


async def clean_authz_audit_log(settings_service, session) -> int:
    """Delegate to the host-registered retention helper.

    Exposed as a module attribute so tests can monkeypatch
    ``langflow.services.task.audit_cleanup.clean_authz_audit_log`` the same way
    they did before the services extraction.
    """
    return await require_hook("clean_authz_audit_log")(settings_service, session)


# Module-level singleton started/stopped by the application lifespan.
audit_log_cleanup_worker = AuditLogCleanupWorker()
