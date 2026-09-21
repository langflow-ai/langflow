"""``GET /api/v1/audits`` and its export against the real API and database.

Rows are written straight into both stores with fixed timestamps, and every read
is windowed around them, so events the login itself records never interfere.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import status
from langflow.services.database.models.audit_event.model import AuditEvent
from langflow.services.database.models.auth import AuthzAuditLog
from langflow.services.deps import session_scope

BASE = datetime(2021, 3, 4, 12, 0, tzinfo=timezone.utc)
WINDOW = "since=2021-03-04T00:00:00Z&until=2021-03-05T00:00:00Z"
ITEM_KEYS = {
    "id",
    "timestamp",
    "source",
    "kind",
    "action",
    "resource_type",
    "resource_id",
    "resource_name",
    "result",
    "user_id",
    "actor_type",
    "actor_id",
    "actor",
    "operation",
    "error_code",
    "request_id",
    "details",
}


def _at(minutes: float) -> datetime:
    return BASE - timedelta(minutes=minutes)


def resource_event(minutes: float, **fields) -> AuditEvent:
    values = {
        "resource_type": "flow",
        "resource_id": uuid4(),
        "resource_name": "Support triage",
        "actor_type": "user",
        "action": "flow:write",
        "operation": "patch",
        "event_type": "action",
        "result": "succeeded",
        "request_id": uuid4(),
        "details": {"schema_version": 1},
        "timestamp": _at(minutes),
    }
    return AuditEvent(**{**values, **fields})


def authz_event(minutes: float, **fields) -> AuthzAuditLog:
    values = {
        "action": "role:update",
        "resource_type": "role",
        "resource_id": uuid4(),
        "result": "allow",
        "actor_type": "user",
        "details": {"event": "mutation"},
        "timestamp": _at(minutes),
    }
    return AuthzAuditLog(**{**values, **fields})


async def seed(*rows) -> list[str]:
    async with session_scope() as session:
        session.add_all(rows)
        await session.flush()
        return [str(row.id) for row in rows]


async def feed(client, headers, query: str = "") -> dict:
    separator = "&" if query else ""
    response = await client.get(f"api/v1/audits?{WINDOW}{separator}{query}", headers=headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


async def ids(client, headers, query: str = "") -> list[str]:
    return [item["id"] for item in (await feed(client, headers, query))["items"]]


async def test_both_stores_merge_newest_first_in_one_page(client, logged_in_headers_super_user):
    expected = await seed(
        authz_event(1),
        resource_event(2, resource_name="Support triage"),
        authz_event(3, details={"event": "authorization_decision"}),
        resource_event(4, event_type="authz", result="deny", error_code="PERMISSION_DENIED"),
    )

    page = await feed(client, logged_in_headers_super_user)

    assert [item["id"] for item in page["items"]] == expected
    assert [(item["source"], item["kind"]) for item in page["items"]] == [
        ("authz", "action"),
        ("resource", "action"),
        ("authz", "check"),
        ("resource", "check"),
    ]
    assert page["next_cursor"] is None
    assert page["total"] is None
    for item in page["items"]:
        assert set(item) == ITEM_KEYS
        assert item["timestamp"].endswith("Z")
    assert page["items"][1]["resource_name"] == "Support triage"
    assert page["items"][1]["operation"] == "patch"
    assert page["items"][0]["resource_name"] is None


async def test_a_cursor_walk_visits_every_row_once_across_stores_and_ties(client, logged_in_headers_super_user):
    rows = []
    for minute in range(12):
        rows.append(resource_event(minute))
        rows.append(authz_event(minute))
    rows.extend(authz_event(5) for _ in range(3))
    await seed(*rows)
    expected = [str(row.id) for row in sorted(rows, key=lambda row: (row.timestamp, UUID(str(row.id))), reverse=True)]

    walked: list[str] = []
    cursor = None
    requests = 0
    while True:
        query = "limit=4" + (f"&cursor={cursor}" if cursor else "")
        page = await feed(client, logged_in_headers_super_user, query)
        requests += 1
        walked.extend(item["id"] for item in page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break

    assert walked == expected
    assert requests == -(-len(expected) // 4)


async def test_a_cursor_is_bound_to_the_filters_that_issued_it(client, logged_in_headers_super_user):
    await seed(*(resource_event(minute) for minute in range(3)))
    page = await feed(client, logged_in_headers_super_user, "limit=1")

    response = await client.get(
        f"api/v1/audits?{WINDOW}&limit=1&result=failed&cursor={page['next_cursor']}",
        headers=logged_in_headers_super_user,
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "different filters" in response.json()["detail"]


async def test_filters_hold_in_both_stores(client, logged_in_headers_super_user):
    # authz_audit_log.user_id references user.id, so the row names a real account.
    whoami = await client.get("api/v1/users/whoami", headers=logged_in_headers_super_user)
    user_id = UUID(whoami.json()["id"])
    request_id = uuid4()
    resource_id = uuid4()
    await seed(
        resource_event(1, user_id=user_id, resource_type="project", resource_id=resource_id),
        resource_event(2, operation="delete", action="flow:delete", request_id=request_id),
        resource_event(3, event_type="authz", result="allow", actor_type="api_key"),
        authz_event(4, user_id=user_id, resource_type="project", resource_id=resource_id),
        authz_event(5, result="owner_override", details={"event": "authorization_decision"}),
        authz_event(6, actor_type=None, details=None, action="flow:read", resource_type="flow"),
        authz_event(7, result="skip", details={"event": "mutation", "request_id": str(request_id)}),
    )

    async def matches(query: str) -> list[tuple[str, str]]:
        page = await feed(client, logged_in_headers_super_user, query)
        return [(item["source"], item["action"]) for item in page["items"]]

    assert await matches(f"user_id={user_id}") == [("resource", "flow:write"), ("authz", "role:update")]
    assert await matches(f"resource_id={resource_id}") == [("resource", "flow:write"), ("authz", "role:update")]
    assert await matches("resource_type=project") == [("resource", "flow:write"), ("authz", "role:update")]
    assert await matches("action=flow:delete&action=flow:read") == [
        ("resource", "flow:delete"),
        ("authz", "flow:read"),
    ]
    assert len(await matches("exclude_action=role:update")) == 4
    # An operation is a resource-store concept, so authorization rows never match one.
    assert await matches("operation=delete") == [("resource", "flow:delete")]
    # Each result exists in only one store, or both.
    assert await matches("result=owner_override") == [("authz", "role:update")]
    assert len(await matches("result=succeeded")) == 2
    assert len(await matches("result=allow")) == 3
    # A check is a tagged decision; untagged history is kept as an action.
    assert await matches("kind=check") == [("resource", "flow:write"), ("authz", "role:update")]
    assert ("authz", "flow:read") in await matches("kind=action")
    # Rows written before actor attribution read as unknown.
    assert await matches("actor_type=unknown") == [("authz", "flow:read")]
    assert await matches("actor_type=api_key") == [("resource", "flow:write")]
    assert await matches(f"request_id={request_id}") == [("resource", "flow:delete"), ("authz", "role:update")]
    assert len(await matches("source=authz")) == 4
    assert await matches("source=resource&operation=delete&result=skip") == []


async def test_the_total_is_opt_in_and_counts_every_match(client, logged_in_headers_super_user):
    await seed(*(resource_event(minute) for minute in range(5)), *(authz_event(minute) for minute in range(4)))

    assert (await feed(client, logged_in_headers_super_user, "limit=2"))["total"] is None
    assert (await feed(client, logged_in_headers_super_user, "limit=2&include_total=true"))["total"] == 9
    assert (await feed(client, logged_in_headers_super_user, "source=authz&include_total=true"))["total"] == 4


@pytest.mark.parametrize(
    "query",
    [
        "unknown=1",
        "limit=0",
        "limit=201",
        "result=maybe",
        "kind=everything",
        "source=elsewhere",
        "operation=rename",
        "resource_type=Flow%20Type",
        "user_id=not-a-uuid",
        "since=2021-03-04",
        "since=2021-03-05T00:00:00Z&until=2021-03-04T00:00:00Z",
        "include_total=yes",
        "limit=5&limit=6",
        "action=",
        "cursor=not-a-cursor",
    ],
)
async def test_a_malformed_query_is_refused(client, logged_in_headers_super_user, query):
    response = await client.get(f"api/v1/audits?{query}", headers=logged_in_headers_super_user)

    assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text


async def test_the_feed_and_its_export_are_for_superusers(client, logged_in_headers):
    for path in ("api/v1/audits", "api/v1/audits/export"):
        response = await client.get(path, headers=logged_in_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_the_csv_export_streams_the_filtered_snapshot(client, logged_in_headers_super_user):
    await seed(
        authz_event(1, details={"event": "mutation", "note": "=HYPERLINK(1)", "b": 2, "a": 1}),
        resource_event(2),
        authz_event(3, result="deny", details={"event": "access", "reason": "administration_required"}),
    )

    response = await client.get(
        f"api/v1/audits/export?{WINDOW}&exclude_action=nothing:matches", headers=logged_in_headers_super_user
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"].startswith('attachment; filename="langflow-audit-')
    records = list(csv.reader(io.StringIO(response.text)))
    assert records[0][:9] == [
        "timestamp",
        "user_id",
        "actor_type",
        "actor_id",
        "action",
        "resource_type",
        "resource_id",
        "result",
        "details",
    ]
    rows = [dict(zip(records[0], record, strict=True)) for record in records[1:]]
    assert [(row["source"], row["result"]) for row in rows] == [
        ("authz", "allow"),
        ("resource", "succeeded"),
        (
            "authz",
            "deny",
        ),
    ]
    assert json.loads(rows[0]["details"]) == {"a": 1, "b": 2, "event": "mutation", "note": "=HYPERLINK(1)"}
    assert list(json.loads(rows[0]["details"])) == ["a", "b", "event", "note"]
    assert response.text.count("\r\n") == 4

    filtered = await client.get(f"api/v1/audits/export?{WINDOW}&source=resource", headers=logged_in_headers_super_user)
    assert len(list(csv.reader(io.StringIO(filtered.text)))) == 2


async def test_a_leading_formula_character_is_neutralized(client, logged_in_headers_super_user):
    await seed(resource_event(1, resource_name="=cmd|'/c calc'!A1"))

    response = await client.get(f"api/v1/audits/export?{WINDOW}", headers=logged_in_headers_super_user)

    [header, row] = list(csv.reader(io.StringIO(response.text)))
    assert dict(zip(header, row, strict=True))["resource_name"] == "'=cmd|'/c calc'!A1"


async def test_the_ndjson_export_carries_the_feed_items(client, logged_in_headers_super_user):
    expected = await seed(resource_event(1), authz_event(2))

    response = await client.get(f"api/v1/audits/export?{WINDOW}&format=ndjson", headers=logged_in_headers_super_user)

    assert response.headers["content-type"].startswith("application/x-ndjson")
    items = [json.loads(line) for line in response.text.splitlines()]
    assert [item["id"] for item in items] == expected
    assert set(items[0]) == ITEM_KEYS


async def test_an_export_rejects_an_unknown_format(client, logged_in_headers_super_user):
    response = await client.get("api/v1/audits/export?format=xlsx", headers=logged_in_headers_super_user)

    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_an_export_spanning_many_batches_keeps_every_row_once_in_order(client, logged_in_headers_super_user):
    rows = [resource_event(index / 60) if index % 3 else authz_event(index / 60) for index in range(1203)]
    await seed(*rows)
    expected = [str(row.id) for row in sorted(rows, key=lambda row: (row.timestamp, UUID(str(row.id))), reverse=True)]

    response = await client.get(f"api/v1/audits/export?{WINDOW}&format=ndjson", headers=logged_in_headers_super_user)

    exported = [json.loads(line)["id"] for line in response.text.splitlines()]
    assert exported == expected
