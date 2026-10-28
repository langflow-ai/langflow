"""List queries and response shaping for the triggers routes.

Kept beside ``triggers.py`` rather than in the service: visibility is an
authorization concern the route layer owns, and every guard stays next to the
route it serves.

Two lists:

* :func:`list_visible_triggers` - the caller's own view, across every flow they
  can read. Uses the plugin's SQL prefilter when available, otherwise checks
  read permission before paginating. Only a cross-user-fetch plugin may widen
  the fallback beyond owned flows.
* :func:`list_all_triggers` - the superuser operator view, across every user,
  with each owner's username.

Every ``TriggerRead`` leaves through :func:`present`, which fills the
server-computed ``allowed_actions`` / ``blocked_actions`` / ``reason`` from the
caller's effective flow permissions.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from fastapi import HTTPException
from lfx.integrations.errors import IntegrationPolicyBlockedError
from lfx.integrations.models import ConnectionRef
from sqlalchemy import case
from sqlalchemy.orm import defer
from sqlmodel import col, select

from langflow.services.authorization import (
    FlowAction,
    capability_probe,
    ensure_flow_permission,
    filter_visible_resources,
    restrict_to_owned_or_visible_scope,
    visible_scope_prefilter,
)
from langflow.services.authorization.fetch import cross_user_fetch_enabled
from langflow.services.authorization.utils import _resolve_authz_domain
from langflow.services.database.models.connection.model import Connection
from langflow.services.database.models.connection.schemas import PersistedConnectionStatus
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.trigger.model import Trigger
from langflow.services.database.models.trigger.schemas import TriggerRead, TriggerReason, TriggerState
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_settings_service
from langflow.services.triggers.capabilities import NO_ACCESS, TriggerCaller, trigger_capabilities
from langflow.services.triggers.ownership import is_owned_by

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.user.model import UserRead


async def _may(user: User | UserRead, flow: Flow, action: FlowAction) -> bool:
    """Whether the route guard would allow ``action`` on ``flow``, without auditing the probe."""
    try:
        with capability_probe():
            await ensure_flow_permission(
                user,
                action,
                flow_id=flow.id,
                flow_user_id=flow.user_id,
                workspace_id=flow.workspace_id,
                folder_id=flow.folder_id,
            )
    except HTTPException:
        # An affordance answer fails closed: a refusal, a ceiling, or an
        # unavailable plugin all mean "do not offer it".
        return False
    return True


async def _reachable(user: User | UserRead, flow: Flow) -> bool:
    """Whether the per-trigger routes can load this flow for ``user`` at all.

    Asks the same question ``authorized_or_owner_scoped`` does: without a
    plugin that supports cross-user fetch, the routes are owner-scoped, so a superuser in the
    operator view cannot act on someone else's trigger through them.
    """
    if flow.user_id == user.id:
        return True
    if not await cross_user_fetch_enabled():
        return False
    return await _may(user, flow, FlowAction.READ)


async def _flow_caller(user: User | UserRead, flow: Flow) -> TriggerCaller:
    if not await _reachable(user, flow):
        return NO_ACCESS
    return TriggerCaller(
        can_write=await _may(user, flow, FlowAction.WRITE),
        can_execute=await _may(user, flow, FlowAction.EXECUTE),
        owns_connection=False,
    )


async def present(
    session: AsyncSession,
    rows: list[tuple[Trigger, Flow, str | None]],
    user: User | UserRead,
    *,
    with_flow_name: bool = True,
) -> list[TriggerRead]:
    """Shape ``(trigger, flow, owner_username)`` rows into responses for ``user``.

    Permissions are probed once per distinct flow, not once per trigger. A row
    the per-trigger routes could not load for ``user`` - the operator view's
    rows on other users' flows, or a plugin whose list prefilter is wider than
    its fetch - offers no per-trigger action.
    """
    connection_ids = {
        row.connection_id
        for row, _flow, _owner in rows
        if row.state == TriggerState.NEEDS_RECONNECT.value and row.connection_id is not None
    }
    # Only non-secret metadata is loaded, once for the whole page. Keeping the
    # rows here also lets readiness validators use the session's identity map.
    connections = (
        {
            connection.id: connection
            for connection in (
                await session.exec(select(Connection).where(col(Connection.id).in_(connection_ids)))
            ).all()
        }
        if connection_ids
        else {}
    )
    callers: dict[UUID, TriggerCaller] = {}
    responses: list[TriggerRead] = []
    for row, flow, owner_username in rows:
        if flow.id not in callers:
            callers[flow.id] = await _flow_caller(user, flow)
        caller = callers[flow.id]
        # The trigger owner owns its connection, so only they may reconnect it.
        owns = caller is not NO_ACCESS and row.user_id == user.id
        recovery_reason = (
            await _connection_recovery_reason(session, row, connections.get(row.connection_id))
            if row.state == TriggerState.NEEDS_RECONNECT.value
            else None
        )
        caps = trigger_capabilities(row, caller=replace(caller, owns_connection=owns), recovery_reason=recovery_reason)
        responses.append(
            TriggerRead.model_validate(row).model_copy(
                update={
                    "reason": caps.reason,
                    "allowed_actions": list(caps.allowed_actions),
                    "blocked_actions": dict(caps.blocked_actions),
                    "flow_name": flow.name if with_flow_name else None,
                    "owner_username": owner_username,
                }
            )
        )
    return responses


async def _connection_recovery_reason(
    session: AsyncSession, row: Trigger, connection: Connection | None
) -> TriggerReason:
    """Read current connection metadata without arming or contacting the provider."""
    if connection is None or row.user_id is None or not is_owned_by(connection, row.user_id):
        return TriggerReason.NEEDS_RECONNECT
    try:
        ref = ConnectionRef.parse((row.config or {}).get("connection", ""))
    except ValueError:
        return TriggerReason.CONFIG_INVALID
    if (
        connection.provider_key != row.kind.split(".", 1)[0]
        or (row.provider is not None and connection.provider_key != row.provider)
        or (ref.provider, ref.name) != (connection.provider_key, connection.name)
    ):
        return TriggerReason.CONFIG_INVALID
    if connection.status != PersistedConnectionStatus.READY.value:
        return TriggerReason.NEEDS_RECONNECT
    if not connection.allow_non_interactive:
        return TriggerReason.CONSENT_REQUIRED

    from langflow.services.triggers.constants import SLACK_TRIGGER_KINDS
    from langflow.services.triggers.providers.registry import source_kinds

    mechanism = (row.config or {}).get("mechanism_id")
    if not isinstance(mechanism, str):
        return TriggerReason.CONFIG_INVALID
    try:
        if row.kind in SLACK_TRIGGER_KINDS:
            from langflow.services.triggers.providers.slack.arming import SlackArming, check_ready_to_arm

            await check_ready_to_arm(
                session,
                kind=row.kind,
                config=row.config or {},
                arming=SlackArming(connection_id=connection.id, mechanism_id=mechanism),
            )
        elif row.kind in source_kinds():
            from langflow.services.triggers.source_arming import SourceArming, check_ready

            await check_ready(
                session,
                kind=row.kind,
                config=row.config,
                arming=SourceArming(connection_id=connection.id, mechanism_id=mechanism),
            )
        else:
            return TriggerReason.CONFIG_INVALID
    except ValueError:
        return TriggerReason.NEEDS_RECONNECT
    except IntegrationPolicyBlockedError:
        return TriggerReason.CONFIG_INVALID
    return TriggerReason.READY_TO_RESUME


async def present_one(session: AsyncSession, user: User | UserRead, row: Trigger) -> TriggerRead:
    """One trigger the caller already reached through ``_authorized_trigger``.

    The flow is in the session's identity map from that authorization, so this
    does not query again.
    """
    flow = await session.get(Flow, row.flow_id)
    if flow is None:  # pragma: no cover - the FK cascade deletes the trigger with its flow
        return TriggerRead.model_validate(row)
    (response,) = await present(session, [(row, flow, None)], user, with_flow_name=False)
    return response


def _filtered(statement, *, provider: str | None, state: TriggerState | None, flow_id: UUID | None = None):
    if provider is not None:
        statement = statement.where(Trigger.provider == provider)
    if state is not None:
        statement = statement.where(Trigger.state == state.value)
    if flow_id is not None:
        statement = statement.where(Trigger.flow_id == flow_id)
    return statement


def _newest_first(statement, *, limit: int, offset: int):
    return statement.order_by(col(Trigger.created_at).desc(), col(Trigger.id).desc()).offset(offset).limit(limit)


async def list_visible_triggers(
    session: AsyncSession,
    user: User | UserRead,
    *,
    provider: str | None,
    state: TriggerState | None,
    limit: int,
    offset: int,
) -> list[tuple[Trigger, Flow, str | None]]:
    """Triggers on every flow ``user`` can read, newest first."""
    owned = col(Flow.user_id) == user.id
    # The flow's JSON is never read here; a page of 200 rows must not load it.
    statement = select(Trigger, Flow).join(Flow, col(Flow.id) == col(Trigger.flow_id)).options(defer(Flow.data))
    visibility = await visible_scope_prefilter(user, resource_type="flow", act=FlowAction.READ)
    if visibility is not None:
        workspace = case((col(Flow.folder_id).is_not(None), Folder.workspace_id), else_=Flow.workspace_id)
        statement = restrict_to_owned_or_visible_scope(
            statement.outerjoin(Folder, col(Folder.id) == col(Flow.folder_id)),
            id_column=Flow.id,
            owner_clause=owned,
            workspace_expression=workspace,
            project_column=Flow.folder_id,
            visibility=visibility,
        )
    elif not await cross_user_fetch_enabled():
        statement = statement.where(owned)
    statement = _filtered(statement, provider=provider, state=state)
    if visibility is not None or not get_settings_service().auth_settings.AUTHZ_ENABLED:
        statement = _newest_first(statement, limit=limit, offset=offset)
        return [(trigger, flow, None) for trigger, flow in (await session.exec(statement)).all()]
    return await _readable_trigger_page(session, user, statement, limit=limit, offset=offset)


async def _readable_trigger_page(
    session: AsyncSession, user: User | UserRead, statement, *, limit: int, offset: int
) -> list[tuple[Trigger, Flow, str | None]]:
    """Apply read permission before the page window without loading the whole table."""
    batch_size = 200
    scanned = 0
    result: list[tuple[Trigger, Flow, str | None]] = []
    while True:
        batch = _newest_first(statement, limit=batch_size, offset=scanned)
        rows = (await session.exec(batch)).all()
        if not rows:
            return result
        flows = list({flow.id: flow for _trigger, flow in rows}.values())
        visible = await filter_visible_resources(
            user,
            resource_type="flow",
            candidates=flows,
            domain_extractor=lambda flow: _resolve_authz_domain(flow.workspace_id, flow.folder_id),
            owner_extractor=lambda flow: flow.user_id,
            act=FlowAction.READ,
        )
        visible_ids = {flow.id for flow in visible}
        for trigger, flow in rows:
            if flow.id not in visible_ids:
                continue
            if offset:
                offset -= 1
                continue
            result.append((trigger, flow, None))
            if len(result) == limit:
                return result
        scanned += len(rows)
        if len(rows) < batch_size:
            return result


async def list_all_triggers(
    session: AsyncSession,
    *,
    flow_id: UUID | None,
    provider: str | None,
    state: TriggerState | None,
    limit: int,
    offset: int,
) -> list[tuple[Trigger, Flow, str | None]]:
    """Every user's triggers, newest first, with each owner's username. Superuser only."""
    statement = (
        select(Trigger, Flow, User.username)
        .join(Flow, col(Flow.id) == col(Trigger.flow_id))
        .join(User, col(User.id) == col(Trigger.user_id))
        .options(defer(Flow.data))
    )
    statement = _newest_first(
        _filtered(statement, provider=provider, state=state, flow_id=flow_id), limit=limit, offset=offset
    )
    return [(trigger, flow, username) for trigger, flow, username in (await session.exec(statement)).all()]
