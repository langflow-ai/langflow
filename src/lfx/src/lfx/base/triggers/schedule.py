"""Turn the Schedule component's guided picker into the cron expression the server runs.

The server only understands one five-field cron expression, so every guided
option offered here must compile to exactly one. That is why the interval list
holds only values that divide an hour or a day evenly, and why each daily,
weekly or monthly schedule fires at a single time of day.
"""

from __future__ import annotations

import re
from typing import Any
from zoneinfo import available_timezones

SCHEDULE_INTERVAL = "At regular intervals"
SCHEDULE_DAILY = "Daily"
SCHEDULE_WEEKLY = "Weekly"
SCHEDULE_MONTHLY = "Monthly"
SCHEDULE_CUSTOM = "Custom (cron)"
SCHEDULE_TYPES = [SCHEDULE_INTERVAL, SCHEDULE_DAILY, SCHEDULE_WEEKLY, SCHEDULE_MONTHLY, SCHEDULE_CUSTOM]

#: Interval label -> cron. Only values that split an hour or a day evenly fit one cron.
INTERVALS: dict[str, str] = {
    "1 minute": "* * * * *",
    "5 minutes": "*/5 * * * *",
    "10 minutes": "*/10 * * * *",
    "15 minutes": "*/15 * * * *",
    "30 minutes": "*/30 * * * *",
    "1 hour": "0 * * * *",
    "2 hours": "0 */2 * * *",
    "3 hours": "0 */3 * * *",
    "6 hours": "0 */6 * * *",
    "12 hours": "0 */12 * * *",
}

#: Weekday label -> cron day-of-week number.
WEEKDAYS: dict[str, int] = {
    "Monday": 1,
    "Tuesday": 2,
    "Wednesday": 3,
    "Thursday": 4,
    "Friday": 5,
    "Saturday": 6,
    "Sunday": 0,
}

#: Month-day label -> cron day-of-month number.
MONTH_DAYS: dict[str, int] = {str(day): day for day in range(1, 32)}
TIMES_OF_DAY = [f"{hour:02d}:{minute:02d}" for hour in range(24) for minute in (0, 30)]

#: Field shown for each schedule type; every other picker field is hidden.
FIELDS_BY_TYPE: dict[str, tuple[str, ...]] = {
    SCHEDULE_INTERVAL: ("interval",),
    SCHEDULE_DAILY: ("time_of_day",),
    SCHEDULE_WEEKLY: ("days_of_week", "time_of_day"),
    SCHEDULE_MONTHLY: ("days_of_month", "time_of_day"),
    SCHEDULE_CUSTOM: ("cron_expression",),
}
PICKER_FIELDS = ("schedule_type", "interval", "time_of_day", "days_of_week", "days_of_month")

_TIME_OF_DAY = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


class ScheduleTriggerError(ValueError):
    """The schedule cannot be armed as configured."""


def timezone_options() -> list[str]:
    """Every IANA zone this interpreter knows, UTC first."""
    zones = sorted(zone for zone in available_timezones() if zone != "UTC")
    return ["UTC", *zones]


def _time_fields(time_of_day: object) -> tuple[int, int]:
    match = _TIME_OF_DAY.match(str(time_of_day or "").strip())
    if not match:
        msg = f"Time of day must be HH:MM in 24-hour time, for example '08:30'; got {time_of_day!r}."
        raise ScheduleTriggerError(msg)
    return int(match.group(1)), int(match.group(2))


def _cron_list(numbers: set[int]) -> str:
    """Sorted numbers as a cron list, with runs of three or more written as ranges (1-5)."""
    parts: list[str] = []
    ordered = sorted(numbers)
    start = previous = ordered[0]
    for number in [*ordered[1:], None]:
        if number is not None and number == previous + 1:
            previous = number
            continue
        min_range_length = 3
        if previous - start + 1 >= min_range_length:
            parts.append(f"{start}-{previous}")
        else:
            parts.extend(str(value) for value in range(start, previous + 1))
        if number is not None:
            start = previous = number
    return ",".join(parts)


def _day_list(days: object, numbers: dict[str, int], noun: str) -> str:
    items = days if isinstance(days, list) else []
    picked = {numbers[str(day)] for day in items if str(day) in numbers}
    if not picked:
        msg = f"Pick at least one day of the {noun}."
        raise ScheduleTriggerError(msg)
    return _cron_list(picked)


def picker_cron(values: dict[str, Any]) -> str | None:
    """The cron expression for the picked schedule, or None for a custom cron."""
    schedule_type = values.get("schedule_type") or SCHEDULE_CUSTOM
    if schedule_type == SCHEDULE_INTERVAL:
        interval = values.get("interval")
        if not isinstance(interval, str) or interval not in INTERVALS:
            msg = f"Pick an interval from the list; got {interval!r}."
            raise ScheduleTriggerError(msg)
        return INTERVALS[interval]
    if schedule_type not in (SCHEDULE_DAILY, SCHEDULE_WEEKLY, SCHEDULE_MONTHLY):
        return None
    hour, minute = _time_fields(values.get("time_of_day") or "")
    if schedule_type == SCHEDULE_WEEKLY:
        return f"{minute} {hour} * * {_day_list(values.get('days_of_week') or [], WEEKDAYS, 'week')}"
    if schedule_type == SCHEDULE_MONTHLY:
        return f"{minute} {hour} {_day_list(values.get('days_of_month') or [], MONTH_DAYS, 'month')} * *"
    return f"{minute} {hour} * * *"


def schedule_cron(values: dict[str, Any], stored_cron: str) -> str:
    """The cron a trigger runs on: the picked schedule, or the stored cron for Custom and older nodes.

    A node saved before the picker has no ``schedule_type`` and keeps its stored cron.
    """
    if not values.get("schedule_type"):
        return stored_cron
    cron = picker_cron(values)
    return stored_cron if cron is None else cron
