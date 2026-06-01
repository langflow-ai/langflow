"""WebSocket and persistence tests for flow collaboration."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock
from uuid import UUID

import anyio
import pytest
from fastapi import status
from langflow.api.utils.collab.access import FlowCollaborationAccessError
from langflow.api.utils.collab.connection import FlowCollaborationConnection
from langflow.api.utils.collab.operations import FlowOperationApplyError, apply_flow_operation_batch
from langflow.api.v1.collaboration_manager import CollaborationManager
from langflow.api.v1.flows_helpers import _get_safe_flow_path
from langflow.services.database.models.flow.model import Flow, FlowCreate
from langflow.services.database.models.user.model import UserRead
from langflow.services.deps import get_storage_service, session_scope
from sqlmodel import select
from starlette.testclient import TestClient
from starlette.websockets import WebSocketState

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import TracebackType

    from httpx import AsyncClient
    from langflow.services.storage.service import StorageService
    from starlette.websockets import WebSocket

NODE_A = {
    "id": "a",
    "type": "genericNode",
    "position": {"x": 0, "y": 0},
    "data": {"type": "genericNode", "node": {"template": {}, "description": "", "display_name": "A"}},
}
NODE_B = {
    "id": "b",
    "type": "genericNode",
    "position": {"x": 100, "y": 0},
    "data": {"type": "genericNode", "node": {"template": {}, "description": "", "display_name": "B"}},
}
EDGE_AB = {
    "id": "e-ab",
    "source": "a",
    "target": "b",
    "sourceHandle": "a-out",
    "targetHandle": "b-in",
}


@pytest.fixture(autouse=True)
def reset_collaboration_manager():
    import langflow.api.v1.collaboration_manager as collaboration_manager_module

    collaboration_manager_module._manager = CollaborationManager()


@pytest.fixture(autouse=True)
def skip_collaboration_poll_loop(monkeypatch):
    import langflow.api.utils.collab.connection as flow_collaboration_connection_module

    async def _noop() -> None:
        return None

    monkeypatch.setattr(flow_collaboration_connection_module, "ensure_collaboration_poll_loop", _noop)


def _access_token(logged_in_headers: dict[str, str]) -> str:
    return logged_in_headers["Authorization"].removeprefix("Bearer ").strip()


async def _create_collab_flow(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
    *,
    fs_path: str | None = None,
) -> UUID:
    payload = FlowCreate(
        name="collab-test",
        data={"nodes": [copy.deepcopy(NODE_A), copy.deepcopy(NODE_B)], "edges": [copy.deepcopy(EDGE_AB)]},
        fs_path=fs_path,
    )
    response = await client.post(
        "api/v1/flows/",
        json=payload.model_dump(mode="json"),
        headers=logged_in_headers,
    )
    assert response.status_code == 201
    return UUID(response.json()["id"])


def _receive_message_type(ws, expected_type: str) -> dict:
    while True:
        message = ws.receive_json()
        if message.get("type") == expected_type:
            return message


def _receive_session_bootstrap(ws) -> tuple[dict, dict]:
    ready = _receive_message_type(ws, "session.ready")
    presence = _receive_message_type(ws, "presence.snapshot")
    return ready, presence


def _close_websocket_cleanly(ws) -> None:
    ws.close()
    ws.portal.call(anyio.sleep, 0.05)


class _FakeWebSocket:
    client_state = WebSocketState.CONNECTED

    def __init__(self) -> None:
        self.sent_messages: list[dict[str, object]] = []
        self.closed_code: int | None = None
        self.closed_reason: str | None = None

    async def send_json(self, message: dict[str, object]) -> None:
        self.sent_messages.append(message)

    async def close(self, code: int, reason: str | None = None) -> None:
        self.closed_code = code
        self.closed_reason = reason
        self.client_state = WebSocketState.DISCONNECTED


class _NoopAsyncSessionScope:
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None


async def _run_websocket_test(app, flow_id: UUID, token: str, fn: Callable) -> None:
    def _invoke() -> None:
        ws_client = TestClient(app)
        try:
            with ws_client.websocket_connect(f"api/v1/flows/{flow_id}/collab?token={token}") as ws:
                fn(ws)
                _close_websocket_cleanly(ws)
        finally:
            ws_client.close()

    await anyio.to_thread.run_sync(_invoke)


async def _run_dual_websocket_test(app, flow_id: UUID, token: str, fn: Callable) -> None:
    def _invoke() -> None:
        ws_client = TestClient(app)
        try:
            with (
                ws_client.websocket_connect(f"api/v1/flows/{flow_id}/collab?token={token}") as ws_a,
                ws_client.websocket_connect(f"api/v1/flows/{flow_id}/collab?token={token}") as ws_b,
            ):
                fn(ws_a, ws_b)
                _close_websocket_cleanly(ws_b)
                _close_websocket_cleanly(ws_a)
        finally:
            ws_client.close()

    await anyio.to_thread.run_sync(_invoke)


async def test_active_session_closes_when_read_access_is_revoked(active_user, monkeypatch):
    import langflow.api.utils.collab.connection as connection_module

    async def _deny_active_read_access(*_args: object) -> None:
        raise FlowCollaborationAccessError(code="unauthorized", detail="Flow not found")

    websocket = _FakeWebSocket()
    monkeypatch.setattr(connection_module, "session_scope_readonly", lambda: _NoopAsyncSessionScope())
    monkeypatch.setattr(connection_module, "validate_flow_access", _deny_active_read_access)

    connection = FlowCollaborationConnection(
        websocket=cast("WebSocket", websocket),
        flow_id=UUID("00000000-0000-0000-0000-000000000001"),
        current_user=UserRead.model_validate(active_user, from_attributes=True),
        starting_revision=0,
        storage_service=cast("StorageService", AsyncMock()),
        manager=CollaborationManager(),
    )

    with pytest.raises(connection_module._CollaborationConnectionClosedError):
        await connection._ensure_active_read_access()
    assert websocket.sent_messages == []
    assert websocket.closed_code == status.WS_1008_POLICY_VIOLATION
    assert websocket.closed_reason == "Flow not found"


async def test_operation_submit_handler_raises_rejection_for_invalid_payload(active_user):
    websocket = _FakeWebSocket()
    connection = FlowCollaborationConnection(
        websocket=cast("WebSocket", websocket),
        flow_id=UUID("00000000-0000-0000-0000-000000000001"),
        current_user=UserRead.model_validate(active_user, from_attributes=True),
        starting_revision=0,
        storage_service=cast("StorageService", AsyncMock()),
        manager=CollaborationManager(),
    )

    await connection._handle_operation_submit({"type": "operation.submit", "request_id": "req-invalid"})

    assert len(websocket.sent_messages) == 1
    rejected = websocket.sent_messages[0]
    assert rejected["type"] == "operation.rejected"
    assert rejected["request_id"] == "req-invalid"
    assert rejected["status"] == 400
    assert rejected["current_revision"] is None
    assert "base_revision" in rejected["detail"]
    assert "operations" in rejected["detail"]


async def test_operation_submit_handler_raises_rejection_for_apply_error(active_user, monkeypatch):
    async def _raise_apply_error(*_args: object) -> None:
        raise FlowOperationApplyError(status_code=409, detail="Stale revision", current_revision=3)

    websocket = _FakeWebSocket()
    connection = FlowCollaborationConnection(
        websocket=cast("WebSocket", websocket),
        flow_id=UUID("00000000-0000-0000-0000-000000000001"),
        current_user=UserRead.model_validate(active_user, from_attributes=True),
        starting_revision=0,
        storage_service=cast("StorageService", AsyncMock()),
        manager=CollaborationManager(),
    )
    monkeypatch.setattr(connection, "_apply_operation", _raise_apply_error)

    await connection._handle_operation_submit(
        {
            "type": "operation.submit",
            "request_id": "req-stale",
            "base_revision": 0,
            "operations": [],
        }
    )

    assert websocket.sent_messages == [
        {
            "type": "operation.rejected",
            "request_id": "req-stale",
            "status": 409,
            "detail": "Stale revision",
            "current_revision": 3,
        }
    ]


async def test_collab_session_ready(client: AsyncClient, logged_in_headers):
    token = _access_token(logged_in_headers)
    flow_id = await _create_collab_flow(client, logged_in_headers)
    app = client._transport.app

    def _assert(ws) -> None:
        ws.send_json({"type": "session.start"})
        ready, presence = _receive_session_bootstrap(ws)
        assert ready["type"] == "session.ready"
        assert ready["current_revision"] == 0
        assert ready["flow_id"] == str(flow_id)
        assert "users" not in ready
        assert presence["type"] == "presence.snapshot"
        assert len(presence["users"]) == 1
        assert presence["users"][0]["username"] == "activeuser"

    await _run_websocket_test(app, flow_id, token, _assert)


async def test_operation_submit_accepted_increments_revision(client: AsyncClient, logged_in_headers):
    token = _access_token(logged_in_headers)
    flow_id = await _create_collab_flow(client, logged_in_headers)
    app = client._transport.app

    def _submit(ws) -> None:
        ws.send_json({"type": "session.start"})
        ready, _ = _receive_session_bootstrap(ws)
        updated = copy.deepcopy(NODE_A)
        updated["position"] = {"x": 50, "y": 50}
        ws.send_json(
            {
                "type": "operation.submit",
                "request_id": "req-1",
                "base_revision": ready["current_revision"],
                "operations": [{"type": "update_nodes", "nodes": [updated]}],
            }
        )
        accepted = _receive_message_type(ws, "operation.accepted")
        assert accepted["type"] == "operation.accepted"
        assert accepted["request_id"] == "req-1"
        assert accepted["revision"] == 1

    await _run_websocket_test(app, flow_id, token, _submit)

    async with session_scope() as session:
        flow = (await session.exec(select(Flow).where(Flow.id == flow_id))).first()
        assert flow is not None
        assert flow.latest_operation_revision == 1
        node = next(n for n in flow.data["nodes"] if n["id"] == "a")
        assert node["position"] == {"x": 50, "y": 50}


async def test_filesystem_mirror_restored_when_commit_fails(
    client: AsyncClient,
    logged_in_headers,
    active_user,
    monkeypatch,
):
    fs_path = "collab-rollback.json"
    flow_id = await _create_collab_flow(client, logged_in_headers, fs_path=fs_path)
    storage_service = get_storage_service()
    mirror_path = _get_safe_flow_path(fs_path, active_user.id, storage_service)
    original_mirror = await mirror_path.read_bytes()

    async with session_scope() as session:
        original_commit = session.commit
        has_failed = False

        async def _fail_once_commit() -> None:
            nonlocal has_failed
            if not has_failed:
                has_failed = True
                msg = "synthetic commit failure"
                raise RuntimeError(msg)
            await original_commit()

        monkeypatch.setattr(session, "commit", _fail_once_commit)

        updated = copy.deepcopy(NODE_A)
        updated["position"] = {"x": 88, "y": 88}
        with pytest.raises(FlowOperationApplyError) as exc:
            await apply_flow_operation_batch(
                session,
                flow_id=flow_id,
                actor_user_id=active_user.id,
                base_revision=0,
                operations=[{"type": "update_nodes", "nodes": [updated]}],
                storage_service=storage_service,
            )

    assert exc.value.status_code == 500
    assert await mirror_path.read_bytes() == original_mirror
    async with session_scope() as session:
        flow = (await session.exec(select(Flow).where(Flow.id == flow_id))).first()
        assert flow is not None
        assert flow.latest_operation_revision == 0


async def test_stale_revision_rejected(client: AsyncClient, logged_in_headers):
    token = _access_token(logged_in_headers)
    flow_id = await _create_collab_flow(client, logged_in_headers)
    app = client._transport.app

    def _submit(ws) -> None:
        ws.send_json({"type": "session.start"})
        ready, _ = _receive_session_bootstrap(ws)
        ws.send_json(
            {
                "type": "operation.submit",
                "request_id": "req-1",
                "base_revision": ready["current_revision"],
                "operations": [{"type": "update_nodes", "nodes": [copy.deepcopy(NODE_A)]}],
            }
        )
        _receive_message_type(ws, "operation.accepted")
        ws.send_json(
            {
                "type": "operation.submit",
                "request_id": "req-2",
                "base_revision": ready["current_revision"],
                "operations": [{"type": "update_nodes", "nodes": [copy.deepcopy(NODE_B)]}],
            }
        )
        rejected = _receive_message_type(ws, "operation.rejected")
        assert rejected["type"] == "operation.rejected"
        assert rejected["status"] == 409
        assert rejected["current_revision"] == 1

    await _run_websocket_test(app, flow_id, token, _submit)


async def test_delete_nodes_removes_incident_edges(client: AsyncClient, logged_in_headers):
    token = _access_token(logged_in_headers)
    flow_id = await _create_collab_flow(client, logged_in_headers)
    app = client._transport.app

    def _submit(ws) -> None:
        ws.send_json({"type": "session.start"})
        _receive_session_bootstrap(ws)
        ws.send_json(
            {
                "type": "operation.submit",
                "request_id": "req-del",
                "base_revision": 0,
                "operations": [{"type": "delete_nodes", "ids": ["a"]}],
            }
        )
        accepted = _receive_message_type(ws, "operation.accepted")
        assert accepted["type"] == "operation.accepted"
        forward_types = [op["type"] for op in accepted["forward_ops"]]
        assert "delete_nodes" in forward_types
        assert "delete_edges" in forward_types

    await _run_websocket_test(app, flow_id, token, _submit)

    async with session_scope() as session:
        flow = (await session.exec(select(Flow).where(Flow.id == flow_id))).first()
        assert flow is not None
        assert flow.data["edges"] == []


async def test_invalid_edge_rejected_without_revision_change(client: AsyncClient, logged_in_headers):
    token = _access_token(logged_in_headers)
    flow_id = await _create_collab_flow(client, logged_in_headers)
    app = client._transport.app

    def _submit(ws) -> None:
        ws.send_json({"type": "session.start"})
        ready, _ = _receive_session_bootstrap(ws)
        ws.send_json(
            {
                "type": "operation.submit",
                "request_id": "req-bad-edge",
                "base_revision": ready["current_revision"],
                "operations": [
                    {
                        "type": "add_edges",
                        "edges": [{"id": "e-missing", "source": "missing", "target": "b"}],
                    }
                ],
            }
        )
        rejected = _receive_message_type(ws, "operation.rejected")
        assert rejected["type"] == "operation.rejected"
        assert rejected["status"] == 400

    await _run_websocket_test(app, flow_id, token, _submit)

    async with session_scope() as session:
        flow = (await session.exec(select(Flow).where(Flow.id == flow_id))).first()
        assert flow is not None
        assert flow.latest_operation_revision == 0


async def test_operation_broadcast_to_peer_socket(client: AsyncClient, logged_in_headers):
    token = _access_token(logged_in_headers)
    flow_id = await _create_collab_flow(client, logged_in_headers)
    app = client._transport.app

    def _peers(ws_a, ws_b) -> None:
        ws_a.send_json({"type": "session.start"})
        ready_a, _ = _receive_session_bootstrap(ws_a)
        ws_b.send_json({"type": "session.start"})
        _receive_session_bootstrap(ws_b)

        updated = copy.deepcopy(NODE_B)
        updated["position"] = {"x": 200, "y": 0}
        ws_a.send_json(
            {
                "type": "operation.submit",
                "request_id": "req-peer",
                "base_revision": ready_a["current_revision"],
                "operations": [{"type": "update_nodes", "nodes": [updated]}],
            }
        )
        accepted_a = _receive_message_type(ws_a, "operation.accepted")
        assert accepted_a["type"] == "operation.accepted"

        broadcast = _receive_message_type(ws_b, "operation.broadcast")
        assert broadcast["type"] == "operation.broadcast"
        assert broadcast["revision"] == accepted_a["revision"]
        assert broadcast["actor_user_id"] is not None

    await _run_dual_websocket_test(app, flow_id, token, _peers)


async def test_presence_shows_each_user_once_with_two_tabs(client: AsyncClient, logged_in_headers):
    token = _access_token(logged_in_headers)
    flow_id = await _create_collab_flow(client, logged_in_headers)
    app = client._transport.app

    def _peers(ws_a, ws_b) -> None:
        ws_a.send_json({"type": "session.start"})
        _, presence_a = _receive_session_bootstrap(ws_a)
        assert len(presence_a["users"]) == 1
        assert presence_a["users"][0]["username"] == "activeuser"

        ws_b.send_json({"type": "session.start"})
        _, presence_b = _receive_session_bootstrap(ws_b)
        assert len(presence_b["users"]) == 1

    await _run_dual_websocket_test(app, flow_id, token, _peers)


async def test_selection_update_broadcasts_to_peer(client: AsyncClient, logged_in_headers):
    token = _access_token(logged_in_headers)
    flow_id = await _create_collab_flow(client, logged_in_headers)
    app = client._transport.app

    def _peers(ws_a, ws_b) -> None:
        ws_a.send_json({"type": "session.start"})
        _receive_session_bootstrap(ws_a)
        ws_b.send_json({"type": "session.start"})
        _receive_session_bootstrap(ws_b)

        ws_a.send_json({"type": "selection.update", "selected": {"kind": "node", "id": "a"}})
        updated = _receive_message_type(ws_b, "selection.updated")
        assert updated["type"] == "selection.updated"
        assert updated["selected"] == {"kind": "node", "id": "a"}
        assert updated["user_id"] is not None

    await _run_dual_websocket_test(app, flow_id, token, _peers)


async def test_selection_update_supports_null(client: AsyncClient, logged_in_headers):
    token = _access_token(logged_in_headers)
    flow_id = await _create_collab_flow(client, logged_in_headers)
    app = client._transport.app

    def _peers(ws_a, ws_b) -> None:
        ws_a.send_json({"type": "session.start"})
        _receive_session_bootstrap(ws_a)
        ws_b.send_json({"type": "session.start"})
        _receive_session_bootstrap(ws_b)

        ws_a.send_json({"type": "selection.update", "selected": {"kind": "edge", "id": "e-ab"}})
        _receive_message_type(ws_b, "selection.updated")
        ws_a.send_json({"type": "selection.update", "selected": None})
        cleared = _receive_message_type(ws_b, "selection.updated")
        assert cleared["selected"] is None

    await _run_dual_websocket_test(app, flow_id, token, _peers)


async def test_selection_update_rejects_malformed_payload(client: AsyncClient, logged_in_headers):
    token = _access_token(logged_in_headers)
    flow_id = await _create_collab_flow(client, logged_in_headers)
    app = client._transport.app

    def _assert(ws) -> None:
        ws.send_json({"type": "session.start"})
        _receive_session_bootstrap(ws)
        ws.send_json({"type": "selection.update", "selected": {"kind": "viewport", "id": "x"}})
        error = ws.receive_json()
        assert error["type"] == "message.error"

    await _run_websocket_test(app, flow_id, token, _assert)
