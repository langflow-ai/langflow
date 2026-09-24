"""``GET /api/v1/flows/audits`` against the real API, database and authorization guards."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import status
from langflow.services.database.models.auth import AuthzRole
from langflow.services.deps import get_settings_service, session_scope

from .audit_helpers import enabled_audit, events_by_user, login, make_user

pytestmark = pytest.mark.usefixtures("audit_on")

GRAPH = {"nodes": [], "edges": []}
ITEM_KEYS = {
    "id",
    "timestamp",
    "flow_id",
    "flow_name",
    "action",
    "operation",
    "event_type",
    "result",
    "error_code",
    "request_id",
    "actor",
    "details",
}


@pytest.fixture
def audit_on(client):  # noqa: ARG001
    yield from enabled_audit()


async def _flow(client, headers, **fields) -> dict:
    response = await client.post(
        "api/v1/flows/", json={"name": f"f-{uuid4().hex}", "data": GRAPH, **fields}, headers=headers
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


async def _audits(client, headers, query: str = "") -> dict:
    response = await client.get(f"api/v1/flows/audits{query}", headers=headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


async def test_a_flow_history_has_the_contract_shape_newest_first(client, logged_in_headers):
    project = (
        await client.post("api/v1/projects/", json={"name": f"p-{uuid4().hex}"}, headers=logged_in_headers)
    ).json()
    flow = await _flow(client, logged_in_headers)
    await client.patch(f"api/v1/flows/{flow['id']}", json={"folder_id": project["id"]}, headers=logged_in_headers)
    await client.delete(f"api/v1/flows/{flow['id']}", headers=logged_in_headers)

    page = await _audits(client, logged_in_headers, f"?flow_id={flow['id']}")

    assert page["next_cursor"] is None
    assert [item["operation"] for item in page["items"]] == ["delete", "patch", "create"]
    for item in page["items"]:
        assert set(item) == ITEM_KEYS
        assert item["flow_id"] == flow["id"]
        assert item["timestamp"].endswith("Z")
    assert page["items"][1]["details"]["project"] == {"before_id": flow["folder_id"], "after_id": project["id"]}
    assert page["items"][0]["flow_name"] == flow["name"]


async def test_a_failure_is_readable_with_its_safe_code(client, logged_in_headers):
    first = await _flow(client, logged_in_headers, endpoint_name=f"ep-{uuid4().hex[:8]}")
    second = await _flow(client, logged_in_headers)
    await client.patch(
        f"api/v1/flows/{second['id']}", json={"endpoint_name": first["endpoint_name"]}, headers=logged_in_headers
    )

    page = await _audits(client, logged_in_headers, f"?flow_id={second['id']}&result=failed")

    [failed] = page["items"]
    assert (failed["event_type"], failed["error_code"], failed["details"]) == (
        "action",
        "FLOW_NAME_CONFLICT",
        {"schema_version": 1, "attempted_fields": ["endpoint_name"]},
    )


async def test_a_cursor_walk_is_exact_and_bound_to_its_filters(client, logged_in_headers):
    created = {(await _flow(client, logged_in_headers))["id"] for _ in range(17)}

    seen, cursor = [], None
    while True:
        suffix = f"&cursor={cursor}" if cursor else ""
        page = await _audits(client, logged_in_headers, f"?operation=create&limit=5{suffix}")
        seen.extend(page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
        refused = await client.get(f"api/v1/flows/audits?limit=5&cursor={cursor}", headers=logged_in_headers)
        assert refused.status_code == status.HTTP_400_BAD_REQUEST

    ids = [item["id"] for item in seen]
    assert len(ids) == len(set(ids))
    assert created <= {item["flow_id"] for item in seen}


async def test_without_a_plugin_a_user_sees_only_their_flows_and_their_own_actions(client, logged_in_headers):
    mine = await _flow(client, logged_in_headers)
    _stranger_id, stranger_name = await make_user("stranger")
    theirs = await _flow(client, await login(client, stranger_name))

    feed = await _audits(client, logged_in_headers, "?limit=200")
    probing = await _audits(client, logged_in_headers, f"?flow_id={theirs['id']}")

    visible = {item["flow_id"] for item in feed["items"]}
    assert mine["id"] in visible
    assert theirs["id"] not in visible
    assert probing["items"] == []


async def test_recreating_a_deleted_flow_id_does_not_hand_over_its_history(client, logged_in_headers):
    """Owning a UUID today is not owning what happened to it before (#15089 F1)."""
    victim = await _flow(client, logged_in_headers)
    victim_id = victim["id"]
    await client.patch(f"api/v1/flows/{victim_id}", json={"name": "renamed"}, headers=logged_in_headers)
    await client.delete(f"api/v1/flows/{victim_id}", headers=logged_in_headers)

    _attacker_id, attacker_name = await make_user("flow-attacker")
    attacker_headers = await login(client, attacker_name)
    recreated = await client.put(
        f"api/v1/flows/{victim_id}",
        json={"name": f"taken-{uuid4().hex[:8]}", "data": GRAPH},
        headers=attacker_headers,
    )
    assert recreated.status_code in {status.HTTP_200_OK, status.HTTP_201_CREATED}, recreated.text

    feed = await _audits(client, attacker_headers, f"?flow_id={victim_id}")

    assert [item["operation"] for item in feed["items"]] == ["create"]
    assert all(item["flow_name"] != victim["name"] for item in feed["items"])


async def test_a_flow_id_that_changed_hands_twice_shows_only_its_current_life(client, logged_in_headers):
    """A → B → A: the same rule the Project feed follows (#15088)."""
    shared_id = str(uuid4())
    body = {"name": f"a1-{uuid4().hex[:8]}", "data": GRAPH}
    first = await client.put(f"api/v1/flows/{shared_id}", json=body, headers=logged_in_headers)
    assert first.status_code in {status.HTTP_200_OK, status.HTTP_201_CREATED}, first.text
    dropped = await client.delete(f"api/v1/flows/{shared_id}", headers=logged_in_headers)
    assert dropped.status_code in {status.HTTP_200_OK, status.HTTP_204_NO_CONTENT}, dropped.text

    other_id, other_name = await make_user("flow-intervening")
    other_headers = await login(client, other_name)
    took = await client.put(
        f"api/v1/flows/{shared_id}", json={"name": f"b-{uuid4().hex[:8]}", "data": GRAPH}, headers=other_headers
    )
    assert took.status_code in {status.HTTP_200_OK, status.HTTP_201_CREATED}, took.text
    between = f"b-renamed-{uuid4().hex[:8]}"
    edited = await client.patch(f"api/v1/flows/{shared_id}", json={"name": between}, headers=other_headers)
    assert edited.status_code == status.HTTP_200_OK, edited.text
    released = await client.delete(f"api/v1/flows/{shared_id}", headers=other_headers)
    assert released.status_code in {status.HTTP_200_OK, status.HTTP_204_NO_CONTENT}, released.text

    retaken = await client.put(
        f"api/v1/flows/{shared_id}", json={"name": f"a2-{uuid4().hex[:8]}", "data": GRAPH}, headers=logged_in_headers
    )
    assert retaken.status_code in {status.HTTP_200_OK, status.HTTP_201_CREATED}, retaken.text

    feed = await _audits(client, logged_in_headers, f"?flow_id={shared_id}&limit=200")

    assert between not in {item["flow_name"] for item in feed["items"]}
    assert all(item["actor"]["user_id"] != str(other_id) for item in feed["items"])


async def test_an_unrecorded_create_does_not_reopen_the_previous_life(client, logged_in_headers):
    """Excluding `flow:create` must not let the window fall back to the old owner's create."""
    settings = get_settings_service().settings
    original = settings.audit_exclude_events
    shared_id = str(uuid4())
    hers = f"alice-{uuid4().hex[:8]}"
    created = await client.put(
        f"api/v1/flows/{shared_id}", json={"name": hers, "data": GRAPH}, headers=logged_in_headers
    )
    assert created.status_code in {status.HTTP_200_OK, status.HTTP_201_CREATED}, created.text
    edited = await client.patch(
        f"api/v1/flows/{shared_id}", json={"name": f"{hers}-v2"}, headers=logged_in_headers
    )
    assert edited.status_code == status.HTTP_200_OK, edited.text
    dropped = await client.delete(f"api/v1/flows/{shared_id}", headers=logged_in_headers)
    assert dropped.status_code in {status.HTTP_200_OK, status.HTTP_204_NO_CONTENT}, dropped.text

    other_id, other_name = await make_user("no-create-recorded")
    other_headers = await login(client, other_name)
    try:
        # A supported setting: the new owner's create is never written.
        settings.audit_exclude_events = "flow:create"
        retaken = await client.put(
            f"api/v1/flows/{shared_id}",
            json={"name": f"bob-{uuid4().hex[:8]}", "data": GRAPH},
            headers=other_headers,
        )
        assert retaken.status_code in {status.HTTP_200_OK, status.HTTP_201_CREATED}, retaken.text

        feed = await _audits(client, other_headers, f"?flow_id={shared_id}&limit=200")
    finally:
        settings.audit_exclude_events = original

    assert feed["items"] == [], "the previous owner's rows must stay theirs"
    assert str(other_id) not in {item["actor"]["user_id"] for item in feed["items"]}


async def test_a_superuser_reads_every_flow(client, logged_in_headers, logged_in_headers_super_user):
    theirs = await _flow(client, logged_in_headers)

    feed = await _audits(client, logged_in_headers_super_user, f"?flow_id={theirs['id']}")

    assert [item["operation"] for item in feed["items"]] == ["create"]


async def test_an_anonymous_caller_is_refused(client):
    response = await client.get("api/v1/flows/audits")

    assert response.status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}


async def test_invalid_input_is_a_400_never_a_422(client, logged_in_headers):
    for query in ("?flow_id=nope", "?limit=abc", "?since=yesterday", "?extra=1", "?operation="):
        response = await client.get(f"api/v1/flows/audits{query}", headers=logged_in_headers)
        assert response.status_code == status.HTTP_400_BAD_REQUEST, (query, response.text)


async def test_project_events_never_appear_in_the_flow_feed(client, logged_in_headers):
    project = (
        await client.post("api/v1/projects/", json={"name": f"p-{uuid4().hex}"}, headers=logged_in_headers)
    ).json()

    feed = await _audits(client, logged_in_headers, "?limit=200")

    assert project["id"] not in {item["flow_id"] for item in feed["items"]}


async def test_a_project_filter_is_not_a_flow_filter(client, logged_in_headers):
    response = await client.get(f"api/v1/flows/audits?project_id={uuid4()}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Unknown query parameter: project_id" in response.json()["detail"]


async def test_reading_records_nothing_and_the_route_is_not_captured(client, logged_in_headers, active_user):
    await _flow(client, logged_in_headers)
    before = len(await events_by_user(active_user.id))

    response = await client.get("api/v1/flows/audits", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK
    assert len(await events_by_user(active_user.id)) == before


async def _role(name: str, permissions: list[str]) -> UUID:
    async with session_scope() as session:
        role = AuthzRole(name=f"{name}-{uuid4().hex[:8]}", description=name, is_system=False, permissions=permissions)
        session.add(role)
        await session.flush()
        return role.id


async def test_with_a_plugin_the_flow_audit_permission_decides(client, logged_in_headers):
    from tests.unit.services.authorization._policy_double import assign_role, install_policy_authz

    target = await _flow(client, logged_in_headers)
    auditor_id, auditor_name = await make_user("auditor")
    reader_id, reader_name = await make_user("reader")
    project_auditor_id, project_auditor_name = await make_user("projectauditor")
    flow_role = await _role("flow-auditor", ["flow:audit_read"])
    read_role = await _role("flow-reader", ["flow:read"])
    project_role = await _role("project-auditor", ["project:audit_read"])
    async with session_scope() as session:
        await assign_role(session, user_id=auditor_id, role_id=flow_role)
        await assign_role(session, user_id=reader_id, role_id=read_role)
        await assign_role(session, user_id=project_auditor_id, role_id=project_role)
    auditor = await login(client, auditor_name)
    reader = await login(client, reader_name)
    project_auditor = await login(client, project_auditor_name)

    with install_policy_authz(get_settings_service()):
        owner_one = await client.get(f"api/v1/flows/audits?flow_id={target['id']}", headers=logged_in_headers)
        owner_all = await client.get("api/v1/flows/audits", headers=logged_in_headers)
        allowed = await client.get(f"api/v1/flows/audits?flow_id={target['id']}", headers=auditor)
        read_only = await client.get("api/v1/flows/audits", headers=reader)
        wrong_resource = await client.get("api/v1/flows/audits", headers=project_auditor)

    assert owner_one.status_code == status.HTTP_403_FORBIDDEN
    assert owner_all.status_code == status.HTTP_403_FORBIDDEN
    assert allowed.status_code == status.HTTP_200_OK
    assert [item["operation"] for item in allowed.json()["items"]] == ["create"]
    assert read_only.status_code == status.HTTP_403_FORBIDDEN
    assert wrong_resource.status_code == status.HTTP_403_FORBIDDEN


async def test_excluding_an_action_stops_new_events_but_keeps_the_stored_history_readable(client, logged_in_headers):
    settings = get_settings_service().settings
    flow = await _flow(client, logged_in_headers)
    await client.patch(f"api/v1/flows/{flow['id']}", json={"name": f"before-{uuid4().hex}"}, headers=logged_in_headers)

    settings.audit_exclude_events = "flow:write"
    await client.patch(f"api/v1/flows/{flow['id']}", json={"name": f"after-{uuid4().hex}"}, headers=logged_in_headers)
    page = await _audits(client, logged_in_headers, f"?flow_id={flow['id']}")

    assert [(item["action"], item["result"]) for item in page["items"]] == [
        ("flow:write", "succeeded"),
        ("flow:create", "succeeded"),
    ]
