"""Unit tests for collaboration heartbeat scheduling and pong handling."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID, uuid4

import pytest
from langflow.api.v1.collaboration_manager import CollaborationConnectionLimitExceededError, CollaborationManager
from langflow.services.collaboration_events.schemas import (
    CollaborationPresenceChange,
    CollaborationPresenceChangeEnvelope,
)
from langflow.services.database.models.user.model import UserRead
from starlette.websockets import WebSocketState


async def _register(manager: CollaborationManager, flow_id, user_id, username):
    ws = AsyncMock()
    ws.client_state = WebSocketState.CONNECTED
    return await manager.register(
        websocket=ws,
        flow_id=flow_id,
        user_id=user_id,
        username=username,
        profile_image=None,
        max_connections=100,
    ), ws


@pytest.fixture
def manager() -> CollaborationManager:
    return CollaborationManager()


def _user_read() -> UserRead:
    now = datetime.now(timezone.utc)
    return UserRead(
        id=uuid4(),
        username="alice",
        profile_image=None,
        store_api_key=None,
        is_active=True,
        is_superuser=False,
        create_at=now,
        updated_at=now,
        last_login_at=None,
    )


@pytest.fixture
def flow_id():
    return uuid4()


@pytest.fixture
def user_id():
    return uuid4()


@pytest.mark.asyncio
async def test_heartbeat_ping_sets_deadline_and_sends_message(manager, flow_id, user_id):
    conn_id, ws = await _register(manager, flow_id, user_id, "alice")
    conn = manager.rooms.get_connection(conn_id)
    assert conn is not None

    with patch("langflow.api.v1.collaboration_manager.time.time", return_value=1000.0):
        await manager.send_heartbeat_ping(conn, 10.0)

    assert conn.pong_deadline_at == 1010.0
    ws.send_json.assert_called_once_with({"type": "heartbeat.ping"})


@pytest.mark.asyncio
async def test_valid_pong_clears_deadline_and_refreshes_presence(manager, flow_id, user_id):
    conn_id, _ws = await _register(manager, flow_id, user_id, "alice")
    conn = manager.rooms.get_connection(conn_id)
    assert conn is not None
    conn.pong_deadline_at = time.time() + 10.0
    event_service = Mock()

    with patch("langflow.api.v1.collaboration_manager.time.time", return_value=1000.0):
        await manager.handle_heartbeat_pong(flow_id, conn_id, event_service)

    assert conn.pong_deadline_at is None
    event_service.update_connection.assert_called_once_with(connection_id=conn_id)


@pytest.mark.asyncio
async def test_late_pong_does_not_refresh_presence(manager, flow_id, user_id):
    conn_id, _ws = await _register(manager, flow_id, user_id, "alice")
    conn = manager.rooms.get_connection(conn_id)
    assert conn is not None
    conn.pong_deadline_at = 500.0
    event_service = Mock()

    with patch("langflow.api.v1.collaboration_manager.time.time", return_value=1000.0):
        await manager.handle_heartbeat_pong(flow_id, conn_id, event_service)

    event_service.update_connection.assert_not_called()


@pytest.mark.asyncio
async def test_expired_deadline_disconnects_and_emits_presence_left(manager, flow_id, user_id):
    conn_id, ws = await _register(manager, flow_id, user_id, "alice")
    conn = manager.rooms.get_connection(conn_id)
    assert conn is not None
    conn.pong_deadline_at = 1.0
    event_service = Mock()
    event_service.remove_connections.return_value = [
        CollaborationPresenceChangeEnvelope(
            flow_id=flow_id,
            change=CollaborationPresenceChange(left_user_id=user_id),
        )
    ]

    with patch("langflow.api.v1.collaboration_manager.time.time", return_value=1000.0):
        await manager.disconnect_expired_heartbeats(event_service)

    assert flow_id not in manager.rooms.active_flow_ids()
    event_service.remove_connections.assert_called_once_with([conn_id])
    ws.close.assert_called_once()


@pytest.mark.asyncio
async def test_disconnect_connection_is_idempotent(manager):
    event_service = Mock()
    event_service.remove_connection.return_value = None

    await manager.disconnect_connection(uuid4(), event_service)
    event_service.remove_connection.assert_not_called()
    event_service.remove_connections.assert_not_called()


@pytest.mark.asyncio
async def test_heartbeat_buckets_split_connections_evenly(manager, flow_id):
    user_ids = [uuid4() for _ in range(5)]
    connections = []
    for index, user_id in enumerate(user_ids):
        conn_id, _ws = await _register(manager, flow_id, user_id, f"user-{index}")
        conn = manager.rooms.get_connection(conn_id)
        assert conn is not None
        connections.append(conn)

    buckets = manager.heartbeat_buckets(connections, bucket_count=2)
    assert len(buckets) == 2
    assert [conn for bucket in buckets for conn in bucket] == connections


@pytest.mark.asyncio
async def test_register_rejects_connection_limit_excess(manager, flow_id):
    await manager.register(
        websocket=AsyncMock(),
        flow_id=flow_id,
        user_id=uuid4(),
        username="alice",
        profile_image=None,
        max_connections=1,
    )

    with pytest.raises(CollaborationConnectionLimitExceededError, match="maximum capacity for this server"):
        await manager.register(
            websocket=AsyncMock(),
            flow_id=flow_id,
            user_id=uuid4(),
            username="bob",
            profile_image=None,
            max_connections=1,
        )


def test_collaboration_settings_defaults(monkeypatch, tmp_path):
    from lfx.services.settings.base import Settings

    monkeypatch.setenv("LANGFLOW_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("LANGFLOW_DIR", str(tmp_path / "langflow"))

    settings = Settings()
    assert settings.collaboration_heartbeat_interval == 45.0
    assert settings.collaboration_heartbeat_stagger == 1.0
    assert settings.collaboration_heartbeat_timeout == 10.0
    assert settings.collaboration_connection_ttl == 90.0
    assert settings.collaboration_presence_snapshot_interval == 120.0
    assert settings.collaboration_max_connections == 100


def test_collaboration_settings_reject_invalid_scheduler(monkeypatch, tmp_path):
    from lfx.services.settings.base import Settings

    monkeypatch.setenv("LANGFLOW_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("LANGFLOW_COLLABORATION_HEARTBEAT_INTERVAL", "10")
    monkeypatch.setenv("LANGFLOW_COLLABORATION_HEARTBEAT_STAGGER", "10")

    with pytest.raises(ValueError, match="stagger"):
        Settings()

    monkeypatch.setenv("LANGFLOW_COLLABORATION_MAX_CONNECTIONS", "0")

    with pytest.raises(ValueError, match="positive integer"):
        Settings()


@pytest.mark.asyncio
async def test_heartbeat_pong_handler_checks_access_before_refresh(monkeypatch):
    import langflow.api.utils.collab.connection as connection_module

    monkeypatch.setattr(connection_module, "get_collaboration_events_service", Mock(return_value=Mock()))
    websocket = AsyncMock()
    manager = CollaborationManager()
    monkeypatch.setattr(connection_module, "get_collaboration_manager", Mock(return_value=manager))
    current_user = _user_read()
    conn_id = await manager.register(
        websocket=websocket,
        flow_id=UUID("00000000-0000-0000-0000-000000000001"),
        user_id=current_user.id,
        username="alice",
        profile_image=None,
        max_connections=100,
    )
    connection = connection_module.FlowCollaborationConnection(
        websocket=websocket,
        flow_id=UUID("00000000-0000-0000-0000-000000000001"),
        current_user=current_user,
        storage_service=AsyncMock(),
    )
    connection._registered_connection_id = conn_id
    manager.handle_heartbeat_pong = AsyncMock()

    async def _allow_access(*_args: object) -> None:
        return None

    monkeypatch.setattr(connection, "_ensure_active_read_access", _allow_access)
    await connection._handle_heartbeat_pong({"type": "heartbeat.pong"})
    manager.handle_heartbeat_pong.assert_awaited_once()


@pytest.mark.asyncio
async def test_heartbeat_pong_rejects_extra_fields(monkeypatch):
    import langflow.api.utils.collab.connection as connection_module

    monkeypatch.setattr(connection_module, "get_collaboration_events_service", Mock(return_value=Mock()))
    websocket = AsyncMock()
    manager = CollaborationManager()
    monkeypatch.setattr(connection_module, "get_collaboration_manager", Mock(return_value=manager))
    connection = connection_module.FlowCollaborationConnection(
        websocket=websocket,
        flow_id=UUID("00000000-0000-0000-0000-000000000001"),
        current_user=_user_read(),
        storage_service=AsyncMock(),
    )
    connection._registered_connection_id = uuid4()
    manager.handle_heartbeat_pong = AsyncMock()

    async def _allow_access(*_args: object) -> None:
        return None

    monkeypatch.setattr(connection, "_ensure_active_read_access", _allow_access)
    await connection._handle_heartbeat_pong({"type": "heartbeat.pong", "unexpected": True})
    manager.handle_heartbeat_pong.assert_not_called()


@pytest.mark.asyncio
async def test_heartbeat_pong_skipped_when_access_denied(monkeypatch):
    import langflow.api.utils.collab.connection as connection_module

    monkeypatch.setattr(connection_module, "get_collaboration_events_service", Mock(return_value=Mock()))
    websocket = AsyncMock()
    manager = CollaborationManager()
    monkeypatch.setattr(connection_module, "get_collaboration_manager", Mock(return_value=manager))
    connection = connection_module.FlowCollaborationConnection(
        websocket=websocket,
        flow_id=UUID("00000000-0000-0000-0000-000000000001"),
        current_user=_user_read(),
        storage_service=AsyncMock(),
    )
    connection._registered_connection_id = uuid4()
    manager.handle_heartbeat_pong = AsyncMock()

    async def _deny_access(*_args: object) -> None:
        raise connection_module._CollaborationConnectionClosedError

    monkeypatch.setattr(connection, "_ensure_active_read_access", _deny_access)
    await connection._handle_heartbeat_pong({"type": "heartbeat.pong"})
    manager.handle_heartbeat_pong.assert_not_called()


def test_sqlite_presence_ttl_from_settings(tmp_path):
    from langflow.services.collaboration_events.sqlite import SQLiteCollaborationEventService

    svc = SQLiteCollaborationEventService(cache_dir=tmp_path / "cache", presence_ttl_seconds=42.0)
    assert svc.PRESENCE_TTL_SECONDS == 42.0
