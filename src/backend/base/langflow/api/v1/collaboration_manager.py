"""In-process WebSocket room state for collaborative flow editing."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, overload
from uuid import UUID

from lfx.log.logger import logger
from pydantic import ValidationError

from langflow.api.v1.schemas.flow_collaboration import (
    CollaborationOperationAcceptedBackplaneEvent,
    CollaborationOperationBroadcastMessage,
    CollaborationPresenceEventPayload,
    CollaborationPresenceUpdatedBackplaneEvent,
    CollaborationPresenceUser,
    UnsupportedCollaborationBackplaneEventError,
    parse_collaboration_backplane_event,
)

if TYPE_CHECKING:
    from starlette.websockets import WebSocket

    from langflow.services.collaboration_events.schemas import CollaborationEvent

WORKER_ID = str(uuid.uuid4())
PRESENCE_ROSTER_TTL_SECONDS = 30.0
FANNED_REVISION_TTL_SECONDS = 120.0


@dataclass
class FlowConnection:
    websocket: WebSocket
    connection_id: str
    flow_id: UUID
    user_id: UUID
    username: str
    profile_image: str | None


@dataclass
class _RemotePresenceRoster:
    users: list[CollaborationPresenceUser]
    published_at: float


class CollaborationManager:
    """Local socket rooms, presence, and operation fanout for one worker."""

    def __init__(self) -> None:
        self._rooms: defaultdict[UUID, dict[str, FlowConnection]] = defaultdict(dict)
        self._remote_rosters: defaultdict[UUID, dict[str, _RemotePresenceRoster]] = defaultdict(dict)
        self._fanned_revisions: dict[tuple[UUID, int], float] = {}
        # Protect local room membership while registering/unregistering and snapshotting broadcasts.
        self._lock = asyncio.Lock()

    def active_flow_ids(self) -> set[UUID]:
        return set(self._rooms.keys())

    def mark_operation_fanned(self, flow_id: UUID, revision: int) -> None:
        self._fanned_revisions[(flow_id, revision)] = time.time()
        self._prune_fanned_revisions()

    def should_fanout_backplane_operation(self, flow_id: UUID, revision: int) -> bool:
        self._prune_fanned_revisions()
        return (flow_id, revision) not in self._fanned_revisions

    async def register(
        self,
        *,
        websocket: WebSocket,
        flow_id: UUID,
        user_id: UUID,
        username: str,
        profile_image: str | None,
    ) -> str:
        connection_id = str(uuid.uuid4())
        conn = FlowConnection(
            websocket=websocket,
            connection_id=connection_id,
            flow_id=flow_id,
            user_id=user_id,
            username=username,
            profile_image=profile_image,
        )
        async with self._lock:
            self._rooms[flow_id][connection_id] = conn
        return connection_id

    async def unregister(self, flow_id: UUID, connection_id: str) -> None:
        async with self._lock:
            room = self._rooms.get(flow_id)
            if not room:
                return
            room.pop(connection_id, None)
            if not room:
                self._rooms.pop(flow_id, None)
                self._remote_rosters.pop(flow_id, None)

    @overload
    def local_users(self, flow_id: UUID, *, serialize: Literal[False] = False) -> list[CollaborationPresenceUser]: ...

    @overload
    def local_users(self, flow_id: UUID, *, serialize: Literal[True]) -> list[dict[str, Any]]: ...

    def local_users(
        self,
        flow_id: UUID,
        *,
        serialize: bool = False,
    ) -> list[CollaborationPresenceUser] | list[dict[str, Any]]:
        """Return unique local users, optionally as JSON-ready payloads."""
        room = self._rooms.get(flow_id, {})
        if serialize:
            seen: dict[str, dict[str, Any]] = {}
            for conn in room.values():
                key = str(conn.user_id)
                if key not in seen:
                    seen[key] = {
                        "user_id": key,
                        "username": conn.username,
                        "profile_image": conn.profile_image,
                    }
            return list(seen.values())

        seen: dict[str, CollaborationPresenceUser] = {}
        for conn in room.values():
            key = str(conn.user_id)
            if key not in seen:
                seen[key] = CollaborationPresenceUser(
                    user_id=key,
                    username=conn.username,
                    profile_image=conn.profile_image,
                )
        return list(seen.values())

    @overload
    def all_users(self, flow_id: UUID, *, serialize: Literal[False] = False) -> list[CollaborationPresenceUser]: ...

    @overload
    def all_users(self, flow_id: UUID, *, serialize: Literal[True]) -> list[dict[str, Any]]: ...

    def all_users(
        self,
        flow_id: UUID,
        *,
        serialize: bool = False,
    ) -> list[CollaborationPresenceUser] | list[dict[str, Any]]:
        """Return unique local and remote users, optionally as JSON-ready payloads."""
        now = time.time()
        if serialize:
            seen: dict[str, dict[str, Any]] = {}
            for user in self.local_users(flow_id, serialize=True):
                seen[user["user_id"]] = user
            for roster in self._remote_rosters.get(flow_id, {}).values():
                if now - roster.published_at > PRESENCE_ROSTER_TTL_SECONDS:
                    continue
                for user in roster.users:
                    seen[user.user_id] = user.model_dump(mode="json")
            return list(seen.values())

        seen: dict[str, CollaborationPresenceUser] = {}
        for user in self.local_users(flow_id):
            seen[user.user_id] = user
        for roster in self._remote_rosters.get(flow_id, {}).values():
            if now - roster.published_at > PRESENCE_ROSTER_TTL_SECONDS:
                continue
            for user in roster.users:
                seen[user.user_id] = user
        return list(seen.values())

    def presence_payload(self, flow_id: UUID) -> dict[str, Any]:
        return {
            "worker_id": WORKER_ID,
            "published_at": time.time(),
            "users": self.local_users(flow_id, serialize=True),
        }

    def presence_message(self, flow_id: UUID) -> dict[str, Any]:
        return {
            "type": "presence.updated",
            "users": self.all_users(flow_id, serialize=True),
        }

    def apply_remote_presence(self, flow_id: UUID, presence: CollaborationPresenceEventPayload) -> None:
        self._remote_rosters[flow_id][presence.worker_id] = _RemotePresenceRoster(
            users=presence.users,
            published_at=presence.published_at,
        )

    async def send_json(self, flow_id: UUID, connection_id: str, message: dict[str, Any]) -> None:
        async with self._lock:
            conn = self._rooms.get(flow_id, {}).get(connection_id)
        if conn is None:
            return
        await conn.websocket.send_json(message)

    async def broadcast_json(
        self,
        flow_id: UUID,
        message: dict[str, Any],
        *,
        exclude_connection_id: str | None = None,
    ) -> None:
        async with self._lock:
            connections = list(self._rooms.get(flow_id, {}).values())
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

        if isinstance(backplane_event, CollaborationOperationAcceptedBackplaneEvent):
            payload = backplane_event.payload
            if not self.should_fanout_backplane_operation(flow_id, payload.revision):
                return
            broadcast = CollaborationOperationBroadcastMessage(
                flow_id=flow_id,
                revision=payload.revision,
                actor_user_id=payload.actor_user_id,
                actor_delegate=payload.actor_delegate,
                forward_ops=payload.forward_ops,
                created_at=payload.created_at,
            )
            await self.broadcast_json(
                flow_id,
                broadcast.model_dump(mode="json"),
            )
            return

        if isinstance(backplane_event, CollaborationPresenceUpdatedBackplaneEvent):
            payload = backplane_event.payload
            if payload.worker_id == WORKER_ID:
                return

            self.apply_remote_presence(flow_id, payload)
            await self.broadcast_json(flow_id, self.presence_message(flow_id))

    def _prune_fanned_revisions(self) -> None:
        now = time.time()
        stale = [key for key, ts in self._fanned_revisions.items() if now - ts > FANNED_REVISION_TTL_SECONDS]
        for key in stale:
            self._fanned_revisions.pop(key, None)


_manager: CollaborationManager | None = None
_poll_task: asyncio.Task | None = None
_poll_task_lock = asyncio.Lock()


def get_collaboration_manager() -> CollaborationManager:
    global _manager  # noqa: PLW0603
    if _manager is None:
        _manager = CollaborationManager()
    return _manager


async def ensure_collaboration_poll_loop() -> None:
    """Start the cross-worker collaboration event poll loop if needed."""
    global _poll_task  # noqa: PLW0603
    async with _poll_task_lock:
        if _poll_task is not None and not _poll_task.done():
            return
        _poll_task = asyncio.create_task(_poll_collaboration_events())


async def stop_collaboration_poll_loop() -> None:
    global _poll_task  # noqa: PLW0603
    async with _poll_task_lock:
        if _poll_task is not None and not _poll_task.done():
            _poll_task.cancel()
            try:  # noqa: SIM105 - explicit cancellation handling is clearer here.
                await _poll_task
            except asyncio.CancelledError:
                pass
        _poll_task = None


async def _poll_collaboration_events() -> None:
    from langflow.services.collaboration_events.schemas import CollaborationPollCursor
    from langflow.services.deps import get_collaboration_events_service

    manager = get_collaboration_manager()
    event_service = get_collaboration_events_service()
    cursors: dict[UUID, CollaborationPollCursor] = {}

    while True:
        flow_ids = manager.active_flow_ids()
        if not flow_ids:
            await asyncio.sleep(0.5)
            continue

        for flow_id in flow_ids:
            cursor = cursors.get(flow_id)
            events, new_cursor = event_service.poll(flow_id, cursor=cursor)
            cursors[flow_id] = new_cursor
            for event in events:
                await manager.handle_backplane_event(event)

        await asyncio.sleep(0.1)
