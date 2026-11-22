"""Schedule validation shared by API writes, canvas reconciliation, and ticks.

A schedule's timing is exactly one of:

* ``cron`` -- one five-field cron expression;
* ``crons`` -- several, firing at each of their times;
* ``interval_minutes`` -- a whole number of minutes between runs;
* ``run_at`` -- one local date and time (``YYYY-MM-DDTHH:MM``), run once.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import CroniterError, croniter

from langflow.services.triggers.error_codes import (
    CRON_NEVER_MATCHES_ERROR,
    INVALID_CRON_ERROR,
    TIMEZONE_REQUIRED_ERROR,
    UNKNOWN_TIMEZONE_ERROR,
)

DEFAULT_TIMEZONE = "UTC"
CRON_FIELD_COUNT = 5
TIMING_KEYS = ("cron", "crons", "interval_minutes", "run_at")
#: The longest interval accepted: 31 days, matching the Schedule component.
MAX_INTERVAL_MINUTES = 31 * 24 * 60
RUN_AT_FORMAT = "%Y-%m-%dT%H:%M"


class InvalidScheduleError(ValueError):
    """The trigger's schedule configuration cannot be evaluated."""


def has_timing(config: dict[str, Any]) -> bool:
    """Whether ``config`` names a timing at all; an unusable pick leaves only a blank cron."""
    return any(config.get(key) not in (None, "", []) for key in TIMING_KEYS)


def _cron(expression: object, tzinfo: ZoneInfo) -> str:
    if (
        not isinstance(expression, str)
        or len(expression.split()) != CRON_FIELD_COUNT
        or not croniter.is_valid(expression)
    ):
        raise InvalidScheduleError(INVALID_CRON_ERROR)
    # ``is_valid`` is syntactic: '0 0 31 2 *' passes it and then never fires.
    # Probe one fire time so "validates" means the tick producer can run it.
    try:
        croniter(expression, datetime.now(tzinfo)).get_next(datetime)
    except (CroniterError, ValueError, KeyError, OverflowError) as exc:
        raise InvalidScheduleError(CRON_NEVER_MATCHES_ERROR) from exc
    return " ".join(expression.split())


def _crons(expressions: object, tzinfo: ZoneInfo) -> list[str]:
    if not isinstance(expressions, list) or not expressions:
        msg = "crons must list at least one cron expression."
        raise InvalidScheduleError(msg)
    return [_cron(expression, tzinfo) for expression in expressions]


def _interval_minutes(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_INTERVAL_MINUTES:
        msg = f"interval_minutes must be a whole number of minutes from 1 to {MAX_INTERVAL_MINUTES}."
        raise InvalidScheduleError(msg)
    return value


def _run_at(value: object) -> str:
    try:
        moment = datetime.fromisoformat(value) if isinstance(value, str) and value.strip() else None
    except ValueError:
        moment = None
    # The timezone says where the moment is; an offset here would contradict it.
    if moment is None or moment.tzinfo is not None:
        msg = "run_at must be a local date and time such as 2026-12-24T18:30."
        raise InvalidScheduleError(msg)
    return moment.strftime(RUN_AT_FORMAT)


def _timing(config: dict[str, Any], tzinfo: ZoneInfo) -> dict[str, Any]:
    present = [key for key in TIMING_KEYS if key in config]
    if len(present) > 1:
        msg = f"Give only one of {', '.join(TIMING_KEYS)}; got {', '.join(present)}."
        raise InvalidScheduleError(msg)
    key = present[0] if present else "cron"
    if key == "crons":
        return {"crons": _crons(config["crons"], tzinfo)}
    if key == "interval_minutes":
        return {"interval_minutes": _interval_minutes(config["interval_minutes"])}
    if key == "run_at":
        return {"run_at": _run_at(config["run_at"])}
    return {"cron": _cron(config.get("cron"), tzinfo)}


def validate_schedule_config(config: dict[str, Any]) -> dict[str, Any]:
    """Validate the timing and its controls without accepting falsy substitutes."""
    zone = config.get("timezone", DEFAULT_TIMEZONE)
    if not isinstance(zone, str) or not zone.strip():
        raise InvalidScheduleError(TIMEZONE_REQUIRED_ERROR)
    try:
        tzinfo = ZoneInfo(zone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise InvalidScheduleError(UNKNOWN_TIMEZONE_ERROR) from exc
    timing = _timing(config, tzinfo)
    catchup = config.get("catchup_policy", "coalesce")
    if not isinstance(catchup, str) or catchup not in {"coalesce", "skip"}:
        msg = "catchup_policy must be 'coalesce' or 'skip'."
        raise InvalidScheduleError(msg)
    if not isinstance(config.get("share_session", False), bool):
        msg = "share_session must be a boolean."
        raise InvalidScheduleError(msg)
    return {**config, **timing, "timezone": zone, "catchup_policy": catchup}


def run_at_instant(config: dict[str, Any]) -> datetime:
    """The UTC instant of a validated run-once schedule."""
    local = datetime.fromisoformat(config["run_at"]).replace(tzinfo=ZoneInfo(config["timezone"]))
    return local.astimezone(timezone.utc)


def schedule_summary(config: dict[str, Any]) -> str | None:
    """A short description of when the schedule runs, for the trigger's generated name."""
    if config.get("cron"):
        return str(config["cron"])
    if config.get("crons"):
        return "; ".join(config["crons"])
    if config.get("interval_minutes"):
        return f"every {config['interval_minutes']} minutes"
    if config.get("run_at"):
        return f"once at {config['run_at']}"
    return None


def schedule_timing_changed(previous: dict[str, Any], current: dict[str, Any]) -> bool:
    """Only changes to the schedule's clock invalidate the next-fire cursor."""
    return any(previous.get(key) != current.get(key) for key in TIMING_KEYS) or previous.get(
        "timezone", DEFAULT_TIMEZONE
    ) != current.get("timezone", DEFAULT_TIMEZONE)
