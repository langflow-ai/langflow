"""Schedule validation shared by API writes, canvas reconciliation, and ticks."""

from __future__ import annotations

from datetime import datetime
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


class InvalidScheduleError(ValueError):
    """The trigger's schedule configuration cannot be evaluated."""


def validate_schedule_config(config: dict[str, Any]) -> dict[str, Any]:
    """Validate five-field cron and its controls without accepting falsy substitutes."""
    expression = config.get("cron")
    if (
        not isinstance(expression, str)
        or len(expression.split()) != CRON_FIELD_COUNT
        or not croniter.is_valid(expression)
    ):
        raise InvalidScheduleError(INVALID_CRON_ERROR)
    zone = config.get("timezone", DEFAULT_TIMEZONE)
    if not isinstance(zone, str) or not zone.strip():
        raise InvalidScheduleError(TIMEZONE_REQUIRED_ERROR)
    try:
        tzinfo = ZoneInfo(zone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise InvalidScheduleError(UNKNOWN_TIMEZONE_ERROR) from exc
    # ``is_valid`` is syntactic: '0 0 31 2 *' passes it and then never fires.
    # Probe one fire time so "validates" means the tick producer can run it.
    try:
        croniter(expression, datetime.now(tzinfo)).get_next(datetime)
    except (CroniterError, ValueError, KeyError, OverflowError) as exc:
        raise InvalidScheduleError(CRON_NEVER_MATCHES_ERROR) from exc
    catchup = config.get("catchup_policy", "coalesce")
    if not isinstance(catchup, str) or catchup not in {"coalesce", "skip"}:
        msg = "catchup_policy must be 'coalesce' or 'skip'."
        raise InvalidScheduleError(msg)
    if not isinstance(config.get("share_session", False), bool):
        msg = "share_session must be a boolean."
        raise InvalidScheduleError(msg)
    return {**config, "cron": " ".join(expression.split()), "timezone": zone, "catchup_policy": catchup}


def schedule_timing_changed(previous: dict[str, Any], current: dict[str, Any]) -> bool:
    """Only changes to the schedule's clock invalidate the next-fire cursor."""
    return previous.get("cron") != current.get("cron") or previous.get("timezone", DEFAULT_TIMEZONE) != current.get(
        "timezone", DEFAULT_TIMEZONE
    )
