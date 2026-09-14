"""``GET /api/v1/projects/audits`` against the real API, database and authorization guards."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import status
from langflow.services.database.models.auth import AuthzRole
from langflow.services.deps import get_settings_service, session_scope

from .audit_helpers import enabled_audit, events_by_user, login, make_user

pytestmark = pytest.mark.usefixtures("audit_on")

ITEM_KEYS = {
    "id",
    "timestamp",
    "project_id",
    "project_name",
    "action",
    "operation",
    "event_type",
    "result",
    "error_code",
    "request_id",
    "actor",
    "details",
}
ACTOR_KEYS = {"type", "id", "user_id", "acting_issuer", "acting_subject"}


@pytest.fixture
def audit_on(client):  # noqa: ARG001
    yield from enabled_audit()


async def _project(client, headers, **fields) -> dict:
    response = await client.post("api/v1/projects/", json={"name": f"p-{uuid4().hex}", **fields}, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


async def _audits(client, headers, query: str = "") -> dict:
    response = await client.get(f"api/v1/projects/audits{query}", headers=headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


async def test_a_page_has_the_contract_shape_newest_first(client, logged_in_headers, active_user):
    project = await _project(client, logged_in_headers, description="d")
    await client.patch(f"api/v1/projects/{project['id']}", json={"description": "e"}, headers=logged_in_headers)
    await client.delete(f"api/v1/projects/{project['id']}", headers=logged_in_headers)

    page = await _audits(client, logged_in_headers, f"?project_id={project['id']}")

    assert set(page) == {"items", "next_cursor"}
    assert page["next_cursor"] is None
    assert [item["operation"] for item in page["items"]] == ["delete", "patch", "create"]
    for item in page["items"]:
        assert set(item) == ITEM_KEYS
        assert set(item["actor"]) == ACTOR_KEYS
        assert item["timestamp"].endswith("Z")
        assert len(item["timestamp"]) == len("2026-09-11T16:42:18.284123Z")
        assert item["project_id"] == project["id"]
    delete = page["items"][0]
    assert delete["project_name"] == project["name"]
    assert delete["actor"] == {
        "type": "user",
        "id": str(active_user.id),
        "user_id": str(active_user.id),
        "acting_issuer": None,
        "acting_subject": None,
    }
    assert delete["error_code"] is None
    assert page["items"][1]["details"] == {"schema_version": 1, "description": "e"}


async def test_a_cursor_walk_returns_every_event_once_and_refuses_other_filters(client, logged_in_headers):
    created = {(await _project(client, logged_in_headers))["id"] for _ in range(23)}

    seen, cursor = [], None
    while True:
        page = await _audits(
            client, logged_in_headers, "?operation=create&limit=7" + (f"&cursor={cursor}" if cursor else "")
        )
        seen.extend(page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
        refused = await client.get(
            f"api/v1/projects/audits?operation=delete&limit=7&cursor={cursor}", headers=logged_in_headers
        )
        assert refused.status_code == status.HTTP_400_BAD_REQUEST

    ids = [item["id"] for item in seen]
    assert len(ids) == len(set(ids))
    assert created <= {item["project_id"] for item in seen}
    keys = [(item["timestamp"], item["id"]) for item in seen]
    assert keys == sorted(keys, reverse=True)


async def test_without_a_plugin_a_user_sees_only_their_projects_and_their_own_actions(client, logged_in_headers):
    mine = await _project(client, logged_in_headers)
    _stranger_id, stranger_name = await make_user("stranger")
    stranger_headers = await login(client, stranger_name)
    theirs = await _project(client, stranger_headers)

    my_feed = await _audits(client, logged_in_headers, "?limit=200")
    probing = await _audits(client, logged_in_headers, f"?project_id={theirs['id']}")

    visible = {item["project_id"] for item in my_feed["items"]}
    assert mine["id"] in visible
    assert theirs["id"] not in visible
    assert probing["items"] == []


async def test_a_superuser_reads_every_project(client, logged_in_headers, logged_in_headers_super_user):
    theirs = await _project(client, logged_in_headers)

    feed = await _audits(client, logged_in_headers_super_user, f"?project_id={theirs['id']}")

    assert [item["operation"] for item in feed["items"]] == ["create"]


async def test_a_deleted_project_stays_readable_by_whoever_acted_on_it(client, logged_in_headers):
    project = await _project(client, logged_in_headers)
    await client.delete(f"api/v1/projects/{project['id']}", headers=logged_in_headers)

    feed = await _audits(client, logged_in_headers, f"?project_id={project['id']}&operation=delete")

    assert [(item["operation"], item["project_name"]) for item in feed["items"]] == [("delete", project["name"])]


async def test_flow_events_never_appear_in_the_project_feed(client, logged_in_headers):
    flow = await client.post("api/v1/flows/", json={"name": f"f-{uuid4().hex}", "data": {}}, headers=logged_in_headers)

    feed = await _audits(client, logged_in_headers, "?limit=200")

    assert flow.json()["id"] not in {item["project_id"] for item in feed["items"]}


async def test_reading_records_nothing(client, logged_in_headers, active_user):
    await _project(client, logged_in_headers)
    before = len(await events_by_user(active_user.id))

    await _audits(client, logged_in_headers)
    await client.get("api/v1/projects/audits?bogus=1", headers=logged_in_headers)

    assert len(await events_by_user(active_user.id)) == before


async def test_invalid_input_is_a_400_never_a_422(client, logged_in_headers):
    for query in ("?project_id=nope", "?limit=abc", "?since=yesterday", "?extra=1", "?operation="):
        response = await client.get(f"api/v1/projects/audits{query}", headers=logged_in_headers)
        assert response.status_code == status.HTTP_400_BAD_REQUEST, (query, response.text)


async def test_the_route_is_not_captured_by_the_project_detail_route(client, logged_in_headers):
    response = await client.get("api/v1/projects/audits", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK


async def test_an_anonymous_caller_is_refused(client):
    response = await client.get("api/v1/projects/audits")

    assert response.status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}


async def _role(name: str, permissions: list[str]) -> UUID:
    async with session_scope() as session:
        role = AuthzRole(name=f"{name}-{uuid4().hex[:8]}", description=name, is_system=False, permissions=permissions)
        session.add(role)
        await session.flush()
        return role.id


async def test_with_a_plugin_the_dedicated_permission_decides(client, logged_in_headers):
    from tests.unit.services.authorization._policy_double import assign_role, install_policy_authz

    target = await _project(client, logged_in_headers)
    auditor_id, auditor_name = await make_user("auditor")
    scoped_id, scoped_name = await make_user("scoped")
    viewer_id, viewer_name = await make_user("viewer")
    global_role = await _role("auditor", ["project:audit_read"])
    scoped_role = await _role("scoped", ["project:audit_read"])
    reader_role = await _role("reader", ["project:read"])
    async with session_scope() as session:
        await assign_role(session, user_id=auditor_id, role_id=global_role)
        await assign_role(
            session, user_id=scoped_id, role_id=scoped_role, domain_type="project", domain_id=UUID(target["id"])
        )
        await assign_role(session, user_id=viewer_id, role_id=reader_role)
    auditor = await login(client, auditor_name)
    scoped = await login(client, scoped_name)
    viewer = await login(client, viewer_name)

    with install_policy_authz(get_settings_service()):
        auditor_feed = await client.get(f"api/v1/projects/audits?project_id={target['id']}", headers=auditor)
        scoped_one = await client.get(f"api/v1/projects/audits?project_id={target['id']}", headers=scoped)
        scoped_all = await client.get("api/v1/projects/audits", headers=scoped)
        viewer_feed = await client.get("api/v1/projects/audits", headers=viewer)

    assert auditor_feed.status_code == status.HTTP_200_OK
    assert [item["operation"] for item in auditor_feed.json()["items"]] == ["create"]
    assert scoped_one.status_code == status.HTTP_200_OK
    assert len(scoped_one.json()["items"]) == 1
    assert scoped_all.status_code == status.HTTP_403_FORBIDDEN
    assert viewer_feed.status_code == status.HTTP_403_FORBIDDEN
