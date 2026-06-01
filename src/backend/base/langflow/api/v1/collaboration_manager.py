"""In-process WebSocket room state for collaborative flow editing."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID

from lfx.log.logger import logger
from pydantic import ValidationError

from langflow.api.v1.schemas.flow_collaboration import (
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
    CollaborationPresenceChange,
    CollaborationPresenceSnapshot,
    CollaborationSelectionTarget,
)

if TYPE_CHECKING:
    from starlette.websockets import WebSocket

    from langflow.services.collaboration_events.schemas import CollaborationEvent

BackplaneEventHandler = Callable[[UUID, Any], Awaitable[None]]
BackplaneEventType = Literal["operation.accepted", "presence.joined", "presence.left", "selection.updated"]

WORKER_ID = str(uuid.uuid4())
FANNED_REVISION_TTL_SECONDS = 120.0
PRESENCE_RECONCILE_INTERVAL_SECONDS = 30.0


@dataclass
class FlowConnection:
    websocket: WebSocket
    connection_id: str
    flow_id: UUID
    user_id: UUID
    username: str
    profile_image: str | None


class CollaborationManager:
    """Local socket rooms and operation fanout for one worker."""

    def __init__(self) -> None:
        self._rooms: defaultdict[UUID, dict[str, FlowConnection]] = defaultdict(dict)
        self._fanned_revisions: dict[tuple[UUID, int], float] = {}
        self._backplane_event_handlers: dict[BackplaneEventType, BackplaneEventHandler] = {
            "operation.accepted": self._handle_operation_accepted_backplane_event,
            "presence.joined": self._handle_presence_joined_backplane_event,
            "presence.left": self._handle_presence_left_backplane_event,
            "selection.updated": self._handle_selection_updated_backplane_event,
        }
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

    async def unregister(self, flow_id: UUID, connection_id: str) -> FlowConnection | None:
        async with self._lock:
            room = self._rooms.get(flow_id)
            if not room:
                return None
            conn = room.pop(connection_id, None)
            if not room:
                self._rooms.pop(flow_id, None)
            return conn

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
        exclude_connection_id: str | None = None,
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
                {"worker_id": WORKER_ID, "user_id": str(change.left_user_id)},
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
        exclude_connection_id: str | None = None,
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
    event_service: CollaborationEventService = get_collaboration_events_service()
    cursors: dict[UUID, CollaborationPollCursor] = {}
    next_presence_reconcile_at = time.monotonic()

    while True:
        flow_ids = manager.active_flow_ids()
        if not flow_ids:
            await asyncio.sleep(0.5)
            continue

        now = time.monotonic()
        should_reconcile_presence = now >= next_presence_reconcile_at
        if should_reconcile_presence:
            next_presence_reconcile_at = now + PRESENCE_RECONCILE_INTERVAL_SECONDS

            snapshots = event_service.list_users(list(flow_ids))
            for flow_id, snapshot in snapshots.items():
                await manager.broadcast_json(flow_id, manager.presence_snapshot_message(snapshot))

        for flow_id in flow_ids:
            cursor = cursors.get(flow_id)
            events, new_cursor = event_service.poll(flow_id, cursor=cursor)
            cursors[flow_id] = new_cursor
            for event in events:
                await manager.handle_backplane_event(event)

        await asyncio.sleep(0.1)
