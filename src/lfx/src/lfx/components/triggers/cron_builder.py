"""Compose a 5-field POSIX cron string from a user-friendly mode + parameters.

Pure functions only. The CronTrigger component's
``update_build_config`` hook calls into here whenever the canvas user
edits a mode or a parameter; the result is written into the node's
``cron_expression`` template field, which is the single source of
truth the rest of the system reads.

Splitting this out of the component file keeps the component shell
declarative (just input/output declarations) and makes the mode →
cron mapping unit-testable without spinning up the canvas.
"""

from __future__ import annotations

# Mode identifiers persisted in ``schedule_mode``. Plain strings so the
# canvas dropdown can render them verbatim — no extra i18n layer
# needed for a feature where the user reads English component names
# anyway.
MODE_EVERY_N_MINUTES = "Every N minutes"
MODE_EVERY_N_HOURS = "Every N hours"
MODE_DAILY = "Daily at…"
MODE_WEEKLY = "Weekly on…"
MODE_CUSTOM = "Custom (cron expression)"

SCHEDULE_MODES: tuple[str, ...] = (
    MODE_EVERY_N_MINUTES,
    MODE_EVERY_N_HOURS,
    MODE_DAILY,
    MODE_WEEKLY,
    MODE_CUSTOM,
)

# Day-of-week dropdown labels. Order matches the cron numbering
# (Sunday=0..Saturday=6) so the index in ``DAYS_OF_WEEK`` IS the cron
# value we emit.
DAYS_OF_WEEK: tuple[str, ...] = (
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
)

# Number of segments in a well-formed "HH:MM" time string.
_HOUR_MINUTE_PARTS = 2


def _clamp(value: int, lo: int, hi: int) -> int:
    """Return ``value`` constrained to ``[lo, hi]``."""
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def _coerce_int(value: object, fallback: int) -> int:
    """Best-effort int coercion with fallback for non-numeric input."""
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return fallback


def _parse_time_of_day(value: object, *, fallback_hour: int = 9, fallback_minute: int = 0) -> tuple[int, int]:
    """Parse ``HH:MM`` (24-hour) into (hour, minute), clamped to valid ranges.

    Tolerates whitespace, single-digit hours, missing minutes, and
    non-numeric input by returning sensible defaults rather than
    raising — invalid input falls back to ``fallback_hour:fallback_minute``.
    """
    if not isinstance(value, str):
        return fallback_hour, fallback_minute
    parts = value.strip().split(":", 1)
    if len(parts) != _HOUR_MINUTE_PARTS:
        return fallback_hour, fallback_minute
    hour = _clamp(_coerce_int(parts[0], fallback_hour), 0, 23)
    minute = _clamp(_coerce_int(parts[1], fallback_minute), 0, 59)
    return hour, minute


def _day_of_week_index(label: object) -> int:
    """Return the cron weekday number (0=Sun..6=Sat) for ``label``.

    Falls back to Monday (1) when the input is missing or unknown.
    """
    if isinstance(label, str) and label in DAYS_OF_WEEK:
        return DAYS_OF_WEEK.index(label)
    return DAYS_OF_WEEK.index("Monday")


def compose_cron(
    *,
    mode: str,
    minutes_interval: object = 5,
    hours_interval: object = 1,
    time_of_day: object = "09:00",
    day_of_week: object = "Monday",
    fallback: str = "*/5 * * * *",
) -> str:
    """Build a 5-field cron expression from the friendly mode controls.

    ``fallback`` is returned when ``mode`` is unrecognised — keeps the
    contract: the function always yields a parseable cron unless the
    caller is in the explicit "Custom (cron expression)" mode (which
    bypasses this function and uses the user's literal input).
    """
    if mode == MODE_EVERY_N_MINUTES:
        n = _clamp(_coerce_int(minutes_interval, 5), 1, 59)
        return f"*/{n} * * * *"
    if mode == MODE_EVERY_N_HOURS:
        n = _clamp(_coerce_int(hours_interval, 1), 1, 23)
        return f"0 */{n} * * *"
    if mode == MODE_DAILY:
        hour, minute = _parse_time_of_day(time_of_day)
        return f"{minute} {hour} * * *"
    if mode == MODE_WEEKLY:
        hour, minute = _parse_time_of_day(time_of_day)
        dow = _day_of_week_index(day_of_week)
        return f"{minute} {hour} * * {dow}"
    return fallback
