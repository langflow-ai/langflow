"""Reading events: filters, ordering, and keyset traversal that never skips or repeats."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from langflow.services.audit.query import (
    MAX_PAGE_SIZE,
    AuditCursorError,
    AuditEventFilters,
    list_audit_events,
)
from langflow.services.audit.vocabulary import (
    PROJECT_CREATE,
    PROJECT_DELETE,
    AuditActorType,
    AuditErrorCode,
    AuditEventType,
    AuditOperation,
    AuditResourceType,
    AuditResult,
)
from langflow.services.audit.writer import build_audit_event
from langflow.services.database.models.audit_event.model import AuditEvent
from sqlmodel import col

from .conftest import project_patch_draft

PROJECTS = AuditResourceType.PROJECT
T0 = datetime(2026, 9, 11, 16, 0, tzinfo=timezone.utc)


async def _insert(session, *, at: datetime, **overrides):
    event = build_audit_event(project_patch_draft(**overrides))
    event.timestamp = at
    session.add(event)
    await session.commit()
    return event


async def _walk(session, filters, limit, cursor=None):
    seen = []
    while True:
        page = await list_audit_events(session, filters, limit=limit, cursor=cursor)
        seen.extend(page.items)
        if page.next_cursor is None:
            return seen
        cursor = page.next_cursor


async def test_a_traversal_returns_every_event_once_newest_first_even_on_timestamp_ties(audit_session):
    inserted = [await _insert(audit_session, at=T0 + timedelta(seconds=index // 5)) for index in range(25)]

    walked = await _walk(audit_session, AuditEventFilters(resource_type=PROJECTS), limit=4)

    expected = sorted(inserted, key=lambda event: (event.timestamp, str(event.id.hex)), reverse=True)
    assert [event.id for event in walked] == [event.id for event in expected]


async def test_rows_timestamped_after_the_traversal_started_are_never_returned(audit_session):
    for index in range(6):
        await _insert(audit_session, at=datetime.now(timezone.utc) - timedelta(minutes=10 - index))
    filters = AuditEventFilters(resource_type=PROJECTS)
    first = await list_audit_events(audit_session, filters, limit=3)

    late = await _insert(audit_session, at=datetime.now(timezone.utc) + timedelta(seconds=1))
    rest = await list_audit_events(audit_session, filters, limit=3, cursor=first.next_cursor)

    assert late.id not in {event.id for event in [*first.items, *rest.items]}
    assert len(first.items) + len(rest.items) == 6


async def test_values_within_a_field_are_ored_and_fields_are_anded(audit_session):
    project = uuid4()
    create = await _insert(
        audit_session, at=T0, resource_id=project, action=PROJECT_CREATE, operation=AuditOperation.CREATE
    )
    delete = await _insert(
        audit_session,
        at=T0 + timedelta(seconds=1),
        resource_id=project,
        action=PROJECT_DELETE,
        operation=AuditOperation.DELETE,
    )
    await _insert(audit_session, at=T0 + timedelta(seconds=2), resource_id=project)
    await _insert(audit_session, at=T0 + timedelta(seconds=3), action=PROJECT_CREATE, operation=AuditOperation.CREATE)

    page = await list_audit_events(
        audit_session,
        AuditEventFilters(
            resource_type=PROJECTS,
            resource_id=project,
            operations=frozenset({AuditOperation.CREATE, AuditOperation.DELETE}),
        ),
        limit=50,
    )

    assert [event.id for event in page.items] == [delete.id, create.id]


async def test_since_is_inclusive_until_is_exclusive_and_offsets_are_honoured(audit_session):
    at_start = await _insert(audit_session, at=T0)
    await _insert(audit_session, at=T0 + timedelta(hours=1))
    brasilia = timezone(timedelta(hours=-3))

    page = await list_audit_events(
        audit_session,
        AuditEventFilters(
            resource_type=PROJECTS,
            since=T0.astimezone(brasilia),
            until=(T0 + timedelta(hours=1)).astimezone(brasilia),
        ),
        limit=50,
    )

    assert [event.id for event in page.items] == [at_start.id]


async def test_failures_and_denials_are_filterable_by_outcome(audit_session):
    failed = await _insert(
        audit_session,
        at=T0,
        result=AuditResult.FAILED,
        error_code=AuditErrorCode.PROJECT_NAME_CONFLICT,
        details={"schema_version": 1, "attempted_fields": ["name"]},
    )
    denied = await _insert(
        audit_session,
        at=T0 + timedelta(seconds=1),
        event_type=AuditEventType.AUTHZ,
        result=AuditResult.DENY,
        error_code=AuditErrorCode.PERMISSION_DENIED,
        details={"schema_version": 1},
    )
    await _insert(audit_session, at=T0 + timedelta(seconds=2))

    page = await list_audit_events(
        audit_session,
        AuditEventFilters(resource_type=PROJECTS, results=frozenset({AuditResult.FAILED, AuditResult.DENY})),
        limit=50,
    )

    assert [event.id for event in page.items] == [denied.id, failed.id]


async def test_another_resource_types_events_never_leak_into_a_view(audit_session):
    await _insert(audit_session, at=T0)

    page = await list_audit_events(audit_session, AuditEventFilters(resource_type=AuditResourceType.FLOW), limit=50)

    assert page.items == []


async def test_visibility_narrows_rows_without_changing_the_cursor_contract(audit_session):
    mine = uuid4()
    for index in range(5):
        await _insert(audit_session, at=T0 + timedelta(seconds=index), resource_id=mine if index % 2 else uuid4())

    page = await list_audit_events(
        audit_session,
        AuditEventFilters(resource_type=PROJECTS, actor_types=frozenset({AuditActorType.USER})),
        limit=1,
        visibility=col(AuditEvent.resource_id) == mine,
    )
    rest = await list_audit_events(
        audit_session,
        AuditEventFilters(resource_type=PROJECTS, actor_types=frozenset({AuditActorType.USER})),
        limit=5,
        cursor=page.next_cursor,
        visibility=col(AuditEvent.resource_id) == mine,
    )

    assert {event.resource_id for event in [*page.items, *rest.items]} == {mine}
    assert len(page.items) + len(rest.items) == 2


async def test_a_cursor_cannot_be_replayed_with_different_filters(audit_session):
    for index in range(3):
        await _insert(audit_session, at=T0 + timedelta(seconds=index))
    page = await list_audit_events(audit_session, AuditEventFilters(resource_type=PROJECTS), limit=1)

    with pytest.raises(AuditCursorError, match="different filters"):
        await list_audit_events(
            audit_session,
            AuditEventFilters(resource_type=PROJECTS, operations=frozenset({AuditOperation.PATCH})),
            limit=1,
            cursor=page.next_cursor,
        )


async def test_a_late_commit_with_an_earlier_timestamp_is_reached_on_a_later_page(audit_session):
    """Invariant 5: the cutoff bounds timestamps, not commits.

    A row is timestamped when its INSERT runs, so an event staged before the
    first page and committed after it keeps a timestamp the walk has not passed
    and is returned later. Each row is still returned once, newest first.
    """
    now = datetime.now(timezone.utc)
    early = [await _insert(audit_session, at=now - timedelta(minutes=10 - index)) for index in range(6)]
    filters = AuditEventFilters(resource_type=PROJECTS)
    first = await list_audit_events(audit_session, filters, limit=3)

    # Older than every row page one returned, so it lies ahead of the cursor.
    staged_earlier = await _insert(audit_session, at=first.items[-1].timestamp - timedelta(seconds=1))
    rest = await _walk(audit_session, filters, limit=3, cursor=first.next_cursor)

    walked = [*first.items, *rest]
    assert staged_earlier.id in {event.id for event in walked}
    assert len(walked) == len(early) + 1
    assert len({event.id for event in walked}) == len(walked)
    assert [event.timestamp for event in walked] == sorted((event.timestamp for event in walked), reverse=True)


@pytest.mark.parametrize(
    ("field", "value"),
    [("i", 1), ("t", "2026-13-01T00:00:00"), ("f", {"not": "a string"})],
)
async def test_a_cursor_with_an_ill_typed_field_is_refused(audit_session, field, value):
    """A hand-made cursor is caller input: it answers 400, never 500."""
    payload = {
        "v": 2,
        "f": "x",
        "c": "2026-01-01T00:00:00+00:00",
        "t": "2026-01-01T00:00:00+00:00",
        "i": str(uuid4()),
        field: value,
    }
    cursor = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")

    with pytest.raises(AuditCursorError):
        await list_audit_events(audit_session, AuditEventFilters(resource_type=PROJECTS), limit=1, cursor=cursor)


async def test_a_cursor_with_an_out_of_range_datetime_is_refused(audit_session):
    """Astimezone raises OverflowError near datetime.min, which is not a ValueError."""
    payload = {
        "v": 2,
        "f": "x",
        "c": "0001-01-01T00:00:00+01:00",
        "t": "2026-01-01T00:00:00",
        "i": str(uuid4()),
    }
    cursor = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")

    with pytest.raises(AuditCursorError):
        await list_audit_events(audit_session, AuditEventFilters(resource_type=PROJECTS), limit=1, cursor=cursor)


@pytest.mark.parametrize("cursor", ["not-a-cursor", "", "e30", "eyJ2IjoxfQ", "%%%"])
async def test_a_malformed_cursor_is_refused(audit_session, cursor):
    with pytest.raises(AuditCursorError):
        await list_audit_events(audit_session, AuditEventFilters(resource_type=PROJECTS), limit=1, cursor=cursor)


@pytest.mark.parametrize("limit", [0, -1, MAX_PAGE_SIZE + 1])
async def test_page_size_is_bounded(audit_session, limit):
    with pytest.raises(ValueError, match="limit"):
        await list_audit_events(audit_session, AuditEventFilters(resource_type=PROJECTS), limit=limit)


async def test_an_empty_history_has_no_next_cursor(audit_session):
    page = await list_audit_events(audit_session, AuditEventFilters(resource_type=PROJECTS), limit=MAX_PAGE_SIZE)

    assert (page.items, page.next_cursor) == ([], None)
