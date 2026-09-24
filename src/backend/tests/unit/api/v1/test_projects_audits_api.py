"""``GET /api/v1/projects/audits`` against the real API, database and authorization guards."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import status
from langflow.services.database.models.audit_event.model import AuditEvent
from langflow.services.database.models.auth import AuthzRole
from langflow.services.deps import get_settings_service, session_scope
from sqlmodel import select

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


async def test_an_owner_sees_another_actors_change_to_their_project(
    client, logged_in_headers, logged_in_headers_super_user
):
    """The positive side of the floor: the window lets the owner see what others did."""
    mine = await _project(client, logged_in_headers)
    renamed = f"by-the-superuser-{uuid4().hex[:8]}"
    patched = await client.patch(
        f"api/v1/projects/{mine['id']}", json={"name": renamed}, headers=logged_in_headers_super_user
    )
    assert patched.status_code == status.HTTP_200_OK, patched.text

    feed = await _audits(client, logged_in_headers, f"?project_id={mine['id']}&limit=200")

    operations = [item["operation"] for item in feed["items"]]
    assert operations.count("patch") == 1, operations
    assert renamed in {item["project_name"] for item in feed["items"]}


async def test_an_owner_keeps_the_history_after_retention_sweeps_the_create(
    client, logged_in_headers, logged_in_headers_super_user
):
    """Retention deletes by age, so a long-lived project loses its create first."""
    mine = await _project(client, logged_in_headers)
    renamed = f"still-visible-{uuid4().hex[:8]}"
    await client.patch(f"api/v1/projects/{mine['id']}", json={"name": renamed}, headers=logged_in_headers_super_user)

    async with session_scope() as session:
        create_row = (
            await session.exec(
                select(AuditEvent).where(AuditEvent.resource_id == UUID(mine["id"]), AuditEvent.operation == "create")
            )
        ).one()
        await session.delete(create_row)

    feed = await _audits(client, logged_in_headers, f"?project_id={mine['id']}&limit=200")

    # Nothing was ever deleted at this id, so no other life can have used it.
    assert renamed in {item["project_name"] for item in feed["items"]}


async def test_a_deleted_project_stays_readable_by_whoever_acted_on_it(client, logged_in_headers):
    project = await _project(client, logged_in_headers)
    await client.delete(f"api/v1/projects/{project['id']}", headers=logged_in_headers)

    feed = await _audits(client, logged_in_headers, f"?project_id={project['id']}&operation=delete")

    assert [(item["operation"], item["project_name"]) for item in feed["items"]] == [("delete", project["name"])]


async def test_recreating_a_deleted_id_does_not_hand_over_its_history(client, logged_in_headers):
    """Owning a UUID today is not owning what happened to it before (#15088 F7)."""
    victim = await _project(client, logged_in_headers)
    victim_id = victim["id"]
    await client.delete(f"api/v1/projects/{victim_id}", headers=logged_in_headers)

    _attacker_id, attacker_name = await make_user("attacker")
    attacker_headers = await login(client, attacker_name)
    recreated = await client.put(
        f"api/v1/projects/{victim_id}",
        json={"name": f"taken-{uuid4().hex[:8]}"},
        headers=attacker_headers,
    )
    assert recreated.status_code in {status.HTTP_200_OK, status.HTTP_201_CREATED}, recreated.text

    feed = await _audits(client, attacker_headers, f"?project_id={victim_id}")

    # Only what the new owner did with that id; nothing from the previous one.
    assert [item["operation"] for item in feed["items"]] == ["create"]
    assert all(item["project_name"] != victim["name"] for item in feed["items"])


async def test_an_id_that_changed_hands_twice_shows_only_its_current_life(client, logged_in_headers):
    """A → B → A: coming back must not open what B did in between."""
    shared_id = str(uuid4())
    await client.put(f"api/v1/projects/{shared_id}", json={"name": f"a1-{uuid4().hex[:8]}"}, headers=logged_in_headers)
    await client.delete(f"api/v1/projects/{shared_id}", headers=logged_in_headers)

    _other_id, other_name = await make_user("intervening")
    other_headers = await login(client, other_name)
    took = await client.put(
        f"api/v1/projects/{shared_id}", json={"name": f"b-{uuid4().hex[:8]}"}, headers=other_headers
    )
    assert took.status_code in {status.HTTP_200_OK, status.HTTP_201_CREATED}, took.text
    between = f"b-renamed-{uuid4().hex[:8]}"
    edited = await client.patch(f"api/v1/projects/{shared_id}", json={"name": between}, headers=other_headers)
    assert edited.status_code == status.HTTP_200_OK, edited.text
    released = await client.delete(f"api/v1/projects/{shared_id}", headers=other_headers)
    assert released.status_code in {status.HTTP_200_OK, status.HTTP_204_NO_CONTENT}, released.text

    back = f"a2-{uuid4().hex[:8]}"
    retaken = await client.put(f"api/v1/projects/{shared_id}", json={"name": back}, headers=logged_in_headers)
    assert retaken.status_code in {status.HTTP_200_OK, status.HTTP_201_CREATED}, retaken.text

    feed = await _audits(client, logged_in_headers, f"?project_id={shared_id}&limit=200")

    names = {item["project_name"] for item in feed["items"]}
    assert between not in names, "the intervening owner's events must stay theirs"
    assert all(item["actor"]["user_id"] != str(_other_id) for item in feed["items"])


async def test_an_earlier_flow_event_does_not_open_project_history_at_the_same_id(client, logged_in_headers):
    """The window is per resource type: a Flow create at this id is not a Project's."""
    shared_id = str(uuid4())
    # 1. The caller acts on a *Flow* at this id, before anything else happens there.
    mine = await client.put(
        f"api/v1/flows/{shared_id}",
        json={"name": f"flow-{uuid4().hex[:8]}", "data": {"nodes": [], "edges": []}},
        headers=logged_in_headers,
    )
    assert mine.status_code in {status.HTTP_200_OK, status.HTTP_201_CREATED}, mine.text

    # 2. Someone else owns, edits and drops a *Project* at the same id.
    _other_id, other_name = await make_user("cross-type")
    other_headers = await login(client, other_name)
    await client.put(f"api/v1/projects/{shared_id}", json={"name": f"p-{uuid4().hex[:8]}"}, headers=other_headers)
    theirs = f"theirs-{uuid4().hex[:8]}"
    await client.patch(f"api/v1/projects/{shared_id}", json={"name": theirs}, headers=other_headers)
    await client.delete(f"api/v1/projects/{shared_id}", headers=other_headers)

    # 3. The caller takes the Project id. Their Flow event predates the other owner's.
    retaken = await client.put(
        f"api/v1/projects/{shared_id}", json={"name": f"mine-{uuid4().hex[:8]}"}, headers=logged_in_headers
    )
    assert retaken.status_code in {status.HTTP_200_OK, status.HTTP_201_CREATED}, retaken.text

    feed = await _audits(client, logged_in_headers, f"?project_id={shared_id}&limit=200")

    assert theirs not in {item["project_name"] for item in feed["items"]}
    assert all(item["actor"]["user_id"] != str(_other_id) for item in feed["items"])


async def test_query_string_api_key_auth_is_not_read_as_a_filter(client, logged_in_headers):
    """``x-api-key`` in the query string authenticates the request (#15088 F2)."""
    await _project(client, logged_in_headers)

    response = await client.get("api/v1/projects/audits?x-api-key=not-a-real-key", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK, response.text


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
    for query in (
        "?project_id=nope",
        "?limit=abc",
        "?since=yesterday",
        "?extra=1",
        "?operation=",
        # Edge inputs that used to reach Python as an exception rather than a 400.
        f"?limit={'0' * 5000}",
        "?since=0001-01-01T00:00:00%2B01:00",
    ):
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
        owner_one = await client.get(f"api/v1/projects/audits?project_id={target['id']}", headers=logged_in_headers)
        owner_all = await client.get("api/v1/projects/audits", headers=logged_in_headers)
        auditor_feed = await client.get(f"api/v1/projects/audits?project_id={target['id']}", headers=auditor)
        scoped_one = await client.get(f"api/v1/projects/audits?project_id={target['id']}", headers=scoped)
        scoped_all = await client.get("api/v1/projects/audits", headers=scoped)
        viewer_feed = await client.get("api/v1/projects/audits", headers=viewer)

    assert owner_one.status_code == status.HTTP_403_FORBIDDEN
    assert owner_all.status_code == status.HTTP_403_FORBIDDEN
    assert auditor_feed.status_code == status.HTTP_200_OK
    assert [item["operation"] for item in auditor_feed.json()["items"]] == ["create"]
    assert scoped_one.status_code == status.HTTP_200_OK
    assert len(scoped_one.json()["items"]) == 1
    assert scoped_all.status_code == status.HTTP_403_FORBIDDEN
    assert viewer_feed.status_code == status.HTTP_403_FORBIDDEN
