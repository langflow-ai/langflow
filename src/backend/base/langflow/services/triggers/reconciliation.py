"""Keep trigger rows in step with the trigger nodes on a flow's canvas.

The split this module enforces:

* the **canvas node** is authoritative for the trigger's *configuration* — the
  cron expression, the timezone, the catch-up policy;
* the **trigger row** is authoritative for everything else — armed state, the
  pinned version, the binding, the connection, the ledger it owns.

So a save copies configuration onto the row and never touches state. Editing a
schedule takes effect at the next tick; it does not silently re-arm a trigger
the owner paused, and it does not move a pin.

Reconciliation must never fail a save. A flow is the user's document; a trigger
that cannot be reconciled is logged and left alone, exactly as the webhook flag
recompute does today.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger

from langflow.services.database.models.trigger.model import Trigger
from langflow.services.database.models.trigger.schemas import TriggerSessionPolicy, TriggerState

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

#: Component type -> trigger kind. TRG-5 and TRG-6 append their provider
#: components here; nothing else in the codebase needs to learn about them.
TRIGGER_COMPONENT_KINDS: dict[str, str] = {
    "ScheduleTrigger": "schedule",
}

#: Trigger kind -> the node template fields that make up its stored config.
#: Field name on the node, key on the row, and the fallback when unset.
_CONFIG_FIELDS: dict[str, tuple[tuple[str, str, Any], ...]] = {
    "schedule": (
        ("cron_expression", "cron", ""),
        ("timezone", "timezone", "UTC"),
        ("catchup_policy", "catchup_policy", "coalesce"),
        ("share_session", "share_session", False),
    ),
}


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
        kind = TRIGGER_COMPONENT_KINDS.get(node_data.get("type"))
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


def _display_name(config: dict[str, Any], kind: str) -> str:
    if kind == "schedule" and config.get("cron"):
        return f"Schedule {config['cron']}"
    return kind.replace("_", " ").title()


async def reconcile_flow_triggers(
    session: AsyncSession,
    *,
    flow_id: UUID,
    owner_id: UUID,
    flow_data: dict[str, Any] | None,
) -> int:
    """Sync trigger rows to the trigger nodes on ``flow_data``. Returns rows touched.

    Adding a node creates a ``pending`` trigger: appearing on a canvas is not
    consent to start running unattended, so arming stays an explicit act.
    Removing a node pauses its trigger rather than deleting it, so the ledger
    and its history survive an accidental delete-and-undo.
    """
    from sqlmodel import select

    nodes = {node_id: (kind, config) for node_id, kind, config in find_trigger_nodes(flow_data)}
    statement = select(Trigger).where(Trigger.flow_id == flow_id, Trigger.node_id.is_not(None))  # type: ignore[union-attr]
    existing = {row.node_id: row for row in (await session.exec(statement)).all()}

    touched = 0
    for node_id, (kind, config) in nodes.items():
        row = existing.get(node_id)
        session_policy = (
            TriggerSessionPolicy.SHARED.value if config.get("share_session") else TriggerSessionPolicy.PER_EVENT.value
        )
        if row is None:
            session.add(
                Trigger(
                    flow_id=flow_id,
                    user_id=owner_id,
                    name=_display_name(config, kind),
                    kind=kind,
                    node_id=node_id,
                    config=config,
                    provider_state={},
                    state=TriggerState.PENDING.value,
                    session_policy=session_policy,
                    concurrency_limit=1,
                    max_attempts=5,
                )
            )
            touched += 1
            continue
        if row.config != config or row.session_policy != session_policy:
            row.config = config
            row.session_policy = session_policy
            # The schedule may have changed; drop the cursor so the next pass
            # recomputes it instead of firing on the old expression's clock.
            row.next_fire_at = None
            session.add(row)
            touched += 1

    for node_id, row in existing.items():
        if node_id in nodes or row.state == TriggerState.PAUSED.value:
            continue
        row.state = TriggerState.PAUSED.value
        row.last_error = "trigger node removed from the flow"
        session.add(row)
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
