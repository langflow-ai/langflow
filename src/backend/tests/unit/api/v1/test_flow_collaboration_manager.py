"""Unit tests for CollaborationManager."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langflow.api.v1 import collaboration_manager as collaboration_manager_module
from langflow.api.v1.collaboration_manager import CollaborationManager
from langflow.api.v1.schemas.flow_collaboration import (
    CollaborationPresenceEventPayload,
    CollaborationSelectionTarget,
)
from langflow.services.collaboration_events.schemas import CollaborationEvent


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
    )


@pytest.mark.asyncio
async def test_register_unregister_cleans_room(manager, flow_id, user_a):
    conn_id = await _register(manager, flow_id, user_a, "alice")
    assert flow_id in manager.active_flow_ids()
    await manager.unregister(flow_id, conn_id)
    assert flow_id not in manager.active_flow_ids()


@pytest.mark.asyncio
async def test_presence_dedupes_same_user_multiple_tabs(manager, flow_id, user_a):
    await _register(manager, flow_id, user_a, "alice")
    await _register(manager, flow_id, user_a, "alice")
    users = manager.local_users(flow_id)
    assert len(users) == 1
    assert users[0].username == "alice"


@pytest.mark.asyncio
async def test_presence_getters_can_return_keyed_rosters(manager, flow_id, user_a, user_b):
    await _register(manager, flow_id, user_a, "alice")
    manager.apply_remote_presence(
        flow_id,
        CollaborationPresenceEventPayload(
            worker_id="remote-worker",
            published_at=9_999_999_999.0,
            users=[{"user_id": str(user_b), "username": "bob", "profile_image": None}],
        ),
    )

    local_users = manager.local_users(flow_id, as_dict=True)
    all_users = manager.all_users(flow_id, as_dict=True)

    assert set(local_users) == {user_a}
    assert set(all_users) == {user_a, user_b}
    assert all_users[user_b].username == "bob"


@pytest.mark.asyncio
async def test_presence_payload_publishes_only_local_roster(manager, flow_id, user_a, user_b):
    await _register(manager, flow_id, user_a, "alice")
    manager.apply_remote_presence(
        flow_id,
        CollaborationPresenceEventPayload(
            worker_id="remote-worker",
            published_at=9_999_999_999.0,
            users=[{"user_id": str(user_b), "username": "bob", "profile_image": None}],
        ),
    )

    payload = manager.presence_payload(flow_id)

    assert [user["username"] for user in payload["users"]] == ["alice"]
    assert {user.username for user in manager.all_users(flow_id)} == {"alice", "bob"}


@pytest.mark.asyncio
async def test_broadcast_excludes_origin_connection(manager, flow_id, user_a, user_b):
    origin = await _register(manager, flow_id, user_a, "alice")
    peer = await _register(manager, flow_id, user_b, "bob")

    await manager.broadcast_json(flow_id, {"type": "ping"}, exclude_connection_id=origin)

    origin_ws = manager._rooms[flow_id][origin].websocket
    peer_ws = manager._rooms[flow_id][peer].websocket
    origin_ws.send_json.assert_not_called()
    peer_ws.send_json.assert_called_once()


@pytest.mark.asyncio
async def test_flow_isolation_for_broadcast(manager, user_a):
    flow_a = uuid4()
    flow_b = uuid4()
    conn_a = await _register(manager, flow_a, user_a, "alice")
    await _register(manager, flow_b, user_a, "alice")

    await manager.broadcast_json(flow_a, {"type": "ping"})

    ws_a = manager._rooms[flow_a][conn_a].websocket
    ws_b = next(iter(manager._rooms[flow_b].values())).websocket
    ws_a.send_json.assert_called_once()
    ws_b.send_json.assert_not_called()


@pytest.mark.asyncio
async def test_backplane_operation_deduped_when_already_fanned(manager, flow_id):
    manager.mark_operation_fanned(flow_id, 3)
    assert manager.should_fanout_backplane_operation(flow_id, 3) is False
    assert manager.should_fanout_backplane_operation(flow_id, 4) is True


@pytest.mark.asyncio
async def test_handle_backplane_operation_broadcasts_to_local_peers(manager, flow_id, user_a, user_b):
    await _register(manager, flow_id, user_a, "alice")
    peer_id = await _register(manager, flow_id, user_b, "bob")
    peer_ws = manager._rooms[flow_id][peer_id].websocket

    event = CollaborationEvent(
        id="evt-1",
        flow_id=flow_id,
        created_at=1.0,
        type="operation.accepted",
        payload={
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
    peer_ws = manager._rooms[flow_id][peer_id].websocket

    event = CollaborationEvent(
        id="evt-bad",
        flow_id=flow_id,
        created_at=1.0,
        type="operation.accepted",
        payload={
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
    peer_ws = manager._rooms[flow_id][peer_id].websocket

    event = CollaborationEvent(
        id="evt-unknown",
        flow_id=flow_id,
        created_at=1.0,
        type="unknown.event",
        payload={},
    )

    await manager.handle_backplane_event(event)

    peer_ws.send_json.assert_not_called()


@pytest.mark.asyncio
async def test_presence_visibility_diff_detects_join_and_leave(manager, flow_id, user_a, user_b):
    await _register(manager, flow_id, user_a, "alice")
    before = manager.all_users(flow_id, as_dict=True)
    await _register(manager, flow_id, user_b, "bob")
    after = manager.all_users(flow_id, as_dict=True)
    joined_users, left_user_ids = manager.presence_visibility_diff(before, after)
    assert [user.username for user in joined_users] == ["bob"]
    assert left_user_ids == []


@pytest.mark.asyncio
async def test_presence_snapshot_and_selection_snapshot_messages(manager, flow_id, user_a):
    await _register(manager, flow_id, user_a, "alice")
    manager.set_user_selection(
        flow_id,
        user_a,
        CollaborationSelectionTarget(kind="node", id="node-1"),
    )

    presence = manager.presence_snapshot_message(flow_id)
    selection = manager.selection_snapshot_message(flow_id)

    assert presence["type"] == "presence.snapshot"
    assert len(presence["users"]) == 1
    assert selection["type"] == "selection.snapshot"
    assert selection["selections"] == [{"user_id": str(user_a), "selected": {"kind": "node", "id": "node-1"}}]


@pytest.mark.asyncio
async def test_clear_user_selection_returns_updated_message(manager, flow_id, user_a):
    await _register(manager, flow_id, user_a, "alice")
    manager.set_user_selection(
        flow_id,
        user_a,
        CollaborationSelectionTarget(kind="edge", id="edge-1"),
    )

    cleared = manager.clear_user_selection(flow_id, user_a)

    assert cleared == {
        "type": "selection.updated",
        "user_id": str(user_a),
        "selected": None,
    }
    assert manager.selection_snapshot_message(flow_id)["selections"] == []


@pytest.mark.asyncio
async def test_handle_backplane_presence_broadcasts_incremental_joined(manager, flow_id, user_a, user_b):
    await _register(manager, flow_id, user_a, "alice")
    peer_id = await _register(manager, flow_id, user_b, "bob")
    peer_ws = manager._rooms[flow_id][peer_id].websocket
    peer_ws.send_json.reset_mock()

    event = CollaborationEvent(
        id="evt-remote-presence",
        flow_id=flow_id,
        created_at=1.0,
        type="presence.roster",
        payload={
            "worker_id": "remote-worker",
            "published_at": 9_999_999_999.0,
            "users": [{"user_id": str(user_a), "username": "alice", "profile_image": None}],
        },
    )

    await manager.handle_backplane_event(event)

    peer_ws.send_json.assert_not_called()

    event = CollaborationEvent(
        id="evt-remote-presence-2",
        flow_id=flow_id,
        created_at=2.0,
        type="presence.roster",
        payload={
            "worker_id": "remote-worker",
            "published_at": 9_999_999_999.0,
            "users": [
                {"user_id": str(user_a), "username": "alice", "profile_image": None},
                {"user_id": str(uuid4()), "username": "carol", "profile_image": None},
            ],
        },
    )

    await manager.handle_backplane_event(event)

    peer_ws.send_json.assert_called_once()
    payload = peer_ws.send_json.call_args.args[0]
    assert payload["type"] == "presence.joined"
    assert payload["user"]["username"] == "carol"


@pytest.mark.asyncio
async def test_handle_backplane_presence_ignores_malformed_payload(manager, flow_id, user_a, user_b):
    await _register(manager, flow_id, user_a, "alice")
    peer_id = await _register(manager, flow_id, user_b, "bob")
    peer_ws = manager._rooms[flow_id][peer_id].websocket

    event = CollaborationEvent(
        id="evt-bad-presence",
        flow_id=flow_id,
        created_at=1.0,
        type="presence.roster",
        payload={
            "worker_id": "remote-worker",
            "published_at": "not-a-timestamp",
            "users": [{"user_id": str(user_b), "username": "bob", "profile_image": None}],
        },
    )

    await manager.handle_backplane_event(event)

    peer_ws.send_json.assert_not_called()


@pytest.mark.asyncio
async def test_handle_backplane_presence_ignores_current_worker_payload(manager, flow_id, user_a, user_b):
    await _register(manager, flow_id, user_a, "alice")
    peer_id = await _register(manager, flow_id, user_b, "bob")
    peer_ws = manager._rooms[flow_id][peer_id].websocket

    event = CollaborationEvent(
        id="evt-own-presence",
        flow_id=flow_id,
        created_at=1.0,
        type="presence.roster",
        payload={
            "worker_id": collaboration_manager_module.WORKER_ID,
            "published_at": 9_999_999_999.0,
            "users": [{"user_id": str(user_b), "username": "bob", "profile_image": None}],
        },
    )

    await manager.handle_backplane_event(event)

    peer_ws.send_json.assert_not_called()
