"""Redact identifying detail keys from an erased person's audit rows; the rows and their UUIDs stay as evidence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import update
from sqlmodel import and_, col, or_, select

from langflow.services.data_subjects.batching import BATCH_SIZE
from langflow.services.database.models.auth.authz import AuthzAuditLog

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.data_subjects.context import EraseContext

REDACTED_DETAIL_KEYS = (
    "username",
    "created_by",
    "email",
    "client_ip",
    "reason",
    "error",
    "team_name",
    "before",
    "after",
    "user_id",
)


def _rows_about(user_id):
    return or_(
        AuthzAuditLog.user_id == user_id,
        AuthzAuditLog.actor_id == user_id,
        and_(AuthzAuditLog.resource_type == "user", AuthzAuditLog.resource_id == user_id),
    )


def _has_identifying_key():
    return or_(*(col(AuthzAuditLog.details)[key].as_string().is_not(None) for key in REDACTED_DETAIL_KEYS))


async def redact_audit_rows(session: AsyncSession, ctx: EraseContext) -> int:
    rows = list(
        (
            await session.exec(
                select(AuthzAuditLog.id, AuthzAuditLog.details)
                .where(_rows_about(ctx.subject_user_id), _has_identifying_key())
                .limit(BATCH_SIZE)
            )
        ).all()
    )
    for row_id, details in rows:
        cleaned = {key: value for key, value in (details or {}).items() if key not in REDACTED_DETAIL_KEYS}
        await session.exec(update(AuthzAuditLog).where(AuthzAuditLog.id == row_id).values(details=cleaned))
    return len(rows)
