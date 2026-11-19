"""Review regressions at the CLI, WebSocket, and authentication boundaries."""

import asyncio
import json
from unittest.mock import AsyncMock
from urllib.parse import urlencode

import pytest
from fastapi import FastAPI, WebSocket
from langflow.api.utils.migration_pause import MigrationPauseMiddleware, admitted_maintenance_caller
from langflow.services.database.models.api_key.crud import create_api_key
from langflow.services.database.models.api_key.model import ApiKeyCreate
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope
from langflow.services.maintenance.state import set_maintenance
from sqlmodel import select

from tests.unit.api.v1 import test_maintenance as maintenance_fixtures

logged_in_headers_super_user = maintenance_fixtures.logged_in_headers_super_user
without_instance_migration = maintenance_fixtures.without_instance_migration


@pytest.mark.parametrize(
    ("subject", "credential"),
    [("admin", "token"), ("ordinary", "token"), ("admin", "key"), ("ordinary", "key"), ("invalid", "token")],
)
async def test_websocket_maintenance_uses_verified_credentials_and_real_asgi_callables(
    active_user, logged_in_headers, logged_in_headers_super_user, subject, credential
):
    async with session_scope() as session:
        admin = (await session.exec(select(User).where(User.username == "maintenance-admin"))).one()
        if credential == "key":
            key = await create_api_key(
                session, ApiKeyCreate(name="websocket"), admin.id if subject == "admin" else active_user.id
            )
        await set_maintenance(session, enabled=True)
    if credential == "key":
        query = {"x-api-key": key.api_key}
    else:
        header = logged_in_headers_super_user if subject == "admin" else logged_in_headers
        query = {"token": "invalid" if subject == "invalid" else header["Authorization"].removeprefix("Bearer ")}
    app = FastAPI()
    app.add_middleware(MigrationPauseMiddleware)

    @app.websocket("/maintenance-websocket")
    async def repair(socket: WebSocket):
        await socket.accept()
        await socket.send_json({"caller": str(admitted_maintenance_caller())})
        await socket.close()

    sent = []

    async def receive():
        return {"type": "websocket.connect"}

    async def send(message):
        sent.append(message)

    await app(
        {
            "type": "websocket",
            "asgi": {"version": "3.0"},
            "scheme": "ws",
            "path": "/maintenance-websocket",
            "root_path": "",
            "query_string": urlencode(query).encode(),
            "headers": [],
            "subprotocols": [],
            "client": ("test", 1),
            "server": ("test", 80),
            "extensions": {"websocket.http.response": {}},
        },
        receive,
        send,
    )
    if subject == "admin":
        assert sent[0]["type"] == "websocket.accept"
        assert json.loads(sent[1]["text"]) == {"caller": str(admin.id)}
        assert sent[-1]["type"] == "websocket.close"
    else:
        assert sent[0]["status"] == 503
        assert json.loads(sent[1]["body"]) == {"detail": "This instance is in maintenance mode."}
        assert not any(message["type"] == "websocket.accept" for message in sent)
    assert admitted_maintenance_caller() is None


@pytest.mark.parametrize("dry_run", [False, True])
@pytest.mark.usefixtures("client")
async def test_reconciliation_reports_maintenance_without_hiding_the_dry_run(monkeypatch, capsys, *, dry_run):
    from langflow import __main__ as cli
    from langflow.api.utils import knowledge_base_service

    monkeypatch.setattr(cli, "initialize_services", AsyncMock())
    scan = AsyncMock(wraps=knowledge_base_service.backfill_all_users_from_disk)
    monkeypatch.setattr(knowledge_base_service, "backfill_all_users_from_disk", scan)
    async with session_scope() as session:
        await set_maintenance(session, enabled=True)
    await cli._reconcile_kb_from_disk(username=None, dry_run=dry_run)
    output = capsys.readouterr().out
    if dry_run:
        scan.assert_awaited_once_with(username=None, dry_run=True)
        assert "would adopt" in output
    else:
        scan.assert_not_awaited()
        assert "skipped because changes are paused" in output
        assert "adopted 0" not in output


def test_unrelated_authentication_outages_keep_their_existing_http_contract():
    from langflow.services.auth.exceptions import AuthBackendUnavailableError
    from langflow.services.auth.utils import _auth_error_to_http

    response = _auth_error_to_http(AuthBackendUnavailableError())
    assert response.status_code == 503
    assert response.detail == "Authentication is temporarily unavailable"
    assert response.headers == {"Retry-After": "1"}


@pytest.mark.parametrize("surface", ["v1", "v1_advanced", "v2"])
async def test_admitted_run_returns_its_completed_result_when_maintenance_starts(
    client, simple_api_test, created_api_key, logged_in_headers_super_user, monkeypatch, surface
):
    from langflow.api.v1 import endpoints
    from langflow.api.v2 import workflow_execution
    from langflow.exceptions.api import WorkflowServiceUnavailableError
    from langflow.services.task.service import TaskService

    finished = asyncio.Event()
    release = asyncio.Event()
    module = workflow_execution if surface == "v2" else endpoints
    run_graph = module.run_graph_internal

    async def hold_completed_graph(**kwargs):
        result = await run_graph(**kwargs)
        finished.set()
        await release.wait()
        return result

    monkeypatch.setattr(module, "run_graph_internal", hold_completed_graph)
    flow_id = simple_api_test["id"]
    if surface == "v2":
        url = "/api/v2/workflows"
        payload = {"flow_id": flow_id, "mode": "sync", "input_value": "completed before maintenance"}
    elif surface == "v1_advanced":
        url = f"/api/v1/run/advanced/{flow_id}"
        payload = {"inputs": [{"input_value": "completed before maintenance", "components": [], "type": "text"}]}
    else:
        url = f"/api/v1/run/{flow_id}?stream=false"
        payload = {"input_value": "completed before maintenance", "output_type": "text"}
    request = asyncio.create_task(
        client.post(
            url,
            headers={"x-api-key": created_api_key.api_key},
            json=payload,
        )
    )
    try:
        await asyncio.wait_for(finished.wait(), timeout=30)
        enabled = await client.post(maintenance_fixtures.ON, json={}, headers=logged_in_headers_super_user)
        assert enabled.status_code == 200
        with pytest.raises(WorkflowServiceUnavailableError, match="maintenance"):
            await TaskService._admit_task()
    finally:
        release.set()
    response = await asyncio.wait_for(request, timeout=30)
    assert response.status_code == 200, response.text
    assert response.json()["outputs"]
    refused = await client.post(
        f"/api/v1/run/{simple_api_test['id']}",
        headers={"x-api-key": created_api_key.api_key},
        json={"input_value": "new work"},
    )
    assert refused.status_code == 503
