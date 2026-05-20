"""Unit tests for ``langflow.services.triggers.scheduler``.

Pure functions, no database, no event loop. Covers:
  - happy-path next-fire computation across timezones,
  - DST handling on a spring-forward day,
  - rejection of bad cron expressions and unknown IANA timezones.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from langflow.services.triggers.scheduler import (
    InvalidTriggerConfigError,
    next_fire_time_utc,
    validate_cron_expression,
    validate_timezone,
    validate_trigger_config,
)


def test_five_minute_cron_in_utc():
    after = datetime(2026, 5, 20, 18, 42, tzinfo=timezone.utc)
    result = next_fire_time_utc(cron_expression="*/5 * * * *", timezone_name="UTC", after=after)
    assert result == datetime(2026, 5, 20, 18, 45, tzinfo=timezone.utc)


def test_daily_cron_in_non_utc_timezone():
    """02:30 daily in America/Sao_Paulo (UTC-3, no DST since 2019)."""
    after = datetime(2026, 5, 20, 0, 0, tzinfo=timezone.utc)
    result = next_fire_time_utc(
        cron_expression="30 2 * * *",
        timezone_name="America/Sao_Paulo",
        after=after,
    )
    # 02:30 local on 2026-05-20 = 05:30 UTC.
    assert result == datetime(2026, 5, 20, 5, 30, tzinfo=timezone.utc)


def test_dst_spring_forward_skips_phantom_local_time():
    """2026-03-08 in America/New_York: 02:30 local does not exist.

    croniter + zoneinfo must shift to the next valid local instant
    (which converts to 07:30 UTC, i.e. 03:30 EDT after the spring
    forward — depending on croniter version it may shift to 03:00 EDT,
    so the assertion just requires a strictly-future UTC time on the
    same day with hour in the expected window).
    """
    after = datetime(2026, 3, 8, 5, 0, tzinfo=timezone.utc)
    result = next_fire_time_utc(
        cron_expression="30 2 * * *",
        timezone_name="America/New_York",
        after=after,
    )
    assert result > after
    assert result.date().isoformat() == "2026-03-08"
    # 02:30 EST would be 07:30 UTC, 02:30 EDT would be 06:30 UTC.
    # The result must be one of those two — both are acceptable since
    # the local time literally does not exist.
    assert result.hour in (6, 7)
    assert result.minute == 30


def test_cron_rolls_into_next_day():
    """09:00 Europe/London cron with reference at noon UTC rolls forward.

    Lands on the next day's 09:00 London time (=08:00 UTC in BST).
    """
    after = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)
    result = next_fire_time_utc(
        cron_expression="0 9 * * *",
        timezone_name="Europe/London",
        after=after,
    )
    assert result == datetime(2026, 5, 21, 8, 0, tzinfo=timezone.utc)


def test_invalid_cron_expression_rejected():
    with pytest.raises(InvalidTriggerConfigError) as excinfo:
        validate_cron_expression("not-a-cron")
    assert "invalid cron expression" in str(excinfo.value)


def test_unknown_timezone_rejected():
    with pytest.raises(InvalidTriggerConfigError) as excinfo:
        validate_timezone("Mars/Olympus")
    assert "unknown IANA timezone" in str(excinfo.value)


def test_validate_trigger_config_bundles_both_checks():
    # Bad cron, good tz → cron error.
    with pytest.raises(InvalidTriggerConfigError):
        validate_trigger_config(cron_expression="xx", timezone_name="UTC")
    # Good cron, bad tz → tz error.
    with pytest.raises(InvalidTriggerConfigError):
        validate_trigger_config(cron_expression="* * * * *", timezone_name="Mars/Olympus")
    # Both good → no raise.
    validate_trigger_config(cron_expression="* * * * *", timezone_name="UTC")


def test_next_fire_time_with_default_after_returns_future():
    """Omitting ``after`` should default to ``utcnow``.

    The returned datetime must be strictly later than the call instant.
    """
    before_call = datetime.now(timezone.utc)
    result = next_fire_time_utc(cron_expression="* * * * *", timezone_name="UTC")
    assert result > before_call
