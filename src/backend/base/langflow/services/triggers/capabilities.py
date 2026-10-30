"""What a caller may do with a trigger right now, and why not.

The triggers settings page and the node badge render this answer as given
(``design/dedicated-integrations-triggers/frontend-surfaces.md``, constraint 1):
the frontend never re-derives permission from ``state``. Keeping the rules in
one pure function is what makes that safe: the routes, the list views, and the
tests all read the same table.

Three outcomes per action:

* **allowed** - the server would accept it from this caller now;
* **blocked** - it applies to this trigger but is refused, with a reason code
  the UI shows in the disabled control's tooltip;
* **absent** - it does not apply to this kind of trigger (no secret to rotate,
  no connection to reconnect, nothing to resume on a running trigger), so the
  UI does not render it.

A state reason outranks a caller reason: a reader looking at a dead trigger is
told it is dead, which stays true whatever access they are later granted.

The answer is conservative, never more permissive than the routes: an action
listed as allowed is one the route accepts. The converse need not hold - a
test event on a paused trigger is accepted by the route but is retired without
running, so it is reported as blocked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from langflow.services.database.models.trigger.schemas import TriggerAction, TriggerReason, TriggerState
from langflow.services.triggers.constants import (
    CONNECTION_NOT_AUTHORIZED_ERROR,
    KIND_INBOUND_WEBHOOK,
    PROVIDER_GOOGLE,
    PROVIDER_MICROSOFT,
    PROVIDER_SLACK,
)
from langflow.services.triggers.reconciliation import NODE_REMOVED_ERROR, SOURCE_SETTINGS_CHANGED_ERROR

if TYPE_CHECKING:
    from langflow.services.database.models.trigger.model import Trigger

#: Providers whose triggers authenticate with a user connection.
_CONNECTION_PROVIDERS = frozenset({PROVIDER_SLACK, PROVIDER_MICROSOFT, PROVIDER_GOOGLE})

#: States whose queued events the dispatcher retires instead of running, so a
#: test or replay there could never produce a run.
_RETIRING_STATES = frozenset({TriggerState.PAUSED.value, TriggerState.EXPIRED.value, TriggerState.DEAD.value})


@dataclass(frozen=True)
class TriggerCaller:
    """What the caller may do on the trigger's flow, as the routes would decide it."""

    can_write: bool
    can_execute: bool
    #: The trigger owner is the connection owner; only they can reconnect it or
    #: grant it background-run consent.
    owns_connection: bool


#: A caller who can reach nothing on the trigger's flow.
NO_ACCESS = TriggerCaller(can_write=False, can_execute=False, owns_connection=False)


@dataclass(frozen=True)
class TriggerCapabilities:
    reason: TriggerReason | None
    allowed_actions: tuple[TriggerAction, ...]
    blocked_actions: dict[TriggerAction, TriggerReason] = field(default_factory=dict)


def _paused_reason(row: Trigger) -> TriggerReason:
    if row.admin_paused_at is not None:
        return TriggerReason.PAUSED_BY_ADMIN
    if row.last_error == NODE_REMOVED_ERROR:
        return TriggerReason.NODE_REMOVED
    if row.last_error == SOURCE_SETTINGS_CHANGED_ERROR:
        return TriggerReason.SOURCE_SETTINGS_CHANGED
    return TriggerReason.PAUSED


def trigger_reason(row: Trigger, *, recovery_reason: TriggerReason | None = None) -> TriggerReason | None:
    """The one stable code explaining ``row``'s state, or ``None`` when it is running cleanly."""
    state = row.state
    if state == TriggerState.ACTIVE.value:
        return TriggerReason.DEGRADED if row.last_error else None
    if state == TriggerState.PENDING.value:
        return TriggerReason.CONFIG_INVALID if row.last_error else TriggerReason.PENDING
    if state == TriggerState.PAUSED.value:
        return _paused_reason(row)
    if state == TriggerState.NEEDS_RECONNECT.value:
        if recovery_reason is not None:
            return recovery_reason
        if row.last_error == CONNECTION_NOT_AUTHORIZED_ERROR:
            return TriggerReason.CONSENT_REQUIRED
        return TriggerReason.NEEDS_RECONNECT
    if state == TriggerState.EXPIRED.value:
        return TriggerReason.EXPIRED
    if state == TriggerState.DEAD.value:
        return TriggerReason.DEAD
    return TriggerReason.ERROR


def _uses_connection(row: Trigger) -> bool:
    from langflow.services.triggers.providers.registry import get_kind

    return row.connection_id is not None or row.provider in _CONNECTION_PROVIDERS or get_kind(row.kind) is not None


def _decide(
    row: Trigger, reason: TriggerReason | None, caller: TriggerCaller
) -> dict[TriggerAction, TriggerReason | None]:
    """Each applicable action mapped to ``None`` (allowed) or the reason it is refused."""
    state = row.state
    dead = state == TriggerState.DEAD.value
    write = None if caller.can_write else TriggerReason.INSUFFICIENT_PERMISSION
    execute = None if caller.can_execute else TriggerReason.INSUFFICIENT_PERMISSION
    run_block = reason if state in _RETIRING_STATES else execute

    decisions: dict[TriggerAction, TriggerReason | None] = {}
    if state not in {TriggerState.PAUSED.value, TriggerState.DEAD.value}:
        decisions[TriggerAction.PAUSE] = write
    if state != TriggerState.ACTIVE.value:
        decisions[TriggerAction.RESUME] = TriggerReason.DEAD if dead else write
        if state == TriggerState.NEEDS_RECONNECT.value and reason is not TriggerReason.READY_TO_RESUME:
            decisions[TriggerAction.RESUME] = write or reason
    decisions[TriggerAction.TEST] = run_block
    if _uses_connection(row):
        if state != TriggerState.NEEDS_RECONNECT.value or reason is TriggerReason.READY_TO_RESUME:
            decisions[TriggerAction.RECONNECT] = TriggerReason.RECONNECT_NOT_NEEDED
        else:
            decisions[TriggerAction.RECONNECT] = None if caller.owns_connection else TriggerReason.NOT_CONNECTION_OWNER
    decisions[TriggerAction.REPLAY] = run_block
    decisions[TriggerAction.DELETE] = write
    if row.kind == KIND_INBOUND_WEBHOOK:
        decisions[TriggerAction.ROTATE_SECRET] = write
    return decisions


def trigger_capabilities(
    row: Trigger, *, caller: TriggerCaller, recovery_reason: TriggerReason | None = None
) -> TriggerCapabilities:
    """The server's answer for ``caller`` on ``row``, in ``TriggerAction`` display order."""
    reason = trigger_reason(row, recovery_reason=recovery_reason)
    decisions = _decide(row, reason, caller)
    allowed: list[TriggerAction] = []
    blocked: dict[TriggerAction, TriggerReason] = {}
    for action in TriggerAction:
        if action not in decisions:
            continue
        refusal = decisions[action]
        if refusal is None:
            allowed.append(action)
        else:
            blocked[action] = refusal
    return TriggerCapabilities(reason=reason, allowed_actions=tuple(allowed), blocked_actions=blocked)
