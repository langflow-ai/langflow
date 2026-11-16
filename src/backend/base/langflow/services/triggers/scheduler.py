"""Schedule evaluation and the tick producer.

Two ideas do the work here.

**Fire times are computed in the trigger's own timezone**, then converted to
UTC. That is what makes "every weekday at 08:00 Europe/Lisbon" keep firing at
08:00 local across a daylight-saving change instead of drifting by an hour: the
wall-clock schedule is the user's intent, and UTC is only the storage format.

**The dedupe key is the scheduled instant, never the wall clock.** Two replicas
that both compute the 08:00 tick produce the same key, and the ledger's unique
index collapses them into one event. Deriving the key from ``now`` would defeat
that and double every run — the exact failure the epic forbids.

``croniter`` lives in langflow-base only. The lfx component validates the
expression syntactically; this module is the single place cron *semantics* are
decided, so swapping the library later touches one file.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from lfx.log.logger import logger

from langflow.services.database.models.trigger.schemas import TriggerCatchupPolicy, TriggerState
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.triggers import leases, ledger
from langflow.services.triggers.constants import SCHEDULER_LEASE_NAME, TICK_DEDUPE_PREFIX
from langflow.services.triggers.schedule_config import (
    DEFAULT_TIMEZONE,
    TIMING_KEYS,
    InvalidScheduleError,
    run_at_instant,
    validate_schedule_config,
)

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.trigger.model import Trigger

SCHEDULE_KIND = "schedule"
#: Upper bound on how many missed ticks one catch-up pass reports, so a trigger
#: that was down for a month cannot build an unbounded payload.
MAX_REPORTED_MISSED_TICKS = 100


def _zone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or DEFAULT_TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError, TypeError) as exc:
        msg = f"Unknown timezone {name!r}"
        raise InvalidScheduleError(msg) from exc


def next_fire_time(cron_expression: str, *, timezone_name: str | None, after: datetime) -> datetime:
    """The next UTC instant this expression fires strictly after ``after``.

    ``after`` may be naive (SQLite hands back naive timestamps); it is read as
    UTC, converted into the trigger's zone for the cron walk, and the result is
    converted back. Doing the walk in local time is what makes DST correct.
    """
    try:
        from croniter import CroniterError, croniter
    except ImportError as exc:  # pragma: no cover - croniter is a langflow-base dependency
        msg = "croniter is required to evaluate schedule triggers"
        raise InvalidScheduleError(msg) from exc

    validate_schedule_config({"cron": cron_expression, "timezone": timezone_name or DEFAULT_TIMEZONE})
    zone = _zone(timezone_name)
    reference = after if after.tzinfo is not None else after.replace(tzinfo=timezone.utc)
    local_reference = reference.astimezone(zone)
    try:
        cursor = croniter(cron_expression, local_reference)
        local_next = cursor.get_next(datetime)
    except (CroniterError, ValueError, KeyError, OverflowError) as exc:
        msg = f"Invalid cron expression {cron_expression!r}"
        raise InvalidScheduleError(msg) from exc
    if local_next.tzinfo is None:  # pragma: no cover - croniter preserves tzinfo
        local_next = local_next.replace(tzinfo=zone)
    return local_next.astimezone(timezone.utc)


def latest_fire_time(cron_expression: str, *, timezone_name: str, at: datetime) -> datetime:
    """Find the latest due instant without walking or truncating a backlog."""
    from croniter import CroniterError, croniter

    try:
        reference = (at + timedelta(microseconds=1)).astimezone(_zone(timezone_name))
        return croniter(cron_expression, reference).get_prev(datetime).astimezone(timezone.utc)
    except (CroniterError, ValueError, KeyError, OverflowError) as exc:
        msg = "Invalid cron expression: no prior fire time could be evaluated."
        raise InvalidScheduleError(msg) from exc


def tick_dedupe_key(scheduled_at: datetime) -> str:
    """The ledger key for one scheduled instant.

    Derived from the instant, in UTC, so two replicas computing the same tick
    produce the same key and the unique index keeps one of them.
    """
    return f"{TICK_DEDUPE_PREFIX}:{scheduled_at.astimezone(timezone.utc).isoformat()}"


def _as_utc(moment: datetime) -> datetime:
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class ScheduleClock:
    """When a validated schedule fires, whatever its timing key.

    ``next_after`` and ``latest_at`` return None when the schedule has no such
    fire time: a run-once schedule before its moment, or after it.
    """

    config: dict[str, Any]

    @property
    def zone(self) -> str:
        return self.config["timezone"]

    @property
    def timing(self) -> dict[str, Any]:
        return {key: self.config[key] for key in TIMING_KEYS if key in self.config}

    def _crons(self) -> list[str]:
        return [self.config["cron"]] if "cron" in self.config else list(self.config.get("crons") or [])

    def _interval(self) -> tuple[datetime, timedelta]:
        # A fixed local origin keeps every replica on the same grid, and keeps
        # intervals that divide a day on round local times (every 60 -> :00).
        origin = datetime(2000, 1, 1, tzinfo=_zone(self.zone)).astimezone(timezone.utc)
        return origin, timedelta(minutes=self.config["interval_minutes"])

    def next_after(self, after: datetime) -> datetime | None:
        after = _as_utc(after)
        if "interval_minutes" in self.config:
            origin, step = self._interval()
            return origin + step * ((after - origin) // step + 1)
        if "run_at" in self.config:
            moment = run_at_instant(self.config)
            return moment if moment > after else None
        return min(next_fire_time(cron, timezone_name=self.zone, after=after) for cron in self._crons())

    def latest_at(self, at: datetime) -> datetime | None:
        at = _as_utc(at)
        if "interval_minutes" in self.config:
            origin, step = self._interval()
            return origin + step * ((at - origin) // step)
        if "run_at" in self.config:
            moment = run_at_instant(self.config)
            return moment if moment <= at else None
        return max(latest_fire_time(cron, timezone_name=self.zone, at=at) for cron in self._crons())

    def fires_between(self, since: datetime, until: datetime, limit: int = MAX_REPORTED_MISSED_TICKS) -> list[datetime]:
        """Every fire time strictly after ``since`` and up to ``until``."""
        fires: list[datetime] = []
        cursor: datetime | None = since
        while len(fires) < limit:
            cursor = self.next_after(cursor)
            if cursor is None or cursor > until:
                break
            fires.append(cursor)
        return fires


def schedule_clock(config: dict[str, Any]) -> ScheduleClock:
    """The clock of a schedule config that :func:`validate_schedule_config` returned."""
    return ScheduleClock(config)


async def produce_ticks_for_trigger(
    session: AsyncSession,
    trigger: Trigger,
    *,
    now: datetime | None = None,
) -> int:
    """Append the events this schedule owes. Returns how many rows were created.

    First sight of a trigger arms it (``next_fire_at`` is computed and nothing
    fires immediately), so enabling a schedule never back-fills history. A
    run-once schedule whose moment has passed has no next fire and stays unarmed.

    When ticks were missed, the ``coalesce`` policy appends ONE event keyed by
    the most recent missed instant and reports the rest in ``missed_ticks``;
    ``skip`` drops missed ticks, but still emits an ordinary tick due within
    one polling interval. Either way the replay window
    bounds how far back catch-up looks, so a week of downtime cannot produce a
    week of runs.
    """
    settings = get_settings_service().settings
    now = _as_utc(now or datetime.now(timezone.utc))
    config = validate_schedule_config(trigger.config or {})
    clock = schedule_clock(config)
    catchup = config["catchup_policy"]

    previous = trigger.next_fire_at
    if previous is None:
        trigger.next_fire_at = clock.next_after(now)
        if trigger.next_fire_at is not None:
            session.add(trigger)
            await session.flush()
        return 0

    previous = _as_utc(previous)
    if previous > now:
        return 0

    # The window bounds the WHOLE catch-up, not just its first entry: a month of
    # downtime on an hourly cron must not stamp an event with a fire time weeks
    # in the past, so the walk starts at the window, not at the stale cursor.
    window_start = max(previous, now - timedelta(days=settings.trigger_replay_window_days))
    scheduled_at = clock.latest_at(now)
    created = 0
    on_time = scheduled_at is not None and now - scheduled_at <= timedelta(
        seconds=settings.trigger_dispatcher_poll_interval_s
    )
    if (
        scheduled_at is not None
        and scheduled_at >= window_start
        and (catchup != TriggerCatchupPolicy.SKIP.value or on_time)
    ):
        payload: dict[str, Any] = {
            "scheduled_at": scheduled_at.isoformat(),
            **clock.timing,
            "timezone": clock.zone,
        }
        if catchup == TriggerCatchupPolicy.COALESCE.value:
            missed = clock.fires_between(
                window_start - timedelta(microseconds=1), scheduled_at - timedelta(microseconds=1)
            )
            if missed:
                payload["missed_ticks"] = [fire.isoformat() for fire in missed]
        _event, was_created = await ledger.append_event(
            session, trigger_id=trigger.id, dedupe_key=tick_dedupe_key(scheduled_at), payload=payload
        )
        created = 1 if was_created else 0

    trigger.next_fire_at = clock.next_after(now)
    session.add(trigger)
    await session.flush()
    return created


async def produce_ticks(session: AsyncSession, *, now: datetime | None = None) -> int:
    """One pass over every armed schedule trigger."""
    from langflow.services.deps import get_trigger_service

    service = get_trigger_service()
    created = 0
    for trigger in await service.list_active(session, kind=SCHEDULE_KIND):
        try:
            created += await produce_ticks_for_trigger(session, trigger, now=now)
        except InvalidScheduleError as exc:
            # A broken schedule stops itself and says why, rather than raising
            # once per poll forever.
            trigger.state = TriggerState.ERROR.value
            trigger.last_error = str(exc)
            session.add(trigger)
            await session.flush()
            await logger.awarning("Schedule trigger %s disabled: %s", trigger.id, exc)
    return created


async def run_scheduler_pass(*, owner: str) -> int:
    """Take the scheduler lease and, when held, produce this pass's ticks."""
    settings = get_settings_service().settings
    async with session_scope() as session:
        held = await leases.acquire(
            session,
            name=SCHEDULER_LEASE_NAME,
            owner=owner,
            ttl_s=settings.trigger_lease_ttl_s,
        )
    if not held:
        return 0
    async with session_scope() as session:
        return await produce_ticks(session)
