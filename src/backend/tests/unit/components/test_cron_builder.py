"""Pure-function tests for ``compose_cron``.

Two branches of ``at_specific_time`` plus defensive input cases so
the cron string the worker eventually schedules on is predictable
regardless of what the canvas sends in.
"""

from __future__ import annotations

import pytest
from lfx.components.triggers.cron_builder import (
    INTERVAL_UNITS,
    UNIT_HOURS,
    UNIT_MINUTES,
    compose_cron,
)

# --------------------------------------------------------------------------- #
#  Interval branch (at_specific_time = False)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("interval_value", "expected"),
    [
        (5, "*/5 * * * *"),
        (1, "*/1 * * * *"),
        (30, "*/30 * * * *"),
    ],
)
def test_minutes_interval_emits_step(interval_value, expected):
    assert (
        compose_cron(
            at_specific_time=False,
            interval_value=interval_value,
            interval_unit=UNIT_MINUTES,
        )
        == expected
    )


@pytest.mark.parametrize(
    ("interval_value", "expected_step"),
    [
        (0, 1),    # below range → clamps to 1
        (-7, 1),   # negative idem
        (60, 59),  # above the minute cap → clamps to 59
        (999, 59),
    ],
)
def test_minutes_interval_clamps_out_of_range(interval_value, expected_step):
    result = compose_cron(
        at_specific_time=False,
        interval_value=interval_value,
        interval_unit=UNIT_MINUTES,
    )
    assert result == f"*/{expected_step} * * * *"


def test_minutes_interval_falls_back_for_non_numeric():
    assert (
        compose_cron(
            at_specific_time=False,
            interval_value="nope",
            interval_unit=UNIT_MINUTES,
        )
        == "*/5 * * * *"
    )


@pytest.mark.parametrize(
    ("interval_value", "expected"),
    [
        (1, "0 */1 * * *"),
        (3, "0 */3 * * *"),
        (12, "0 */12 * * *"),
    ],
)
def test_hours_interval_emits_top_of_hour_step(interval_value, expected):
    assert (
        compose_cron(
            at_specific_time=False,
            interval_value=interval_value,
            interval_unit=UNIT_HOURS,
        )
        == expected
    )


def test_hours_interval_clamps_out_of_range():
    assert (
        compose_cron(
            at_specific_time=False,
            interval_value=0,
            interval_unit=UNIT_HOURS,
        )
        == "0 */1 * * *"
    )
    # Above the cron hour cap (23) → clamps to 23.
    assert (
        compose_cron(
            at_specific_time=False,
            interval_value=24,
            interval_unit=UNIT_HOURS,
        )
        == "0 */23 * * *"
    )


def test_unknown_unit_falls_back_to_minutes():
    """Unexpected ``interval_unit`` value (e.g. legacy/typo) defaults to minutes."""
    assert (
        compose_cron(
            at_specific_time=False,
            interval_value=5,
            interval_unit="weeks",  # not in INTERVAL_UNITS
        )
        == "*/5 * * * *"
    )


# --------------------------------------------------------------------------- #
#  Specific-time branch (at_specific_time = True)
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
def test_specific_time_emits_correct_minute_hour(time_of_day, expected):
    assert (
        compose_cron(at_specific_time=True, time_of_day=time_of_day)
        == expected
    )


def test_specific_time_clamps_out_of_range_components():
    assert (
        compose_cron(at_specific_time=True, time_of_day="25:99")
        == "59 23 * * *"
    )


@pytest.mark.parametrize(
    "bad_value",
    [
        "garbage",  # missing colon → fall back to 09:00
        "",         # empty
        None,       # non-string
        42,         # non-string
    ],
)
def test_specific_time_falls_back_for_malformed_input(bad_value):
    assert (
        compose_cron(at_specific_time=True, time_of_day=bad_value)
        == "0 9 * * *"
    )


def test_specific_time_ignores_interval_params():
    """In specific-time mode, ``interval_value`` / ``interval_unit`` must not leak into the result."""
    assert (
        compose_cron(
            at_specific_time=True,
            interval_value=999,
            interval_unit=UNIT_HOURS,
            time_of_day="07:15",
        )
        == "15 7 * * *"
    )


# --------------------------------------------------------------------------- #
#  Constants
# --------------------------------------------------------------------------- #


def test_interval_units_constant_lists_both_units():
    """Pinned: dropdown options come from this tuple.

    Keeps the component declaration and the builder in sync.
    """
    assert set(INTERVAL_UNITS) == {UNIT_MINUTES, UNIT_HOURS}
