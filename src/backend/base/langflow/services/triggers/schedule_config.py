"""Schedule validation shared by API writes, canvas reconciliation, and ticks."""

from __future__ import annotations

from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter

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
        msg = "Invalid cron expression: a valid five-field cron expression is required."
        raise InvalidScheduleError(msg)
    zone = config.get("timezone", DEFAULT_TIMEZONE)
    if not isinstance(zone, str) or not zone.strip():
        msg = "A non-empty IANA timezone is required."
        raise InvalidScheduleError(msg)
    try:
        ZoneInfo(zone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        msg = "Unknown timezone; use an IANA timezone name."
        raise InvalidScheduleError(msg) from exc
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
