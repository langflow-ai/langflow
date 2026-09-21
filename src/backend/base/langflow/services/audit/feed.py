"""One audit feed over both audit stores, filtered and keyset-paginated on the server.

``audit_events`` records resource operations and ``authz_audit_log`` records
authorization, identity and governance events. Both order by
``(timestamp DESC, id DESC)``, so a page asks each store for one row more than
it returns, merges the candidates and keeps the newest ``limit``: a row that
belongs on the page is always within its own store's first ``limit + 1`` rows.

Every filter is defined for both stores. Where a filter cannot hold for a store
(an ``operation`` on an authorization row, a result one store never writes), that
store is left out of the read instead of the filter being ignored.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import and_, func, or_
from sqlmodel import col, select

from langflow.services.audit.query import AuditCursorError, CursorState, decode_state, encode_cursor, to_utc
from langflow.services.database.models.audit_event.model import AuditEvent, as_utc
from langflow.services.database.models.auth import AuthzAuditLog

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.sql.elements import ColumnElement
    from sqlmodel.ext.asyncio.session import AsyncSession

MAX_FEED_PAGE_SIZE = 200
AUTHZ_DECISION_EVENT = "authorization_decision"


class AuditSource(str, Enum):
    """Which store a row came from."""

    RESOURCE = "resource"
    AUTHZ = "authz"


class AuditKind(str, Enum):
    """Whether a row records a permission check or something that was done."""

    ACTION = "action"
    CHECK = "check"


RESOURCE_RESULTS = frozenset({"allow", "deny", "succeeded", "failed"})
AUTHZ_RESULTS = frozenset({"allow", "deny", "owner_override", "skip"})
FEED_RESULTS = RESOURCE_RESULTS | AUTHZ_RESULTS


def _sorted(values: frozenset[str]) -> list[str]:
    return sorted(values)


@dataclass(frozen=True)
class AuditFeedFilters:
    """Every filter the feed accepts. Values within a field OR; fields AND."""

    sources: frozenset[AuditSource] = field(default_factory=frozenset)
    kinds: frozenset[AuditKind] = field(default_factory=frozenset)
    resource_types: frozenset[str] = field(default_factory=frozenset)
    resource_id: UUID | None = None
    actions: frozenset[str] = field(default_factory=frozenset)
    exclude_actions: frozenset[str] = field(default_factory=frozenset)
    operations: frozenset[str] = field(default_factory=frozenset)
    results: frozenset[str] = field(default_factory=frozenset)
    actor_types: frozenset[str] = field(default_factory=frozenset)
    user_id: UUID | None = None
    actor_id: UUID | None = None
    request_id: UUID | None = None
    since: datetime | None = None
    until: datetime | None = None

    def fingerprint(self) -> str:
        canonical: dict[str, Any] = {
            "feed": 1,
            "sources": _sorted(frozenset(source.value for source in self.sources)),
            "kinds": _sorted(frozenset(kind.value for kind in self.kinds)),
            "resource_types": _sorted(self.resource_types),
            "resource_id": str(self.resource_id) if self.resource_id else None,
            "actions": _sorted(self.actions),
            "exclude_actions": _sorted(self.exclude_actions),
            "operations": _sorted(self.operations),
            "results": _sorted(self.results),
            "actor_types": _sorted(self.actor_types),
            "user_id": str(self.user_id) if self.user_id else None,
            "actor_id": str(self.actor_id) if self.actor_id else None,
            "request_id": str(self.request_id) if self.request_id else None,
            "since": to_utc(self.since).isoformat() if self.since else None,
            "until": to_utc(self.until).isoformat() if self.until else None,
        }
        encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def with_until(self, until: datetime) -> AuditFeedFilters:
        values = {name: getattr(self, name) for name in self.__dataclass_fields__}
        return AuditFeedFilters(**{**values, "until": until})

    def includes(self, source: AuditSource) -> bool:
        return not self.sources or source in self.sources


def _shared_clauses(model: Any, filters: AuditFeedFilters) -> list[ColumnElement[bool]]:
    """Filters both stores express with the same columns."""
    clauses: list[ColumnElement[bool]] = []
    exact = {model.resource_id: filters.resource_id, model.user_id: filters.user_id, model.actor_id: filters.actor_id}
    clauses.extend(col(column) == value for column, value in exact.items() if value is not None)
    if filters.resource_types:
        clauses.append(col(model.resource_type).in_(_sorted(filters.resource_types)))
    if filters.actions:
        clauses.append(col(model.action).in_(_sorted(filters.actions)))
    if filters.exclude_actions:
        clauses.append(col(model.action).not_in(_sorted(filters.exclude_actions)))
    if filters.since is not None:
        clauses.append(col(model.timestamp) >= to_utc(filters.since))
    if filters.until is not None:
        clauses.append(col(model.timestamp) < to_utc(filters.until))
    return clauses


def resource_clauses(filters: AuditFeedFilters) -> list[ColumnElement[bool]] | None:
    """Clauses over ``audit_events``, or None when no row there can match."""
    if not filters.includes(AuditSource.RESOURCE):
        return None
    results = filters.results & RESOURCE_RESULTS if filters.results else RESOURCE_RESULTS
    if not results:
        return None
    clauses = _shared_clauses(AuditEvent, filters)
    if filters.results:
        clauses.append(col(AuditEvent.result).in_(_sorted(results)))
    if filters.kinds:
        event_types = {AuditKind.CHECK: "authz", AuditKind.ACTION: "action"}
        clauses.append(col(AuditEvent.event_type).in_(sorted(event_types[kind] for kind in filters.kinds)))
    if filters.operations:
        clauses.append(col(AuditEvent.operation).in_(_sorted(filters.operations)))
    if filters.actor_types:
        clauses.append(col(AuditEvent.actor_type).in_(_sorted(filters.actor_types)))
    if filters.request_id is not None:
        clauses.append(col(AuditEvent.request_id) == filters.request_id)
    return clauses


def _authz_event_class() -> ColumnElement[Any]:
    # Rendered as json_extract on SQLite and ->> on PostgreSQL.
    return col(AuthzAuditLog.details)["event"].as_string()


def _authz_kind_clause(kinds: frozenset[AuditKind]) -> ColumnElement[bool] | None:
    """A check is a tagged decision; anything else, including untagged history, is an action."""
    if kinds == frozenset(AuditKind):
        return None
    event_class = _authz_event_class()
    if AuditKind.CHECK in kinds:
        return event_class == AUTHZ_DECISION_EVENT
    return or_(event_class != AUTHZ_DECISION_EVENT, event_class.is_(None))


def _authz_actor_clause(actor_types: frozenset[str]) -> ColumnElement[bool]:
    # Rows written before actor attribution have no type and read as ``unknown``.
    clause = col(AuthzAuditLog.actor_type).in_(_sorted(actor_types))
    return or_(clause, col(AuthzAuditLog.actor_type).is_(None)) if "unknown" in actor_types else clause


def authz_clauses(filters: AuditFeedFilters) -> list[ColumnElement[bool]] | None:
    """Clauses over ``authz_audit_log``, or None when no row there can match."""
    if not filters.includes(AuditSource.AUTHZ) or filters.operations:
        return None
    results = filters.results & AUTHZ_RESULTS if filters.results else AUTHZ_RESULTS
    if not results:
        return None
    clauses = _shared_clauses(AuthzAuditLog, filters)
    if filters.results:
        clauses.append(col(AuthzAuditLog.result).in_(_sorted(results)))
    kind_clause = _authz_kind_clause(filters.kinds) if filters.kinds else None
    if kind_clause is not None:
        clauses.append(kind_clause)
    if filters.actor_types:
        clauses.append(_authz_actor_clause(filters.actor_types))
    if filters.request_id is not None:
        clauses.append(col(AuthzAuditLog.details)["request_id"].as_string() == str(filters.request_id))
    return clauses


@dataclass(frozen=True)
class AuditFeedRow:
    """One row of either store, in the feed's shape."""

    source: AuditSource
    row: Any

    @property
    def key(self) -> tuple[datetime, UUID]:
        return as_utc(self.row.timestamp), UUID(str(self.row.id))

    @property
    def kind(self) -> AuditKind:
        if self.source is AuditSource.RESOURCE:
            return AuditKind.CHECK if self.row.event_type == "authz" else AuditKind.ACTION
        event_class = (self.row.details or {}).get("event")
        return AuditKind.CHECK if event_class == AUTHZ_DECISION_EVENT else AuditKind.ACTION


@dataclass(frozen=True)
class AuditFeedPage:
    items: list[AuditFeedRow]
    next_cursor: str | None
    total: int | None = None


def _after(model: Any, state: CursorState) -> ColumnElement[bool]:
    return or_(
        col(model.timestamp) < state.timestamp,
        and_(col(model.timestamp) == state.timestamp, col(model.id) < state.event_id),
    )


def _store_plans(filters: AuditFeedFilters) -> list[tuple[AuditSource, Any, list[ColumnElement[bool]]]]:
    plans: list[tuple[AuditSource, Any, list[ColumnElement[bool]]]] = []
    resource = resource_clauses(filters)
    if resource is not None:
        plans.append((AuditSource.RESOURCE, AuditEvent, resource))
    authz = authz_clauses(filters)
    if authz is not None:
        plans.append((AuditSource.AUTHZ, AuthzAuditLog, authz))
    return plans


async def _store_window(
    session: AsyncSession,
    model: Any,
    clauses: list[ColumnElement[bool]],
    state: CursorState | None,
    size: int,
) -> list[Any]:
    where = [*clauses, _after(model, state)] if state is not None else clauses
    statement = select(model).where(*where).order_by(col(model.timestamp).desc(), col(model.id).desc()).limit(size)
    return list((await session.exec(statement)).all())


async def count_feed(session: AsyncSession, filters: AuditFeedFilters) -> int:
    total = 0
    for _, model, clauses in _store_plans(filters):
        statement = select(func.count()).select_from(model).where(*clauses)
        total += int((await session.exec(statement)).one())
    return total


def decode_feed_cursor(cursor: str, filters: AuditFeedFilters) -> CursorState:
    return decode_state(cursor, filters.fingerprint())


async def list_feed(
    session: AsyncSession,
    filters: AuditFeedFilters,
    *,
    limit: int,
    cursor: str | None = None,
    include_total: bool = False,
) -> AuditFeedPage:
    """One newest-first page across both stores; the total costs a COUNT and is opt-in."""
    if not 1 <= limit <= MAX_FEED_PAGE_SIZE:
        msg = f"limit must be between 1 and {MAX_FEED_PAGE_SIZE}"
        raise ValueError(msg)
    state = decode_feed_cursor(cursor, filters) if cursor is not None else None
    rows = await _merged_window(session, filters, state, limit + 1)
    items = rows[:limit]
    next_cursor = None
    if len(rows) > limit:
        timestamp, event_id = items[-1].key
        next_cursor = encode_cursor(CursorState(filters.fingerprint(), timestamp, event_id))
    total = await count_feed(session, filters) if include_total else None
    return AuditFeedPage(items=items, next_cursor=next_cursor, total=total)


async def _merged_window(
    session: AsyncSession,
    filters: AuditFeedFilters,
    state: CursorState | None,
    size: int,
) -> list[AuditFeedRow]:
    candidates: list[AuditFeedRow] = []
    for source, model, clauses in _store_plans(filters):
        rows = await _store_window(session, model, clauses, state, size)
        candidates.extend(AuditFeedRow(source, row) for row in rows)
    candidates.sort(key=lambda candidate: candidate.key, reverse=True)
    return candidates[:size]


async def iter_feed(
    session: AsyncSession,
    filters: AuditFeedFilters,
    *,
    batch_size: int = 500,
) -> AsyncIterator[AuditFeedRow]:
    """Every matching row, newest first, walked in batches on the server.

    The caller freezes ``until`` so the walk is a snapshot: a row written while it
    runs is newer than every position still to be read.
    """
    state: CursorState | None = None
    fingerprint = filters.fingerprint()
    while True:
        rows = await _merged_window(session, filters, state, batch_size)
        for row in rows:
            yield row
        if len(rows) < batch_size:
            return
        timestamp, event_id = rows[-1].key
        state = CursorState(fingerprint, timestamp, event_id)


def frozen_until(filters: AuditFeedFilters) -> AuditFeedFilters:
    """Pin an open-ended window at now, so an export is a consistent snapshot."""
    return filters if filters.until is not None else filters.with_until(datetime.now(timezone.utc))


__all__ = [
    "AUTHZ_RESULTS",
    "FEED_RESULTS",
    "MAX_FEED_PAGE_SIZE",
    "RESOURCE_RESULTS",
    "AuditCursorError",
    "AuditFeedFilters",
    "AuditFeedPage",
    "AuditFeedRow",
    "AuditKind",
    "AuditSource",
    "count_feed",
    "frozen_until",
    "iter_feed",
    "list_feed",
]
