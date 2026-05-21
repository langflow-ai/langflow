"""Pure-function tests for ``compose_cron``.

Every branch of the mode mapping is exercised with both well-formed
and defensive inputs (out-of-range values, non-numeric strings, missing
fields) so the cron string the worker eventually ends up scheduling
on is predictable no matter what the canvas sends in.
"""

from __future__ import annotations

import pytest
from lfx.components.triggers.cron_builder import (
    DAYS_OF_WEEK,
    MODE_CUSTOM,
    MODE_DAILY,
    MODE_EVERY_N_HOURS,
    MODE_EVERY_N_MINUTES,
    MODE_WEEKLY,
    SCHEDULE_MODES,
    compose_cron,
)

# --------------------------------------------------------------------------- #
#  every-N-minutes
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("minutes", "expected"),
    [
        (5, "*/5 * * * *"),
        (1, "*/1 * * * *"),
        (30, "*/30 * * * *"),
    ],
)
def test_every_n_minutes_emits_step(minutes, expected):
    assert compose_cron(mode=MODE_EVERY_N_MINUTES, minutes_interval=minutes) == expected


@pytest.mark.parametrize(
    ("minutes", "expected_step"),
    [
        (0, 1),   # below range — clamps to 1
        (-7, 1),  # below range — clamps to 1
        (60, 59),  # above range — clamps to 59
        (999, 59),
    ],
)
def test_every_n_minutes_clamps_out_of_range(minutes, expected_step):
    result = compose_cron(mode=MODE_EVERY_N_MINUTES, minutes_interval=minutes)
    assert result == f"*/{expected_step} * * * *"


def test_every_n_minutes_falls_back_for_non_numeric():
    assert compose_cron(mode=MODE_EVERY_N_MINUTES, minutes_interval="nope") == "*/5 * * * *"


# --------------------------------------------------------------------------- #
#  every-N-hours
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("hours", "expected"),
    [
        (1, "0 */1 * * *"),
        (3, "0 */3 * * *"),
        (12, "0 */12 * * *"),
    ],
)
def test_every_n_hours_emits_top_of_hour_step(hours, expected):
    assert compose_cron(mode=MODE_EVERY_N_HOURS, hours_interval=hours) == expected


def test_every_n_hours_clamps_out_of_range():
    assert compose_cron(mode=MODE_EVERY_N_HOURS, hours_interval=0) == "0 */1 * * *"
    assert compose_cron(mode=MODE_EVERY_N_HOURS, hours_interval=24) == "0 */23 * * *"


# --------------------------------------------------------------------------- #
#  daily
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("time_of_day", "expected"),
    [
        ("09:00", "0 9 * * *"),
        ("14:30", "30 14 * * *"),
        ("00:00", "0 0 * * *"),
        ("23:59", "59 23 * * *"),
    ],
)
def test_daily_emits_correct_minute_hour(time_of_day, expected):
    assert compose_cron(mode=MODE_DAILY, time_of_day=time_of_day) == expected


def test_daily_clamps_out_of_range_components():
    assert compose_cron(mode=MODE_DAILY, time_of_day="25:99") == "59 23 * * *"


def test_daily_falls_back_for_malformed_input():
    # Missing colon → fall back to 09:00 defaults.
    assert compose_cron(mode=MODE_DAILY, time_of_day="garbage") == "0 9 * * *"
    # Empty string idem.
    assert compose_cron(mode=MODE_DAILY, time_of_day="") == "0 9 * * *"
    # Non-string idem.
    assert compose_cron(mode=MODE_DAILY, time_of_day=None) == "0 9 * * *"


# --------------------------------------------------------------------------- #
#  weekly
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("day", "time_of_day", "expected"),
    [
        ("Sunday", "00:00", "0 0 * * 0"),
        ("Monday", "09:00", "0 9 * * 1"),
        ("Friday", "18:30", "30 18 * * 5"),
        ("Saturday", "12:00", "0 12 * * 6"),
    ],
)
def test_weekly_appends_day_index(day, time_of_day, expected):
    assert (
        compose_cron(mode=MODE_WEEKLY, day_of_week=day, time_of_day=time_of_day)
        == expected
    )


def test_weekly_falls_back_to_monday_for_unknown_day():
    assert compose_cron(mode=MODE_WEEKLY, day_of_week="NotADay", time_of_day="09:00") == "0 9 * * 1"


def test_days_of_week_order_matches_cron_numbering():
    """Pinned: Sunday must be index 0, Saturday index 6 — that's what cron expects."""
    assert DAYS_OF_WEEK[0] == "Sunday"
    assert DAYS_OF_WEEK[6] == "Saturday"


# --------------------------------------------------------------------------- #
#  custom / unknown mode → fallback
# --------------------------------------------------------------------------- #


def test_unknown_mode_returns_fallback():
    # Custom mode never goes through compose_cron in real usage —
    # the component bypasses it. But if anything calls compose_cron
    # with an unknown mode, the fallback keeps the contract.
    assert compose_cron(mode="not-a-real-mode") == "*/5 * * * *"
    assert compose_cron(mode=MODE_CUSTOM, fallback="0 0 * * *") == "0 0 * * *"


def test_schedule_modes_constant_lists_all_modes():
    assert set(SCHEDULE_MODES) == {
        MODE_EVERY_N_MINUTES,
        MODE_EVERY_N_HOURS,
        MODE_DAILY,
        MODE_WEEKLY,
        MODE_CUSTOM,
    }
