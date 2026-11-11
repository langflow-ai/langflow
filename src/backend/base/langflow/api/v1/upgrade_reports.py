"""Admin-only imports never execute report contents or connect to their source."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, JsonValue, ValidationError

from langflow.api.utils import DbSession, DbSessionReadOnly
from langflow.api.utils.migration_pause import changes_the_instance
from langflow.services.auth.utils import get_current_active_superuser
from langflow.services.authorization.audit import audit_decision
from langflow.services.database.models.upgrade_report import UpgradeReport
from langflow.services.database.models.user.model import User
from langflow.services.upgrade_reports.history import (
    MAX_REPORT_BYTES,
    UnsupportedReportFormatError,
    list_repairs,
    list_reports,
    store_report,
)
from langflow.services.upgrade_reports.schema import UpgradeReportMetadata

router = APIRouter(prefix="/upgrade-reports", tags=["Upgrade Reports"])
Superuser = Annotated[User, Depends(get_current_active_superuser)]


ReportHistoryEntry = UpgradeReportMetadata


class ReportHistory(BaseModel):
    items: list[ReportHistoryEntry]
    total: int
    offset: int
    limit: int


class ReportDetail(ReportHistoryEntry):
    document: dict[str, JsonValue]


def entry(row: UpgradeReport | UpgradeReportMetadata) -> ReportHistoryEntry:
    values = {name: getattr(row, name) for name in ReportHistoryEntry.model_fields}
    for name in ("created_at", "generated_at"):
        if values[name].tzinfo is None:
            values[name] = values[name].replace(tzinfo=timezone.utc)
    return ReportHistoryEntry(**values)


async def read_row(session: DbSessionReadOnly, report_id: UUID) -> UpgradeReport:
    row = await session.get(UpgradeReport, report_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Upgrade report not found")
    return row


@router.post("", status_code=201)
async def import_report(request: Request, response: Response, admin: Superuser, session: DbSession) -> ReportDetail:
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > MAX_REPORT_BYTES:
            raise HTTPException(status_code=413, detail="Upgrade report exceeds 20 MiB")
        content.extend(chunk)
    try:
        row = await store_report(session, bytes(content), admin.id)
    except UnsupportedReportFormatError:
        raise HTTPException(
            status_code=422, detail={"code": "unsupported_upgrade_report_format", "supported": [1]}
        ) from None
    except ValidationError as exc:
        errors = [{"loc": list(error["loc"]), "message": error["msg"]} for error in exc.errors()[:20]]
        raise HTTPException(status_code=422, detail={"code": "invalid_upgrade_report", "errors": errors}) from None
    except (ValueError, UnicodeError, RecursionError):
        raise HTTPException(status_code=422, detail={"code": "invalid_upgrade_report"}) from None
    await audit_decision(
        user_id=admin.id, action="upgrade-report:import", obj=f"upgrade-report:{row.id}", result="allow"
    )
    response.headers["Cache-Control"] = "no-store"
    return ReportDetail(**entry(row).model_dump(), document=json.loads(row.document_json))


@router.get("")
async def history(
    _admin: Superuser,
    session: DbSessionReadOnly,
    response: Response,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    target_version: Annotated[str | None, Query(max_length=128)] = None,
) -> ReportHistory:
    rows, total = await list_reports(session, offset=offset, limit=limit, target_version=target_version)
    response.headers["Cache-Control"] = "no-store"
    return ReportHistory(items=[entry(row) for row in rows], total=total, offset=offset, limit=limit)


@router.get("/{report_id}")
async def detail(report_id: UUID, _admin: Superuser, session: DbSessionReadOnly, response: Response) -> ReportDetail:
    row = await read_row(session, report_id)
    response.headers["Cache-Control"] = "no-store"
    return ReportDetail(**entry(row).model_dump(), document=json.loads(row.document_json))


@router.get("/{report_id}/export")
async def export(
    report_id: UUID,
    admin: Superuser,
    session: DbSessionReadOnly,
    _changes: Annotated[None, Depends(changes_the_instance)],
) -> Response:
    row = await read_row(session, report_id)
    await audit_decision(
        user_id=admin.id, action="upgrade-report:export", obj=f"upgrade-report:{row.id}", result="allow"
    )
    return Response(
        content=row.document_json,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="upgrade-report-{row.id}.json"',
            "Cache-Control": "no-store",
        },
    )


class RepairHistoryEntry(BaseModel):
    id: UUID
    created_at: datetime
    created_by: UUID | None
    target_sha256: str
    result: dict[str, JsonValue]


class RepairHistory(BaseModel):
    items: list[RepairHistoryEntry]
    total: int
    offset: int
    limit: int


@router.get("/{report_id}/repairs")
async def repair_history(
    report_id: UUID,
    _admin: Superuser,
    session: DbSessionReadOnly,
    response: Response,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> RepairHistory:
    await read_row(session, report_id)
    rows, total = await list_repairs(session, report_id=report_id, offset=offset, limit=limit)
    response.headers["Cache-Control"] = "no-store"
    return RepairHistory(
        items=[
            RepairHistoryEntry(
                id=row.id,
                created_at=row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=timezone.utc),
                created_by=row.created_by,
                target_sha256=row.target_sha256,
                result=json.loads(row.result_json),
            )
            for row in rows
        ],
        total=total,
        offset=offset,
        limit=limit,
    )
