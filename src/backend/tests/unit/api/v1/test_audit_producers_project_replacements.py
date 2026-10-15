"""Replacement outcomes commit with their receipts and remain unique across retries."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from langflow.api.v1 import projects as projects_module
from langflow.services.audit.details import DESCRIPTION_LIMIT
from langflow.services.authorization.refusal import mark_authorization_refusal
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.project_replacement_operation import ProjectReplacementOperation
from langflow.services.deps import get_db_service, get_settings_service, session_scope
from sqlalchemy import event as sqlalchemy_event
from sqlalchemy.exc import OperationalError
from sqlmodel import select

from .audit_helpers import enabled_audit, events_for

pytestmark = pytest.mark.usefixtures("audit_on")
GRAPH = {"nodes": [], "edges": [], "private_marker": "must not reach audit details"}


@pytest.fixture
def audit_on(client):  # noqa: ARG001
    yield from enabled_audit()


async def _seed_project(user, project_id, *, flows=()):
    """Seed the prior state without generating unrelated API audit events."""
    name = f"deployment-{uuid4().hex[:12]}"
    async with session_scope() as session:
        session.add(Folder(id=project_id, name=name, description="before", user_id=user.id))
        await session.flush()
        for flow in flows:
            session.add(Flow(**flow, folder_id=project_id, user_id=user.id))
    return name


def _flow(name):
    return {"id": str(uuid4()), "name": name, "data": GRAPH}


def _url(project_id, operation_id=None):
    return f"api/v1/projects/{project_id}/replacement-operations/{operation_id or uuid4()}"


@pytest.mark.parametrize("create", [True, False])
@pytest.mark.parametrize("deleted", [True, False])
async def test_expired_receipt_retry_retains_name_in_audit_export(
    client, active_super_user, logged_in_headers_super_user, create, deleted
):
    project_id, operation_id = uuid4(), uuid4()
    name = f"deployment-{uuid4().hex[:12]}" if create else await _seed_project(active_super_user, project_id)
    body = {"description": "committed", "flows": [_flow("committed-flow")]}
    if create:
        body["project_name"] = name
    url = _url(project_id, operation_id)
    response = await client.put(url, json=body, headers=logged_in_headers_super_user)
    assert response.status_code == 200, response.text
    async with session_scope() as session:
        receipt = await session.get(ProjectReplacementOperation, (project_id, operation_id))
        receipt.result = None
        session.add(receipt)
    if deleted:
        removed = await client.delete(f"api/v1/projects/{project_id}", headers=logged_in_headers_super_user)
        assert removed.status_code == 204, removed.text

    retry = await client.put(url, json=body, headers=logged_in_headers_super_user)
    assert retry.status_code == 410, retry.text
    assert retry.headers["X-Langflow-Error-Code"] == "replacement_receipt_expired"
    events = await events_for(project_id)
    success, failure = events[0], events[-1]
    assert success.result == "succeeded"
    assert (failure.resource_name, failure.result, failure.error_code) == (name, "failed", "CONSTRAINT_VIOLATION")
    exported = await client.get(
        "api/v1/audits/export",
        params={"q": name, "source": "resource", "format": "ndjson"},
        headers=logged_in_headers_super_user,
    )
    assert exported.status_code == 200, exported.text
    assert str(failure.id) in {json.loads(line)["id"] for line in exported.text.splitlines()}
    async with session_scope() as session:
        project = await session.get(Folder, project_id)
        if deleted:
            assert project is None
        else:
            assert project.description == "committed"
        assert (await session.get(ProjectReplacementOperation, (project_id, operation_id))).result is None


@pytest.mark.parametrize("create", [True, False])
async def test_replacement_records_one_project_event_and_replays_without_more_events(
    client, active_user, logged_in_headers, create
):
    project_id = uuid4()
    name = f"deployment-{uuid4().hex[:12]}" if create else await _seed_project(active_user, project_id)
    flow = _flow("first")
    body = {"description": "d" * (DESCRIPTION_LIMIT + 1), "flows": [flow]}
    if create:
        body["project_name"] = name
    url = _url(project_id)

    response = await client.put(url, json=body, headers=logged_in_headers)
    assert response.status_code == 200, response.text
    [event] = await events_for(project_id, resource_type="project")
    assert (event.action, event.operation, event.event_type, event.result) == (
        "project:create" if create else "project:write",
        "create" if create else "replace",
        "action",
        "succeeded",
    )
    assert event.resource_name == name
    assert event.user_id == active_user.id
    assert event.request_id is not None
    assert event.details == {
        "schema_version": 1,
        "description": "d" * DESCRIPTION_LIMIT,
        "flows": {
            "before_count": 0,
            "after_count": 1,
            "updated_count": 0,
            "changes": [{"id": flow["id"], "name": "first", "change": "added"}],
            "truncated": False,
        },
    }
    [flow_event] = await events_for(flow["id"], resource_type="flow")
    assert (flow_event.action, flow_event.operation, flow_event.result) == ("flow:create", "create", "succeeded")
    assert flow_event.request_id == event.request_id
    assert "private_marker" not in str(flow_event.details)

    replay = await client.put(url, json=body, headers=logged_in_headers)
    receipt = await client.get(url, headers=logged_in_headers)
    assert replay.status_code == receipt.status_code == 200
    assert replay.json() == receipt.json() == response.json()
    assert [row.id for row in await events_for(project_id)] == [event.id]
    assert [row.id for row in await events_for(flow["id"])] == [flow_event.id]

    conflict = await client.put(url, json={**body, "description": "different"}, headers=logged_in_headers)
    assert conflict.status_code == 409
    success, failure = await events_for(project_id)
    assert success.id == event.id
    assert (failure.result, failure.error_code) == ("failed", "CONSTRAINT_VIOLATION")
    assert failure.operation == event.operation
    assert len(await events_for(flow["id"])) == 1


async def test_replacement_records_added_updated_and_removed_flows(client, active_user, logged_in_headers):
    project_id = uuid4()
    kept, removed, added = _flow("original"), _flow("removed"), _flow("added")
    await _seed_project(
        active_user, project_id, flows=[{**kept, "id": UUID(kept["id"])}, {**removed, "id": UUID(removed["id"])}]
    )

    response = await client.put(
        _url(project_id),
        json={"description": None, "flows": [{**kept, "name": "updated"}, added]},
        headers=logged_in_headers,
    )
    assert response.status_code == 200, response.text
    [event] = await events_for(project_id)
    assert event.details["description"] is None
    summary = event.details["flows"]
    assert (summary["before_count"], summary["after_count"], summary["updated_count"]) == (2, 2, 1)
    assert {(change["id"], change["name"], change["change"]) for change in summary["changes"]} == {
        (kept["id"], "updated", "updated"),
        (removed["id"], "removed", "removed"),
        (added["id"], "added", "added"),
    }
    for flow, action, operation in [
        (kept, "flow:write", "replace"),
        (removed, "flow:delete", "delete"),
        (added, "flow:create", "create"),
    ]:
        [flow_event] = await events_for(flow["id"])
        assert (flow_event.action, flow_event.operation, flow_event.result) == (action, operation, "succeeded")
        assert flow_event.request_id == event.request_id
        assert "__lf_replace_" not in str(flow_event.details)
    [deleted] = await events_for(removed["id"])
    assert deleted.resource_name == "removed"
    assert deleted.details["project"] == {"before_id": str(project_id), "after_id": None}


async def test_replacement_inserts_flow_and_project_audits_in_one_batch(client, active_user, logged_in_headers):
    project_id = uuid4()
    kept, removed, added = _flow("kept"), _flow("removed"), _flow("added")
    await _seed_project(
        active_user, project_id, flows=[{**kept, "id": UUID(kept["id"])}, {**removed, "id": UUID(removed["id"])}]
    )
    inserts = []

    def observe(_connection, _cursor, statement, _parameters, _context, _executemany):
        if statement.startswith("INSERT INTO audit_events"):
            inserts.append(statement)

    engine = get_db_service().engine.sync_engine
    sqlalchemy_event.listen(engine, "before_cursor_execute", observe)
    try:
        response = await client.put(
            _url(project_id),
            json={"description": "after", "flows": [{**kept, "name": "updated"}, added]},
            headers=logged_in_headers,
        )
    finally:
        sqlalchemy_event.remove(engine, "before_cursor_execute", observe)
    assert response.status_code == 200, response.text
    assert len(inserts) == 1
    for resource in (project_id, kept["id"], removed["id"], added["id"]):
        [audit] = await events_for(resource)
        assert audit.result == "succeeded"


class _DeadlockError(Exception):
    sqlstate = "40P01"


@pytest.mark.parametrize("create", [True, False])
@pytest.mark.parametrize("failure", ["recover", "exhaust", "error"])
@pytest.mark.parametrize("failure_point", ["stage_project_succeeded", "flush_audit_event_batch"])
async def test_replacement_rolls_back_staged_events_before_retry_or_failure(
    client, active_user, logged_in_headers, monkeypatch, create, failure, failure_point
):
    project_id = uuid4()
    kept, removed = _flow("before-flow"), _flow("removed")
    name = (
        f"deployment-{uuid4().hex[:12]}"
        if create
        else await _seed_project(
            active_user, project_id, flows=[{**kept, "id": UUID(kept["id"])}, {**removed, "id": UUID(removed["id"])}]
        )
    )
    flow = _flow("target")
    requested_flows = [flow] if create else [{**kept, "name": "after-flow"}, flow]
    body = {"description": "after", "flows": requested_flows}
    if create:
        body["project_name"] = name
    url = _url(project_id)
    original_stage = getattr(projects_module, failure_point)
    attempts = 0

    async def fail_after_staging(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        await original_stage(*args, **kwargs)
        if failure == "error":
            raise HTTPException(500, "private failure text")
        if failure == "exhaust" or attempts == 1:
            statement = "private SQL"
            raise OperationalError(statement, None, _DeadlockError("private database error"))

    monkeypatch.setattr(projects_module, failure_point, fail_after_staging)
    response = await client.put(url, json=body, headers=logged_in_headers)
    assert response.status_code == {"recover": 200, "exhaust": 503, "error": 500}[failure], response.text
    assert attempts == {"recover": 2, "exhaust": projects_module._REPLACEMENT_MAX_ATTEMPTS, "error": 1}[failure]
    [event] = await events_for(project_id)
    assert (event.action, event.operation) == (
        "project:create" if create else "project:write",
        "create" if create else "replace",
    )
    assert event.resource_name == name
    assert event.result == ("succeeded" if failure == "recover" else "failed")
    if failure != "recover":
        assert event.error_code == {"exhaust": "SERVICE_UNAVAILABLE", "error": "INTERNAL_ERROR"}[failure]
        assert event.details["requested_flow_count"] == len(requested_flows)
        assert "flows" in event.details["attempted_fields"]
        assert "private" not in str(event.details)
    flow_events = await events_for(flow["id"])
    assert len(flow_events) == (1 if failure == "recover" else 0)
    async with session_scope() as session:
        stored = await session.get(Folder, project_id)
        receipt = (
            await session.exec(
                select(ProjectReplacementOperation).where(ProjectReplacementOperation.project_id == project_id)
            )
        ).first()
        if failure == "recover":
            assert stored.description == "after"
            assert receipt is not None
        else:
            if create:
                assert stored is None
            else:
                assert stored.description == "before"
            assert receipt is None
            assert await session.get(Flow, UUID(flow["id"])) is None
        if not create:
            stored_kept = await session.get(Flow, UUID(kept["id"]))
            stored_removed = await session.get(Flow, UUID(removed["id"]))
            assert stored_kept.name == ("after-flow" if failure == "recover" else "before-flow")
            assert (stored_removed is None) == (failure == "recover")
    if not create:
        for prior in (kept, removed):
            assert len(await events_for(prior["id"])) == (1 if failure == "recover" else 0)


@pytest.mark.parametrize("guard", ["ensure_project_permission", "ensure_flow_permission"])
async def test_replacement_authorization_refusal_writes_no_mutation_events(
    client, active_user, logged_in_headers, monkeypatch, guard
):
    project_id = uuid4()
    await _seed_project(active_user, project_id)
    flow = _flow("denied")
    denial = mark_authorization_refusal(HTTPException(403, "denied"))
    monkeypatch.setattr(projects_module, guard, AsyncMock(side_effect=denial))

    response = await client.put(
        _url(project_id), json={"description": "after", "flows": [flow]}, headers=logged_in_headers
    )
    assert response.status_code == 404
    assert await events_for(project_id) == []
    assert await events_for(flow["id"]) == []


@pytest.mark.parametrize("mode", ["disabled", "excluded"])
@pytest.mark.parametrize("create", [True, False])
async def test_replacement_respects_audit_settings(client, active_user, logged_in_headers, monkeypatch, mode, create):
    project_id = uuid4()
    if not create:
        await _seed_project(active_user, project_id)
    settings = get_settings_service().settings
    if mode == "disabled":
        monkeypatch.setattr(settings, "audit_enabled", False)
    else:
        monkeypatch.setattr(settings, "audit_exclude_events", ["project:create", "project:write", "flow:*"])
    flow = _flow("target")
    url = _url(project_id)
    body = {"description": "after", "flows": [flow]}
    if create:
        body["project_name"] = f"deployment-{uuid4().hex[:12]}"

    response = await client.put(url, json=body, headers=logged_in_headers)
    assert response.status_code == 200, response.text
    conflict = await client.put(url, json={**body, "description": "different"}, headers=logged_in_headers)
    assert conflict.status_code == 409
    assert await events_for(project_id) == []
    assert await events_for(flow["id"]) == []


async def test_replacement_cleanup_failure_does_not_record_a_failed_mutation(
    client, active_user, logged_in_headers, monkeypatch
):
    from langflow.services.memory_base import flow_cleanup

    project_id = uuid4()
    removed = _flow("removed")
    await _seed_project(active_user, project_id, flows=[{**removed, "id": UUID(removed["id"])}])
    original_delete = projects_module.cascade_delete_flow

    async def collect_cleanup(*args, **kwargs):
        deleted = await original_delete(*args, **kwargs)
        kwargs["memory_base_cleanups"].append(object())
        return deleted

    monkeypatch.setattr(projects_module, "cascade_delete_flow", collect_cleanup)
    cleanup = AsyncMock(side_effect=RuntimeError("cleanup unavailable"))
    monkeypatch.setattr(flow_cleanup, "finalize_flow_memory_base_cleanup", cleanup)
    response = await client.put(_url(project_id), json={"description": "after", "flows": []}, headers=logged_in_headers)

    assert response.status_code == 200, response.text
    cleanup.assert_awaited_once()
    [event] = await events_for(project_id)
    assert event.result == "succeeded"
    [deleted] = await events_for(removed["id"])
    assert deleted.result == "succeeded"
