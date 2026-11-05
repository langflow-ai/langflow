"""Erase complete report archives without rewriting their immutable contents."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import delete
from sqlmodel import select

from langflow.services.data_subjects.batching import delete_batch
from langflow.services.data_subjects.context import EraseStepPending
from langflow.services.data_subjects.errors import ReportOwnerAttributionRequiredError
from langflow.services.database.models.upgrade_report import UpgradeReport, UpgradeReportRepair
from langflow.services.upgrade_reports.history import lock_report

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.data_subjects.context import EraseContext

_CURSOR = "upgrade_report_after"
REPORT_SCAN_BATCH_SIZE = 10


def _names_subject(document: str, ctx: EraseContext, report_id: UUID) -> bool:
    ambiguous_name = False
    for flow in json.loads(document).get("flows", []):
        owner = flow.get("owner")
        if not isinstance(owner, dict):
            continue
        try:
            if UUID(owner.get("id")) == ctx.subject_user_id:
                return True
        except (ValueError, TypeError, AttributeError):
            if ctx.username is not None and owner.get("username") == ctx.username:
                ambiguous_name = True
    if ambiguous_name:
        msg = "Review upgrade report owner attribution before continuing this account erasure."
        raise ReportOwnerAttributionRequiredError(
            msg,
            details={
                "report_id": str(report_id),
                "action": "Resolve the report owner's identity through manual attribution review before retrying.",
            },
        )
    return False


async def erase_upgrade_reports(session: AsyncSession, ctx: EraseContext) -> int | EraseStepPending:
    """Delete one affected report or a batch of its children; preserve other archives.

    Report JSON may be 20 MB, so page over IDs and inspect only one document at a
    time. Keep the last inspected ID with the erase cursor to avoid rescanning
    unrelated archives after each delete. Reset it at exhaustion so the engine's
    final pass also catches reports imported during the first pass.
    """
    statement = select(UpgradeReport.id).order_by(UpgradeReport.id).limit(REPORT_SCAN_BATCH_SIZE)
    if after := ctx.cursor.get(_CURSOR):
        statement = statement.where(UpgradeReport.id > UUID(after))
    ids = list((await session.exec(statement)).all())
    if not ids:
        ctx.cursor.pop(_CURSOR, None)
        return 0
    for report_id in ids:
        row = await session.get(UpgradeReport, report_id)
        if row is not None and (
            row.created_by == ctx.subject_user_id or _names_subject(row.document_json, ctx, report_id)
        ):
            if not await lock_report(session, report_id):
                ctx.cursor[_CURSOR] = str(report_id)
                continue
            # Explicit child-first deletes work even when SQLite FK cascade
            # is disabled. Keep this report pending until all children drain.
            deleted = await delete_batch(session, UpgradeReportRepair, UpgradeReportRepair.report_id == report_id)
            if deleted:
                return deleted
            await session.exec(delete(UpgradeReport).where(UpgradeReport.id == report_id))
            ctx.cursor[_CURSOR] = str(report_id)
            return 1
        ctx.cursor[_CURSOR] = str(report_id)
    return EraseStepPending()
