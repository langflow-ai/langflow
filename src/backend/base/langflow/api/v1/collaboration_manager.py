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
    CollaborationPresenceJoinedMessage,
    CollaborationPresenceLeftMessage,
    CollaborationPresenceRosterBackplaneEvent,
    CollaborationPresenceSnapshotMessage,
    CollaborationPresenceUser,
    CollaborationSelectionSnapshotMessage,
    CollaborationSelectionTarget,
    CollaborationSelectionUpdatedMessage,
    CollaborationUserSelection,
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
        self._selections: defaultdict[UUID, dict[UUID, CollaborationSelectionTarget | None]] = defaultdict(dict)
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

    async def unregister(self, flow_id: UUID, connection_id: str) -> FlowConnection | None:
        async with self._lock:
            room = self._rooms.get(flow_id)
            if not room:
                return None
            conn = room.pop(connection_id, None)
            if not room:
                self._rooms.pop(flow_id, None)
                self._remote_rosters.pop(flow_id, None)
                self._selections.pop(flow_id, None)
            return conn

    @overload
    def local_users(
        self,
        flow_id: UUID,
        *,
        serialize: Literal[False] = False,
        as_dict: Literal[False] = False,
    ) -> list[CollaborationPresenceUser]: ...

    @overload
    def local_users(
        self,
        flow_id: UUID,
        *,
        serialize: Literal[False] = False,
        as_dict: Literal[True] = True,
    ) -> dict[UUID, CollaborationPresenceUser]: ...

    @overload
    def local_users(
        self,
        flow_id: UUID,
        *,
        serialize: Literal[True],
        as_dict: Literal[False] = False,
    ) -> list[dict[str, Any]]: ...

    @overload
    def local_users(
        self,
        flow_id: UUID,
        *,
        serialize: Literal[True],
        as_dict: Literal[True] = True,
    ) -> dict[str, dict[str, Any]]: ...

    def local_users(
        self,
        flow_id: UUID,
        *,
        serialize: bool = False,
        as_dict: bool = False,
    ) -> (
        list[CollaborationPresenceUser]
        | list[dict[str, Any]]
        | dict[UUID, CollaborationPresenceUser]
        | dict[str, dict[str, Any]]
    ):
        """Return unique local users, optionally as a keyed map or JSON-ready payloads."""
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
            return seen if as_dict else list(seen.values())

        seen: dict[UUID, CollaborationPresenceUser] = {}
        for conn in room.values():
            key = conn.user_id
            if key not in seen:
                seen[key] = CollaborationPresenceUser(
                    user_id=conn.user_id,
                    username=conn.username,
                    profile_image=conn.profile_image,
                )
        return seen if as_dict else list(seen.values())

    @overload
    def all_users(
        self,
        flow_id: UUID,
        *,
        serialize: Literal[False] = False,
        as_dict: Literal[False] = False,
    ) -> list[CollaborationPresenceUser]: ...

    @overload
    def all_users(
        self,
        flow_id: UUID,
        *,
        serialize: Literal[False] = False,
        as_dict: Literal[True] = True,
    ) -> dict[UUID, CollaborationPresenceUser]: ...

    @overload
    def all_users(
        self,
        flow_id: UUID,
        *,
        serialize: Literal[True],
        as_dict: Literal[False] = False,
    ) -> list[dict[str, Any]]: ...

    @overload
    def all_users(
        self,
        flow_id: UUID,
        *,
        serialize: Literal[True],
        as_dict: Literal[True] = True,
    ) -> dict[str, dict[str, Any]]: ...

    def all_users(
        self,
        flow_id: UUID,
        *,
        serialize: bool = False,
        as_dict: bool = False,
    ) -> (
        list[CollaborationPresenceUser]
        | list[dict[str, Any]]
        | dict[UUID, CollaborationPresenceUser]
        | dict[str, dict[str, Any]]
    ):
        """Return unique local and remote users, optionally as a keyed map or JSON-ready payloads."""
        now = time.time()
        if serialize:
            seen = self.local_users(flow_id, serialize=True, as_dict=True)
            for roster in self._remote_rosters.get(flow_id, {}).values():
                if now - roster.published_at > PRESENCE_ROSTER_TTL_SECONDS:
                    continue
                for user in roster.users:
                    seen[str(user.user_id)] = user.model_dump(mode="json")
            return seen if as_dict else list(seen.values())

        seen = self.local_users(flow_id, as_dict=True)
        for roster in self._remote_rosters.get(flow_id, {}).values():
            if now - roster.published_at > PRESENCE_ROSTER_TTL_SECONDS:
                continue
            for user in roster.users:
                seen[user.user_id] = user
        return seen if as_dict else list(seen.values())

    def presence_payload(self, flow_id: UUID) -> dict[str, Any]:
        return {
            "worker_id": WORKER_ID,
            "published_at": time.time(),
            "users": self.local_users(flow_id, serialize=True),
        }

    def presence_snapshot_message(self, flow_id: UUID) -> dict[str, Any]:
        return CollaborationPresenceSnapshotMessage(users=self.all_users(flow_id)).model_dump(mode="json")

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

    def selection_snapshot_message(self, flow_id: UUID) -> dict[str, Any]:
        selections = [
            CollaborationUserSelection(user_id=user_id, selected=selected)
            for user_id, selected in self._selections.get(flow_id, {}).items()
        ]
        return CollaborationSelectionSnapshotMessage(selections=selections).model_dump(mode="json")

    def selection_updated_message(
        self,
        user_id: UUID,
        selected: CollaborationSelectionTarget | None,
    ) -> dict[str, Any]:
        return CollaborationSelectionUpdatedMessage(
            user_id=user_id,
            selected=selected,
        ).model_dump(mode="json")

    def set_user_selection(
        self,
        flow_id: UUID,
        user_id: UUID,
        selected: CollaborationSelectionTarget | None,
    ) -> dict[str, Any]:
        flow_selections = self._selections[flow_id]
        if selected is None:
            flow_selections.pop(user_id, None)
        else:
            flow_selections[user_id] = selected
        return self.selection_updated_message(user_id, selected)

    def clear_user_selection(self, flow_id: UUID, user_id: UUID) -> dict[str, Any] | None:
        flow_selections = self._selections.get(flow_id)
        if not flow_selections or user_id not in flow_selections:
            return None
        flow_selections.pop(user_id, None)
        return self.selection_updated_message(user_id, None)

    def presence_visibility_diff(
        self,
        before: dict[UUID, CollaborationPresenceUser],
        after: dict[UUID, CollaborationPresenceUser],
    ) -> tuple[list[CollaborationPresenceUser], list[UUID]]:
        joined_ids = after.keys() - before.keys()
        left_ids = before.keys() - after.keys()
        joined_users = [after[user_id] for user_id in sorted(joined_ids, key=str)]
        return joined_users, sorted(left_ids, key=str)

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

        if isinstance(backplane_event, CollaborationPresenceRosterBackplaneEvent):
            payload = backplane_event.payload
            if payload.worker_id == WORKER_ID:
                return

            before = self.all_users(flow_id, as_dict=True)
            self.apply_remote_presence(flow_id, payload)
            after = self.all_users(flow_id, as_dict=True)
            joined_users, left_user_ids = self.presence_visibility_diff(before, after)
            for user in joined_users:
                await self.broadcast_json(
                    flow_id,
                    self.presence_joined_message(
                        user_id=user.user_id,
                        username=user.username,
                        profile_image=user.profile_image,
                    ),
                )
            for user_id in left_user_ids:
                await self.broadcast_json(flow_id, self.presence_left_message(user_id))

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
