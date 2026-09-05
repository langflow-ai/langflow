"""Owner-scoped API for triggers and their event ledger.

Triggers have no resource word of their own: they ride the flow they fire, so
every route authorizes with ``ensure_flow_permission``. Reads need flow read,
management needs flow write, and replay/test need flow execute — the same
ceiling as running the flow by hand, which is what a trigger ultimately does.

Existence privacy follows the connections precedent: a trigger the caller cannot
read at all is a 404, while a caller who can read the flow but not write it gets
an honest 403.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from langflow.api.utils import CurrentActiveUser, DbSession, DbSessionReadOnly
from langflow.api.v1.flows_helpers import _read_flow
from langflow.services.authorization import FlowAction, ensure_flow_permission
from langflow.services.authorization.fetch import deny_to_404
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.trigger.model import Trigger
from langflow.services.database.models.trigger.schemas import (
    TriggerBindingTarget,
    TriggerCreate,
    TriggerEventRead,
    TriggerPinRequest,
    TriggerRead,
    TriggerReplayRequest,
    TriggerState,
    TriggerTestRequest,
    TriggerUpdate,
)
from langflow.services.deps import get_settings_service, get_trigger_service
from langflow.services.triggers import ledger
from langflow.services.triggers.constants import TEST_DEDUPE_PREFIX
from langflow.services.triggers.errors import (
    ReplayWindowExpiredError,
    TriggerEventNotFoundError,
    TriggerNotFoundError,
)
from langflow.services.triggers.service import TriggerService

router = APIRouter(prefix="/triggers", tags=["Triggers"])

_MAX_PAGE_SIZE = 200


def _service() -> TriggerService:
    return get_trigger_service()


TriggerServiceDep = Annotated[TriggerService, Depends(_service)]


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trigger not found")


async def _authorized_flow(session, user: CurrentActiveUser, flow_id: UUID, action: FlowAction) -> Flow:
    """Load the flow a trigger rides and enforce ``action`` on it.

    ``_read_flow`` is the share-aware fetch the flow routes themselves use, so a
    trigger is visible exactly when its flow is: owned, shared, or reachable
    through a role. A caller who cannot even read the flow gets 404 (a 403 on a
    resource you cannot see is an existence oracle); a caller who can read it but
    not perform ``action`` gets an honest 403.
    """
    flow = await _read_flow(session, flow_id, user.id)
    if flow is None:
        raise _not_found()
    try:
        await ensure_flow_permission(
            user,
            action,
            flow_id=flow.id,
            flow_user_id=flow.user_id,
            workspace_id=flow.workspace_id,
            folder_id=flow.folder_id,
        )
    except HTTPException as exc:
        if action is FlowAction.READ or exc.status_code != status.HTTP_403_FORBIDDEN:
            raise deny_to_404(exc, detail="Trigger not found") from exc
        try:
            await ensure_flow_permission(
                user,
                FlowAction.READ,
                flow_id=flow.id,
                flow_user_id=flow.user_id,
                workspace_id=flow.workspace_id,
                folder_id=flow.folder_id,
            )
        except HTTPException as read_exc:
            raise deny_to_404(read_exc, detail="Trigger not found") from read_exc
        raise
    return flow


async def _authorized_trigger(
    *,
    service: TriggerService,
    session,
    user: CurrentActiveUser,
    trigger_id: UUID,
    action: FlowAction,
) -> Trigger:
    try:
        row = await service.get(session, trigger_id)
    except TriggerNotFoundError as exc:
        raise _not_found() from exc
    await _authorized_flow(session, user, row.flow_id, action)
    return row


@router.get("", response_model=list[TriggerRead])
async def list_triggers(
    session: DbSessionReadOnly,
    current_user: CurrentActiveUser,
    service: TriggerServiceDep,
    flow_id: Annotated[UUID, Query(description="Flow whose triggers to list")],
    limit: Annotated[int, Query(ge=1, le=_MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[TriggerRead]:
    """List the triggers on one flow.

    ``flow_id`` is required rather than optional: an unscoped list would have to
    fan out over every flow the caller can read, and the answer a client wants is
    always "the triggers on this flow".
    """
    await _authorized_flow(session, current_user, flow_id, FlowAction.READ)
    rows = await service.list_for_flows(session, flow_ids=[flow_id], limit=limit, offset=offset)
    return [TriggerRead.model_validate(row) for row in rows]


@router.post("", response_model=TriggerRead, status_code=status.HTTP_201_CREATED)
async def create_trigger(
    payload: TriggerCreate,
    session: DbSession,
    current_user: CurrentActiveUser,
    service: TriggerServiceDep,
) -> TriggerRead:
    """Create a trigger on a flow the caller may write.

    The trigger is owned by the *flow owner*, not by whoever created it. The
    execution-principal matrix classifies a trigger run as ``flow_owner``, and
    flow-save reconciliation already creates rows that way; keying the API path
    off the caller instead would give one flow two kinds of trigger identity
    depending on which surface armed it, and would let a collaborator with flow
    write silently schedule unattended runs under their own connections.
    """
    flow = await _authorized_flow(session, current_user, payload.flow_id, FlowAction.WRITE)
    _reject_unsupported_binding(payload.binding_target, payload.deployment_id)
    row = await service.create(session, payload=payload, owner_id=flow.user_id)
    return TriggerRead.model_validate(row)


def _reject_unsupported_binding(target: TriggerBindingTarget, deployment_id: UUID | None) -> None:
    """A deployment binding must name a deployment; it is stored, never dispatched.

    Creating it is allowed so the binding survives until the adapter path is
    decided, but the caller is told at dispatch time (typed error) rather than
    discovering a silent flow run.
    """
    if target is TriggerBindingTarget.DEPLOYMENT and deployment_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A deployment binding requires deployment_id.",
        )


@router.get("/{trigger_id}", response_model=TriggerRead)
async def get_trigger(
    trigger_id: UUID,
    session: DbSessionReadOnly,
    current_user: CurrentActiveUser,
    service: TriggerServiceDep,
) -> TriggerRead:
    row = await _authorized_trigger(
        service=service, session=session, user=current_user, trigger_id=trigger_id, action=FlowAction.READ
    )
    return TriggerRead.model_validate(row)


@router.patch("/{trigger_id}", response_model=TriggerRead)
async def update_trigger(
    trigger_id: UUID,
    payload: TriggerUpdate,
    session: DbSession,
    current_user: CurrentActiveUser,
    service: TriggerServiceDep,
) -> TriggerRead:
    row = await _authorized_trigger(
        service=service, session=session, user=current_user, trigger_id=trigger_id, action=FlowAction.WRITE
    )
    updated = await service.update(session, row=row, payload=payload)
    _reject_unsupported_binding(TriggerBindingTarget(updated.binding_target), updated.deployment_id)
    return TriggerRead.model_validate(updated)


@router.delete("/{trigger_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trigger(
    trigger_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
    service: TriggerServiceDep,
) -> Response:
    row = await _authorized_trigger(
        service=service, session=session, user=current_user, trigger_id=trigger_id, action=FlowAction.WRITE
    )
    await service.delete(session, row=row)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{trigger_id}/enable", response_model=TriggerRead)
async def enable_trigger(
    trigger_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
    service: TriggerServiceDep,
) -> TriggerRead:
    row = await _authorized_trigger(
        service=service, session=session, user=current_user, trigger_id=trigger_id, action=FlowAction.WRITE
    )
    try:
        updated = await service.enable(session, row=row)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return TriggerRead.model_validate(updated)


@router.post("/{trigger_id}/disable", response_model=TriggerRead)
async def disable_trigger(
    trigger_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
    service: TriggerServiceDep,
) -> TriggerRead:
    row = await _authorized_trigger(
        service=service, session=session, user=current_user, trigger_id=trigger_id, action=FlowAction.WRITE
    )
    updated = await service.disable(session, row=row)
    return TriggerRead.model_validate(updated)


@router.post("/{trigger_id}/pin", response_model=TriggerRead)
async def pin_trigger(
    trigger_id: UUID,
    payload: TriggerPinRequest,
    session: DbSession,
    current_user: CurrentActiveUser,
    service: TriggerServiceDep,
) -> TriggerRead:
    """Pin the trigger to a flow version, or unpin it with a null id.

    A pin is only accepted for a version of the trigger's own flow: pinning
    across flows would let a writer on flow A run flow B's data as A's owner.
    """
    row = await _authorized_trigger(
        service=service, session=session, user=current_user, trigger_id=trigger_id, action=FlowAction.WRITE
    )
    if payload.flow_version_id is not None:
        from langflow.services.database.models.flow_version.model import FlowVersion

        version = await session.get(FlowVersion, payload.flow_version_id)
        if version is None or version.flow_id != row.flow_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Flow version not found for this trigger's flow.",
            )
    updated = await service.pin(session, row=row, flow_version_id=payload.flow_version_id)
    return TriggerRead.model_validate(updated)


@router.get("/{trigger_id}/events", response_model=list[TriggerEventRead])
async def list_trigger_events(
    trigger_id: UUID,
    session: DbSessionReadOnly,
    current_user: CurrentActiveUser,
    service: TriggerServiceDep,
    limit: Annotated[int, Query(ge=1, le=_MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[TriggerEventRead]:
    await _authorized_trigger(
        service=service, session=session, user=current_user, trigger_id=trigger_id, action=FlowAction.READ
    )
    rows = await ledger.list_events(session, trigger_id=trigger_id, limit=limit, offset=offset)
    return [TriggerEventRead.model_validate(row) for row in rows]


@router.post("/{trigger_id}/replay", response_model=TriggerEventRead, status_code=status.HTTP_202_ACCEPTED)
async def replay_trigger_event(
    trigger_id: UUID,
    payload: TriggerReplayRequest,
    session: DbSession,
    current_user: CurrentActiveUser,
    service: TriggerServiceDep,
) -> TriggerEventRead:
    """Re-run one ledger row as a new, linked event.

    Replay costs a flow execution, so it needs flow execute — the same ceiling
    as pressing Run.
    """
    await _authorized_trigger(
        service=service, session=session, user=current_user, trigger_id=trigger_id, action=FlowAction.EXECUTE
    )
    settings = get_settings_service().settings
    try:
        replay = await ledger.replay_event(
            session,
            trigger_id=trigger_id,
            event_id=payload.event_id,
            replay_window_days=settings.trigger_replay_window_days,
        )
    except TriggerEventNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found") from exc
    except ReplayWindowExpiredError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return TriggerEventRead.model_validate(replay)


@router.post("/{trigger_id}/test", response_model=TriggerEventRead, status_code=status.HTTP_202_ACCEPTED)
async def test_trigger(
    trigger_id: UUID,
    payload: TriggerTestRequest,
    session: DbSession,
    current_user: CurrentActiveUser,
    service: TriggerServiceDep,
) -> TriggerEventRead:
    """Append a synthetic event so an owner can exercise the whole path.

    The event goes through the ordinary ledger and dispatcher — there is no
    side-channel — so a passing test is evidence about production behaviour.
    """
    row = await _authorized_trigger(
        service=service, session=session, user=current_user, trigger_id=trigger_id, action=FlowAction.EXECUTE
    )
    if row.state == TriggerState.DEAD.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Trigger is dead and cannot be tested.")
    from uuid import uuid4

    event, _created = await ledger.append_event(
        session,
        trigger_id=trigger_id,
        dedupe_key=f"{TEST_DEDUPE_PREFIX}:{uuid4()}",
        payload={"test": True, **payload.payload},
    )
    return TriggerEventRead.model_validate(event)
