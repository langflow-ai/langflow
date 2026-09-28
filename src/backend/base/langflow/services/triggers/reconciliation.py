"""Keep trigger rows in step with the trigger nodes on a flow's canvas.

The split this module enforces:

* the **canvas node** is authoritative for the trigger's *configuration* — the
  cron expression, the timezone, the catch-up policy;
* the **trigger row** is authoritative for everything else — armed state, the
  pinned version, the binding, the connection, the ledger it owns.

So a save copies configuration onto the row and never arms, pauses, or moves a
pin. Editing a schedule takes effect at the next tick; it does not silently
re-arm a trigger the owner paused.

The one state a save does touch is the configuration's validity verdict, and it
touches it symmetrically (see :func:`apply_config_verdict`): a broken schedule,
or a Slack trigger whose connection can no longer be armed, takes an armed
trigger out of service, and fixing it puts the trigger back.

Provider triggers (Slack) additionally get their ``provider``, their
``connection_id`` and their ``config.mechanism_id`` from the save: the node
names a connection by its portable handle, and which Slack transport the trigger
runs on follows from what that handle resolves to for the flow owner
(``providers/slack/arming.py``). Nothing is decrypted to decide it.

Reconciliation must never fail a save. A flow is the user's document; a trigger
that cannot be reconciled is logged and left alone, exactly as the webhook flag
recompute does today.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger

from langflow.services.database.models.trigger.model import Trigger
from langflow.services.database.models.trigger.schemas import TriggerSessionPolicy, TriggerState
from langflow.services.triggers.constants import (
    KIND_INBOUND_WEBHOOK,
    KIND_SLACK_MESSAGE,
    KIND_SLACK_REACTION,
    PROVIDER_SLACK,
    SLACK_TRIGGER_KINDS,
)
from langflow.services.triggers.schedule_config import (
    InvalidScheduleError,
    schedule_timing_changed,
    validate_schedule_config,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

#: Component type -> trigger kind, for the core trigger components.
TRIGGER_COMPONENT_KINDS: dict[str, str] = {
    "InboundWebhookTrigger": "inbound_webhook",
    "ScheduleTrigger": "schedule",
}

#: ``(bundle, component class)`` -> trigger kind, for provider trigger
#: components shipped in a bundle. A bundle node is saved as
#: ``ext:<bundle>:<Class>@<slot>``; the bundle is part of the key so a class
#: of the same name in another bundle is never taken for these.
BUNDLE_TRIGGER_COMPONENT_KINDS: dict[tuple[str, str], str] = {
    ("slack", "SlackOnMessageTriggerComponent"): KIND_SLACK_MESSAGE,
    ("slack", "SlackOnReactionTriggerComponent"): KIND_SLACK_REACTION,
}

_BUNDLE_NODE_TYPE = re.compile(
    r"^ext:(?P<bundle>[a-z0-9][a-z0-9_-]*):(?P<cls>[A-Za-z_][A-Za-z0-9_]*)@(official|extra)$"
)

#: Display names for provider kinds; core kinds derive theirs from the kind.
_KIND_DISPLAY_NAMES = {KIND_SLACK_MESSAGE: "Slack: On Message", KIND_SLACK_REACTION: "Slack: On Reaction"}

_SLACK_MESSAGE_FIELDS = (
    "connection",
    "channels",
    "conversation_types",
    "mentions_only",
    "include_thread_replies",
    "include_bot_messages",
    "include_edits",
)
_SLACK_REACTION_FIELDS = ("connection", "channels", "emoji", "reaction_events")

#: Trigger kind -> the node template fields that make up its stored config.
#: Field name on the node, key on the row, and the fallback when unset.
_CONFIG_FIELDS: dict[str, tuple[tuple[str, str, Any], ...]] = {
    "schedule": (
        ("cron_expression", "cron", ""),
        ("timezone", "timezone", "UTC"),
        ("catchup_policy", "catchup_policy", "coalesce"),
        ("share_session", "share_session", False),
    ),
    # The URL and the signing secret are NOT here: they are minted by the server
    # on the trigger row, so a flow export carries the webhook's shape without
    # carrying its credential.
    "inbound_webhook": (
        ("payload_schema", "payload_schema", ""),
        ("share_session", "share_session", False),
    ),
    # Defaults are ``None`` so the Slack normalizer, not this table, owns them.
    KIND_SLACK_MESSAGE: tuple((field, field, None) for field in _SLACK_MESSAGE_FIELDS),
    KIND_SLACK_REACTION: tuple((field, field, None) for field in _SLACK_REACTION_FIELDS),
}


class InvalidWebhookConfigError(ValueError):
    """The inbound webhook node cannot be reconciled as configured."""


def normalize_webhook_config(config: dict[str, Any]) -> dict[str, Any]:
    """Turn the node's fields into the stored config for an inbound webhook.

    The node carries the schema as text (it is edited in a textarea); the row
    carries it as a JSON object or not at all. Normalizing on save rather than
    on delivery means a malformed schema is a save-time message next to the node
    instead of a rejection the caller sees weeks later.
    """
    normalized: dict[str, Any] = {"share_session": bool(config.get("share_session"))}
    raw = config.get("payload_schema")
    if isinstance(raw, dict):
        normalized["payload_schema"] = raw
        return normalized
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return normalized
    if not isinstance(raw, str):
        msg = "The payload schema must be a JSON object, or empty to accept any body."
        raise InvalidWebhookConfigError(msg)
    try:
        parsed = json.loads(raw)
    except ValueError as exc:
        msg = "The payload schema must be valid JSON, or empty to accept any body."
        raise InvalidWebhookConfigError(msg) from exc
    if not isinstance(parsed, dict):
        msg = "The payload schema must be a JSON object."
        raise InvalidWebhookConfigError(msg)
    normalized["payload_schema"] = parsed
    return normalized


#: Why a trigger whose node left the canvas was paused. Reconciliation owns this
#: reason, and a clean save must not erase it: re-adding the node leaves the
#: trigger paused, and the reason is still the explanation.
NODE_REMOVED_ERROR = "trigger node removed from the flow"

#: States whose ``last_error`` a schedule verdict owns. The provider states and
#: the terminal ``dead`` state carry reasons that a schedule edit cannot fix.
_VERDICT_STATES = frozenset(
    {
        TriggerState.PENDING.value,
        TriggerState.ACTIVE.value,
        TriggerState.PAUSED.value,
        TriggerState.ERROR.value,
    }
)


def apply_config_verdict(row: Trigger, error: str | None) -> bool:
    """Record whether ``row``'s configuration validates. Returns whether the row changed.

    An invalid configuration - a broken schedule, a Slack trigger whose
    connection can no longer be armed - takes an armed trigger out of service
    (``active`` to ``error``) and says why; a pending or paused trigger keeps
    its state and carries the reason. A configuration that validates undoes
    exactly that: the stale reason is cleared and an ``error`` row goes back to
    ``active``.

    Going back to ``active`` is not arming on the owner's behalf. A row only
    reaches ``error`` from ``active``, here or in the loop that serves it (which
    reads only active rows), so the owner armed it and the system took it out.
    Like ``enable``, re-arming starts from now: schedule ticks missed while it
    was broken are not replayed.
    """
    before = (row.state, row.last_error, row.next_fire_at)
    if error is not None:
        row.last_error = error
        if row.state == TriggerState.ACTIVE.value:
            row.state = TriggerState.ERROR.value
    else:
        if row.state == TriggerState.ERROR.value:
            row.state = TriggerState.ACTIVE.value
            row.next_fire_at = None
        if row.state in _VERDICT_STATES and row.last_error != NODE_REMOVED_ERROR:
            row.last_error = None
    return (row.state, row.last_error, row.next_fire_at) != before


def _template_value(node_data: dict[str, Any], field: str, default: Any) -> Any:
    template = node_data.get("node", {}).get("template", {})
    entry = template.get(field)
    if not isinstance(entry, dict):
        return default
    value = entry.get("value")
    return default if value is None else value


def find_trigger_nodes(flow_data: dict[str, Any] | None) -> list[tuple[str, str, dict[str, Any]]]:
    """Return ``(node_id, kind, config)`` for every trigger node on the canvas."""
    if not flow_data:
        return []
    found: list[tuple[str, str, dict[str, Any]]] = []
    for node in flow_data.get("nodes", []) or []:
        node_data = node.get("data") or {}
        kind = _node_kind(node_data.get("type"))
        if kind is None:
            continue
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id:
            continue
        config = {
            key: _template_value(node_data, field, default) for field, key, default in _CONFIG_FIELDS.get(kind, ())
        }
        found.append((node_id, kind, config))
    return found


def _node_kind(node_type: Any) -> str | None:
    """The trigger kind a saved node's ``type`` declares, or None for any other node."""
    if not isinstance(node_type, str):
        return None
    kind = TRIGGER_COMPONENT_KINDS.get(node_type)
    if kind is not None:
        return kind
    match = _BUNDLE_NODE_TYPE.match(node_type)
    if match is None:
        return None
    return BUNDLE_TRIGGER_COMPONENT_KINDS.get((match["bundle"], match["cls"]))


def _display_name(config: dict[str, Any], kind: str) -> str:
    if kind == "schedule" and config.get("cron"):
        return f"Schedule {config['cron']}"
    return _KIND_DISPLAY_NAMES.get(kind) or kind.replace("_", " ").title()


async def _reconcile_slack(
    session: AsyncSession, *, kind: str, owner_id: UUID, raw: dict[str, Any]
) -> tuple[dict[str, Any], UUID | None, str | None]:
    """Normalize a Slack node and arm it: ``(config, connection_id, error)``.

    The mechanism is merged into the config here, before the caller compares
    it with the stored row, so an unchanged node never rewrites (or strips)
    it. A node that cannot be armed keeps whatever filters did validate and
    records why, with no connection and no mechanism.
    """
    from langflow.services.connection.oauth.config import deployment_context
    from langflow.services.triggers.providers.slack.arming import SlackTriggerArmingError, resolve_arming
    from langflow.services.triggers.providers.slack.config import (
        InvalidSlackTriggerConfigError,
        normalize_slack_config,
    )

    try:
        config = normalize_slack_config(kind, raw)
    except InvalidSlackTriggerConfigError as exc:
        # Kept as entered, so the row shows what the owner has to fix.
        return {key: value for key, value in raw.items() if value is not None}, None, str(exc)
    try:
        arming = await resolve_arming(session, owner_id=owner_id, config=config, context=deployment_context())
    except SlackTriggerArmingError as exc:
        return config, None, str(exc)
    return {**config, "mechanism_id": arming.mechanism_id}, arming.connection_id, None


async def _apply_slack_verdict(
    session: AsyncSession, row: Trigger, *, error: str | None, moved: bool, filters_changed: bool
) -> bool:
    """:func:`apply_config_verdict` for a Slack row. Returns whether the row changed.

    Two differences from a schedule.

    A save that would put the trigger into service against something new - an
    ``active`` row whose connection or filters changed, or an ``error`` row this
    save would heal - first checks what enabling checks, so it cannot go live on
    an installation missing the scopes its events need, or on a connection whose
    owner has not allowed background runs.

    And an ``active`` row on the same connection keeps its ``last_error``. On a
    serving row that is the listener's banner (``record_listener_error``), not
    a verdict a save can overturn: a configuration error never sits on an active
    row, because the verdict moves it to ``error``. A move to another connection
    does clear it, since the banner was about the old one.
    """
    from langflow.services.triggers.providers.slack.arming import (
        SlackArming,
        SlackTriggerArmingError,
        check_ready_to_arm,
    )

    active = row.state == TriggerState.ACTIVE.value
    goes_live = row.state == TriggerState.ERROR.value or (active and (moved or filters_changed))
    if error is None and goes_live and row.connection_id is not None:
        config = row.config or {}
        arming = SlackArming(connection_id=row.connection_id, mechanism_id=config.get("mechanism_id") or "")
        try:
            await check_ready_to_arm(session, kind=row.kind, config=config, arming=arming)
        except SlackTriggerArmingError as exc:
            error = str(exc)
    if error is None and active and not moved:
        return False
    return apply_config_verdict(row, error)


async def reconcile_flow_triggers(
    session: AsyncSession,
    *,
    flow_id: UUID,
    owner_id: UUID,
    flow_data: dict[str, Any] | None,
) -> int:
    """Sync trigger rows to the trigger nodes on ``flow_data``. Returns rows touched.

    Adding a node creates a ``pending`` trigger: appearing on a canvas is not
    consent to start running unattended, so arming stays an explicit act. That
    holds for a node whose schedule is invalid too: it waits in ``pending`` with
    the reason recorded, so fixing it later cannot arm it.
    Removing a node pauses its trigger rather than deleting it, so the ledger
    and its history survive an accidental delete-and-undo.
    """
    from sqlmodel import select

    nodes = {node_id: (kind, config) for node_id, kind, config in find_trigger_nodes(flow_data)}
    statement = select(Trigger).where(Trigger.flow_id == flow_id, Trigger.node_id.is_not(None))  # type: ignore[union-attr]
    existing = {row.node_id: row for row in (await session.exec(statement)).all()}

    touched = 0
    for node_id, (kind, raw_config) in nodes.items():
        row = existing.get(node_id)
        config = raw_config
        error = None
        provider = None
        connection_id = None
        if kind in SLACK_TRIGGER_KINDS:
            provider = PROVIDER_SLACK
            config, connection_id, error = await _reconcile_slack(session, kind=kind, owner_id=owner_id, raw=raw_config)
        elif kind == "schedule":
            try:
                config = validate_schedule_config(config)
            except InvalidScheduleError as exc:
                error = str(exc)
        elif kind == KIND_INBOUND_WEBHOOK:
            try:
                config = normalize_webhook_config(config)
            except InvalidWebhookConfigError as exc:
                error = str(exc)
        session_policy = (
            TriggerSessionPolicy.SHARED.value
            if config.get("share_session") is True
            else TriggerSessionPolicy.PER_EVENT.value
        )
        if row is None:
            session.add(
                Trigger(
                    flow_id=flow_id,
                    user_id=owner_id,
                    name=_display_name(config if error is None else {}, kind),
                    kind=kind,
                    provider=provider,
                    node_id=node_id,
                    connection_id=connection_id,
                    config=config,
                    provider_state={},
                    state=TriggerState.PENDING.value,
                    last_error=error,
                    session_policy=session_policy,
                    concurrency_limit=1,
                    max_attempts=5,
                )
            )
            touched += 1
            continue
        config_changed = row.config != config
        changed = config_changed or row.session_policy != session_policy
        if changed:
            if schedule_timing_changed(row.config or {}, config):
                row.next_fire_at = None
            row.config = config
            row.session_policy = session_policy
        moved = False
        if provider is not None:
            from langflow.services.triggers.providers.slack.arming import bind_connection

            if row.provider != provider:
                row.provider = provider
                changed = True
            moved = bind_connection(row, connection_id)
            changed = changed or moved
        # Evaluated on every save, not only when the config changed, so a row an
        # earlier save left in ``error`` with an already-valid config heals.
        if kind == "schedule":
            changed = apply_config_verdict(row, error) or changed
        elif kind in SLACK_TRIGGER_KINDS:
            verdict = await _apply_slack_verdict(session, row, error=error, moved=moved, filters_changed=config_changed)
            changed = verdict or changed
        if changed:
            session.add(row)
            touched += 1

    # Imported here, not at module scope: ``subscriptions`` reaches the service
    # registry, which imports this module back.
    from langflow.services.triggers.subscriptions import revoke_for_trigger

    for node_id, row in existing.items():
        if node_id in nodes or row.state in {TriggerState.PAUSED.value, TriggerState.DEAD.value}:
            continue
        row.state = TriggerState.PAUSED.value
        row.last_error = NODE_REMOVED_ERROR
        session.add(row)
        # Retire the provider subscription with the node, for the same reason
        # ``TriggerService.disable`` does: a paused trigger whose subscription is
        # still live keeps consuming the provider's per-tenant quota and keeps
        # delivering notifications this instance will only reject. Removing the
        # node is as much an "off" as pressing pause.
        await revoke_for_trigger(session, trigger_id=row.id)
        touched += 1

    if touched:
        await session.flush()
    return touched


async def reconcile_flow_triggers_safely(
    session: AsyncSession,
    *,
    flow_id: UUID,
    owner_id: UUID | None,
    flow_data: dict[str, Any] | None,
) -> None:
    """Reconcile without ever failing the save that called it.

    The work runs inside a SAVEPOINT, and that is the load-bearing part rather
    than the ``except``. Swallowing the exception alone is not enough: an
    ``IntegrityError`` raised by this function's own ``flush`` leaves the
    caller's ``AsyncSession`` in a failed transaction, so the flow save that
    called us would still die — at ``commit``, with a ``PendingRollbackError``
    the caller cannot attribute to trigger bookkeeping. The savepoint rollback
    undoes only what reconciliation wrote and hands the save back a usable
    session.

    The failure is real, not theoretical: two concurrent saves of the same flow
    (an autosave PATCH racing a PUT) can both see no row for a newly added
    trigger node and both insert ``(flow_id, node_id)``; the loser violates
    ``uq_trigger_flow_node``.
    """
    if owner_id is None:
        return
    try:
        async with session.begin_nested():
            await reconcile_flow_triggers(session, flow_id=flow_id, owner_id=owner_id, flow_data=flow_data)
    except Exception:  # noqa: BLE001 — a flow save must never fail on trigger bookkeeping
        await logger.awarning("Trigger reconciliation failed for flow %s", flow_id, exc_info=True)
