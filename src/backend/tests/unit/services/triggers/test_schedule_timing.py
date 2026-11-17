"""Schedules that one cron cannot express: several crons, a minute interval, and a single run."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from itertools import pairwise

import pytest
from langflow.services.database.models.trigger.model import Trigger, TriggerEvent
from langflow.services.database.models.trigger.schemas import TriggerState
from langflow.services.deps import get_trigger_service, session_scope
from langflow.services.triggers.reconciliation import reconcile_flow_triggers
from langflow.services.triggers.schedule_config import (
    InvalidScheduleError,
    schedule_timing_changed,
    validate_schedule_config,
)
from langflow.services.triggers.scheduler import produce_ticks_for_trigger, schedule_clock
from sqlmodel import select

pytestmark = pytest.mark.no_blockbuster


def _utc(*args) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


def _config(**timing) -> dict:
    return {"timezone": "Europe/Lisbon", "catchup_policy": "coalesce", **timing}


@pytest.mark.parametrize(
    ("timing", "normalized"),
    [
        ({"crons": ["0  8 * * *", "30 18 * * *"]}, {"crons": ["0 8 * * *", "30 18 * * *"]}),
        ({"interval_minutes": 7}, {"interval_minutes": 7}),
        ({"run_at": "2026-12-24 18:30"}, {"run_at": "2026-12-24T18:30"}),
    ],
)
def test_each_timing_is_accepted_and_normalized(timing, normalized) -> None:
    config = validate_schedule_config(_config(**timing))

    assert {key: config[key] for key in normalized} == normalized


@pytest.mark.parametrize(
    ("timing", "message"),
    [
        ({"crons": []}, "at least one cron"),
        ({"crons": ["0 8 * * *", "bad"]}, "Invalid cron expression"),
        ({"crons": "0 8 * * *"}, "at least one cron"),
        ({"interval_minutes": 0}, "whole number of minutes"),
        ({"interval_minutes": 44641}, "whole number of minutes"),
        ({"interval_minutes": True}, "whole number of minutes"),
        ({"interval_minutes": "7"}, "whole number of minutes"),
        ({"run_at": "soon"}, "date and time"),
        ({"run_at": "2026-12-24T18:30+01:00"}, "date and time"),
        ({"cron": "0 8 * * *", "interval_minutes": 5}, "only one of"),
        ({}, "Invalid cron expression"),
        ({"cron": ""}, "Invalid cron expression"),
    ],
)
def test_an_unusable_timing_is_refused_with_its_reason(timing, message) -> None:
    with pytest.raises(InvalidScheduleError, match=message):
        validate_schedule_config(_config(**timing))


def test_changing_the_interval_or_the_date_resets_the_next_run() -> None:
    assert schedule_timing_changed(_config(interval_minutes=7), _config(interval_minutes=8))
    assert schedule_timing_changed(_config(cron="0 8 * * *"), _config(crons=["0 8 * * *", "0 9 * * *"]))
    assert schedule_timing_changed(_config(run_at="2026-12-24T18:30"), _config(run_at="2026-12-25T18:30"))
    assert not schedule_timing_changed(
        _config(interval_minutes=7), {**_config(interval_minutes=7), "share_session": True}
    )


def test_several_crons_fire_at_each_of_their_times() -> None:
    clock = schedule_clock(validate_schedule_config(_config(crons=["0 8 * * *", "30 18 * * *"])))

    # Lisbon is UTC+0 in December.
    first = clock.next_after(_utc(2026, 12, 1, 9, 0))
    second = clock.next_after(first)

    assert first == _utc(2026, 12, 1, 18, 30)
    assert second == _utc(2026, 12, 2, 8, 0)
    assert clock.latest_at(_utc(2026, 12, 2, 12, 0)) == _utc(2026, 12, 2, 8, 0)


def test_an_interval_fires_every_n_minutes_without_resetting_at_the_hour() -> None:
    clock = schedule_clock(validate_schedule_config(_config(interval_minutes=7)))

    fires = [clock.next_after(_utc(2026, 12, 1, 9, 55))]
    for _step in range(3):
        fires.append(clock.next_after(fires[-1]))

    assert {later - earlier for earlier, later in pairwise(fires)} == {timedelta(minutes=7)}
    assert clock.latest_at(fires[2] + timedelta(minutes=3)) == fires[2]


def test_once_fires_at_its_local_moment_and_never_again() -> None:
    clock = schedule_clock(validate_schedule_config(_config(run_at="2026-07-01T18:30")))

    # Lisbon is UTC+1 in July.
    assert clock.next_after(_utc(2026, 7, 1, 0, 0)) == _utc(2026, 7, 1, 17, 30)
    assert clock.next_after(_utc(2026, 7, 1, 17, 30)) is None
    assert clock.latest_at(_utc(2026, 7, 1, 17, 0)) is None


async def _events(trigger_id) -> list[TriggerEvent]:
    async with session_scope() as session:
        return list((await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == trigger_id))).all())


async def _tick(trigger_id, now: datetime) -> int:
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        return await produce_ticks_for_trigger(session, trigger, now=now)


async def test_a_once_schedule_runs_a_single_time(make_trigger) -> None:
    trigger_id = await make_trigger(config=_config(run_at="2026-12-24T18:30"))

    await _tick(trigger_id, _utc(2026, 12, 24, 18, 0))
    fired = await _tick(trigger_id, _utc(2026, 12, 24, 18, 30, 5))
    later = [await _tick(trigger_id, _utc(2026, 12, 24, 18, 31)), await _tick(trigger_id, _utc(2027, 12, 24, 18, 31))]

    assert fired == 1
    assert later == [0, 0]
    [event] = await _events(trigger_id)
    assert event.payload["scheduled_at"] == _utc(2026, 12, 24, 18, 30).isoformat()
    assert event.payload["run_at"] == "2026-12-24T18:30"


async def test_an_interval_schedule_runs_at_each_step(make_trigger) -> None:
    trigger_id = await make_trigger(config=_config(interval_minutes=7))
    start = _utc(2026, 12, 1, 9, 0)

    await _tick(trigger_id, start)
    fired = [await _tick(trigger_id, start + timedelta(minutes=minute, seconds=5)) for minute in range(1, 22)]

    assert sum(fired) == 3
    events = sorted(await _events(trigger_id), key=lambda event: event.payload["scheduled_at"])
    instants = [datetime.fromisoformat(event.payload["scheduled_at"]) for event in events]
    assert {later - earlier for earlier, later in pairwise(instants)} == {timedelta(minutes=7)}
    assert events[0].payload["interval_minutes"] == 7


def _once_node(run_at: str) -> dict:
    template = {
        "schedule_type": {"value": "Once"},
        "run_at": {"value": run_at},
        "cron_expression": {"value": "0 8 * * 1-5"},
        "timezone": {"value": "Europe/Lisbon"},
    }
    return {"id": "ScheduleTrigger-once", "data": {"type": "ScheduleTrigger", "node": {"template": template}}}


async def _reconcile_once(trigger_owner, owned_flow, run_at: str) -> Trigger:
    async with session_scope() as session:
        await reconcile_flow_triggers(
            session, flow_id=owned_flow, owner_id=trigger_owner, flow_data={"nodes": [_once_node(run_at)], "edges": []}
        )
    async with session_scope() as session:
        return (await session.exec(select(Trigger).where(Trigger.flow_id == owned_flow))).one()


async def test_enabling_a_once_schedule_in_the_past_is_refused(trigger_owner, owned_flow) -> None:
    row = await _reconcile_once(trigger_owner, owned_flow, "2020-01-01T08:00")

    assert row.name == "Schedule once at 2020-01-01T08:00"
    async with session_scope() as session:
        with pytest.raises(ValueError, match="already passed"):
            await get_trigger_service().enable(session, row=await session.get(Trigger, row.id))


async def test_enabling_a_future_once_schedule_arms_it(trigger_owner, owned_flow) -> None:
    run_at = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M")
    row = await _reconcile_once(trigger_owner, owned_flow, run_at)

    async with session_scope() as session:
        enabled = await get_trigger_service().enable(session, row=await session.get(Trigger, row.id))

    assert enabled.state == TriggerState.ACTIVE.value
