"""Unit tests for CollaborationManager."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langflow.api.v1 import collaboration_manager as collaboration_manager_module
from langflow.api.v1.collaboration_manager import CollaborationManager
from langflow.services.collaboration_events.schemas import (
    CollaborationEvent,
    CollaborationPresenceChange,
    CollaborationPresenceConnectionUser,
    CollaborationPresenceSnapshot,
)
from langflow.services.collaboration_events.schemas import (
    CollaborationSelectionTarget as ServiceSelectionTarget,
)


@pytest.fixture
def manager() -> CollaborationManager:
    return CollaborationManager()


@pytest.fixture
def flow_id():
    return uuid4()


@pytest.fixture
def user_a():
    return uuid4()


@pytest.fixture
def user_b():
    return uuid4()


async def _register(manager: CollaborationManager, flow_id, user_id, username):
    ws = AsyncMock()
    return await manager.register(
        websocket=ws,
        flow_id=flow_id,
        user_id=user_id,
        username=username,
        profile_image=None,
        max_connections=100,
    )


def _snapshot(*users: CollaborationPresenceConnectionUser) -> CollaborationPresenceSnapshot:
    return CollaborationPresenceSnapshot(users=list(users))


@pytest.mark.asyncio
async def test_register_unregister_cleans_room(manager, flow_id, user_a):
    conn_id = await _register(manager, flow_id, user_a, "alice")
    assert flow_id in manager.rooms.active_flow_ids()
    await manager.unregister(conn_id)
    assert flow_id not in manager.rooms.active_flow_ids()


@pytest.mark.asyncio
async def test_broadcast_excludes_origin_connection(manager, flow_id, user_a, user_b):
    origin = await _register(manager, flow_id, user_a, "alice")
    peer = await _register(manager, flow_id, user_b, "bob")

    await manager.broadcast_json(flow_id, {"type": "ping"}, exclude_connection_id=origin)

    origin_conn = manager.rooms.get_connection(origin)
    peer_conn = manager.rooms.get_connection(peer)
    assert origin_conn is not None
    assert peer_conn is not None
    origin_ws = origin_conn.websocket
    peer_ws = peer_conn.websocket
    origin_ws.send_json.assert_not_called()
    peer_ws.send_json.assert_called_once()


@pytest.mark.asyncio
async def test_flow_isolation_for_broadcast(manager, user_a):
    flow_a = uuid4()
    flow_b = uuid4()
    conn_a = await _register(manager, flow_a, user_a, "alice")
    await _register(manager, flow_b, user_a, "alice")

    await manager.broadcast_json(flow_a, {"type": "ping"})

    conn_a_obj = manager.rooms.get_connection(conn_a)
    flow_b_conn = manager.rooms.connections_for_flow(flow_b)[0]
    assert conn_a_obj is not None
    ws_a = conn_a_obj.websocket
    ws_b = flow_b_conn.websocket
    ws_a.send_json.assert_called_once()
    ws_b.send_json.assert_not_called()


@pytest.mark.asyncio
async def test_handle_backplane_operation_ignores_current_worker(manager, flow_id, user_a):
    peer_id = await _register(manager, flow_id, user_a, "alice")
    peer_conn = manager.rooms.get_connection(peer_id)
    assert peer_conn is not None
    peer_ws = peer_conn.websocket

    event = CollaborationEvent(
        id=uuid4(),
        flow_id=flow_id,
        created_at=1.0,
        type="operation.accepted",
        payload={
            "worker_id": collaboration_manager_module.WORKER_ID,
            "revision": 3,
            "actor_user_id": str(user_a),
            "actor_delegate": "self",
            "forward_ops": [],
            "created_at": "2026-01-01T00:00:00+00:00",
        },
    )

    await manager.handle_backplane_event(event)

    peer_ws.send_json.assert_not_called()


@pytest.mark.asyncio
async def test_handle_backplane_operation_broadcasts_to_local_peers(manager, flow_id, user_a, user_b):
    await _register(manager, flow_id, user_a, "alice")
    peer_id = await _register(manager, flow_id, user_b, "bob")
    peer_conn = manager.rooms.get_connection(peer_id)
    assert peer_conn is not None
    peer_ws = peer_conn.websocket

    event = CollaborationEvent(
        id=uuid4(),
        flow_id=flow_id,
        created_at=1.0,
        type="operation.accepted",
        payload={
            "worker_id": "other-worker",
            "revision": 2,
            "actor_user_id": str(user_a),
            "actor_delegate": "self",
            "forward_ops": [],
            "created_at": "2026-01-01T00:00:00+00:00",
        },
    )
    await manager.handle_backplane_event(event)
    peer_ws.send_json.assert_called_once()
    payload = peer_ws.send_json.call_args.args[0]
    assert payload["type"] == "operation.broadcast"
    assert payload["revision"] == 2


@pytest.mark.asyncio
async def test_handle_backplane_operation_ignores_malformed_payload(manager, flow_id, user_a, user_b):
    await _register(manager, flow_id, user_a, "alice")
    peer_id = await _register(manager, flow_id, user_b, "bob")
    peer_conn = manager.rooms.get_connection(peer_id)
    assert peer_conn is not None
    peer_ws = peer_conn.websocket

    event = CollaborationEvent(
        id=uuid4(),
        flow_id=flow_id,
        created_at=1.0,
        type="operation.accepted",
        payload={
            "worker_id": "other-worker",
            "revision": True,
            "actor_user_id": str(user_a),
            "forward_ops": [],
            "created_at": "2026-01-01T00:00:00+00:00",
        },
    )

    await manager.handle_backplane_event(event)

    peer_ws.send_json.assert_not_called()


@pytest.mark.asyncio
async def test_handle_backplane_event_ignores_unknown_type(manager, flow_id, user_a, user_b):
    await _register(manager, flow_id, user_a, "alice")
    peer_id = await _register(manager, flow_id, user_b, "bob")
    peer_conn = manager.rooms.get_connection(peer_id)
    assert peer_conn is not None
    peer_ws = peer_conn.websocket

    event = CollaborationEvent(
        id=uuid4(),
        flow_id=flow_id,
        created_at=1.0,
        type="unknown.event",
        payload={},
    )

    await manager.handle_backplane_event(event)

    peer_ws.send_json.assert_not_called()


@pytest.mark.asyncio
async def test_presence_snapshot_includes_selection(manager, user_a):
    snapshot = _snapshot(
        CollaborationPresenceConnectionUser(
            user_id=user_a,
            username="alice",
            profile_image=None,
            selected=ServiceSelectionTarget(kind="node", id="node-1"),
        )
    )

    presence = manager.presence_snapshot_message(snapshot)

    assert presence["type"] == "presence.snapshot"
    assert presence["users"] == [
        {
            "user_id": str(user_a),
            "username": "alice",
            "profile_image": None,
            "selected": {"kind": "node", "id": "node-1"},
        }
    ]


@pytest.mark.asyncio
async def test_emit_presence_change_broadcasts_and_publishes_left(manager, flow_id, user_a, user_b):
    await _register(manager, flow_id, user_a, "alice")
    peer_id = await _register(manager, flow_id, user_b, "bob")
    peer_conn = manager.rooms.get_connection(peer_id)
    assert peer_conn is not None
    peer_ws = peer_conn.websocket
    event_service = AsyncMock()

    await manager.emit_presence_change(flow_id, CollaborationPresenceChange(left_user_id=user_a), event_service)

    peer_ws.send_json.assert_called_once()
    payload = peer_ws.send_json.call_args.args[0]
    assert payload["type"] == "presence.left"
    assert payload["user_id"] == str(user_a)
    event_service.publish.assert_awaited_once_with(
        flow_id,
        "presence.left",
        {"worker_id": collaboration_manager_module.WORKER_ID, "user_id": str(user_a)},
    )


@pytest.mark.asyncio
async def test_handle_backplane_presence_joined_broadcasts(manager, flow_id, user_a, user_b):
    await _register(manager, flow_id, user_a, "alice")
    peer_id = await _register(manager, flow_id, user_b, "bob")
    peer_conn = manager.rooms.get_connection(peer_id)
    assert peer_conn is not None
    peer_ws = peer_conn.websocket

    event = CollaborationEvent(
        id=uuid4(),
        flow_id=flow_id,
        created_at=1.0,
        type="presence.joined",
        payload={
            "worker_id": "remote-worker",
            "user": {"user_id": str(uuid4()), "username": "carol", "profile_image": None},
        },
    )

    await manager.handle_backplane_event(event)

    peer_ws.send_json.assert_called_once()
    payload = peer_ws.send_json.call_args.args[0]
    assert payload["type"] == "presence.joined"
    assert payload["user"]["username"] == "carol"


@pytest.mark.asyncio
async def test_handle_backplane_presence_ignores_current_worker(manager, flow_id, user_a, user_b):
    await _register(manager, flow_id, user_a, "alice")
    peer_id = await _register(manager, flow_id, user_b, "bob")
    peer_conn = manager.rooms.get_connection(peer_id)
    assert peer_conn is not None
    peer_ws = peer_conn.websocket

    event = CollaborationEvent(
        id=uuid4(),
        flow_id=flow_id,
        created_at=1.0,
        type="presence.joined",
        payload={
            "worker_id": collaboration_manager_module.WORKER_ID,
            "user": {"user_id": str(user_b), "username": "bob", "profile_image": None},
        },
    )

    await manager.handle_backplane_event(event)

    peer_ws.send_json.assert_not_called()


@pytest.mark.asyncio
async def test_handle_backplane_selection_updated_broadcasts(manager, flow_id, user_a, user_b):
    await _register(manager, flow_id, user_a, "alice")
    peer_id = await _register(manager, flow_id, user_b, "bob")
    peer_conn = manager.rooms.get_connection(peer_id)
    assert peer_conn is not None
    peer_ws = peer_conn.websocket

    event = CollaborationEvent(
        id=uuid4(),
        flow_id=flow_id,
        created_at=1.0,
        type="selection.updated",
        payload={
            "worker_id": "remote-worker",
            "user_id": str(user_a),
            "selected": {"kind": "node", "id": "n-1"},
        },
    )

    await manager.handle_backplane_event(event)

    peer_ws.send_json.assert_called_once()
    payload = peer_ws.send_json.call_args.args[0]
    assert payload["type"] == "selection.updated"
    assert payload["selected"] == {"kind": "node", "id": "n-1"}
