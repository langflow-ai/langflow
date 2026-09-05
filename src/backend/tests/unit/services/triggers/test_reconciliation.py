"""Flow saves keep trigger rows in step without ever changing their state."""

from __future__ import annotations

from typing import Any

import pytest
from langflow.services.database.models.trigger.model import Trigger
from langflow.services.database.models.trigger.schemas import TriggerSessionPolicy, TriggerState
from langflow.services.deps import session_scope
from langflow.services.triggers.reconciliation import find_trigger_nodes, reconcile_flow_triggers
from sqlmodel import select

pytestmark = pytest.mark.no_blockbuster


def _schedule_node(node_id: str = "ScheduleTrigger-abc123", **values: Any) -> dict:
    template = {
        "cron_expression": {"value": values.get("cron", "0 8 * * 1-5")},
        "timezone": {"value": values.get("timezone", "Europe/Lisbon")},
        "catchup_policy": {"value": values.get("catchup_policy", "coalesce")},
        "share_session": {"value": values.get("share_session", False)},
    }
    return {"id": node_id, "data": {"type": "ScheduleTrigger", "node": {"template": template}}}


def _flow_data(*nodes) -> dict:
    return {"nodes": list(nodes), "edges": []}


async def _triggers(flow_id) -> list[Trigger]:
    async with session_scope() as session:
        return list((await session.exec(select(Trigger).where(Trigger.flow_id == flow_id))).all())


def test_only_trigger_nodes_are_recognised() -> None:
    data = _flow_data(
        _schedule_node(),
        {"id": "ChatInput-1", "data": {"type": "ChatInput", "node": {"template": {}}}},
        {"id": "no-data-node"},
    )
    found = find_trigger_nodes(data)
    assert [node_id for node_id, _kind, _config in found] == ["ScheduleTrigger-abc123"]
    assert found[0][1] == "schedule"
    assert found[0][2]["cron"] == "0 8 * * 1-5"


def test_missing_template_fields_fall_back_rather_than_crash() -> None:
    node = {"id": "ScheduleTrigger-x", "data": {"type": "ScheduleTrigger", "node": {}}}
    _node_id, _kind, config = find_trigger_nodes(_flow_data(node))[0]
    assert config == {"cron": "", "timezone": "UTC", "catchup_policy": "coalesce", "share_session": False}


async def test_a_new_trigger_node_creates_a_pending_row(trigger_owner, owned_flow) -> None:
    """Appearing on a canvas is not consent to start running unattended."""
    async with session_scope() as session:
        touched = await reconcile_flow_triggers(
            session, flow_id=owned_flow, owner_id=trigger_owner, flow_data=_flow_data(_schedule_node())
        )
    assert touched == 1
    rows = await _triggers(owned_flow)
    assert len(rows) == 1
    assert rows[0].state == TriggerState.PENDING.value
    assert rows[0].node_id == "ScheduleTrigger-abc123"
    assert rows[0].config["cron"] == "0 8 * * 1-5"


async def test_reconciliation_is_idempotent(trigger_owner, owned_flow) -> None:
    data = _flow_data(_schedule_node())
    async with session_scope() as session:
        await reconcile_flow_triggers(session, flow_id=owned_flow, owner_id=trigger_owner, flow_data=data)
    async with session_scope() as session:
        touched = await reconcile_flow_triggers(session, flow_id=owned_flow, owner_id=trigger_owner, flow_data=data)
    assert touched == 0
    assert len(await _triggers(owned_flow)) == 1


async def test_editing_the_schedule_updates_config_but_never_state_or_pin(trigger_owner, owned_flow) -> None:
    """The row owns state and pinning; the canvas owns configuration."""
    async with session_scope() as session:
        await reconcile_flow_triggers(
            session, flow_id=owned_flow, owner_id=trigger_owner, flow_data=_flow_data(_schedule_node())
        )
    async with session_scope() as session:
        row = (await session.exec(select(Trigger).where(Trigger.flow_id == owned_flow))).one()
        row.state = TriggerState.ACTIVE.value
        row.concurrency_limit = 7
        session.add(row)

    async with session_scope() as session:
        touched = await reconcile_flow_triggers(
            session,
            flow_id=owned_flow,
            owner_id=trigger_owner,
            flow_data=_flow_data(_schedule_node(cron="*/5 * * * *", share_session=True)),
        )

    assert touched == 1
    row = (await _triggers(owned_flow))[0]
    assert row.config["cron"] == "*/5 * * * *"
    assert row.session_policy == TriggerSessionPolicy.SHARED.value
    # The schedule changed, so the cursor is dropped and recomputed next pass.
    assert row.next_fire_at is None
    # State the owner chose is untouched by a save.
    assert row.state == TriggerState.ACTIVE.value
    assert row.concurrency_limit == 7


async def test_removing_the_node_pauses_the_trigger_rather_than_deleting_it(trigger_owner, owned_flow) -> None:
    """Delete-and-undo must not destroy the ledger."""
    async with session_scope() as session:
        await reconcile_flow_triggers(
            session, flow_id=owned_flow, owner_id=trigger_owner, flow_data=_flow_data(_schedule_node())
        )
    async with session_scope() as session:
        await reconcile_flow_triggers(session, flow_id=owned_flow, owner_id=trigger_owner, flow_data=_flow_data())

    rows = await _triggers(owned_flow)
    assert len(rows) == 1
    assert rows[0].state == TriggerState.PAUSED.value
    assert "removed" in rows[0].last_error


async def test_api_created_triggers_are_left_alone(trigger_owner, owned_flow) -> None:
    """A trigger with no node did not come from the canvas, so a save must not pause it."""
    async with session_scope() as session:
        session.add(
            Trigger(
                flow_id=owned_flow,
                user_id=trigger_owner,
                name="api made",
                kind="schedule",
                config={},
                provider_state={},
                state=TriggerState.ACTIVE.value,
                concurrency_limit=1,
                max_attempts=5,
            )
        )
    async with session_scope() as session:
        touched = await reconcile_flow_triggers(
            session, flow_id=owned_flow, owner_id=trigger_owner, flow_data=_flow_data()
        )

    assert touched == 0
    assert (await _triggers(owned_flow))[0].state == TriggerState.ACTIVE.value


async def test_two_trigger_nodes_become_two_rows(trigger_owner, owned_flow) -> None:
    async with session_scope() as session:
        touched = await reconcile_flow_triggers(
            session,
            flow_id=owned_flow,
            owner_id=trigger_owner,
            flow_data=_flow_data(_schedule_node("ScheduleTrigger-a"), _schedule_node("ScheduleTrigger-b")),
        )
    assert touched == 2
    assert {row.node_id for row in await _triggers(owned_flow)} == {"ScheduleTrigger-a", "ScheduleTrigger-b"}


async def test_a_racing_save_leaves_the_callers_transaction_usable(trigger_owner, owned_flow) -> None:
    """A duplicate insert must cost the save nothing at all.

    Two concurrent saves of one flow (an autosave PATCH racing a PUT) can both
    see no row for a newly added trigger node and both insert
    ``(flow_id, node_id)``. The loser violates ``uq_trigger_flow_node``. If the
    reconciler only swallowed that exception, the caller's session would be left
    in a failed transaction and the flow save would die at ``commit`` — a 500 on
    the user's document, caused by trigger bookkeeping. The SAVEPOINT is what
    makes the swallow honest.
    """
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.triggers.reconciliation import reconcile_flow_triggers_safely

    node = _schedule_node()

    # The winner of the race.
    async with session_scope() as session:
        await reconcile_flow_triggers_safely(
            session, flow_id=owned_flow, owner_id=trigger_owner, flow_data=_flow_data(node)
        )

    # The loser: a session that has not yet seen the winner's row, so it tries
    # the same insert, and then goes on to write the flow the user actually saved.
    async with session_scope() as session:
        session.expire_all()
        duplicate = Trigger(
            flow_id=owned_flow,
            user_id=trigger_owner,
            name="racing insert",
            kind="schedule",
            node_id=node["id"],
            config={},
            provider_state={},
            concurrency_limit=1,
            max_attempts=5,
        )

        async def _explode(*_args, **_kwargs):
            session.add(duplicate)
            await session.flush()

        # Stand in for "both savers saw no row": force the duplicate insert
        # through the same call path a real race takes.
        import langflow.services.triggers.reconciliation as reconciliation_module

        original = reconciliation_module.reconcile_flow_triggers
        reconciliation_module.reconcile_flow_triggers = _explode
        try:
            await reconcile_flow_triggers_safely(
                session, flow_id=owned_flow, owner_id=trigger_owner, flow_data=_flow_data(node)
            )
        finally:
            reconciliation_module.reconcile_flow_triggers = original

        # The save the user asked for still lands, on the same session.
        flow = await session.get(Flow, owned_flow)
        flow.name = f"{flow.name}-saved-anyway"
        session.add(flow)

    async with session_scope() as session:
        flow = await session.get(Flow, owned_flow)
    assert flow.name.endswith("-saved-anyway")
    assert len(await _triggers(owned_flow)) == 1
