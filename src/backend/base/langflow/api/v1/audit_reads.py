"""The request and response contract shared by the resource-specific audit read APIs.

Parsing is strict on purpose: the Control Plane translates these events into its
public API, and a filter that is silently ignored returns a feed that looks
complete but is not. Unknown parameters, empty values, malformed identifiers or
timestamps, unsupported values, and a cursor reused with other filters all answer 400.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel, field_serializer
from sqlalchemy import func
from sqlalchemy.orm import aliased
from sqlmodel import and_, col, or_, select

from langflow.services.audit.query import MAX_PAGE_SIZE, AuditCursorError, AuditEventFilters, list_audit_events
from langflow.services.audit.vocabulary import AuditActorType, AuditEventType, AuditOperation, AuditResult
from langflow.services.database.models.audit_event.model import (
    ACTING_ISSUER_MAX_LENGTH,
    ACTING_SUBJECT_MAX_LENGTH,
    AuditEvent,
    as_utc,
)
from langflow.services.deps import get_authorization_service

if TYPE_CHECKING:
    from fastapi import Request
    from sqlalchemy.sql.elements import ColumnElement
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.audit.query import AuditEventPage
    from langflow.services.audit.vocabulary import AuditResourceType
    from langflow.services.database.models.user.model import User

DEFAULT_PAGE_SIZE = 50
_REPEATABLE: dict[str, type[Enum]] = {
    "operation": AuditOperation,
    "event_type": AuditEventType,
    "result": AuditResult,
    "actor_type": AuditActorType,
}
_SINGLE_UUIDS = ("user_id", "actor_id", "request_id")
_TEXT_LIMITS = {"acting_subject": ACTING_SUBJECT_MAX_LENGTH, "acting_issuer": ACTING_ISSUER_MAX_LENGTH}
_RFC3339 = re.compile(
    r"^(?P<base>\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2})(?:\.(?P<fraction>\d{1,6}))?(?P<offset>[Zz]|[+-]\d{2}:\d{2})$"
)


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _uuid(name: str, value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        msg = f"{name} must be a UUID"
        raise _bad_request(msg) from exc


def _timestamp(name: str, value: str) -> datetime:
    """RFC 3339 with a mandatory offset; Python 3.10 cannot parse ``Z`` or short fractions itself."""
    match = _RFC3339.fullmatch(value)
    if match is None:
        msg = f"{name} must be an RFC 3339 timestamp with a timezone offset"
        raise _bad_request(msg)
    offset = match["offset"].upper().replace("Z", "+00:00")
    fraction = f".{match['fraction'].ljust(6, '0')}" if match["fraction"] else ""
    try:
        return datetime.fromisoformat(f"{match['base'].replace('t', 'T')}{fraction}{offset}").astimezone(timezone.utc)
    except (OverflowError, ValueError) as exc:
        msg = f"{name} is not a valid timestamp"
        raise _bad_request(msg) from exc


def _limit(value: str | None) -> int:
    if value is None:
        return DEFAULT_PAGE_SIZE
    msg = f"limit must be an integer from 1 through {MAX_PAGE_SIZE}"
    if not (value.isascii() and value.isdigit()):
        raise _bad_request(msg)
    try:
        parsed = int(value)
    except ValueError as exc:  # More digits than int() will convert.
        raise _bad_request(msg) from exc
    if not 1 <= parsed <= MAX_PAGE_SIZE:
        raise _bad_request(msg)
    return parsed


@dataclass(frozen=True)
class AuditReadQuery:
    filters: AuditEventFilters
    cursor: str | None
    limit: int


#: Authentication, not filtering: ``APIKeyQuery`` reads this from the query string.
_AUTH_PARAMS = frozenset({"x-api-key"})


def _grouped(request: Request, allowed: set[str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for key, value in request.query_params.multi_items():
        if key in _AUTH_PARAMS:
            continue
        if key not in allowed:
            msg = f"Unknown query parameter: {key}"
            raise _bad_request(msg)
        if value == "":
            msg = f"Empty value for query parameter: {key}"
            raise _bad_request(msg)
        grouped.setdefault(key, []).append(value)
    for key, values in grouped.items():
        if key not in _REPEATABLE and len(values) > 1:
            msg = f"Query parameter may appear once: {key}"
            raise _bad_request(msg)
    return grouped


def _enum_values(key: str, values: list[str], allowed_values: frozenset[Enum] | None = None) -> frozenset[Any]:
    enum = _REPEATABLE[key]
    try:
        parsed = frozenset(enum(value) for value in values)
    except ValueError as exc:
        msg = f"Unsupported value for {key}"
        raise _bad_request(msg) from exc
    if allowed_values is not None and not parsed.issubset(allowed_values):
        msg = f"Unsupported value for {key}"
        raise _bad_request(msg)
    return parsed


def parse_audit_query(
    request: Request,
    *,
    resource_type: AuditResourceType,
    id_param: str,
    allowed_operations: frozenset[AuditOperation],
    allowed_event_types: frozenset[AuditEventType],
    allowed_results: frozenset[AuditResult],
) -> AuditReadQuery:
    """Turn the raw query string into filters, or answer 400."""
    allowed = {id_param, *_REPEATABLE, *_SINGLE_UUIDS, *_TEXT_LIMITS, "since", "until", "cursor", "limit"}
    grouped = _grouped(request, allowed)
    single = {key: values[0] for key, values in grouped.items() if key not in _REPEATABLE}
    for key, limit in _TEXT_LIMITS.items():
        if key in single and len(single[key]) > limit:
            msg = f"{key} is longer than {limit} characters"
            raise _bad_request(msg)
    if "acting_issuer" in single and "acting_subject" not in single:
        msg = "acting_issuer must be paired with acting_subject"
        raise _bad_request(msg)
    since = _timestamp("since", single["since"]) if "since" in single else None
    until = _timestamp("until", single["until"]) if "until" in single else None
    if since is not None and until is not None and until <= since:
        msg = "until must be later than since"
        raise _bad_request(msg)
    uuids = {key: _uuid(key, single[key]) for key in (id_param, *_SINGLE_UUIDS) if key in single}
    allowed_enums: dict[str, frozenset[Enum]] = {
        "operation": allowed_operations,
        "event_type": allowed_event_types,
        "result": allowed_results,
    }
    enums = {
        key: _enum_values(key, values, allowed_enums.get(key)) for key, values in grouped.items() if key in _REPEATABLE
    }
    filters = AuditEventFilters(
        resource_type=resource_type,
        resource_id=uuids.get(id_param),
        operations=enums.get("operation", allowed_operations),
        event_types=enums.get("event_type", allowed_event_types),
        results=enums.get("result", allowed_results),
        actor_types=enums.get("actor_type", frozenset()),
        user_id=uuids.get("user_id"),
        actor_id=uuids.get("actor_id"),
        acting_issuer=single.get("acting_issuer"),
        acting_subject=single.get("acting_subject"),
        request_id=uuids.get("request_id"),
        since=since,
        until=until,
    )
    return AuditReadQuery(filters=filters, cursor=single.get("cursor"), limit=_limit(single.get("limit")))


async def read_audit_page(
    session: AsyncSession,
    query: AuditReadQuery,
    visibility: ColumnElement[bool] | None,
) -> AuditEventPage:
    try:
        return await list_audit_events(
            session, query.filters, limit=query.limit, cursor=query.cursor, visibility=visibility
        )
    except AuditCursorError as exc:
        raise _bad_request(str(exc)) from exc


async def plugin_decides_visibility() -> bool:
    """True when a registered plugin may widen reads; the OSS pass-through never does."""
    authz = get_authorization_service()
    return bool(await authz.supports_cross_user_fetch() and await authz.is_enabled())


# The same table read from the caller's side, so the window can be correlated.
#: The same table read from the resource's side, to find where its current life began.
_Incarnation = aliased(AuditEvent)


async def owner_visibility(user: User, owned_resource_ids: Any) -> ColumnElement[bool] | None:
    """The OSS floor: events the caller made, and events on what they own in its current life.

    Superusers read everything, and so does a caller a plugin authorized, because
    then the plugin, not ownership, decides what is visible.

    Ownership is of a UUID, and a UUID can be reused: ``PUT /flows/{id}`` and
    ``PUT /projects/{id}`` create at an id the caller chooses, and a delete frees
    that id, for another resource type as much as for the same one. Owning the id
    today therefore cannot grant everything ever recorded for it, or re-creating a
    deleted resource would hand its previous owners' trails to whoever asked.

    The window is the resource's current life: it opens at the newest ``create``
    for that id *and* resource type, so an id that changed hands twice shows only
    what happened after it came back. Without such an event — auditing was off
    when the resource was created — the period cannot be established and the
    ownership side matches nothing. The caller's own events stay readable either
    way, and a deliberate transfer of ownership without a new ``create`` is not
    something Langflow does today; if it ever does, the period has to come from a
    recorded owner rather than from the create.
    """
    if user.is_superuser or await plugin_decides_visibility():
        return None
    current_life_began = (
        select(func.max(col(_Incarnation.timestamp)))
        .where(
            col(_Incarnation.resource_id) == col(AuditEvent.resource_id),
            col(_Incarnation.resource_type) == col(AuditEvent.resource_type),
            col(_Incarnation.operation) == AuditOperation.CREATE.value,
        )
        .scalar_subquery()
    )
    # A NULL bound (no create recorded) compares as unknown, so the row is left
    # out: the ownership side fails closed rather than opening the whole history.
    owned_in_its_current_life = and_(
        col(AuditEvent.resource_id).in_(owned_resource_ids),
        col(AuditEvent.timestamp) >= current_life_began,
    )
    return or_(owned_in_its_current_life, col(AuditEvent.user_id) == user.id)


class AuditActorRead(BaseModel):
    type: str
    id: UUID | None
    user_id: UUID | None
    acting_issuer: str | None
    acting_subject: str | None


def actor_of(event: AuditEvent) -> AuditActorRead:
    return AuditActorRead(
        type=event.actor_type,
        id=event.actor_id,
        user_id=event.user_id,
        acting_issuer=event.acting_issuer,
        acting_subject=event.acting_subject,
    )


class AuditEventReadBase(BaseModel):
    id: UUID
    timestamp: datetime
    action: str
    operation: str
    event_type: str
    result: str
    error_code: str | None
    request_id: UUID
    actor: AuditActorRead
    details: dict[str, Any]

    @field_serializer("timestamp")
    def _rfc3339(self, value: datetime) -> str:
        # Full precision: the order is (timestamp, id), and a rounded timestamp would let
        # a client re-sorting a page disagree with the order the server returned.
        return as_utc(value).isoformat(timespec="microseconds").replace("+00:00", "Z")


def base_fields(event: AuditEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "timestamp": event.timestamp,
        "action": event.action,
        "operation": event.operation,
        "event_type": event.event_type,
        "result": event.result,
        "error_code": event.error_code,
        "request_id": event.request_id,
        "actor": actor_of(event),
        "details": event.details,
    }


def openapi_parameters(id_param: str, id_description: str) -> list[dict[str, Any]]:
    """Document the strictly parsed query string, which the handler reads itself."""

    def param(name: str, description: str, schema: dict[str, Any]) -> dict[str, Any]:
        return {"name": name, "in": "query", "required": False, "description": description, "schema": schema}

    def many(name: str, enum: type[Enum]) -> dict[str, Any]:
        values = [member.value for member in enum]
        return param(name, "Repeatable; values are ORed.", {"type": "array", "items": {"enum": values}})

    return [
        param(id_param, id_description, {"type": "string", "format": "uuid"}),
        many("operation", AuditOperation),
        many("event_type", AuditEventType),
        many("result", AuditResult),
        param("user_id", "Exact Langflow account.", {"type": "string", "format": "uuid"}),
        many("actor_type", AuditActorType),
        param("actor_id", "Exact authenticated principal or credential.", {"type": "string", "format": "uuid"}),
        param("acting_subject", "Exact represented-user subject.", {"type": "string"}),
        param("acting_issuer", "Represented-user issuer; requires acting_subject.", {"type": "string"}),
        param("request_id", "Exact request correlation id.", {"type": "string", "format": "uuid"}),
        param("since", "Inclusive RFC 3339 timestamp.", {"type": "string", "format": "date-time"}),
        param("until", "Exclusive RFC 3339 timestamp, later than since.", {"type": "string", "format": "date-time"}),
        param("cursor", "Opaque cursor from the previous page.", {"type": "string"}),
        param("limit", "Page size.", {"type": "integer", "minimum": 1, "maximum": MAX_PAGE_SIZE, "default": 50}),
    ]
