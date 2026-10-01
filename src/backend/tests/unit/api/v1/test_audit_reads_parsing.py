"""The strict query contract shared by the audit read APIs: anything unclear answers 400."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from langflow.api.v1.audit_reads import DEFAULT_PAGE_SIZE, parse_audit_query
from langflow.services.audit.vocabulary import AuditEventType, AuditOperation, AuditResourceType, AuditResult
from starlette.requests import Request

PROJECT = AuditResourceType.PROJECT
OPERATIONS = frozenset({AuditOperation.CREATE, AuditOperation.REPLACE, AuditOperation.PATCH, AuditOperation.DELETE})
EVENT_TYPES = frozenset({AuditEventType.ACTION})
RESULTS = frozenset({AuditResult.SUCCEEDED, AuditResult.FAILED})


def _request(query: str) -> Request:
    return Request({"type": "http", "method": "GET", "path": "/", "query_string": query.encode("latin-1")})


def _parse(query: str):
    return parse_audit_query(
        _request(query),
        resource_type=PROJECT,
        id_param="project_id",
        allowed_operations=OPERATIONS,
        allowed_event_types=EVENT_TYPES,
        allowed_results=RESULTS,
    )


def test_no_parameters_means_every_project_event_with_the_default_page():
    parsed = _parse("")

    assert parsed.limit == DEFAULT_PAGE_SIZE
    assert parsed.cursor is None
    assert parsed.filters.resource_type is PROJECT
    assert parsed.filters.resource_id is None


def test_repeated_values_are_collected_and_fields_combined():
    project_id, user_id = uuid4(), uuid4()

    parsed = _parse(
        f"project_id={project_id}&operation=create&operation=delete&result=failed&user_id={user_id}"
        "&acting_subject=auth0%7C123&acting_issuer=https%3A%2F%2Fidp.example&limit=200"
    )

    assert parsed.filters.resource_id == project_id
    assert parsed.filters.operations == {AuditOperation.CREATE, AuditOperation.DELETE}
    assert parsed.filters.results == {AuditResult.FAILED}
    assert (parsed.filters.acting_subject, parsed.filters.acting_issuer) == ("auth0|123", "https://idp.example")
    assert parsed.limit == 200


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-09-11T16:42:18Z", datetime(2026, 9, 11, 16, 42, 18, tzinfo=timezone.utc)),
        ("2026-09-11T16:42:18.2z", datetime(2026, 9, 11, 16, 42, 18, 200000, tzinfo=timezone.utc)),
        ("2026-09-11T13:42:18.284-03:00", datetime(2026, 9, 11, 16, 42, 18, 284000, tzinfo=timezone.utc)),
        ("2026-09-11t16:42:18%2B00:00", datetime(2026, 9, 11, 16, 42, 18, tzinfo=timezone.utc)),
    ],
)
def test_rfc3339_timestamps_are_read_as_utc(value, expected):
    assert _parse(f"since={value}").filters.since == expected


@pytest.mark.parametrize(
    ("query", "message"),
    [
        ("flow_id=00000000-0000-0000-0000-000000000000", "Unknown query parameter"),
        ("total=1", "Unknown query parameter"),
        ("operation=", "Empty value"),
        ("project_id=", "Empty value"),
        ("project_id=not-a-uuid", "must be a UUID"),
        (
            "project_id=11111111-1111-1111-1111-111111111111&project_id=22222222-2222-2222-2222-222222222222",
            "may appear once",
        ),
        ("operation=update", "Unsupported value for operation"),
        ("operation=run", "Unsupported value for operation"),
        ("operation=create&operation=upsert", "Unsupported value for operation"),
        ("event_type=Action", "Unsupported value for event_type"),
        ("event_type=authz", "Unsupported value for event_type"),
        ("result=denied", "Unsupported value for result"),
        ("result=deny", "Unsupported value for result"),
        ("actor_type=apiKey", "Unsupported value for actor_type"),
        ("request_id=123", "must be a UUID"),
        ("since=2026-09-11", "RFC 3339"),
        ("since=2026-09-11T16:42:18", "RFC 3339"),
        ("since=2026-09-11T16:42:18 00:00", "RFC 3339"),
        ("since=2026-02-30T16:42:18Z", "not a valid timestamp"),
        ("since=2026-09-11T16:42:18.1234567Z", "RFC 3339"),
        ("since=2026-09-11T16:00:00Z&until=2026-09-11T16:00:00Z", "later than since"),
        ("since=2026-09-11T16:00:00Z&until=2026-09-11T12:59:59-03:00", "later than since"),
        ("acting_issuer=https%3A%2F%2Fidp.example", "paired with acting_subject"),
        ("acting_subject=" + "s" * 513, "longer than"),
        ("limit=0", "limit"),
        ("limit=201", "limit"),
        ("limit=ten", "limit"),
        ("limit=-5", "limit"),
        ("limit=%C2%B2", "limit"),
        ("limit=50&limit=60", "may appear once"),
    ],
)
def test_anything_unclear_is_refused_with_400(query, message):
    with pytest.raises(HTTPException) as refused:
        _parse(query)

    assert refused.value.status_code == 400
    assert message in refused.value.detail
