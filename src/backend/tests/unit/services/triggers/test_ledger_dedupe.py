"""The ledger's deduplication guarantee, exercised through the append path."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from langflow.services.database.models.trigger.model import TriggerEvent
from langflow.services.database.models.trigger.schemas import TriggerEventState
from langflow.services.deps import session_scope
from langflow.services.triggers import ledger
from langflow.services.triggers.errors import ReplayWindowExpiredError
from sqlmodel import select

pytestmark = pytest.mark.no_blockbuster


async def test_the_same_dedupe_key_yields_one_row(make_trigger) -> None:
    """A duplicate tick is collapsed by the database, and the original is returned."""
    trigger_id = await make_trigger()
    async with session_scope() as session:
        first, created_first = await ledger.append_event(
            session, trigger_id=trigger_id, dedupe_key="tick:2026-09-05T08:00:00+00:00", payload={"n": 1}
        )
        first_id = first.id
    async with session_scope() as session:
        second, created_second = await ledger.append_event(
            session, trigger_id=trigger_id, dedupe_key="tick:2026-09-05T08:00:00+00:00", payload={"n": 2}
        )
        second_id, second_payload = second.id, second.payload

    assert created_first is True
    assert created_second is False
    assert second_id == first_id
    # The FIRST delivery's payload wins; a redelivery must not rewrite history.
    assert second_payload == {"n": 1}

    async with session_scope() as session:
        rows = (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == trigger_id))).all()
    assert len(rows) == 1


async def test_the_transaction_survives_a_collapsed_duplicate(make_trigger) -> None:
    """A duplicate must not poison the caller's transaction.

    Regression guard: the IntegrityError is absorbed in a SAVEPOINT, so a
    producer that appends several events in one transaction keeps the ones that
    are new when one of them is a redelivery.
    """
    trigger_id = await make_trigger()
    async with session_scope() as session:
        await ledger.append_event(session, trigger_id=trigger_id, dedupe_key="a")

    async with session_scope() as session:
        _existing, created_duplicate = await ledger.append_event(session, trigger_id=trigger_id, dedupe_key="a")
        _fresh, created_fresh = await ledger.append_event(session, trigger_id=trigger_id, dedupe_key="b")

    assert created_duplicate is False
    assert created_fresh is True

    async with session_scope() as session:
        rows = (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == trigger_id))).all()
    assert {row.dedupe_key for row in rows} == {"a", "b"}


async def test_two_triggers_may_share_a_dedupe_key(make_trigger) -> None:
    """Dedupe is scoped per trigger; two schedules firing at 08:00 are two events."""
    first_id = await make_trigger(name="first")
    second_id = await make_trigger(name="second")
    async with session_scope() as session:
        _, created_first = await ledger.append_event(session, trigger_id=first_id, dedupe_key="tick:08:00")
        _, created_second = await ledger.append_event(session, trigger_id=second_id, dedupe_key="tick:08:00")
    assert created_first is True
    assert created_second is True


async def test_replay_links_a_new_row_and_never_rewinds_the_original(make_trigger) -> None:
    trigger_id = await make_trigger()
    async with session_scope() as session:
        original, _ = await ledger.append_event(
            session, trigger_id=trigger_id, dedupe_key="delivery:1", payload={"body": "x"}
        )
        original.state = TriggerEventState.COMPLETED.value
        session.add(original)
        original_id = original.id

    async with session_scope() as session:
        replay = await ledger.replay_event(session, trigger_id=trigger_id, event_id=original_id, replay_window_days=7)
        replay_id, replay_payload, replay_state = replay.id, replay.payload, replay.state

    assert replay_id != original_id
    assert replay_payload == {"body": "x"}
    assert replay_state == TriggerEventState.PENDING.value

    async with session_scope() as session:
        untouched = await session.get(TriggerEvent, original_id)
        assert untouched.state == TriggerEventState.COMPLETED.value
        second_replay = await ledger.replay_event(
            session, trigger_id=trigger_id, event_id=original_id, replay_window_days=7
        )
        assert second_replay.id not in {original_id, replay_id}


async def test_replay_outside_the_window_is_refused(make_trigger) -> None:
    trigger_id = await make_trigger()
    async with session_scope() as session:
        old, _ = await ledger.append_event(session, trigger_id=trigger_id, dedupe_key="ancient")
        old.created_at = datetime.now(timezone.utc) - timedelta(days=30)
        session.add(old)
        old_id = old.id

    async with session_scope() as session:
        with pytest.raises(ReplayWindowExpiredError):
            await ledger.replay_event(session, trigger_id=trigger_id, event_id=old_id, replay_window_days=7)


async def test_purge_removes_only_old_terminal_rows(make_trigger) -> None:
    """Pending work is never purged, however old the row looks."""
    trigger_id = await make_trigger()
    stale = datetime.now(timezone.utc) - timedelta(days=45)
    async with session_scope() as session:
        old_done, _ = await ledger.append_event(session, trigger_id=trigger_id, dedupe_key="old-done")
        old_done.state = TriggerEventState.COMPLETED.value
        old_done.created_at = stale
        old_pending, _ = await ledger.append_event(session, trigger_id=trigger_id, dedupe_key="old-pending")
        old_pending.created_at = stale
        recent_done, _ = await ledger.append_event(session, trigger_id=trigger_id, dedupe_key="recent-done")
        recent_done.state = TriggerEventState.COMPLETED.value
        session.add(old_done)
        session.add(old_pending)
        session.add(recent_done)

    async with session_scope() as session:
        removed = await ledger.purge_events(session, retention_days=30)

    assert removed == 1
    async with session_scope() as session:
        remaining = (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == trigger_id))).all()
    assert {row.dedupe_key for row in remaining} == {"old-pending", "recent-done"}
