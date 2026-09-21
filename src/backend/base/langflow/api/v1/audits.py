"""``GET /api/v1/audits``: every audit event, from both stores, in one keyset-paginated feed.

Resource operations (``audit_events``) and authorization, identity and governance
events (``authz_audit_log``) are merged on the server, so a client asks for one
page and gets one page, and exports stream straight from the database instead of
being assembled in the browser. The query string is parsed as strictly as the
resource-specific audit reads: anything unknown, empty or malformed answers 400.
"""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_serializer

from langflow.api.utils import DbSession
from langflow.api.v1.audit_reads import (
    bad_request,
    group_query_params,
    parse_limit,
    parse_timestamp,
    parse_uuid,
)
from langflow.services.audit.feed import (
    FEED_RESULTS,
    MAX_SEARCH_LENGTH,
    AuditCursorError,
    AuditFeedFilters,
    AuditFeedRow,
    AuditKind,
    AuditSource,
    frozen_until,
    iter_feed_batches,
    list_feed,
)
from langflow.services.audit.vocabulary import AuditOperation
from langflow.services.auth.utils import get_current_active_superuser
from langflow.services.database.models.audit_event.model import as_utc

# Imported at runtime: FastAPI resolves the dependency annotation below.
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

router = APIRouter(prefix="/audits", tags=["Audit"])

_SLUG = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_ACTION = re.compile(r"^[A-Za-z0-9_:.\-]{1,128}$")
_SLUG_LISTS = ("resource_type", "actor_type")
_ACTION_LISTS = ("action", "exclude_action")
_ENUM_LISTS: dict[str, frozenset[str]] = {
    "source": frozenset(source.value for source in AuditSource),
    "kind": frozenset(kind.value for kind in AuditKind),
    "operation": frozenset(operation.value for operation in AuditOperation),
    "result": FEED_RESULTS,
}
_REPEATABLE = frozenset({*_SLUG_LISTS, *_ACTION_LISTS, *_ENUM_LISTS})
_UUIDS = ("resource_id", "user_id", "actor_id", "request_id")
_FILTER_PARAMS = frozenset({*_REPEATABLE, *_UUIDS, "since", "until", "q"})
_PAGE_PARAMS = frozenset({"cursor", "limit", "include_total"})
_EXPORT_FORMATS = {"csv": "text/csv; charset=utf-8", "ndjson": "application/x-ndjson"}
_EXPORT_BATCH = 500

CSV_COLUMNS = (
    "timestamp",
    "user_id",
    "actor_type",
    "actor_id",
    "action",
    "resource_type",
    "resource_id",
    "result",
    "details",
    "source",
    "kind",
    "resource_name",
    "operation",
    "error_code",
    "request_id",
)


def _repeatable_values(key: str, values: list[str]) -> frozenset[str]:
    pattern = _SLUG if key in _SLUG_LISTS else _ACTION if key in _ACTION_LISTS else None
    for value in values:
        valid = pattern.fullmatch(value) if pattern is not None else value in _ENUM_LISTS[key]
        if not valid:
            msg = f"Unsupported value for {key}"
            raise bad_request(msg)
    return frozenset(values)


def _window(single: dict[str, str]) -> tuple[datetime | None, datetime | None]:
    since = parse_timestamp("since", single["since"]) if "since" in single else None
    until = parse_timestamp("until", single["until"]) if "until" in single else None
    if since is not None and until is not None and until <= since:
        msg = "until must be later than since"
        raise bad_request(msg)
    return since, until


def _search(single: dict[str, str]) -> str | None:
    if "q" not in single:
        return None
    text = single["q"].strip()
    if not text or len(text) > MAX_SEARCH_LENGTH:
        msg = f"q must be 1 to {MAX_SEARCH_LENGTH} characters"
        raise bad_request(msg)
    return text


def _filters(grouped: dict[str, list[str]]) -> AuditFeedFilters:
    single = {key: values[0] for key, values in grouped.items() if key not in _REPEATABLE}
    lists = {key: _repeatable_values(key, values) for key, values in grouped.items() if key in _REPEATABLE}
    uuids = {key: parse_uuid(key, single[key]) for key in _UUIDS if key in single}
    since, until = _window(single)
    return AuditFeedFilters(
        sources=frozenset(AuditSource(value) for value in lists.get("source", ())),
        kinds=frozenset(AuditKind(value) for value in lists.get("kind", ())),
        resource_types=lists.get("resource_type", frozenset()),
        resource_id=uuids.get("resource_id"),
        actions=lists.get("action", frozenset()),
        exclude_actions=lists.get("exclude_action", frozenset()),
        operations=lists.get("operation", frozenset()),
        results=lists.get("result", frozenset()),
        actor_types=lists.get("actor_type", frozenset()),
        user_id=uuids.get("user_id"),
        actor_id=uuids.get("actor_id"),
        request_id=uuids.get("request_id"),
        since=since,
        until=until,
        search=_search(single),
    )


def _grouped(request: Request, extra: frozenset[str]) -> dict[str, list[str]]:
    return group_query_params(request, set(_FILTER_PARAMS | extra), repeatable=_REPEATABLE)


def _flag(name: str, value: str | None) -> bool:
    if value is None or value == "false":
        return False
    if value == "true":
        return True
    msg = f"{name} must be true or false"
    raise bad_request(msg)


class AuditFeedActor(BaseModel):
    type: str | None
    id: UUID | None
    user_id: UUID | None
    acting_issuer: str | None
    acting_subject: str | None


class AuditFeedItem(BaseModel):
    """One event from either store. Store-specific fields are null on the other."""

    id: UUID
    timestamp: datetime
    source: AuditSource
    kind: AuditKind
    action: str
    resource_type: str | None
    resource_id: UUID | None
    resource_name: str | None
    result: str
    user_id: UUID | None
    actor_type: str | None
    actor_id: UUID | None
    actor: AuditFeedActor
    operation: str | None
    error_code: str | None
    request_id: UUID | None
    details: dict[str, Any] | None

    @field_serializer("timestamp")
    def _rfc3339(self, value: datetime) -> str:
        return _timestamp_text(value)


class AuditFeedResponse(BaseModel):
    items: list[AuditFeedItem]
    next_cursor: str | None
    # Null unless the caller asked for it: a COUNT over a large log is not free.
    total: int | None


def _timestamp_text(value: datetime) -> str:
    return as_utc(value).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _request_id(feed_row: AuditFeedRow) -> UUID | None:
    if feed_row.source is AuditSource.RESOURCE:
        return feed_row.row.request_id
    raw = (feed_row.row.details or {}).get("request_id")
    try:
        return UUID(str(raw)) if raw else None
    except ValueError:
        return None


def feed_item(feed_row: AuditFeedRow) -> AuditFeedItem:
    row = feed_row.row
    is_resource = feed_row.source is AuditSource.RESOURCE
    actor = AuditFeedActor(
        type=row.actor_type,
        id=row.actor_id,
        user_id=row.user_id,
        acting_issuer=row.acting_issuer if is_resource else None,
        acting_subject=row.acting_subject if is_resource else None,
    )
    return AuditFeedItem(
        id=row.id,
        timestamp=row.timestamp,
        source=feed_row.source,
        kind=feed_row.kind,
        action=row.action,
        resource_type=row.resource_type,
        resource_id=row.resource_id,
        resource_name=row.resource_name if is_resource else None,
        result=row.result,
        user_id=row.user_id,
        actor_type=row.actor_type,
        actor_id=row.actor_id,
        actor=actor,
        operation=row.operation if is_resource else None,
        error_code=row.error_code if is_resource else None,
        request_id=_request_id(feed_row),
        details=row.details,
    )


@router.get("", response_model=AuditFeedResponse)
@router.get("/", response_model=AuditFeedResponse, include_in_schema=False)
async def read_audits(
    request: Request,
    session: DbSession,
    _admin: Annotated[User, Depends(get_current_active_superuser)],
) -> AuditFeedResponse:
    """Every audit event, newest first, filtered and keyset-paginated on the server.

    Filters: ``source``, ``kind``, ``resource_type``, ``action``, ``exclude_action``,
    ``operation``, ``result`` and ``actor_type`` repeat and OR within themselves;
    ``resource_id``, ``user_id``, ``actor_id``, ``request_id``, ``since`` and
    ``until`` narrow further. ``q`` keeps rows whose action, operation, resource
    type or name, actor username or details contain it, ignoring case.
    ``include_total=true`` adds a count of every match.
    """
    grouped = _grouped(request, _PAGE_PARAMS)
    filters = _filters(grouped)
    single = {key: values[0] for key, values in grouped.items()}
    try:
        page = await list_feed(
            session,
            filters,
            limit=parse_limit(single.get("limit")),
            cursor=single.get("cursor"),
            include_total=_flag("include_total", single.get("include_total")),
        )
    except AuditCursorError as exc:
        raise bad_request(str(exc)) from exc
    return AuditFeedResponse(
        items=[feed_item(row) for row in page.items], next_cursor=page.next_cursor, total=page.total
    )


def _stable_json(value: dict[str, Any] | None) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":")) if value else ""


def _csv_cell(value: object) -> str:
    """Neutralize spreadsheet formulas; the csv writer does the RFC 4180 quoting."""
    text = "" if value is None else str(value)
    first_visible = text.lstrip("\x00\t\n\r ")[:1]
    return f"'{text}" if first_visible and first_visible in "=+-@" else text


def _csv_values(feed_row: AuditFeedRow) -> list[object]:
    """The CSV columns straight from the stored row; building the response model per row halves throughput."""
    row = feed_row.row
    is_resource = feed_row.source is AuditSource.RESOURCE
    return [
        _timestamp_text(row.timestamp),
        row.user_id,
        row.actor_type,
        row.actor_id,
        row.action,
        row.resource_type,
        row.resource_id,
        row.result,
        _stable_json(row.details),
        feed_row.source.value,
        feed_row.kind.value,
        row.resource_name if is_resource else None,
        row.operation if is_resource else None,
        row.error_code if is_resource else None,
        _request_id(feed_row),
    ]


def _csv_chunk(records: list[list[object]]) -> str:
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\r\n").writerows([_csv_cell(value) for value in record] for record in records)
    return buffer.getvalue()


async def _export_chunks(filters: AuditFeedFilters, export_format: str) -> AsyncIterator[str]:
    """One chunk per keyset batch, on a session of its own: the request's closes before the body streams."""
    if export_format == "csv":
        yield _csv_chunk([list(CSV_COLUMNS)])
    async with session_scope() as session:
        async for batch in iter_feed_batches(session, filters, batch_size=_EXPORT_BATCH):
            if export_format == "csv":
                yield _csv_chunk([_csv_values(feed_row) for feed_row in batch])
            else:
                yield "".join(feed_item(feed_row).model_dump_json() + "\n" for feed_row in batch)


@router.get("/export")
async def export_audits(
    request: Request,
    _admin: Annotated[User, Depends(get_current_active_superuser)],
) -> StreamingResponse:
    """Stream every matching event as CSV (default) or NDJSON, newest first.

    The window is frozen when the export starts, so it is one consistent snapshot
    however long it runs, and the rows are never gathered in memory.
    """
    grouped = _grouped(request, frozenset({"format"}))
    export_format = grouped.get("format", ["csv"])[0]
    if export_format not in _EXPORT_FORMATS:
        msg = "format must be csv or ndjson"
        raise bad_request(msg)
    filters = frozen_until(_filters(grouped))
    filename = f"langflow-audit-{datetime.now(timezone.utc).date().isoformat()}.{export_format}"
    return StreamingResponse(
        _export_chunks(filters, export_format),
        media_type=_EXPORT_FORMATS[export_format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
    )


__all__ = ["CSV_COLUMNS", "AuditFeedItem", "AuditFeedResponse", "router"]
