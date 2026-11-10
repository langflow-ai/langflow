"""One busy trigger must not starve every other trigger on the instance.

The per-trigger concurrency cap and the candidate scan are the same mechanism
seen from two sides. If the scan picks events first and applies the cap
afterwards, a trigger sitting at its cap with a large backlog owns the whole
candidate window: all of its rows are unclaimable, and a second trigger's event
never enters the window at all. These tests pin the other behaviour — the scan
chooses triggers, and each one contributes only its remaining headroom.
"""

from __future__ import annotations

import pytest
from langflow.services.database.models.trigger.model import TriggerEvent
from langflow.services.database.models.trigger.schemas import TriggerEventState
from langflow.services.deps import session_scope
from langflow.services.triggers import dispatcher, ledger

pytestmark = pytest.mark.no_blockbuster

BACKLOG = 60


async def _append(trigger_id, dedupe_key: str):
    async with session_scope() as session:
        event, _ = await ledger.append_event(session, trigger_id=trigger_id, dedupe_key=dedupe_key)
        return event.id


async def test_a_backlogged_trigger_at_its_cap_does_not_starve_another(
    make_trigger,
    fake_background_service,  # noqa: ARG001 - installs the recorder the dispatcher submits into
) -> None:
    """The classic head-of-line block: a burst on A, one event on B."""
    busy = await make_trigger(name="busy", concurrency_limit=1)
    quiet = await make_trigger(name="quiet", concurrency_limit=1)

    # A backlog larger than one poll's batch, appended first so every row of it
    # is older than the quiet trigger's single event.
    for index in range(BACKLOG):
        await _append(busy, f"busy:{index}")
    quiet_event = await _append(quiet, "quiet:0")

    # First pass: the busy trigger contributes exactly its cap (1), and the
    # quiet trigger's event is dispatched in the SAME pass rather than waiting
    # for the backlog to drain.
    assert await dispatcher.run_once(owner="solo") == 2

    async with session_scope() as session:
        row = await session.get(TriggerEvent, quiet_event)
    assert row.state == TriggerEventState.DISPATCHED.value

    # And the busy trigger really is capped: one in flight, the rest pending.
    async with session_scope() as session:
        from sqlmodel import select

        busy_rows = (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == busy))).all()
    dispatched = [row for row in busy_rows if row.state == TriggerEventState.DISPATCHED.value]
    assert len(dispatched) == 1
    assert len(busy_rows) == BACKLOG


async def test_one_pass_never_claims_more_than_a_triggers_headroom(make_trigger, fake_background_service) -> None:
    """Headroom is cap minus what is already in flight, not cap per pass."""
    trigger_id = await make_trigger(concurrency_limit=3)
    for index in range(10):
        await _append(trigger_id, f"e:{index}")

    assert await dispatcher.run_once(owner="solo") == 3
    assert len(fake_background_service.submits) == 3
    # Still at the cap, so a second pass adds nothing.
    assert await dispatcher.run_once(owner="solo") == 0
