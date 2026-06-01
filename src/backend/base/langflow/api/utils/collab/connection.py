"""WebSocket protocol runner for collaborative flow editing."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any
from uuid import UUID

from fastapi import status
from lfx.log.logger import logger
from lfx.services.deps import session_scope_readonly
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect, WebSocketState

from langflow.api.utils.collab.access import (
    FlowCollaborationAccessError,
    ensure_operation_write_permission,
    validate_flow_access,
)
from langflow.api.utils.collab.operations import (
    AcceptedFlowOperation,
    FlowOperationApplyError,
    apply_flow_operation_batch,
)
from langflow.api.v1.collaboration_manager import (
    CollaborationManager,
    ensure_collaboration_poll_loop,
    get_collaboration_manager,
)
from langflow.api.v1.schemas.flow_collaboration import (
    CollaborationOperationAcceptedMessage,
    CollaborationOperationBroadcastMessage,
    CollaborationOperationRejectedMessage,
    CollaborationOperationSubmitMessage,
    CollaborationSelectionUpdateMessage,
    CollaborationSessionReadyMessage,
    CollaborationSessionStartMessage,
    CollaborationUnknownMessageError,
)
from langflow.services.collaboration_events.schemas import (
    CollaborationPresenceChange,
)
from langflow.services.database.models.user.model import UserRead
from langflow.services.deps import get_collaboration_events_service, session_scope

if TYPE_CHECKING:
    from starlette.websockets import WebSocket

    from langflow.services.storage.service import StorageService


_PRESENCE_HEARTBEAT_SECONDS = 5.0


class _CollaborationConnectionClosedError(Exception):
    """Raised after this connection has already closed its websocket."""


class FlowCollaborationConnection:
    """Owns one accepted collaboration websocket connection."""

    def __init__(
        self,
        *,
        websocket: WebSocket,
        flow_id: UUID,
        current_user: UserRead,
        starting_revision: int,
        storage_service: StorageService,
        manager: CollaborationManager | None = None,
    ) -> None:
        self.websocket = websocket
        self.flow_id = flow_id
        self.current_user = current_user
        self.starting_revision = starting_revision
        self.storage_service = storage_service
        self.manager = manager or get_collaboration_manager()
        self.connection_id: str | None = None
        self._presence_task: asyncio.Task | None = None
        self._event_service = get_collaboration_events_service()

    async def run(self) -> None:
        try:
            await self._receive_messages()
        except (WebSocketDisconnect, _CollaborationConnectionClosedError):
            pass
        except Exception:  # noqa: BLE001
            await logger.aexception("Collaboration websocket error for flow %s", self.flow_id)
        finally:
            await self._cleanup()

    async def _receive_messages(self) -> None:
        raw = await self.websocket.receive_json()
        msg_type = raw.get("type") if isinstance(raw, dict) else None
        await self._handle_session_start(raw, msg_type)

        while True:
            raw = await self.websocket.receive_json()
            msg_type = raw.get("type") if isinstance(raw, dict) else None

            await self._ensure_active_read_access()

            if msg_type == "operation.submit":
                await self._handle_operation_submit(raw)
                continue

            if msg_type == "selection.update":
                await self._handle_selection_update(raw)
                continue

            await self.websocket.send_json(CollaborationUnknownMessageError().model_dump(mode="json"))

    async def _handle_session_start(self, raw: Any, msg_type: str | None) -> None:
        if msg_type != "session.start":
            await self.websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="First message must be session.start",
            )
            raise _CollaborationConnectionClosedError

        try:
            CollaborationSessionStartMessage.model_validate(raw)
        except ValidationError as exc:
            await self.websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Invalid session.start payload",
            )
            raise _CollaborationConnectionClosedError from exc

        self.connection_id = await self.manager.register(
            websocket=self.websocket,
            flow_id=self.flow_id,
            user_id=self.current_user.id,
            username=self.current_user.username,
            profile_image=self.current_user.profile_image,
        )
        await ensure_collaboration_poll_loop()
        self._presence_task = asyncio.create_task(self._presence_heartbeat())

        presence_change = self._event_service.add_connection(
            flow_id=self.flow_id,
            user_id=self.current_user.id,
            connection_id=self.connection_id,
            username=self.current_user.username,
            profile_image=self.current_user.profile_image,
        )
        snapshot = self._event_service.list_users([self.flow_id])[self.flow_id]

        await self.websocket.send_json(
            CollaborationSessionReadyMessage(
                connection_id=self.connection_id,
                flow_id=self.flow_id,
                current_revision=self.starting_revision,
            ).model_dump(mode="json")
        )
        await self.websocket.send_json(self.manager.presence_snapshot_message(snapshot))

        await self._emit_presence_change(presence_change, exclude_connection_id=self.connection_id)

    async def _handle_operation_submit(self, raw: Any) -> None:
        try:
            submit = CollaborationOperationSubmitMessage.model_validate(raw)
        except ValidationError as exc:
            await self._send_operation_rejected(
                request_id=raw.get("request_id") if isinstance(raw, dict) else None,
                status_code=400,
                detail=str(exc),
            )
            return

        try:
            accepted = await self._apply_operation(submit)
        except FlowOperationApplyError as exc:
            await self._send_operation_rejected(
                request_id=submit.request_id,
                status_code=exc.status_code,
                detail=exc.detail,
                current_revision=exc.current_revision,
            )
            return

        await self._send_operation_accepted(submit.request_id, accepted)
        await self._broadcast_operation(accepted)
        self._publish_operation_accepted(accepted)

    async def _apply_operation(
        self,
        submit: CollaborationOperationSubmitMessage,
    ) -> AcceptedFlowOperation:
        async with session_scope() as operation_session:
            await ensure_operation_write_permission(
                operation_session,
                self.flow_id,
                self.current_user,
            )

            return await apply_flow_operation_batch(
                operation_session,
                flow_id=self.flow_id,
                actor_user_id=self.current_user.id,
                base_revision=submit.base_revision,
                operations=submit.operations,
                storage_service=self.storage_service,
            )

    async def _ensure_active_read_access(self) -> None:
        try:
            async with session_scope_readonly() as session:
                await validate_flow_access(
                    session,
                    self.flow_id,
                    self.current_user,
                )
        except FlowCollaborationAccessError as exc:
            await self.websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=exc.detail)
            raise _CollaborationConnectionClosedError from exc

    async def _send_operation_accepted(
        self,
        request_id: str,
        accepted: AcceptedFlowOperation,
    ) -> None:
        accepted_msg = CollaborationOperationAcceptedMessage(
            request_id=request_id,
            flow_id=accepted.flow_id,
            revision=accepted.revision,
            actor_user_id=accepted.actor_user_id,
            actor_delegate=accepted.actor_delegate,
            forward_ops=accepted.forward_ops,
            created_at=accepted.created_at,
        )
        await self.websocket.send_json(accepted_msg.model_dump(mode="json"))

    async def _send_operation_rejected(
        self,
        *,
        request_id: str | None,
        status_code: int,
        detail: str,
        current_revision: int | None = None,
    ) -> None:
        await self.websocket.send_json(
            CollaborationOperationRejectedMessage(
                request_id=request_id,
                status=status_code,
                detail=detail,
                current_revision=current_revision,
            ).model_dump(mode="json")
        )

    async def _broadcast_operation(self, accepted: AcceptedFlowOperation) -> None:
        self.manager.mark_operation_fanned(self.flow_id, accepted.revision)
        broadcast = CollaborationOperationBroadcastMessage(
            flow_id=accepted.flow_id,
            revision=accepted.revision,
            actor_user_id=accepted.actor_user_id,
            actor_delegate=accepted.actor_delegate,
            forward_ops=accepted.forward_ops,
            created_at=accepted.created_at,
        )
        await self.manager.broadcast_json(
            self.flow_id,
            broadcast.model_dump(mode="json"),
            exclude_connection_id=self.connection_id,
        )

    def _publish_operation_accepted(self, accepted: AcceptedFlowOperation) -> None:
        event_payload = {
            "revision": accepted.revision,
            "actor_user_id": str(accepted.actor_user_id),
            "actor_delegate": accepted.actor_delegate.value,
            "forward_ops": accepted.forward_ops,
            "created_at": accepted.created_at.isoformat(),
            "origin_connection_id": self.connection_id,
        }
        self._event_service.publish(self.flow_id, "operation.accepted", event_payload)

    async def _handle_selection_update(self, raw: Any) -> None:
        try:
            update = CollaborationSelectionUpdateMessage.model_validate(raw)
        except ValidationError as exc:
            await self.websocket.send_json(
                CollaborationUnknownMessageError(
                    detail=f"Invalid selection.update payload: {exc}",
                ).model_dump(mode="json")
            )
            return

        if self.connection_id is None:
            return

        change = self._event_service.update_connection(
            flow_id=self.flow_id,
            connection_id=self.connection_id,
            selected=update.selected,
        )
        await self._emit_selection_change(change, exclude_connection_id=self.connection_id)

    async def _presence_heartbeat(self) -> None:
        while True:
            await asyncio.sleep(_PRESENCE_HEARTBEAT_SECONDS)
            if self.connection_id is None:
                continue
            if self.websocket.client_state != WebSocketState.CONNECTED:
                return
            try:
                await self._ensure_active_read_access()
            except _CollaborationConnectionClosedError:
                return
            self._event_service.update_connection(
                flow_id=self.flow_id,
                connection_id=self.connection_id,
            )

    async def _cleanup(self) -> None:
        if self._presence_task is not None:
            self._presence_task.cancel()
            try:  # noqa: SIM105 - explicit cancellation handling is clearer here.
                await self._presence_task
            except asyncio.CancelledError:
                pass

        if self.connection_id is not None:
            await self.manager.unregister(self.flow_id, self.connection_id)
            change = self._event_service.remove_connection(
                flow_id=self.flow_id,
                connection_id=self.connection_id,
            )
            await self._emit_presence_change(change)

    async def _emit_presence_change(
        self,
        change: CollaborationPresenceChange | None,
        *,
        exclude_connection_id: str | None = None,
    ) -> None:
        await self.manager.emit_presence_change(
            self.flow_id,
            change,
            self._event_service,
            exclude_connection_id=exclude_connection_id,
        )

    async def _emit_selection_change(
        self,
        change: CollaborationPresenceChange | None,
        *,
        exclude_connection_id: str | None = None,
    ) -> None:
        await self.manager.emit_selection_change(
            self.flow_id,
            change,
            self._event_service,
            exclude_connection_id=exclude_connection_id,
        )
