"""Retention for ``audit_events``: delete by age, and by nothing else.

Deleting a project, flow, user or API key never deletes its events; only the
retention window does.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from lfx.log.logger import logger
from sqlalchemy import exc as sqlalchemy_exc
from sqlmodel import col, delete

from langflow.services.database.models.audit_event.model import AuditEvent
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.task.audit_cleanup import AuditLogCleanupWorker

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService
    from sqlmodel.ext.asyncio.session import AsyncSession


async def purge_expired_audit_events(
    session: AsyncSession,
    *,
    retention_days: int,
    now: datetime | None = None,
) -> int:
    """Delete events older than the window; ``0`` or less keeps everything."""
    if retention_days <= 0:
        return 0
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=retention_days)
    result = await session.exec(delete(AuditEvent).where(col(AuditEvent.timestamp) < cutoff))
    deleted = getattr(result, "rowcount", None)
    return int(deleted) if deleted is not None and deleted >= 0 else -1


async def clean_audit_events(settings_service: SettingsService, session: AsyncSession) -> int:
    """Best-effort sweep: a database hiccup must never fail startup or the worker."""
    retention_days = int(settings_service.settings.audit_retention_days)
    try:
        deleted = await purge_expired_audit_events(session, retention_days=retention_days)
    except (sqlalchemy_exc.SQLAlchemyError, asyncio.TimeoutError) as exc:
        await logger.awarning("op=clean_audit_events outcome=failed error=%s", type(exc).__name__)
        return -1
    await logger.adebug("op=clean_audit_events deleted=%s retention_days=%s", deleted, retention_days)
    return deleted


class AuditEventCleanupWorker(AuditLogCleanupWorker):
    """Keeps a long-running instance inside the audit retention window.

    Shares the schedule of the authorization audit sweep and differs only in what
    it gates on and what it deletes.
    """

    async def start(self) -> None:
        if self._task is not None:
            return
        settings_service = get_settings_service()
        settings = settings_service.settings
        if not settings.audit_enabled or int(settings.audit_retention_days) <= 0:
            return
        self._interval = self._resolve_interval(settings_service.auth_settings)
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="audit-events-cleanup")

    async def _run_once(self) -> int:
        try:
            async with session_scope() as session:
                return await clean_audit_events(get_settings_service(), session)
        except Exception as exc:  # noqa: BLE001
            await logger.aerror("op=audit_events_cleanup outcome=failed error=%s", type(exc).__name__)
            return -1


audit_event_cleanup_worker = AuditEventCleanupWorker()
