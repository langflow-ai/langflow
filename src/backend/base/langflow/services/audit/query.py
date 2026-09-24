"""Reading audit events: filtered, newest first, with keyset pagination.

Offsets are not used because inserts and the retention sweep shift every offset
under a reader. The first page captures the database clock as an upper bound and
carries it in the cursor, so a row timestamped after the traversal started is
never returned; later pages walk ``(timestamp DESC, id DESC)`` from the last row
seen, where the bound is already implied. It is an upper bound on timestamps, not
a commit snapshot: a row is timestamped when its ``INSERT`` runs, so an event
staged before the first page and committed after it can still be reached. A
cursor is bound to the filters that produced it.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import and_, or_
from sqlmodel import col, select

from langflow.services.database.models.audit_event.model import AuditDatabaseClock, AuditEvent, as_utc

if TYPE_CHECKING:
    from sqlalchemy.sql.elements import ColumnElement
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.audit.vocabulary import (
        AuditActorType,
        AuditEventType,
        AuditOperation,
        AuditResourceType,
        AuditResult,
    )

CURSOR_VERSION = 2
MAX_PAGE_SIZE = 200


class AuditCursorError(ValueError):
    """A cursor that is malformed or was issued for different filters."""


def to_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


@dataclass(frozen=True)
class AuditEventFilters:
    """Every filter a read may apply. Values within a field OR; fields AND."""

    resource_type: AuditResourceType
    resource_id: UUID | None = None
    operations: frozenset[AuditOperation] = field(default_factory=frozenset)
    event_types: frozenset[AuditEventType] = field(default_factory=frozenset)
    results: frozenset[AuditResult] = field(default_factory=frozenset)
    actor_types: frozenset[AuditActorType] = field(default_factory=frozenset)
    user_id: UUID | None = None
    actor_id: UUID | None = None
    acting_issuer: str | None = None
    acting_subject: str | None = None
    request_id: UUID | None = None
    since: datetime | None = None
    until: datetime | None = None

    def fingerprint(self) -> str:
        canonical: dict[str, Any] = {
            "resource_type": self.resource_type.value,
            "resource_id": str(self.resource_id) if self.resource_id else None,
            "operations": sorted(value.value for value in self.operations),
            "event_types": sorted(value.value for value in self.event_types),
            "results": sorted(value.value for value in self.results),
            "actor_types": sorted(value.value for value in self.actor_types),
            "user_id": str(self.user_id) if self.user_id else None,
            "actor_id": str(self.actor_id) if self.actor_id else None,
            "acting_issuer": self.acting_issuer,
            "acting_subject": self.acting_subject,
            "request_id": str(self.request_id) if self.request_id else None,
            "since": to_utc(self.since).isoformat() if self.since else None,
            "until": to_utc(self.until).isoformat() if self.until else None,
        }
        encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def clauses(self) -> list[ColumnElement[bool]]:
        clauses: list[ColumnElement[bool]] = [col(AuditEvent.resource_type) == self.resource_type.value]
        exact = {
            AuditEvent.resource_id: self.resource_id,
            AuditEvent.user_id: self.user_id,
            AuditEvent.actor_id: self.actor_id,
            AuditEvent.acting_issuer: self.acting_issuer,
            AuditEvent.acting_subject: self.acting_subject,
            AuditEvent.request_id: self.request_id,
        }
        clauses.extend(col(column) == value for column, value in exact.items() if value is not None)
        any_of = {
            AuditEvent.operation: self.operations,
            AuditEvent.event_type: self.event_types,
            AuditEvent.result: self.results,
            AuditEvent.actor_type: self.actor_types,
        }
        clauses.extend(
            col(column).in_(sorted(value.value for value in values)) for column, values in any_of.items() if values
        )
        if self.since is not None:
            clauses.append(col(AuditEvent.timestamp) >= to_utc(self.since))
        if self.until is not None:
            clauses.append(col(AuditEvent.timestamp) < to_utc(self.until))
        return clauses


@dataclass(frozen=True)
class CursorState:
    fingerprint: str
    cutoff: datetime
    timestamp: datetime
    event_id: UUID


def encode_cursor(state: CursorState) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "f": state.fingerprint,
        "c": state.cutoff.isoformat(),
        "t": state.timestamp.isoformat(),
        "i": str(state.event_id),
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(cursor: str, filters: AuditEventFilters) -> CursorState:
    """Read a cursor back, refusing one that belongs to another traversal."""
    return decode_state(cursor, filters.fingerprint())


def decode_state(cursor: str, fingerprint: str) -> CursorState:
    """Read a cursor back for the traversal whose filters hash to ``fingerprint``."""
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        payload = json.loads(raw.decode("utf-8"))
        state = CursorState(
            fingerprint=str(payload["f"]),
            cutoff=to_utc(datetime.fromisoformat(payload["c"])),
            timestamp=to_utc(datetime.fromisoformat(payload["t"])),
            event_id=UUID(payload["i"]),
        )
        version = payload["v"]
    except (
        AttributeError,  # UUID() of a non-string, e.g. a JSON number.
        binascii.Error,
        UnicodeDecodeError,
        json.JSONDecodeError,
        KeyError,
        OverflowError,
        TypeError,
        ValueError,
    ) as exc:
        msg = "Malformed cursor"
        raise AuditCursorError(msg) from exc
    if version != CURSOR_VERSION:
        msg = "Unsupported cursor version"
        raise AuditCursorError(msg)
    if state.fingerprint != fingerprint:
        msg = "Cursor was issued for different filters"
        raise AuditCursorError(msg)
    return state


def keyset_after(model: Any, state: CursorState) -> ColumnElement[bool]:
    """Rows after ``state`` in ``(timestamp DESC, id DESC)`` order.

    The leading ``timestamp <=`` bound is implied by the rest but is what lets an
    index on the timestamp start the scan at the cursor. Without it the database
    reads every newer row and discards it, so each page costs its depth.
    """
    timestamp, event_id = col(model.timestamp), col(model.id)
    return and_(
        timestamp <= state.timestamp,
        or_(timestamp < state.timestamp, and_(timestamp == state.timestamp, event_id < state.event_id)),
    )


@dataclass(frozen=True)
class AuditEventPage:
    items: list[AuditEvent]
    next_cursor: str | None


async def list_audit_events(
    session: AsyncSession,
    filters: AuditEventFilters,
    *,
    limit: int,
    cursor: str | None = None,
    visibility: ColumnElement[bool] | None = None,
) -> AuditEventPage:
    """One page ordered by ``(timestamp DESC, id DESC)``, never with a total.

    ``visibility`` narrows rows to what the caller may read; it is the caller's
    authorization, applied on top of the filters and not part of the cursor.
    """
    if not 1 <= limit <= MAX_PAGE_SIZE:
        msg = f"limit must be between 1 and {MAX_PAGE_SIZE}"
        raise ValueError(msg)
    clauses = filters.clauses()
    if visibility is not None:
        clauses.append(visibility)

    if cursor is not None:
        state = decode_cursor(cursor, filters)
        cutoff = state.cutoff
        clauses.append(keyset_after(AuditEvent, state))
    else:
        cutoff = to_utc((await session.exec(select(AuditDatabaseClock()))).one())

    clauses.append(col(AuditEvent.timestamp) <= cutoff)

    statement = (
        select(AuditEvent)
        .where(*clauses)
        .order_by(col(AuditEvent.timestamp).desc(), col(AuditEvent.id).desc())
        .limit(limit + 1)
    )
    rows = list((await session.exec(statement)).all())
    if len(rows) <= limit:
        return AuditEventPage(items=rows, next_cursor=None)

    items = rows[:limit]
    last = items[-1]
    next_cursor = encode_cursor(
        CursorState(
            fingerprint=filters.fingerprint(),
            cutoff=cutoff,
            timestamp=as_utc(last.timestamp),
            event_id=last.id,
        )
    )
    return AuditEventPage(items=items, next_cursor=next_cursor)
