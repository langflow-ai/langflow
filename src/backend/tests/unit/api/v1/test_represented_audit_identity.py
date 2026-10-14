"""Represented identity crosses the real authentication, mutation and audit boundary."""

from __future__ import annotations

import asyncio
import base64
from uuid import uuid4

import pytest
from langflow.services.audit.represented import ISSUER_HEADER, SUBJECT_HEADER
from langflow.services.database.models.api_key.crud import create_api_key
from langflow.services.database.models.api_key.model import ApiKeyCreate
from langflow.services.database.models.folder.model import Folder
from langflow.services.deps import get_settings_service, session_scope
from sqlmodel import select

from .audit_helpers import enabled_audit, events_for, login, make_user, record_event

pytestmark = pytest.mark.usefixtures("audit_on")


@pytest.fixture
def audit_on(client):  # noqa: ARG001
    yield from enabled_audit()


async def _key(user):
    async with session_scope() as session:
        return await create_api_key(session, ApiKeyCreate(name=f"audit-{uuid4().hex}"), user.id)


def _headers(key, subject="用户-Ålice"):
    def encode(value):
        return "v1." + base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")

    return {"x-api-key": key.api_key, ISSUER_HEADER: encode("https://idp.example"), SUBJECT_HEADER: encode(subject)}


@pytest.fixture
async def trusted_key(active_user, monkeypatch):
    key = await _key(active_user)
    monkeypatch.setattr(get_settings_service().settings, "audit_trusted_api_key_ids", [key.id])
    return key


async def test_service_account_and_represented_user_survive_project_and_flow_lifecycle(
    client, active_user, trusted_key
):
    headers = _headers(trusted_key)
    created = await client.post("api/v1/projects/", json={"name": f"project-{uuid4().hex}"}, headers=headers)
    assert created.status_code == 201, created.text
    project_id = created.json()["id"]
    flow = await client.post(
        "api/v1/flows/",
        json={"name": f"flow-{uuid4().hex}", "folder_id": project_id, "data": {"nodes": [], "edges": []}},
        headers=headers,
    )
    assert flow.status_code == 201, flow.text
    patched = await client.patch(f"api/v1/projects/{project_id}", json={"description": "after"}, headers=headers)
    assert patched.status_code == 200, patched.text
    deleted = await client.delete(f"api/v1/projects/{project_id}", headers=headers)
    assert deleted.status_code == 204, deleted.text
    project_events, flow_events = await events_for(project_id), await events_for(flow.json()["id"])
    assert [row.operation for row in project_events] == ["create", "patch", "delete"]
    assert [row.operation for row in flow_events] == ["create", "delete"]
    for row in project_events + flow_events:
        assert (row.user_id, row.actor_type, row.actor_id) == (active_user.id, "api_key", trusted_key.id)
        assert (row.represented_issuer, row.represented_subject) == ("https://idp.example", "用户-Ålice")
        assert (row.acting_issuer, row.acting_subject) == (None, None)
    feed = await client.get(
        f"api/v1/projects/audits?project_id={project_id}", headers={"x-api-key": trusted_key.api_key}
    )
    assert feed.status_code == 200, feed.text
    assert all(item["actor"]["represented_subject"] == "用户-Ålice" for item in feed.json()["items"])
    assert all(item["actor"]["acting_subject"] is None for item in feed.json()["items"])


async def test_another_key_on_the_same_account_and_a_user_token_cannot_assert_identity(
    client, active_user, trusted_key, logged_in_headers
):
    other = await _key(active_user)
    represented = {key: value for key, value in _headers(trusted_key).items() if key != "x-api-key"}
    for credential in ({"x-api-key": other.api_key}, logged_in_headers):
        name = f"forged-{uuid4().hex}"
        response = await client.post("api/v1/projects/", json={"name": name}, headers={**credential, **represented})
        assert response.status_code == 403, response.text
        assert response.headers["X-Langflow-Error-Code"] == "REPRESENTED_IDENTITY_NOT_ALLOWED"
        async with session_scope() as session:
            assert (await session.exec(select(Folder).where(Folder.name == name))).first() is None


@pytest.mark.parametrize("malformed", ["partial", "duplicate", "oversized"])
async def test_invalid_identity_is_rejected_before_mutation(client, trusted_key, malformed):
    headers = list(_headers(trusted_key).items())
    if malformed == "partial":
        headers = [(key, value) for key, value in headers if key != SUBJECT_HEADER]
    elif malformed == "duplicate":
        headers.append((SUBJECT_HEADER, _headers(trusted_key)[SUBJECT_HEADER]))
    else:
        headers = list(_headers(trusted_key, "s" * 513).items())
    name = f"invalid-{uuid4().hex}"
    response = await client.post("api/v1/projects/", json={"name": name}, headers=headers)
    assert response.status_code == 400, response.text
    assert response.headers["X-Langflow-Error-Code"] == "INVALID_AUDIT_CONTEXT"
    async with session_scope() as session:
        assert (await session.exec(select(Folder).where(Folder.name == name))).first() is None


async def test_failure_retains_identity_after_rollback(client, trusted_key):
    headers = _headers(trusted_key)
    projects = []
    for _ in range(2):
        created = await client.post("api/v1/projects/", json={"name": f"project-{uuid4().hex}"}, headers=headers)
        assert created.status_code == 201, created.text
        projects.append(created.json())
    response = await client.patch(
        f"api/v1/projects/{projects[1]['id']}", json={"name": projects[0]["name"]}, headers=headers
    )
    assert response.status_code == 409, response.text
    _created, failed = await events_for(projects[1]["id"])
    assert failed.result == "failed"
    assert failed.actor_id == trusted_key.id
    assert failed.represented_subject == "用户-Ålice"


async def test_replacement_create_replace_and_receipt_replay_preserve_identity(client, trusted_key):
    headers = _headers(trusted_key)
    project_id, operation_id = uuid4(), uuid4()
    url = f"api/v1/projects/{project_id}/replacement-operations/{operation_id}"
    body = {
        "project_name": f"deployment-{uuid4().hex[:12]}",
        "description": "first",
        "flows": [{"id": str(uuid4()), "name": "first", "data": {"nodes": [], "edges": []}}],
    }
    created = await client.put(url, json=body, headers=headers)
    assert created.status_code == 200, created.text
    replay = await client.put(url, json=body, headers=_headers(trusted_key, "bob"))
    assert replay.status_code == 200, replay.text
    assert replay.json() == created.json()
    [event] = await events_for(project_id)
    assert event.operation == "create"
    assert event.represented_subject == "用户-Ålice"
    [flow_event] = await events_for(body["flows"][0]["id"])
    assert flow_event.represented_subject == "用户-Ålice"
    replaced = await client.put(
        f"api/v1/projects/{project_id}/replacement-operations/{uuid4()}",
        json={"description": "second", "flows": []},
        headers=_headers(trusted_key, "bob"),
    )
    assert replaced.status_code == 200, replaced.text
    _created, replacement = await events_for(project_id)
    assert (replacement.operation, replacement.represented_subject) == ("replace", "bob")
    _flow_create, flow_delete = await events_for(body["flows"][0]["id"])
    assert (flow_delete.operation, flow_delete.represented_subject) == ("delete", "bob")


async def test_concurrent_requests_and_direct_calls_do_not_share_identity(client, trusted_key):
    async def create(subject):
        headers = _headers(trusted_key, subject) if subject else {"x-api-key": trusted_key.api_key}
        response = await client.post("api/v1/projects/", json={"name": f"project-{uuid4().hex}"}, headers=headers)
        assert response.status_code == 201, response.text
        [event] = await events_for(response.json()["id"])
        return event.represented_subject

    assert await asyncio.gather(create("alice"), create("bob"), create(None)) == ["alice", "bob", None]
    assert await create(None) is None


async def test_acting_history_is_not_projected_as_represented_identity(client, trusted_key):
    row = await record_event(
        resource_type="project",
        resource_id=uuid4(),
        resource_name="old-project",
        user_id=trusted_key.user_id,
        actor_type="api_key",
        actor_id=trusted_key.id,
        action="project:write",
        operation="patch",
        acting_issuer="https://idp.example",
        acting_subject="authenticated-user",
    )
    for prefix in ("acting", "represented"):
        response = await client.get(
            f"api/v1/projects/audits?{prefix}_issuer=https%3A%2F%2Fidp.example&{prefix}_subject=authenticated-user",
            headers={"x-api-key": trusted_key.api_key},
        )
        assert response.status_code == 200, response.text
        if prefix == "represented":
            assert response.json()["items"] == []
            continue
        [item] = response.json()["items"]
        assert item["id"] == str(row.id)
        assert item["actor"]["acting_subject"] == "authenticated-user"
        assert item["actor"]["represented_subject"] is None


async def test_both_identity_pairs_remain_distinct_in_filters_and_responses(client, trusted_key):
    row = await record_event(
        resource_type="project",
        resource_id=uuid4(),
        user_id=trusted_key.user_id,
        actor_type="api_key",
        actor_id=trusted_key.id,
        action="project:write",
        operation="patch",
        acting_issuer="actor-issuer",
        acting_subject="actor",
        represented_issuer="end-user-issuer",
        represented_subject="end-user",
    )
    response = await client.get(
        "api/v1/projects/audits?acting_subject=actor&represented_subject=end-user",
        headers={"x-api-key": trusted_key.api_key},
    )
    assert response.status_code == 200, response.text
    [item] = response.json()["items"]
    assert item["id"] == str(row.id)
    assert item["actor"]["acting_issuer"] == "actor-issuer"
    assert item["actor"]["represented_issuer"] == "end-user-issuer"
    _admin_id, admin_name = await make_user("identityadmin", superuser=True)
    admin_headers = await login(client, admin_name)
    combined = await client.get(f"api/v1/audits?resource_id={row.resource_id}", headers=admin_headers)
    assert combined.status_code == 200, combined.text
    [resource_item] = [item for item in combined.json()["items"] if item["id"] == str(row.id)]
    assert resource_item["actor"]["acting_subject"] == "actor"
    assert resource_item["actor"]["represented_subject"] == "end-user"
