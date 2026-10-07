"""Approve requests still waiting for review once their due date passes, when the operator opts in.

A request a guard blocks keeps its status and records the block in ``error``, so the sweep never
retries it; an administrator sees why and decides by hand.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from lfx.log.logger import logger
from lfx.services.settings.feature_flags import FEATURE_FLAGS
from sqlmodel import col, select

from langflow.services.data_subjects.errors import DataSubjectError
from langflow.services.data_subjects.requests import approve
from langflow.services.database.models.data_subject_request import DataSubjectRequest, DataSubjectRequestStatus
from langflow.services.deps import get_settings_service, session_scope

if TYPE_CHECKING:
    from uuid import UUID

EXPIRY_BATCH = 50
AUTO_APPROVAL_BLOCKED = "auto_approval_blocked"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def auto_erase_enabled() -> bool:
    return FEATURE_FLAGS.data_subject_requests and get_settings_service().settings.data_subject_auto_erase_on_expiry


async def _expired_request_ids(now: datetime) -> list[UUID]:
    eligible: list[UUID] = []
    offset = 0
    async with session_scope() as session:
        while len(eligible) < EXPIRY_BATCH:
            rows = (
                await session.exec(
                    select(DataSubjectRequest)
                    .where(
                        DataSubjectRequest.status == DataSubjectRequestStatus.REQUESTED.value,
                        col(DataSubjectRequest.due_at) <= now,
                    )
                    .order_by(col(DataSubjectRequest.due_at), col(DataSubjectRequest.id))
                    .offset(offset)
                    .limit(EXPIRY_BATCH)
                )
            ).all()
            eligible.extend(row.id for row in rows if not (row.error or {}).get(AUTO_APPROVAL_BLOCKED))
            if len(rows) < EXPIRY_BATCH:
                break
            offset += EXPIRY_BATCH
    return eligible[:EXPIRY_BATCH]


async def _approve_expired(request_id: UUID) -> bool:
    async with session_scope() as session:
        request = await session.get(DataSubjectRequest, request_id)
        if request is None or request.status != DataSubjectRequestStatus.REQUESTED.value:
            return False
        try:
            await approve(session, request, None, automatic=True)
        except DataSubjectError as exc:
            request.error = {AUTO_APPROVAL_BLOCKED: True, "code": exc.code, "message": exc.message}
            session.add(request)
            await logger.awarning("op=data_subject_expiry request=%s blocked_by=%s", request_id, exc.code)
            return False
        return True


async def approve_expired_requests(now: datetime | None = None) -> int:
    """Approve every overdue request a guard allows; return how many were approved."""
    if not auto_erase_enabled():
        return 0
    approved = 0
    for request_id in await _expired_request_ids(now or _now()):
        approved += int(await _approve_expired(request_id))
    return approved
