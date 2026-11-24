"""Admin-only imports never execute report contents or connect to their source."""

from __future__ import annotations

import json
import shutil
from contextlib import aclosing
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, JsonValue, ValidationError

from langflow.api.utils import DbSession, DbSessionReadOnly
from langflow.api.utils.migration_pause import changes_the_instance, write_refusal
from langflow.services.auth.utils import get_current_active_superuser
from langflow.services.authorization.audit import audit_decision
from langflow.services.database.models.upgrade_report import UpgradeReport
from langflow.services.database.models.user.model import User
from langflow.services.upgrade_reports.history import (
    MAX_REPORT_BYTES,
    UnsupportedReportFormatError,
    import_report_content,
    list_repairs,
    list_reports,
)
from langflow.services.upgrade_reports.run import (
    InvalidTargetVersionError,
    check_lock,
    fetch_pypi,
    installed_package,
    ndjson,
    parse_releases,
    parse_target_version,
    run_check,
    running_version,
)
from langflow.services.upgrade_reports.schema import ReportHistorySummary, UpgradeReportMetadata

router = APIRouter(prefix="/upgrade-reports", tags=["Upgrade Reports"])
Superuser = Annotated[User, Depends(get_current_active_superuser)]


ReportHistoryEntry = UpgradeReportMetadata


class ReportHistory(BaseModel):
    items: list[ReportHistorySummary]
    total: int
    offset: int
    limit: int


class ReportDetail(ReportHistoryEntry):
    document: dict[str, JsonValue]


def entry(row: UpgradeReport | UpgradeReportMetadata) -> ReportHistoryEntry:
    values = {name: getattr(row, name) for name in ReportHistoryEntry.model_fields}
    return ReportHistoryEntry(**values)


async def read_row(session: DbSessionReadOnly, report_id: UUID) -> UpgradeReport:
    row = await session.get(UpgradeReport, report_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Upgrade report not found")
    return row


@router.post("", status_code=201)
async def import_report(
    request: Request,
    response: Response,
    admin: Superuser,
    _changes: Annotated[None, Depends(changes_the_instance)],
    session: DbSession,
) -> ReportDetail:
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > MAX_REPORT_BYTES:
            raise HTTPException(status_code=413, detail="Upgrade report exceeds 20 MiB")
        content.extend(chunk)
    try:
        row, _ = await import_report_content(session, bytes(content), admin.id)
    except UnsupportedReportFormatError:
        raise HTTPException(
            status_code=422, detail={"code": "unsupported_upgrade_report_format", "supported": [1]}
        ) from None
    except ValidationError as exc:
        errors = [{"loc": list(error["loc"]), "message": error["msg"]} for error in exc.errors()[:20]]
        raise HTTPException(status_code=422, detail={"code": "invalid_upgrade_report", "errors": errors}) from None
    except (ValueError, UnicodeError, RecursionError):
        raise HTTPException(status_code=422, detail={"code": "invalid_upgrade_report"}) from None
    response.headers["Cache-Control"] = "no-store"
    return ReportDetail(**entry(row).model_dump(), document=json.loads(row.document_json))


class ReleaseChoices(BaseModel):
    current: str
    package: str
    releases: list[str]


@router.get("/checks/releases")
async def releases(_admin: Superuser) -> ReleaseChoices:
    current, package = running_version(), installed_package()
    try:
        found = parse_releases(await fetch_pypi(package), current=current)
    except (httpx.HTTPError, ValueError):
        raise HTTPException(status_code=502, detail={"code": "releases_unavailable"}) from None
    return ReleaseChoices(current=str(current), package=package, releases=found)


class CheckRequest(BaseModel):
    target_version: str


@router.post("/checks")
async def run_upgrade_check(body: CheckRequest, admin: Superuser) -> StreamingResponse:
    current = running_version()
    try:
        target = parse_target_version(body.target_version, current=current)
    except InvalidTargetVersionError:
        raise HTTPException(status_code=422, detail={"code": "invalid_target_version"}) from None
    if check_lock.locked():
        raise HTTPException(status_code=409, detail={"code": "check_running"})
    if target != current and shutil.which("uvx") is None:
        raise HTTPException(status_code=503, detail={"code": "uvx_unavailable"})
    # Only a look at the pause: a place held for the whole run would make a pause wait for the check.
    if refusal := await write_refusal(admin.id):
        raise HTTPException(status_code=503, detail=refusal)
    events = run_check(target, current=current, package=installed_package(), admin_id=admin.id)

    async def stream():
        # Closing the response closes the run, which stops its child.
        async with aclosing(events):
            async for event in events:
                yield ndjson(event)

    return StreamingResponse(
        stream(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


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
    return ReportHistory(items=rows, total=total, offset=offset, limit=limit)


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
