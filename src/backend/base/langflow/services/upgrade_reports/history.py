"""Persist validated reports and retrieve bounded history pages."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import col, func, select

from langflow.services.database.models.upgrade_report import UpgradeReport, UpgradeReportRepair
from langflow.services.upgrade_reports.schema import UpgradeReportDocument

if TYPE_CHECKING:
    from uuid import UUID

    from pydantic import JsonValue
    from sqlmodel.ext.asyncio.session import AsyncSession

MAX_REPORT_BYTES = 20 * 1024 * 1024


def reject_nonfinite(value: str) -> None:
    msg = f"{value} is not valid JSON"
    raise ValueError(msg)


def validate_document(content: bytes) -> tuple[str, UpgradeReportDocument]:
    text = content.decode("utf-8")
    document = json.loads(text, parse_constant=reject_nonfinite)
    return text, UpgradeReportDocument.model_validate(document)


async def store_report(session: AsyncSession, content: bytes, actor_id: UUID) -> UpgradeReport:
    text, document = validate_document(content)
    row = UpgradeReport(
        created_by=actor_id,
        generated_at=datetime.fromisoformat(document.generated_at.replace("Z", "+00:00")),
        source_identity=document.source.identity.sha256 if document.source.identity is not None else None,
        target_version=document.target.langflow,
        flow_count=sum((document.summary.flows.ok, document.summary.flows.warn, document.summary.flows.fail)),
        warning_count=document.summary.flows.warn,
        failing_count=document.summary.flows.fail,
        content_sha256=hashlib.sha256(content).hexdigest(),
        document_json=text,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def list_reports(
    session: AsyncSession, *, offset: int, limit: int, target_version: str | None = None
) -> tuple[list[UpgradeReport], int]:
    filters = [UpgradeReport.target_version == target_version] if target_version else []
    count = (await session.exec(select(func.count()).select_from(UpgradeReport).where(*filters))).one()
    rows = (
        await session.exec(
            select(UpgradeReport)
            .where(*filters)
            .order_by(col(UpgradeReport.created_at).desc(), col(UpgradeReport.id).desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()
    return list(rows), count


async def require_report(session: AsyncSession, report_id: UUID | None) -> None:
    if report_id is not None and await session.get(UpgradeReport, report_id) is None:
        msg = "Upgrade report not found"
        raise ValueError(msg)


async def record_repair_result(
    session: AsyncSession,
    *,
    report_id: UUID | None,
    actor_id: UUID,
    target_sha256: str,
    result: dict[str, JsonValue],
) -> UUID | None:
    """Add trusted server outcomes to the caller's existing repair transaction."""
    if report_id is None:
        return None
    await require_report(session, report_id)
    row = UpgradeReportRepair(
        report_id=report_id,
        created_by=actor_id,
        target_sha256=target_sha256,
        result_json=json.dumps(result, allow_nan=False),
    )
    session.add(row)
    await session.flush()
    return row.id


async def list_repairs(
    session: AsyncSession, *, report_id: UUID, offset: int, limit: int
) -> tuple[list[UpgradeReportRepair], int]:
    filters = [UpgradeReportRepair.report_id == report_id]
    count = (await session.exec(select(func.count()).select_from(UpgradeReportRepair).where(*filters))).one()
    rows = (
        await session.exec(
            select(UpgradeReportRepair)
            .where(*filters)
            .order_by(col(UpgradeReportRepair.created_at).desc(), col(UpgradeReportRepair.id).desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()
    return list(rows), count
