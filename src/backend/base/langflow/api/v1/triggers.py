"""Owner-scoped API for triggers and their event ledger.

Triggers have no resource word of their own: they ride the flow they fire, so
every route authorizes with ``ensure_flow_permission``. Reads need flow read,
management needs flow write, and replay/test need flow execute — the same
ceiling as running the flow by hand, which is what a trigger ultimately does.

Existence privacy follows the connections precedent: a trigger the caller cannot
read at all is a 404, while a caller who can read the flow but not write it gets
an honest 403.

Two routes are not flow-scoped. ``GET /triggers?scope=all`` and the ``/bulk``
routes are the operator view (TRG-7 B3): superuser only, across every user, for
incident response. Every ``TriggerRead`` carries the server-computed
``allowed_actions`` / ``blocked_actions`` / ``reason`` for the caller.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from langflow.api.utils import CurrentActiveUser, DbSession, DbSessionReadOnly
from langflow.api.v1.flows_helpers import _read_flow
from langflow.api.v1.triggers_helpers import list_all_triggers, list_visible_triggers, present, present_one
from langflow.services.auth.utils import get_current_active_superuser
from langflow.services.authorization import FlowAction, ensure_flow_permission
from langflow.services.authorization.fetch import deny_to_404
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.exceptions import FlowVersionNotFoundError
from langflow.services.database.models.trigger.model import Trigger
from langflow.services.database.models.trigger.schemas import (
    PROVIDER_PATTERN,
    TriggerBindingTarget,
    TriggerBulkRequest,
    TriggerBulkResult,
    TriggerCreate,
    TriggerEventRead,
    TriggerIngressRead,
    TriggerListScope,
    TriggerPinRequest,
    TriggerRead,
    TriggerReplayRequest,
    TriggerSigningSecretRead,
    TriggerState,
    TriggerTestRequest,
    TriggerUpdate,
)
from langflow.services.database.models.user.model import User, UserRead
from langflow.services.deps import get_settings_service, get_trigger_service
from langflow.services.triggers import ledger, operator
from langflow.services.triggers.constants import (
    KIND_INBOUND_WEBHOOK,
    PROVIDER_WEBHOOK,
    PUSH_MECHANISMS,
    TEST_DEDUPE_PREFIX,
)
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
CurrentSuperuser = Annotated[User | UserRead, Depends(get_current_active_superuser)]


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trigger not found")


def _require_ingress_kind(row: Trigger) -> None:
    """Only the generic signed webhook owns a secret the owner can rotate.

    Slack signs with a registration-level secret and Microsoft and Google verify
    against a secret Langflow mints per subscription, so offering an owner a
    rotate button for those would be a control that changes nothing.
    """
    if row.kind != KIND_INBOUND_WEBHOOK:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only inbound webhook triggers have an owner-managed signing secret.",
        )


def _ingress_read(row: Trigger, request: Request) -> TriggerIngressRead:
    """The public address of a trigger, built from the request's own origin.

    Derived from the request rather than from a configured base URL because the
    URL an owner needs is the one their deployment is actually reachable at, and
    a single instance is often reachable at more than one.
    """
    url = None
    if row.public_id:
        url = str(request.url_for("receive_provider_delivery", provider=PROVIDER_WEBHOOK, public_id=row.public_id))
    return TriggerIngressRead(
        trigger_id=row.id,
        public_id=row.public_id,
        ingress_url=url,
        has_signing_secret=bool(row.signing_secret_encrypted),
    )


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
    flow_id: Annotated[UUID | None, Query(description="Only the triggers on this flow")] = None,
    scope: Annotated[
        TriggerListScope,
        Query(description="'mine': every flow the caller can read. 'all': every user's triggers (superuser only)."),
    ] = TriggerListScope.MINE,
    provider: Annotated[str | None, Query(max_length=64, pattern=PROVIDER_PATTERN)] = None,
    state: TriggerState | None = None,
    limit: Annotated[int, Query(ge=1, le=_MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[TriggerRead]:
    """List triggers, newest first, each with its flow's name.

    With ``flow_id``, the triggers on that one flow, authorized as a flow read
    (404 when the caller cannot read it). Without it, the triggers on every flow
    the caller can read, including shared flows when a registered plugin
    supports cross-user fetch. ``scope=all`` is the
    operator view: every user's triggers with each owner's username, superuser
    only.
    """
    if scope is TriggerListScope.ALL:
        if not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Only a superuser can list every user's triggers."
            )
        rows = await list_all_triggers(
            session, flow_id=flow_id, provider=provider, state=state, limit=limit, offset=offset
        )
        return await present(rows, current_user)
    if flow_id is None:
        rows = await list_visible_triggers(
            session, current_user, provider=provider, state=state, limit=limit, offset=offset
        )
        return await present(rows, current_user)
    flow = await _authorized_flow(session, current_user, flow_id, FlowAction.READ)
    triggers = await service.list_for_flows(
        session, flow_ids=[flow_id], limit=limit, offset=offset, provider=provider, state=state
    )
    return await present([(row, flow, None) for row in triggers], current_user)


@router.post("/bulk/pause", response_model=TriggerBulkResult)
async def bulk_pause_triggers(
    payload: TriggerBulkRequest,
    session: DbSession,
    current_user: CurrentSuperuser,
    service: TriggerServiceDep,
) -> TriggerBulkResult:
    """Pause every armed trigger the filter selects, across all users. Superuser only.

    For incident response. Only ``active``, ``error`` and ``needs_reconnect``
    triggers are paused; each is marked so its owner sees ``paused_by_admin``
    and the operator's bulk resume can re-arm exactly these. ``dry_run`` reports
    the same answer without changing anything, for a confirmation dialog.
    """
    return await operator.bulk_pause(session, service, request=payload, actor_id=current_user.id)


@router.post("/bulk/resume", response_model=TriggerBulkResult)
async def bulk_resume_triggers(
    payload: TriggerBulkRequest,
    session: DbSession,
    current_user: CurrentSuperuser,
    service: TriggerServiceDep,
) -> TriggerBulkResult:
    """Resume the triggers an operator paused that the filter selects. Superuser only.

    A trigger its owner paused stays paused. A trigger that cannot start is
    reported in ``failed``: if enabling it is refused it stays paused, released
    from the operator's hold, with the reason in ``last_error``; if a push
    source's subscription fails, the trigger records the failure as it would
    for the owner's own resume. Each change commits with its audit row.
    """
    return await operator.bulk_resume(session, service, request=payload, actor_id=current_user.id)


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
    try:
        row = await service.create(session, payload=payload, owner_id=flow.user_id)
    except FlowVersionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    return await present_one(session, current_user, row)


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
    return await present_one(session, current_user, row)


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
    try:
        updated = await service.update(session, row=row, payload=payload)
    except FlowVersionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    _reject_unsupported_binding(TriggerBindingTarget(updated.binding_target), updated.deployment_id)
    return await present_one(session, current_user, updated)


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
        updated = await service.enable_and_activate(session, row=row)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return await present_one(session, current_user, updated)


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
    try:
        updated = await service.disable(session, row=row)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return await present_one(session, current_user, updated)


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
    try:
        updated = await service.pin(session, row=row, flow_version_id=payload.flow_version_id)
    except FlowVersionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    return await present_one(session, current_user, updated)


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
        payload={**payload.payload, "test": True},
    )
    return TriggerEventRead.model_validate(event)


@router.get("/{trigger_id}/ingress", response_model=TriggerIngressRead)
async def get_trigger_ingress(
    trigger_id: UUID,
    request: Request,
    session: DbSession,
    current_user: CurrentActiveUser,
    service: TriggerServiceDep,
) -> TriggerIngressRead:
    """Where a caller posts to this trigger, and whether a secret is set.

    Never the secret itself. A signing secret is shown exactly once, by the
    route that mints it; a GET that returned it would put it in every browser
    history, proxy log, and screen share that touches the triggers page.
    """
    row = await _authorized_trigger(
        service=service, session=session, user=current_user, trigger_id=trigger_id, action=FlowAction.READ
    )
    if (
        row.provider in {"microsoft", "google"}
        and row.public_id
        and (row.config or {}).get("mechanism_id") in PUSH_MECHANISMS
    ):
        from langflow.services.triggers.source_subscription import source_ingress_url

        return TriggerIngressRead(
            trigger_id=row.id,
            public_id=row.public_id,
            ingress_url=await source_ingress_url(session, row),
            has_signing_secret=False,
        )
    _require_ingress_kind(row)
    return _ingress_read(row, request)


@router.post("/{trigger_id}/signing-secret", response_model=TriggerSigningSecretRead)
async def rotate_trigger_signing_secret(
    trigger_id: UUID,
    request: Request,
    session: DbSession,
    current_user: CurrentActiveUser,
    service: TriggerServiceDep,
) -> TriggerSigningSecretRead:
    """Mint this trigger's ingress address and signing secret, or rotate them.

    Rotation replaces the stored secret, so the previous one stops verifying on
    the next delivery: there is no grace window, deliberately. A webhook secret
    is rotated because it leaked, and a grace window is exactly the period the
    leak is still useful.

    The address (``public_id``) is minted once and kept across rotations, so
    rotating a secret does not require reconfiguring the caller's URL.
    """
    row = await _authorized_trigger(
        service=service, session=session, user=current_user, trigger_id=trigger_id, action=FlowAction.WRITE
    )
    _require_ingress_kind(row)
    secret = await service.rotate_signing_secret(session, row=row)
    return TriggerSigningSecretRead(
        **_ingress_read(row, request).model_dump(),
        signing_secret=secret,
    )
