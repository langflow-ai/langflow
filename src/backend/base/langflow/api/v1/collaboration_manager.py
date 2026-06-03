"""In-process WebSocket room state for collaborative flow editing."""

from __future__ import annotations

import asyncio
import math
import time
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable, ItemsView, KeysView, ValuesView
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID

from fastapi import status
from lfx.log.logger import logger
from pydantic import PositiveInt, ValidationError
from starlette.websockets import WebSocketState

from langflow.api.v1.schemas.flow_collaboration import (
    CollaborationHeartbeatPingMessage,
    CollaborationOperationAcceptedBackplaneEvent,
    CollaborationOperationBroadcastMessage,
    CollaborationPresenceJoinedBackplaneEvent,
    CollaborationPresenceJoinedMessage,
    CollaborationPresenceLeftBackplaneEvent,
    CollaborationPresenceLeftMessage,
    CollaborationPresenceSnapshotMessage,
    CollaborationPresenceUser,
    CollaborationSelectionUpdatedBackplaneEvent,
    CollaborationSelectionUpdatedMessage,
    UnsupportedCollaborationBackplaneEventError,
    parse_collaboration_backplane_event,
)
from langflow.services.collaboration_events import CollaborationEventService
from langflow.services.collaboration_events.schemas import (
    CollaborationPollCursor,
    CollaborationPresenceChange,
    CollaborationPresenceSnapshot,
    CollaborationSelectionTarget,
)
from langflow.services.deps import get_collaboration_events_service, get_settings_service

if TYPE_CHECKING:
    from starlette.websockets import WebSocket

    from langflow.services.collaboration_events.schemas import CollaborationEvent

BackplaneEventHandler = Callable[[UUID, Any], Awaitable[None]]
BackplaneEventType = Literal["operation.accepted", "presence.joined", "presence.left", "selection.updated"]

WORKER_ID = str(uuid.uuid4())
_HEARTBEAT_PING_MESSAGE = CollaborationHeartbeatPingMessage().model_dump(mode="json")


@dataclass
class FlowConnection:
    websocket: WebSocket
    connection_id: UUID
    flow_id: UUID
    user_id: UUID
    username: str
    profile_image: str | None
    pong_deadline_at: float | None = field(default=None)


@dataclass
class FlowRooms:
    """Typed room collection keyed by connection id with flow id as a secondary index."""

    by_connection_id: dict[UUID, FlowConnection] = field(default_factory=dict)
    by_flow_id: defaultdict[UUID, set[UUID]] = field(default_factory=lambda: defaultdict(set))

    def active_flow_ids(self) -> KeysView[UUID]:
        return self.by_flow_id.keys()

    def add(self, conn: FlowConnection) -> None:
        self.by_connection_id[conn.connection_id] = conn
        self.by_flow_id[conn.flow_id].add(conn.connection_id)

    def remove(self, connection_id: UUID) -> FlowConnection | None:
        conn = self.by_connection_id.pop(connection_id, None)
        if conn is None:
            return None
        flow_connections = self.by_flow_id[conn.flow_id]
        flow_connections.discard(connection_id)
        if not flow_connections:
            self.by_flow_id.pop(conn.flow_id, None)
        return conn

    def get_connection(self, connection_id: UUID) -> FlowConnection | None:
        return self.by_connection_id.get(connection_id)

    def connections_for_flow(self, flow_id: UUID) -> list[FlowConnection]:
        return [
            conn
            for connection_id in self.by_flow_id.get(flow_id, set())
            if (conn := self.by_connection_id.get(connection_id)) is not None
        ]

    def iter_connections(self) -> ValuesView[UUID, FlowConnection]:
        return self.by_connection_id.values()

    def iter_connection_items(self) -> ItemsView[UUID, FlowConnection]:
        return self.by_connection_id.items()


class CollaborationConnectionLimitExceededError(RuntimeError):
    """Raised when local collaboration connections exceed the configured heartbeat capacity."""


class CollaborationManager:
    """Local socket rooms and operation fanout for one worker."""

    def __init__(self) -> None:
        self.rooms = FlowRooms()
        self._backplane_event_handlers: dict[BackplaneEventType, BackplaneEventHandler] = {
            "operation.accepted": self._handle_operation_accepted_backplane_event,
            "presence.joined": self._handle_presence_joined_backplane_event,
            "presence.left": self._handle_presence_left_backplane_event,
            "selection.updated": self._handle_selection_updated_backplane_event,
        }
        self._lock = asyncio.Lock()

    async def register(
        self,
        *,
        websocket: WebSocket,
        flow_id: UUID,
        user_id: UUID,
        username: str,
        profile_image: str | None,
        max_connections: PositiveInt,
    ) -> UUID:
        connection_id = uuid.uuid4()
        conn = FlowConnection(
            websocket=websocket,
            connection_id=connection_id,
            flow_id=flow_id,
            user_id=user_id,
            username=username,
            profile_image=profile_image,
        )
        async with self._lock:
            if len(self.rooms.by_connection_id) >= max_connections:
                msg = (
                    "Collaboration websocket connections is at maximum capacity for this server "
                    f"({len(self.rooms.by_connection_id) + 1} > {max_connections})"
                )
                raise CollaborationConnectionLimitExceededError(msg)
            self.rooms.add(conn)
        return connection_id

    async def unregister(self, connection_id: UUID) -> FlowConnection | None:
        async with self._lock:
            return self.rooms.remove(connection_id)

    async def local_connections_snapshot(self) -> list[FlowConnection]:
        async with self._lock:
            connections = list(self.rooms.iter_connections())
        connections.sort(key=lambda conn: conn.connection_id)
        return connections

    @staticmethod
    def heartbeat_buckets(connections: list[FlowConnection], bucket_count: PositiveInt) -> list[list[FlowConnection]]:
        """Split connections into stable timing-wheel buckets for staggered heartbeat pings."""
        if not connections:
            return [[] for _ in range(bucket_count)]

        bucket_size = math.ceil(len(connections) / bucket_count)
        return [connections[i * bucket_size : (i + 1) * bucket_size] for i in range(bucket_count)]

    async def disconnect_expired_heartbeats(self, event_service: CollaborationEventService) -> None:
        expired: list[UUID] = []
        async with self._lock:
            current = time.time()
            for connection_id, conn in self.rooms.iter_connection_items():
                if conn.pong_deadline_at is not None and conn.pong_deadline_at <= current:
                    expired.append(connection_id)
        await self.disconnect_connections(expired, event_service)

    async def send_heartbeat_ping(self, conn: FlowConnection, timeout_seconds: float) -> None:
        async with self._lock:
            stored = self.rooms.get_connection(conn.connection_id)
            if stored is None:
                return
            deadline = time.time() + timeout_seconds
            stored.pong_deadline_at = deadline
        try:
            await conn.websocket.send_json(_HEARTBEAT_PING_MESSAGE)
        except Exception as exc:  # noqa: BLE001
            await logger.adebug("Failed to send collaboration heartbeat ping: %s", exc)

    async def handle_heartbeat_pong(
        self,
        flow_id: UUID,
        connection_id: UUID,
        event_service: CollaborationEventService,
    ) -> None:
        async with self._lock:
            conn = self.rooms.get_connection(connection_id)
            if conn is None:
                return
            if conn.flow_id != flow_id:
                return
            if conn.pong_deadline_at is None or conn.pong_deadline_at < time.time():
                return
            conn.pong_deadline_at = None

        event_service.update_connection(connection_id=connection_id)

    async def disconnect_connection(
        self,
        connection_id: UUID,
        event_service: CollaborationEventService,
    ) -> None:
        await self.disconnect_connections([connection_id], event_service)

    async def disconnect_connections(
        self,
        connection_ids: list[UUID],
        event_service: CollaborationEventService,
    ) -> None:
        if not connection_ids:
            return

        removed_connections: list[FlowConnection] = []
        store_connection_ids: list[UUID] = []
        for connection_id in connection_ids:
            conn = await self.unregister(connection_id)
            if conn is None:
                continue
            removed_connections.append(conn)
            store_connection_ids.append(connection_id)

        for conn in removed_connections:
            if conn.websocket.client_state != WebSocketState.CONNECTED:
                continue
            try:
                await conn.websocket.close(
                    code=status.WS_1000_NORMAL_CLOSURE,
                    reason="Collaboration heartbeat timeout",
                )
            except Exception as exc:  # noqa: BLE001
                await logger.adebug("Failed to close collaboration socket after heartbeat timeout: %s", exc)

        if not store_connection_ids:
            return

        for presence_change in event_service.remove_connections(store_connection_ids):
            await self.emit_presence_change(presence_change.flow_id, presence_change.change, event_service)

    def presence_snapshot_message(self, snapshot: CollaborationPresenceSnapshot) -> dict[str, Any]:
        users = [
            CollaborationPresenceUser(
                user_id=user.user_id,
                username=user.username,
                profile_image=user.profile_image,
                selected=user.selected,
            )
            for user in snapshot.users
        ]
        return CollaborationPresenceSnapshotMessage(users=users).model_dump(mode="json")

    def presence_joined_message(
        self,
        *,
        user_id: UUID,
        username: str,
        profile_image: str | None,
    ) -> dict[str, Any]:
        user = CollaborationPresenceUser(user_id=user_id, username=username, profile_image=profile_image)
        return CollaborationPresenceJoinedMessage(user=user).model_dump(mode="json")

    def presence_left_message(self, user_id: UUID) -> dict[str, Any]:
        return CollaborationPresenceLeftMessage(user_id=user_id).model_dump(mode="json")

    def selection_updated_message(
        self,
        user_id: UUID,
        selected: CollaborationSelectionTarget | None,
    ) -> dict[str, Any]:
        return CollaborationSelectionUpdatedMessage(
            user_id=user_id,
            selected=selected,
        ).model_dump(mode="json")

    async def broadcast_json(
        self,
        flow_id: UUID,
        message: dict[str, Any],
        *,
        exclude_connection_id: UUID | None = None,
    ) -> None:
        async with self._lock:
            connections = self.rooms.connections_for_flow(flow_id)
        for conn in connections:
            if exclude_connection_id and conn.connection_id == exclude_connection_id:
                continue
            try:
                await conn.websocket.send_json(message)
            except Exception as exc:  # noqa: BLE001
                await logger.adebug("Dropping collaboration broadcast to disconnected socket: %s", exc)
                continue

    async def handle_backplane_event(self, event: CollaborationEvent) -> None:
        flow_id = event.flow_id
        try:
            backplane_event = parse_collaboration_backplane_event(event.type, event.payload)
        except (UnsupportedCollaborationBackplaneEventError, ValidationError) as exc:
            await logger.adebug("Ignoring malformed collaboration event %s: %s", event.id, exc)
            return

        handler = self._backplane_event_handlers.get(backplane_event.type)
        if handler is None:
            return
        await handler(flow_id, backplane_event)

    async def emit_presence_change(
        self,
        flow_id: UUID,
        change: CollaborationPresenceChange | None,
        event_service: CollaborationEventService,
        *,
        exclude_connection_id: UUID | None = None,
    ) -> None:
        if change is None:
            return

        if change.joined:
            message = self.presence_joined_message(
                user_id=change.joined.user_id,
                username=change.joined.username,
                profile_image=change.joined.profile_image,
            )
            await self.broadcast_json(
                flow_id,
                message,
                exclude_connection_id=exclude_connection_id,
            )
            event_service.publish(
                flow_id,
                "presence.joined",
                {
                    "worker_id": WORKER_ID,
                    "user": {
                        "user_id": str(change.joined.user_id),
                        "username": change.joined.username,
                        "profile_image": change.joined.profile_image,
                    },
                },
            )

        if change.left_user_id:
            message = self.presence_left_message(change.left_user_id)
            await self.broadcast_json(flow_id, message)
            event_service.publish(
                flow_id,
                "presence.left",
                {
                    "worker_id": WORKER_ID,
                    "user_id": str(change.left_user_id),
                },
            )

        await self.emit_selection_change(
            flow_id,
            change,
            event_service,
            exclude_connection_id=exclude_connection_id,
        )

    async def emit_selection_change(
        self,
        flow_id: UUID,
        change: CollaborationPresenceChange | None,
        event_service: CollaborationEventService,
        *,
        exclude_connection_id: UUID | None = None,
    ) -> None:
        if change is None or change.selection_updated is None:
            return

        selected = change.selection_updated.selected
        message = self.selection_updated_message(change.selection_updated.user_id, selected)
        await self.broadcast_json(
            flow_id,
            message,
            exclude_connection_id=exclude_connection_id,
        )
        payload: dict[str, object] = {
            "worker_id": WORKER_ID,
            "user_id": str(change.selection_updated.user_id),
            "selected": {"kind": selected.kind, "id": selected.id} if selected is not None else None,
        }
        event_service.publish(flow_id, "selection.updated", payload)

    async def _handle_operation_accepted_backplane_event(
        self,
        flow_id: UUID,
        event: CollaborationOperationAcceptedBackplaneEvent,
    ) -> None:
        payload = event.payload
        if payload.worker_id == WORKER_ID:
            return

        broadcast = CollaborationOperationBroadcastMessage(
            flow_id=flow_id,
            revision=payload.revision,
            actor_user_id=payload.actor_user_id,
            actor_delegate=payload.actor_delegate,
            forward_ops=payload.forward_ops,
            created_at=payload.created_at,
        )
        await self.broadcast_json(flow_id, broadcast.model_dump(mode="json"))

    async def _handle_presence_joined_backplane_event(
        self,
        flow_id: UUID,
        event: CollaborationPresenceJoinedBackplaneEvent,
    ) -> None:
        payload = event.payload
        if payload.worker_id == WORKER_ID:
            return

        user = payload.user
        await self.broadcast_json(
            flow_id,
            self.presence_joined_message(
                user_id=user.user_id,
                username=user.username,
                profile_image=user.profile_image,
            ),
        )

    async def _handle_presence_left_backplane_event(
        self,
        flow_id: UUID,
        event: CollaborationPresenceLeftBackplaneEvent,
    ) -> None:
        payload = event.payload
        if payload.worker_id == WORKER_ID:
            return

        await self.broadcast_json(flow_id, self.presence_left_message(payload.user_id))

    async def _handle_selection_updated_backplane_event(
        self,
        flow_id: UUID,
        event: CollaborationSelectionUpdatedBackplaneEvent,
    ) -> None:
        payload = event.payload
        if payload.worker_id == WORKER_ID:
            return

        await self.broadcast_json(
            flow_id,
            self.selection_updated_message(payload.user_id, payload.selected),
        )


_manager: CollaborationManager | None = None
_poll_task: asyncio.Task | None = None
_heartbeat_task: asyncio.Task | None = None
_background_loop_lock = asyncio.Lock()


def get_collaboration_manager() -> CollaborationManager:
    global _manager  # noqa: PLW0603
    if _manager is None:
        _manager = CollaborationManager()
    return _manager


async def start_collaboration_background_tasks() -> None:
    """Start collaboration background loops (event poll + heartbeat) if needed."""
    global _poll_task, _heartbeat_task  # noqa: PLW0603
    async with _background_loop_lock:
        if _poll_task is None or _poll_task.done():
            _poll_task = asyncio.create_task(_poll_collaboration_events())
        if _heartbeat_task is None or _heartbeat_task.done():
            _heartbeat_task = asyncio.create_task(_collaboration_heartbeat_loop())


async def stop_collaboration_background_tasks() -> None:
    global _poll_task, _heartbeat_task  # noqa: PLW0603
    async with _background_loop_lock:
        for task in (_poll_task, _heartbeat_task):
            if task is not None and not task.done():
                task.cancel()
                try:  # noqa: SIM105 - explicit cancellation handling is clearer here.
                    await task
                except asyncio.CancelledError:
                    pass
        _poll_task = None
        _heartbeat_task = None


async def _collaboration_heartbeat_loop() -> None:
    """Run server-initiated heartbeat checks for local collaboration sockets.

    The server owns liveness decisions: each ping sets a pong deadline, valid pongs
    clear that deadline and refresh presence TTL, and expired deadlines remove the
    local connection plus its backplane presence row. Connections are split into
    timing-wheel buckets so pings and the resulting pongs are spread across the
    heartbeat interval instead of spiking all sockets at once.
    """
    manager = get_collaboration_manager()
    event_service = get_collaboration_events_service()
    settings_service = get_settings_service()
    settings = settings_service.settings
    interval = settings.collaboration_heartbeat_interval
    stagger = settings.collaboration_heartbeat_stagger
    timeout = settings.collaboration_heartbeat_timeout
    bucket_count = math.ceil(interval / stagger)

    while True:
        cycle_start = time.monotonic()
        connections = await manager.local_connections_snapshot()
        # Timing-wheel buckets stagger pings and avoid a single large burst of
        # incoming pongs when many clients are connected to the current worker.
        buckets = manager.heartbeat_buckets(connections, bucket_count)

        for bucket in buckets:
            await manager.disconnect_expired_heartbeats(event_service)
            for conn in bucket:
                if conn.pong_deadline_at is None:
                    await manager.send_heartbeat_ping(conn, timeout)
            await asyncio.sleep(stagger)

        elapsed = time.monotonic() - cycle_start
        remaining = interval - elapsed
        if remaining > 0:
            await asyncio.sleep(remaining)


async def _poll_collaboration_events() -> None:
    manager = get_collaboration_manager()
    event_service: CollaborationEventService = get_collaboration_events_service()
    settings_service = get_settings_service()
    cursors: dict[UUID, CollaborationPollCursor] = {}
    next_users_snapshot_at = time.monotonic()

    while True:
        flow_ids = manager.rooms.active_flow_ids()
        if not flow_ids:
            await asyncio.sleep(0.5)
            continue

        now = time.monotonic()
        should_fetch_users = now >= next_users_snapshot_at
        if should_fetch_users:
            snapshot_interval = settings_service.settings.collaboration_presence_snapshot_interval
            next_users_snapshot_at = now + snapshot_interval

            snapshots = event_service.list_users(flow_ids)
            for flow_id, snapshot in snapshots.items():
                await manager.broadcast_json(flow_id, manager.presence_snapshot_message(snapshot))

        # This loop awaits while processing events, so snapshot flow ids to avoid
        # iterating over a live dict view if rooms change mid-iteration.
        for flow_id in tuple(flow_ids):
            cursor = cursors.get(flow_id)
            events, new_cursor = event_service.poll(flow_id, cursor=cursor)
            cursors[flow_id] = new_cursor
            for event in events:
                await manager.handle_backplane_event(event)

        await asyncio.sleep(0.1)
