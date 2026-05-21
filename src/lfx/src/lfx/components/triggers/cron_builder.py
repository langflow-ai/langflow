"""Compose a 5-field POSIX cron string from the friendly schedule controls.

Pure functions only. The CronTrigger component's
``update_build_config`` hook calls into here whenever the canvas user
edits a field; the result is written into the node's
``cron_expression`` template field, which is the single source of
truth the rest of the system (lifecycle hook, worker, discovery)
reads.

Two scheduling shapes are supported, chosen by the ``at_specific_time``
boolean:

* ``False`` (default) — **intervals**. Fires every N units, where the
  unit is either minutes or hours. Timezone is irrelevant because
  ``*/N * * * *`` and ``0 */N * * *`` fire at the same wall-clock
  cadence regardless of locale.
* ``True`` — **specific time of day**. Fires at HH:MM every day, in
  the IANA timezone selected on the node.

This module owns the mapping. Splitting it out of the component file
keeps the component shell declarative (just input/output declarations)
and makes the mapping unit-testable without spinning up the canvas.
"""

from __future__ import annotations

# Unit identifiers persisted in ``interval_unit``. Plain strings so
# the canvas dropdown can render them verbatim — no extra i18n layer
# needed.
UNIT_MINUTES = "minutes"
UNIT_HOURS = "hours"

INTERVAL_UNITS: tuple[str, ...] = (UNIT_MINUTES, UNIT_HOURS)

# Bounds reflect what a single cron field can express.
_MAX_MINUTES = 59
_MAX_HOURS = 23

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


def compose_cron(
    *,
    at_specific_time: bool,
    interval_value: object = 5,
    interval_unit: object = UNIT_MINUTES,
    time_of_day: object = "09:00",
) -> str:
    """Build a 5-field cron expression from the friendly controls.

    ``at_specific_time`` is the top-level toggle. When False, the
    ``interval_*`` parameters drive an "every N units" cron and the
    other fields are ignored. When True, the ``time_of_day`` field
    drives a "daily at HH:MM" cron and the interval fields are ignored.

    Defensive: every parameter has a fallback so the canvas can never
    push a config that breaks the downstream croniter parse.
    """
    if at_specific_time:
        hour, minute = _parse_time_of_day(time_of_day)
        return f"{minute} {hour} * * *"

    unit = interval_unit if interval_unit in INTERVAL_UNITS else UNIT_MINUTES
    if unit == UNIT_HOURS:
        n = _clamp(_coerce_int(interval_value, 1), 1, _MAX_HOURS)
        return f"0 */{n} * * *"
    n = _clamp(_coerce_int(interval_value, 5), 1, _MAX_MINUTES)
    return f"*/{n} * * * *"
