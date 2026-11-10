"""Cron semantics, DST, catch-up, and the tick producer's dedupe contract."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from langflow.services.database.models.trigger.model import Trigger, TriggerEvent
from langflow.services.database.models.trigger.schemas import TriggerCatchupPolicy, TriggerState
from langflow.services.deps import session_scope
from langflow.services.triggers import scheduler
from langflow.services.triggers.scheduler import (
    InvalidScheduleError,
    next_fire_time,
    produce_ticks,
    produce_ticks_for_trigger,
    tick_dedupe_key,
)
from sqlmodel import select

pytestmark = pytest.mark.no_blockbuster

LISBON = ZoneInfo("Europe/Lisbon")
WEEKDAYS_AT_8 = "0 8 * * 1-5"


def _utc(*args) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


def test_the_next_fire_time_is_the_local_wall_clock_converted_to_utc() -> None:
    # 2026-09-07 is a Monday; Lisbon is UTC+1 in September (WEST).
    fire = next_fire_time(WEEKDAYS_AT_8, timezone_name="Europe/Lisbon", after=_utc(2026, 9, 7, 0, 0))
    assert fire == _utc(2026, 9, 7, 7, 0)
    assert fire.astimezone(LISBON).hour == 8


def test_the_schedule_holds_its_local_hour_across_the_dst_change() -> None:
    """The user asked for 08:00 Lisbon; the UTC instant moves, the local hour does not.

    Lisbon leaves summer time on 2026-10-25, so the same expression fires at
    07:00Z before the change and 08:00Z after it.
    """
    before = next_fire_time(WEEKDAYS_AT_8, timezone_name="Europe/Lisbon", after=_utc(2026, 10, 22, 12, 0))
    after = next_fire_time(WEEKDAYS_AT_8, timezone_name="Europe/Lisbon", after=_utc(2026, 10, 27, 12, 0))

    assert before.hour == 7
    assert after.hour == 8
    assert before.astimezone(LISBON).hour == after.astimezone(LISBON).hour == 8


def test_a_spring_forward_gap_still_produces_a_fire_time() -> None:
    """02:30 does not exist on the spring-forward night; the schedule must not stall."""
    fire = next_fire_time("30 2 * * *", timezone_name="Europe/Lisbon", after=_utc(2026, 3, 28, 12, 0))
    assert fire > _utc(2026, 3, 28, 12, 0)


def test_the_weekend_is_skipped() -> None:
    friday_evening = _utc(2026, 9, 11, 18, 0)
    assert next_fire_time(WEEKDAYS_AT_8, timezone_name="Europe/Lisbon", after=friday_evening).weekday() == 0


def test_an_unknown_timezone_or_expression_is_a_typed_error() -> None:
    with pytest.raises(InvalidScheduleError):
        next_fire_time(WEEKDAYS_AT_8, timezone_name="Europe/Atlantis", after=_utc(2026, 9, 7))
    with pytest.raises(InvalidScheduleError):
        next_fire_time("not a cron", timezone_name="UTC", after=_utc(2026, 9, 7))


def test_the_dedupe_key_comes_from_the_scheduled_instant_not_the_wall_clock() -> None:
    """Two replicas computing the same tick must produce the same key."""
    scheduled = _utc(2026, 9, 7, 7, 0)
    assert tick_dedupe_key(scheduled) == tick_dedupe_key(scheduled.astimezone(LISBON))
    assert tick_dedupe_key(scheduled) != tick_dedupe_key(scheduled + timedelta(minutes=1))


async def _events(trigger_id) -> list[TriggerEvent]:
    async with session_scope() as session:
        return list((await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == trigger_id))).all())


def _schedule_config(**overrides) -> dict:
    config = {"cron": WEEKDAYS_AT_8, "timezone": "Europe/Lisbon", "catchup_policy": "coalesce"}
    config.update(overrides)
    return config


async def test_arming_a_schedule_never_back_fills_history(make_trigger) -> None:
    trigger_id = await make_trigger(config=_schedule_config())
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        created = await produce_ticks_for_trigger(session, trigger, now=_utc(2026, 9, 7, 12, 0))
        armed_at = trigger.next_fire_at

    assert created == 0
    assert armed_at is not None
    assert await _events(trigger_id) == []


async def test_a_due_tick_appends_exactly_one_event(make_trigger) -> None:
    trigger_id = await make_trigger(config=_schedule_config())
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        trigger.next_fire_at = _utc(2026, 9, 7, 7, 0)
        created = await produce_ticks_for_trigger(session, trigger, now=_utc(2026, 9, 7, 7, 0, 30))

    assert created == 1
    events = await _events(trigger_id)
    assert len(events) == 1
    assert events[0].dedupe_key == tick_dedupe_key(_utc(2026, 9, 7, 7, 0))
    assert events[0].payload["scheduled_at"] == _utc(2026, 9, 7, 7, 0).isoformat()


async def test_a_second_replica_producing_the_same_tick_adds_nothing(make_trigger) -> None:
    trigger_id = await make_trigger(config=_schedule_config())
    for _pass in range(2):
        async with session_scope() as session:
            trigger = await session.get(Trigger, trigger_id)
            trigger.next_fire_at = _utc(2026, 9, 7, 7, 0)
            await produce_ticks_for_trigger(session, trigger, now=_utc(2026, 9, 7, 7, 0, 30))

    assert len(await _events(trigger_id)) == 1


async def test_downtime_coalesces_missed_ticks_into_one_run_that_reports_the_rest(make_trigger) -> None:
    """The documented catch-up behaviour: one run, and a record of what was missed."""
    trigger_id = await make_trigger(config=_schedule_config())
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        trigger.next_fire_at = _utc(2026, 9, 7, 7, 0)  # Monday
        created = await produce_ticks_for_trigger(session, trigger, now=_utc(2026, 9, 10, 12, 0))  # Thursday

    assert created == 1
    events = await _events(trigger_id)
    assert len(events) == 1
    payload = events[0].payload
    # Monday through Thursday morning: Thursday runs, Monday-Wednesday are reported.
    assert payload["scheduled_at"] == _utc(2026, 9, 10, 7, 0).isoformat()
    assert len(payload["missed_ticks"]) == 3


async def test_the_skip_policy_runs_nothing_and_simply_re_arms(make_trigger) -> None:
    trigger_id = await make_trigger(config=_schedule_config(catchup_policy=TriggerCatchupPolicy.SKIP.value))
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        trigger.next_fire_at = _utc(2026, 9, 7, 7, 0)
        created = await produce_ticks_for_trigger(session, trigger, now=_utc(2026, 9, 10, 12, 0))
        rearmed = trigger.next_fire_at

    assert created == 0
    assert await _events(trigger_id) == []
    assert rearmed > _utc(2026, 9, 10, 12, 0)


async def test_catch_up_never_reaches_past_the_replay_window(make_trigger) -> None:
    """Two months of downtime produce one run, dated inside the window.

    The bound is the window, not just the report size: an event stamped with a
    ``scheduled_at`` from eight weeks ago would hand the flow a fire time older
    than any row the ledger still keeps.
    """
    from langflow.services.deps import get_settings_service

    window_days = get_settings_service().settings.trigger_replay_window_days
    trigger_id = await make_trigger(config=_schedule_config(cron="0 * * * *"))
    now = datetime.now(timezone.utc)
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        trigger.next_fire_at = now - timedelta(days=60)
        created = await produce_ticks_for_trigger(session, trigger, now=now)

    assert created == 1
    events = await _events(trigger_id)
    reported = events[0].payload.get("missed_ticks", [])
    assert len(reported) <= scheduler.MAX_REPORTED_MISSED_TICKS

    window_start = now - timedelta(days=window_days)
    scheduled_at = datetime.fromisoformat(events[0].payload["scheduled_at"])
    assert scheduled_at >= window_start
    assert all(datetime.fromisoformat(fire) >= window_start for fire in reported)


async def test_a_broken_schedule_stops_itself_instead_of_erroring_every_poll(make_trigger) -> None:
    trigger_id = await make_trigger(config={"cron": "not a cron", "timezone": "UTC"})
    async with session_scope() as session:
        await produce_ticks(session)
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)

    assert trigger.state == TriggerState.ERROR.value
    assert "Invalid cron expression" in trigger.last_error


async def test_only_active_schedules_produce_ticks(make_trigger) -> None:
    paused_id = await make_trigger(state=TriggerState.PAUSED.value, config=_schedule_config())
    async with session_scope() as session:
        trigger = await session.get(Trigger, paused_id)
        trigger.next_fire_at = _utc(2026, 9, 7, 7, 0)
        session.add(trigger)
    async with session_scope() as session:
        await produce_ticks(session, now=_utc(2026, 9, 10, 12, 0))

    assert await _events(paused_id) == []
