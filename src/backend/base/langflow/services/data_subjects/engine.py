"""Run an approved request to completion: row steps, storage, a final pass, then (for a builder) the account.

Each step batch commits together with the request's cursor, so a crash resumes at the next batch.
The automatic storage upgrade's application backup holds every row an erase deletes. After the final
pass, the erase deletes it if the upgrade has finished, and otherwise records it as not reached.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger

from langflow.services.data_subjects import audit_events
from langflow.services.data_subjects.builder_account_steps import BUILDER_ACCOUNT_STEPS
from langflow.services.data_subjects.builder_flow_steps import erase_owned_flows
from langflow.services.data_subjects.end_user_steps import END_USER_STEPS
from langflow.services.data_subjects.errors import DataSubjectError
from langflow.services.data_subjects.knowledge_base_steps import erase_knowledge_base_upgrades, erase_knowledge_bases
from langflow.services.data_subjects.memory_base_storage import memory_base_items
from langflow.services.data_subjects.requests import close_request, erase_context
from langflow.services.data_subjects.storage_steps import run_storage_item
from langflow.services.database.models.data_subject_request import (
    DataSubjectRequest,
    DataSubjectRequestStatus,
    DataSubjectType,
)
from langflow.services.deps import session_scope
from langflow.services.knowledge_base_storage.application_backup import discard_outside_pass

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from uuid import UUID

    from langflow.services.data_subjects.context import EraseContext

    Heartbeat = Callable[[], Awaitable[None]]

BUILDER_STEPS = (
    ("flows", erase_owned_flows),
    ("knowledge_bases", erase_knowledge_bases),
    ("knowledge_base_upgrades", erase_knowledge_base_upgrades),
    *BUILDER_ACCOUNT_STEPS,
)
PHASE_ROWS = "rows"
PHASE_STORAGE = "storage"
PHASE_LATE_ROWS = "late_rows"
PHASE_ACCOUNT = "account"
MAX_ATTEMPTS = 5
RETRY_BASE_SECONDS = 30
LATE_WRITE_SETTLE_SECONDS = 2.0
RUNNABLE = (DataSubjectRequestStatus.APPROVED.value, DataSubjectRequestStatus.ERASING.value)
STORAGE_LOCATIONS = "storage_locations"
RETAINED_BACKUPS = "retained_backups"
_NOT_ROWS = (STORAGE_LOCATIONS, RETAINED_BACKUPS)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def is_retry_due(request: DataSubjectRequest, now: datetime | None = None) -> bool:
    error = request.error or {}
    if not error:
        return True
    if int(error.get("attempts", 0)) >= MAX_ATTEMPTS:
        return False
    retry_at = error.get("retry_at")
    return retry_at is None or datetime.fromisoformat(retry_at) <= (now or _now())


async def _load(session, request_id: UUID) -> DataSubjectRequest | None:
    return await session.get(DataSubjectRequest, request_id)


async def _run_steps(request_id: UUID, ctx: EraseContext, steps, heartbeat: Heartbeat, *, final: bool) -> None:
    key = "final_step" if final else "step"
    while True:
        async with session_scope() as session:
            request = await _load(session, request_id)
            cursor: dict[str, Any] = dict(request.cursor or {})
            index = int(cursor.get(key, 0))
            if index >= len(steps):
                return
            name, step = steps[index]
            processed = await step(session, ctx)
            counts = dict(request.counts or {})
            counts[name] = int(counts.get(name, 0)) + processed
            cursor[key] = index if processed else index + 1
            cursor["data"] = ctx.cursor
            request.counts, request.cursor = counts, cursor
            if ctx.memory_base_cleanups:
                # Committed with the row delete, so a crash or a remote outage cannot lose the handles.
                request.pending_paths = [
                    *(request.pending_paths or []),
                    *memory_base_items(ctx.memory_base_cleanups),
                ]
            session.add(request)
        ctx.memory_base_cleanups = []
        await heartbeat()


async def _run_storage(request_id: UUID, heartbeat: Heartbeat) -> None:
    while True:
        async with session_scope() as session:
            request = await _load(session, request_id)
            pending = list(request.pending_paths or [])
        if not pending:
            return
        await run_storage_item(pending[0])
        async with session_scope() as session:
            request = await _load(session, request_id)
            request.pending_paths = list(request.pending_paths or [])[1:]
            counts = dict(request.counts or {})
            counts[STORAGE_LOCATIONS] = int(counts.get(STORAGE_LOCATIONS, 0)) + 1
            request.counts = counts
            session.add(request)
        await heartbeat()


async def _record_retained_backups(request_id: UUID) -> None:
    """Delete a finished upgrade's application backup, or record that it still holds the subject's rows."""
    retained = await discard_outside_pass()
    async with session_scope() as session:
        request = await _load(session, request_id)
        request.counts = {**(request.counts or {}), RETAINED_BACKUPS: retained}
        session.add(request)


async def _set_phase(request_id: UUID, phase: str) -> None:
    async with session_scope() as session:
        request = await _load(session, request_id)
        request.phase = phase
        session.add(request)


async def _finish(request_id: UUID) -> None:
    async with session_scope() as session:
        request = await _load(session, request_id)
        counts = dict(request.counts or {})
        close_request(request, DataSubjectRequestStatus.DONE)
        request.phase = None
        request.error = None
        session.add(request)
        await audit_events.record_dsar_event(
            session,
            actor_id=request.decided_by,
            action=audit_events.ACTION_ERASE,
            request_id=request.id,
            details={
                "request_id": str(request.id),
                "subject_type": request.subject_type,
                "rows_deleted": sum(int(v) for k, v in counts.items() if isinstance(v, int) and k not in _NOT_ROWS),
                "paths_deleted": int(counts.get(STORAGE_LOCATIONS, 0)),
                "rows_redacted": int(counts.get("audit_redaction", 0)),
                "backups_not_reached": int(counts.get(RETAINED_BACKUPS, 0)),
            },
        )


async def _record_failure(request_id: UUID, step: str, exc: Exception) -> None:
    async with session_scope() as session:
        request = await _load(session, request_id)
        attempts = int((request.error or {}).get("attempts", 0)) + 1
        request.error = {
            "phase": request.phase,
            "step": step,
            "code": exc.code if isinstance(exc, DataSubjectError) else type(exc).__name__,
            "attempts": attempts,
            "failed_at": _now().isoformat(),
            "retry_at": (_now() + timedelta(seconds=RETRY_BASE_SECONDS * 2 ** (attempts - 1))).isoformat(),
        }
        session.add(request)


async def _noop() -> None:
    return None


async def run_request(request_id: UUID, heartbeat: Heartbeat = _noop) -> str | None:
    """Advance one request as far as it goes; return its status afterwards."""
    from langflow.services.data_subjects.account import delete_account

    async with session_scope() as session:
        request = await _load(session, request_id)
        if request is None or request.status not in RUNNABLE or not is_retry_due(request):
            return request.status if request else None
        request.status = DataSubjectRequestStatus.ERASING.value
        request.phase = request.phase or PHASE_ROWS
        session.add(request)
        ctx = erase_context(request)
        ctx.cursor = dict((request.cursor or {}).get("data", {}))
        is_end_user = request.subject_type == DataSubjectType.END_USER.value
        phase = request.phase
        subject_id, actor_id = request.subject_user_id, request.decided_by
    steps = END_USER_STEPS if is_end_user else BUILDER_STEPS
    try:
        if phase == PHASE_ROWS:
            await _run_steps(request_id, ctx, steps, heartbeat, final=False)
            phase = PHASE_STORAGE
            await _set_phase(request_id, phase)
        if phase == PHASE_STORAGE:
            await _run_storage(request_id, heartbeat)
            phase = PHASE_LATE_ROWS
            await _set_phase(request_id, phase)
        if phase == PHASE_LATE_ROWS:
            await asyncio.sleep(LATE_WRITE_SETTLE_SECONDS)
            ctx.cursor = {}
            await _run_steps(request_id, ctx, steps, heartbeat, final=True)
            await _run_storage(request_id, heartbeat)
            await _record_retained_backups(request_id)
            phase = PHASE_ACCOUNT
            await _set_phase(request_id, phase)
        if phase == PHASE_ACCOUNT and not is_end_user:
            await delete_account(request_id, subject_id, actor_id)
        await _finish(request_id)
    except Exception as exc:  # noqa: BLE001 - any failure is recorded on the request and retried
        await logger.aerror(
            "op=data_subject_erase request_id=%s phase=%s failed: %s", request_id, phase, type(exc).__name__
        )
        await _record_failure(request_id, phase, exc)
        return DataSubjectRequestStatus.ERASING.value
    return DataSubjectRequestStatus.DONE.value
