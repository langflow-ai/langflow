"""Schedule polling preserves current ticks and isolates bad configuration."""

from datetime import datetime, timedelta, timezone

import pytest
from langflow.services.database.models.trigger.model import Trigger, TriggerEvent
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.triggers.scheduler import MAX_REPORTED_MISSED_TICKS, produce_ticks, produce_ticks_for_trigger
from sqlmodel import select

pytestmark = pytest.mark.no_blockbuster
NOW = datetime(2026, 9, 14, 12, tzinfo=timezone.utc)


@pytest.mark.parametrize("delay", [0, 1, 4])
async def test_skip_still_emits_the_current_tick_with_normal_poll_latency(make_trigger, delay):
    trigger_id = await make_trigger(
        config={"cron": "* * * * *", "timezone": "UTC", "catchup_policy": "skip"}, next_fire_at=NOW
    )
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        assert await produce_ticks_for_trigger(session, trigger, now=NOW + timedelta(seconds=delay)) == 1
        assert await produce_ticks_for_trigger(session, trigger, now=NOW + timedelta(seconds=delay)) == 0
        event = (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == trigger_id))).one()
        assert event.payload["scheduled_at"] == NOW.isoformat()
        assert "missed_ticks" not in event.payload


@pytest.mark.parametrize("policy", ["coalesce", "skip"])
async def test_long_backlog_selects_the_latest_tick_independent_of_report_limit(make_trigger, policy):
    trigger_id = await make_trigger(
        config={"cron": "* * * * *", "timezone": "UTC", "catchup_policy": policy}, next_fire_at=NOW - timedelta(days=2)
    )
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        assert await produce_ticks_for_trigger(session, trigger, now=NOW) == 1
        event = (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == trigger_id))).one()
        assert event.payload["scheduled_at"] == NOW.isoformat()
        assert trigger.next_fire_at == NOW + timedelta(minutes=1)
        reported = event.payload.get("missed_ticks", [])
        assert len(reported) == (MAX_REPORTED_MISSED_TICKS if policy == "coalesce" else 0)
        assert all(datetime.fromisoformat(tick) < NOW for tick in reported)


@pytest.mark.parametrize(
    "invalid",
    [
        {"timezone": 42},
        {"timezone": False},
        {"timezone": []},
        {"timezone": ""},
        {"timezone": None},
        {"cron": "* * * * * *"},
        {"cron": 42},
        {"cron": "0 0 31 2 *"},
        {"catchup_policy": "invalid"},
        {"catchup_policy": False},
        {"catchup_policy": []},
    ],
)
async def test_invalid_schedule_stops_only_itself(make_trigger, invalid):
    bad_id = await make_trigger(config={"cron": "* * * * *", "timezone": "UTC", **invalid})
    good_id = await make_trigger(config={"cron": "* * * * *", "timezone": "UTC"}, next_fire_at=NOW)
    async with session_scope() as session:
        assert await produce_ticks(session, now=NOW) == 1
        bad = await session.get(Trigger, bad_id)
        assert bad.state == "error"
        assert bad.last_error
        assert (await session.get(Trigger, good_id)).state == "active"


async def test_skip_drops_ticks_older_than_the_normal_poll_window(make_trigger):
    delay = get_settings_service().settings.trigger_dispatcher_poll_interval_s + 1
    trigger_id = await make_trigger(
        config={"cron": "0 * * * *", "timezone": "UTC", "catchup_policy": "skip"}, next_fire_at=NOW
    )
    async with session_scope() as session:
        assert (
            await produce_ticks_for_trigger(
                session, await session.get(Trigger, trigger_id), now=NOW + timedelta(seconds=delay)
            )
            == 0
        )
        assert not (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == trigger_id))).all()
