"""Cron evaluation and the schedule tick producer.

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

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from lfx.log.logger import logger

from langflow.services.database.models.trigger.schemas import TriggerCatchupPolicy, TriggerState
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.triggers import leases, ledger
from langflow.services.triggers.constants import SCHEDULER_LEASE_NAME, TICK_DEDUPE_PREFIX

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.trigger.model import Trigger

SCHEDULE_KIND = "schedule"
DEFAULT_TIMEZONE = "UTC"
#: Upper bound on how many missed ticks one catch-up pass reports, so a trigger
#: that was down for a month cannot build an unbounded payload.
MAX_REPORTED_MISSED_TICKS = 100


class InvalidScheduleError(ValueError):
    """The trigger's schedule configuration cannot be evaluated."""


def _zone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or DEFAULT_TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        msg = f"Unknown timezone {name!r}"
        raise InvalidScheduleError(msg) from exc


def next_fire_time(cron_expression: str, *, timezone_name: str | None, after: datetime) -> datetime:
    """The next UTC instant this expression fires strictly after ``after``.

    ``after`` may be naive (SQLite hands back naive timestamps); it is read as
    UTC, converted into the trigger's zone for the cron walk, and the result is
    converted back. Doing the walk in local time is what makes DST correct.
    """
    try:
        from croniter import CroniterBadCronError, croniter
    except ImportError as exc:  # pragma: no cover - croniter is a langflow-base dependency
        msg = "croniter is required to evaluate schedule triggers"
        raise InvalidScheduleError(msg) from exc

    zone = _zone(timezone_name)
    reference = after if after.tzinfo is not None else after.replace(tzinfo=timezone.utc)
    local_reference = reference.astimezone(zone)
    try:
        cursor = croniter(cron_expression, local_reference)
        local_next = cursor.get_next(datetime)
    except (CroniterBadCronError, ValueError, KeyError) as exc:
        msg = f"Invalid cron expression {cron_expression!r}"
        raise InvalidScheduleError(msg) from exc
    if local_next.tzinfo is None:  # pragma: no cover - croniter preserves tzinfo
        local_next = local_next.replace(tzinfo=zone)
    return local_next.astimezone(timezone.utc)


def missed_fire_times(
    cron_expression: str,
    *,
    timezone_name: str | None,
    since: datetime,
    until: datetime,
    limit: int = MAX_REPORTED_MISSED_TICKS,
) -> list[datetime]:
    """Every fire time strictly between ``since`` and ``until`` (inclusive of ``until``)."""
    fires: list[datetime] = []
    cursor = since
    while len(fires) < limit:
        cursor = next_fire_time(cron_expression, timezone_name=timezone_name, after=cursor)
        if cursor > until:
            break
        fires.append(cursor)
    return fires


def tick_dedupe_key(scheduled_at: datetime) -> str:
    """The ledger key for one scheduled instant.

    Derived from the instant, in UTC, so two replicas computing the same tick
    produce the same key and the unique index keeps one of them.
    """
    return f"{TICK_DEDUPE_PREFIX}:{scheduled_at.astimezone(timezone.utc).isoformat()}"


def _config(trigger: Trigger) -> tuple[str, str, str]:
    config = trigger.config or {}
    cron_expression = config.get("cron")
    if not isinstance(cron_expression, str) or not cron_expression or cron_expression.isspace():
        msg = "Schedule trigger has no cron expression"
        raise InvalidScheduleError(msg)
    timezone_name = config.get("timezone") or DEFAULT_TIMEZONE
    catchup = config.get("catchup_policy") or TriggerCatchupPolicy.COALESCE.value
    return cron_expression, timezone_name, catchup


async def produce_ticks_for_trigger(
    session: AsyncSession,
    trigger: Trigger,
    *,
    now: datetime | None = None,
) -> int:
    """Append the events this schedule owes. Returns how many rows were created.

    First sight of a trigger arms it (``next_fire_at`` is computed and nothing
    fires immediately), so enabling a schedule never back-fills history.

    When ticks were missed, the ``coalesce`` policy appends ONE event keyed by
    the most recent missed instant and reports the rest in ``missed_ticks``;
    ``skip`` appends nothing and simply re-arms. Either way the replay window
    bounds how far back catch-up looks, so a week of downtime cannot produce a
    week of runs.
    """
    settings = get_settings_service().settings
    now = now or datetime.now(timezone.utc)
    cron_expression, timezone_name, catchup = _config(trigger)

    previous = trigger.next_fire_at
    if previous is None:
        trigger.next_fire_at = next_fire_time(cron_expression, timezone_name=timezone_name, after=now)
        session.add(trigger)
        await session.flush()
        return 0

    previous = previous if previous.tzinfo is not None else previous.replace(tzinfo=timezone.utc)
    if previous > now:
        return 0

    window_start = max(previous, now - timedelta(days=settings.trigger_replay_window_days))
    due = [previous] if previous >= window_start else []
    due.extend(missed_fire_times(cron_expression, timezone_name=timezone_name, since=previous, until=now))

    created = 0
    if due:
        if catchup == TriggerCatchupPolicy.SKIP.value:
            # Nothing runs; the schedule simply resumes.
            pass
        else:
            scheduled_at = due[-1]
            payload: dict[str, Any] = {
                "scheduled_at": scheduled_at.isoformat(),
                "cron": cron_expression,
                "timezone": timezone_name,
            }
            if len(due) > 1:
                payload["missed_ticks"] = [fire.isoformat() for fire in due[:-1]]
            _event, was_created = await ledger.append_event(
                session,
                trigger_id=trigger.id,
                dedupe_key=tick_dedupe_key(scheduled_at),
                payload=payload,
            )
            created = 1 if was_created else 0

    trigger.next_fire_at = next_fire_time(cron_expression, timezone_name=timezone_name, after=now)
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
