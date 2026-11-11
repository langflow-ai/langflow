"""Review regressions at the CLI, WebSocket, and authentication boundaries."""

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
