"""Turn the Schedule component's guided picker into the timing the server runs.

A pick compiles to exactly one of these timing keys, which the server reads:

* ``cron`` -- one five-field cron expression;
* ``crons`` -- several, when the picked times of day need more than one;
* ``interval_minutes`` -- a whole number of minutes between runs;
* ``run_at`` -- one local date and time (``YYYY-MM-DDTHH:MM``), run once.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from zoneinfo import available_timezones

SCHEDULE_INTERVAL = "At regular intervals"
SCHEDULE_ONCE = "Once"
SCHEDULE_DAILY = "Daily"
SCHEDULE_WEEKLY = "Weekly"
SCHEDULE_MONTHLY = "Monthly"
SCHEDULE_CUSTOM = "Custom (cron)"
SCHEDULE_TYPES = [
    SCHEDULE_INTERVAL,
    SCHEDULE_ONCE,
    SCHEDULE_DAILY,
    SCHEDULE_WEEKLY,
    SCHEDULE_MONTHLY,
    SCHEDULE_CUSTOM,
]

#: The longest interval offered: 31 days. Longer gaps are a monthly schedule.
MAX_INTERVAL_MINUTES = 31 * 24 * 60
TIMING_KEYS = ("cron", "crons", "interval_minutes", "run_at")

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

#: Field shown for each schedule type; every other picker field is hidden.
FIELDS_BY_TYPE: dict[str, tuple[str, ...]] = {
    SCHEDULE_INTERVAL: ("interval_minutes",),
    SCHEDULE_ONCE: ("run_at",),
    SCHEDULE_DAILY: ("times_of_day",),
    SCHEDULE_WEEKLY: ("days_of_week", "times_of_day"),
    SCHEDULE_MONTHLY: ("days_of_month", "times_of_day"),
    SCHEDULE_CUSTOM: ("cron_expression",),
}
PICKER_FIELDS = ("schedule_type", "interval_minutes", "run_at", "times_of_day", "days_of_week", "days_of_month")

_TIME_24H = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
_TIME_12H = re.compile(r"^(0?[1-9]|1[0-2]):([0-5]\d)\s*([AaPp])\.?[Mm]\.?$")
_NOON = 12


class ScheduleTriggerError(ValueError):
    """The schedule cannot be armed as configured."""


def timezone_options() -> list[str]:
    """Every IANA zone this interpreter knows, UTC first."""
    zones = sorted(zone for zone in available_timezones() if zone != "UTC")
    return ["UTC", *zones]


def _time_fields(time_of_day: object) -> tuple[int, int]:
    text = time_of_day.strip() if isinstance(time_of_day, str) else ""
    match = _TIME_24H.match(text)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = _TIME_12H.match(text)
    if match:
        hour = int(match.group(1)) % _NOON + (_NOON if match.group(3).lower() == "p" else 0)
        return hour, int(match.group(2))
    msg = f"Write the time of day as 18:30 or 6:30 PM; got {time_of_day!r}."
    raise ScheduleTriggerError(msg)


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


def _interval_minutes(value: object) -> int:
    minutes: int | None = None
    if isinstance(value, int) and not isinstance(value, bool):
        minutes = value
    elif isinstance(value, str) and value.strip().isdigit():
        minutes = int(value.strip())
    if minutes is None or not 1 <= minutes <= MAX_INTERVAL_MINUTES:
        msg = f"The interval is a whole number of minutes from 1 to {MAX_INTERVAL_MINUTES}; got {value!r}."
        raise ScheduleTriggerError(msg)
    return minutes


def _run_at(value: object) -> str:
    try:
        moment = datetime.fromisoformat(value.strip()) if isinstance(value, str) and value.strip() else None
    except ValueError:
        moment = None
    # The timezone field says where the moment is; an offset here would contradict it.
    if moment is None or moment.tzinfo is not None:
        msg = f"Pick the date and time to run at, for example 2026-12-24 18:30; got {value!r}."
        raise ScheduleTriggerError(msg)
    return moment.strftime("%Y-%m-%dT%H:%M")


def _time_crons(times: object, days: str) -> dict[str, Any]:
    """One cron per distinct minute: 08:00 and 12:00 share ``0 8,12``, 18:30 needs its own."""
    items = [times] if isinstance(times, str) else times if isinstance(times, list) else []
    # A row added on the canvas and not filled in yet is not a time to run at.
    items = [item for item in items if not (isinstance(item, str) and not item.strip())]
    if not items:
        msg = "Add at least one time of day."
        raise ScheduleTriggerError(msg)
    hours_by_minute: dict[int, set[int]] = {}
    for item in items:
        hour, minute = _time_fields(item)
        hours_by_minute.setdefault(minute, set()).add(hour)
    crons = [
        f"{minute} {_cron_list(hours)} {days}"
        for minute, hours in sorted(hours_by_minute.items(), key=lambda entry: (min(entry[1]), entry[0]))
    ]
    return {"cron": crons[0]} if len(crons) == 1 else {"crons": crons}


def picker_timing(values: dict[str, Any]) -> dict[str, Any] | None:
    """The timing for the picked schedule, or None for a custom cron."""
    schedule_type = values.get("schedule_type") or SCHEDULE_CUSTOM
    if schedule_type == SCHEDULE_INTERVAL:
        return {"interval_minutes": _interval_minutes(values.get("interval_minutes"))}
    if schedule_type == SCHEDULE_ONCE:
        return {"run_at": _run_at(values.get("run_at"))}
    if schedule_type == SCHEDULE_DAILY:
        return _time_crons(values.get("times_of_day"), "* * *")
    if schedule_type == SCHEDULE_WEEKLY:
        days = _day_list(values.get("days_of_week"), WEEKDAYS, "week")
        return _time_crons(values.get("times_of_day"), f"* * {days}")
    if schedule_type == SCHEDULE_MONTHLY:
        days = _day_list(values.get("days_of_month"), MONTH_DAYS, "month")
        return _time_crons(values.get("times_of_day"), f"{days} * *")
    return None


def schedule_timing(values: dict[str, Any], stored_cron: str) -> dict[str, Any]:
    """The timing a trigger runs on: the picked schedule, or the stored cron for Custom and older nodes.

    A node saved before the picker has no ``schedule_type`` and keeps its stored cron.
    """
    timing = picker_timing(values) if values.get("schedule_type") else None
    return {"cron": stored_cron} if timing is None else timing
