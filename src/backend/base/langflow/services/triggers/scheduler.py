"""Pure-function helpers for cron/timezone math.

No database, no I/O. The API layer and the worker both call into here.

Two public entrypoints:

* :func:`validate_trigger_config` — validates a cron expression and an
  IANA timezone name; raises ``InvalidTriggerConfigError`` with a
  human-readable message on failure. Called by the create/patch
  endpoints before the row is inserted.
* :func:`next_fire_time_utc` — computes the next datetime (in UTC) at
  which a given cron expression should fire, given an IANA timezone
  and a reference instant. Used both to compute the very first
  ``trigger_job.scheduled_at`` at creation time and to enqueue the
  follow-up job after each fire.

The reason we route through the trigger's timezone first and only
convert to UTC at the end is DST correctness: a "daily at 02:30" cron
must fire at 02:30 local time on every day except the spring-forward
Sunday (when 02:30 does not exist locally and the next valid local
time is used).
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter


class InvalidTriggerConfigError(ValueError):
    """Raised by :func:`validate_trigger_config` on bad input."""


def validate_timezone(name: str) -> ZoneInfo:
    """Return a ``ZoneInfo`` for ``name`` or raise InvalidTriggerConfigError."""
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        msg = f"unknown IANA timezone: {name!r}"
        raise InvalidTriggerConfigError(msg) from exc


def validate_cron_expression(expression: str) -> None:
    """Raise InvalidTriggerConfigError if ``expression`` does not parse."""
    if not croniter.is_valid(expression):
        msg = f"invalid cron expression: {expression!r}"
        raise InvalidTriggerConfigError(msg)


def validate_trigger_config(*, cron_expression: str, timezone_name: str) -> None:
    """Validate a trigger's cron + timezone pair in one shot.

    Called from the route handlers so the user sees a single, useful
    400 with both checks performed. Re-raised as
    ``InvalidTriggerConfigError`` which the route maps to
    ``HTTPException(400)``.
    """
    validate_timezone(timezone_name)
    validate_cron_expression(cron_expression)


def next_fire_time_utc(
    *,
    cron_expression: str,
    timezone_name: str,
    after: datetime | None = None,
) -> datetime:
    """Compute the next fire time in UTC for ``cron_expression``.

    Args:
        cron_expression: standard 5-field POSIX cron.
        timezone_name: IANA name (e.g. ``"America/Sao_Paulo"``). The
            cron expression is interpreted in this timezone, so a
            ``"30 2 * * *"`` cron with ``timezone_name="UTC"`` fires
            at 02:30 UTC, but with ``"America/Sao_Paulo"`` it fires
            at 02:30 local time (=05:30 UTC in standard time).
        after: reference instant. ``croniter`` returns the smallest
            fire time strictly greater than ``after``. Defaults to
            ``datetime.now(timezone.utc)``.

    Returns:
        A tz-aware ``datetime`` in UTC.
    """
    tz = validate_timezone(timezone_name)
    validate_cron_expression(cron_expression)

    reference_utc = after if after is not None else datetime.now(timezone.utc)
    # croniter operates in the timezone of the reference datetime; we
    # convert to the trigger's timezone before computing so DST
    # transitions are evaluated locally.
    reference_local = reference_utc.astimezone(tz)
    iterator = croniter(cron_expression, reference_local)
    next_local: datetime = iterator.get_next(datetime)
    return next_local.astimezone(timezone.utc)
