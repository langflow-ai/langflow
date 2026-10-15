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
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.trigger.model import Trigger
from langflow.services.database.models.trigger.schemas import TriggerRead, TriggerState
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_settings_service
from langflow.services.triggers.capabilities import NO_ACCESS, TriggerCaller, trigger_capabilities

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
    callers: dict[UUID, TriggerCaller] = {}
    responses: list[TriggerRead] = []
    for row, flow, owner_username in rows:
        if flow.id not in callers:
            callers[flow.id] = await _flow_caller(user, flow)
        caller = callers[flow.id]
        # The trigger owner owns its connection, so only they may reconnect it.
        owns = caller is not NO_ACCESS and row.user_id == user.id
        caps = trigger_capabilities(row, caller=replace(caller, owns_connection=owns))
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


async def present_one(session: AsyncSession, user: User | UserRead, row: Trigger) -> TriggerRead:
    """One trigger the caller already reached through ``_authorized_trigger``.

    The flow is in the session's identity map from that authorization, so this
    does not query again.
    """
    flow = await session.get(Flow, row.flow_id)
    if flow is None:  # pragma: no cover - the FK cascade deletes the trigger with its flow
        return TriggerRead.model_validate(row)
    (response,) = await present([(row, flow, None)], user, with_flow_name=False)
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
