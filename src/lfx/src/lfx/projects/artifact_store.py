"""Browse reports without loading original source text until a report is opened."""

from __future__ import annotations

import asyncio
import base64
import json
import re
from datetime import timezone
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from lfx.projects.artifacts import ReportSummary, SourcedReport

if TYPE_CHECKING:
    from lfx.services.storage.service import StorageService

_RECORD_NAME = re.compile(r"report-([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})\.json\Z")
MAX_REPORT_PAGE_SIZE = 100
_CURSOR_FIELDS = 3


class InvalidReportCursorError(ValueError):
    """The caller supplied a malformed report-list position."""


class ReportPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    items: tuple[ReportSummary, ...]
    next_cursor: str | None = None
    unavailable_count: int = 0


def _key(report: ReportSummary) -> tuple[str, str, str]:
    return report.created_at.astimezone(timezone.utc).isoformat(), str(report.execution.flow_id), str(report.id)


def _cursor_key(cursor: str) -> tuple[str, str, str]:
    try:
        value = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        if (
            not isinstance(value, list)
            or len(value) != _CURSOR_FIELDS
            or not all(isinstance(item, str) for item in value)
        ):
            raise ValueError
        return value[0], value[1], value[2]
    except (ValueError, UnicodeError) as exc:
        msg = "Invalid report cursor."
        raise InvalidReportCursorError(msg) from exc


async def read_report(storage: StorageService, flow_id: UUID, report_id: UUID) -> SourcedReport:
    """Read and validate the original record from an already-authorized flow."""
    content = await storage.get_file(str(flow_id), f"report-{report_id}.json")
    report = SourcedReport.model_validate_json(content)
    if report.id != report_id or report.execution.flow_id != flow_id:
        msg = "The report does not match its storage location."
        raise ValueError(msg)
    return report


async def list_reports(
    storage: StorageService, flow_ids: list[UUID], *, limit: int = 20, cursor: str | None = None
) -> ReportPage:
    """Return newest first, with stable pagination across authorized flow namespaces.

    The canonical JSON is the publication marker written last by store_report.
    New reports use compact sidecars. Earlier reports remain discoverable by
    validating their canonical records; this read path never rewrites files.
    """
    if not 1 <= limit <= MAX_REPORT_PAGE_SIZE:
        msg = "Report page size must be between 1 and 100."
        raise ValueError(msg)
    before = _cursor_key(cursor) if cursor else None
    semaphore = asyncio.Semaphore(8)

    async def read_summary(flow_id: UUID, report_id: UUID, names: set[str]):
        async with semaphore:
            summary_name = f"report-{report_id}.summary.json"
            try:
                if summary_name in names:
                    content = await storage.get_file(str(flow_id), summary_name)
                    summary = ReportSummary.model_validate_json(content)
                    if summary.id != report_id or summary.execution.flow_id != flow_id:
                        return None
                    return summary
                return ReportSummary.from_report(await read_report(storage, flow_id, report_id))
            except (FileNotFoundError, ValueError):
                return None

    async def read_flow(flow_id: UUID):
        async with semaphore:
            names = set(await storage.list_files(str(flow_id)))
        return await asyncio.gather(
            *(read_summary(flow_id, UUID(match[1]), names) for name in names if (match := _RECORD_NAME.fullmatch(name)))
        )

    groups = await asyncio.gather(*(read_flow(flow_id) for flow_id in dict.fromkeys(flow_ids)))
    summaries = [summary for group in groups for summary in group if summary is not None]
    unavailable = sum(summary is None for group in groups for summary in group)
    ordered = sorted(
        (summary for summary in summaries if before is None or _key(summary) < before), key=_key, reverse=True
    )
    items = tuple(ordered[:limit])
    next_cursor = (
        base64.urlsafe_b64encode(json.dumps(_key(items[-1])).encode()).decode() if len(ordered) > limit else None
    )
    return ReportPage(items=items, next_cursor=next_cursor, unavailable_count=unavailable)
