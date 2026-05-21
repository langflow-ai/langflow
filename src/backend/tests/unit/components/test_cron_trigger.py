"""Unit tests for the CronTrigger component.

Pure instantiation tests — no graph wiring, no DB. The component is
a config-only marker (no outputs, no execution side-effects); tests
verify the immutable identifier, the expected friendly mode inputs,
and the ``update_build_config`` visibility + cron-derivation logic.
"""

from __future__ import annotations

from lfx.components.triggers import CronTriggerComponent
from lfx.components.triggers.constants import (
    COMMON_TIMEZONES,
    DEFAULT_CRON_EXPRESSION,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_TIMEZONE,
)
from lfx.components.triggers.cron_builder import (
    MODE_CUSTOM,
    MODE_DAILY,
    MODE_EVERY_N_HOURS,
    MODE_EVERY_N_MINUTES,
    MODE_WEEKLY,
)

# --------------------------------------------------------------------------- #
#  Identity / metadata / inputs surface
# --------------------------------------------------------------------------- #


def test_class_identity_is_immutable():
    # ``name`` is persisted in the node id of every saved flow.
    # Pinning the value here makes any accidental rename a test failure.
    assert CronTriggerComponent.name == "CronTrigger"


def test_metadata_for_palette():
    assert CronTriggerComponent.display_name == "Cron Trigger"
    assert CronTriggerComponent.icon == "clock"
    assert "schedule" in CronTriggerComponent.description.lower()


def test_inputs_present_with_expected_names():
    component = CronTriggerComponent()
    names = {i.name for i in component.inputs}
    assert names == {
        "schedule_mode",
        "minutes_interval",
        "hours_interval",
        "time_of_day",
        "day_of_week",
        "cron_expression",
        "timezone",
        "max_attempts",
    }


def test_component_has_no_outputs():
    """A CronTrigger is a marker, not a data source.

    Pinning ``outputs == []`` keeps the contract that the node has no
    handle on the canvas. Adding an output later would mean reverting
    a deliberate UX decision.
    """
    assert CronTriggerComponent.outputs == []


def test_initial_visibility_matches_default_mode():
    """Default mode is 'Every N minutes' — initial visibility matches.

    Only ``minutes_interval`` is visible among the parameter group;
    ``cron_expression`` stays hidden until the user picks Custom mode.
    """
    component = CronTriggerComponent()
    by_name = {i.name: i for i in component.inputs}
    assert by_name["minutes_interval"].show is True
    assert by_name["hours_interval"].show is False
    assert by_name["time_of_day"].show is False
    assert by_name["day_of_week"].show is False
    assert by_name["cron_expression"].show is False
    # Always-visible secondary control
    assert by_name["timezone"].show is True


def test_inputs_carry_sensible_defaults():
    component = CronTriggerComponent()
    by_name = {i.name: i for i in component.inputs}
    assert by_name["schedule_mode"].value == MODE_EVERY_N_MINUTES
    assert by_name["minutes_interval"].value == 5
    assert by_name["hours_interval"].value == 1
    assert by_name["time_of_day"].value == "09:00"
    assert by_name["day_of_week"].value == "Monday"
    assert by_name["cron_expression"].value == DEFAULT_CRON_EXPRESSION
    assert by_name["timezone"].value == DEFAULT_TIMEZONE
    assert by_name["max_attempts"].value == DEFAULT_MAX_ATTEMPTS


def test_timezone_dropdown_lists_common_iana_names():
    component = CronTriggerComponent()
    by_name = {i.name: i for i in component.inputs}
    options = by_name["timezone"].options
    assert "UTC" in options
    assert "America/Sao_Paulo" in options
    assert set(options) == set(COMMON_TIMEZONES)


# --------------------------------------------------------------------------- #
#  update_build_config — visibility + cron derivation
# --------------------------------------------------------------------------- #


def _seed_build_config() -> dict:
    """A build_config dict in the shape Langflow passes around."""
    return {
        "schedule_mode": {"value": MODE_EVERY_N_MINUTES},
        "minutes_interval": {"value": 5, "show": True},
        "hours_interval": {"value": 1, "show": False},
        "time_of_day": {"value": "09:00", "show": False},
        "day_of_week": {"value": "Monday", "show": False},
        "cron_expression": {"value": DEFAULT_CRON_EXPRESSION, "show": False},
        "timezone": {"value": "UTC"},
    }


def test_update_build_config_for_every_n_minutes():
    component = CronTriggerComponent()
    config = _seed_build_config()
    config["minutes_interval"]["value"] = 10
    out = component.update_build_config(config, MODE_EVERY_N_MINUTES, "schedule_mode")
    assert out["minutes_interval"]["show"] is True
    assert out["hours_interval"]["show"] is False
    assert out["cron_expression"]["show"] is False
    assert out["cron_expression"]["value"] == "*/10 * * * *"


def test_update_build_config_for_every_n_hours_changes_visibility():
    component = CronTriggerComponent()
    config = _seed_build_config()
    config["hours_interval"]["value"] = 3
    out = component.update_build_config(config, MODE_EVERY_N_HOURS, "schedule_mode")
    assert out["minutes_interval"]["show"] is False
    assert out["hours_interval"]["show"] is True
    assert out["cron_expression"]["value"] == "0 */3 * * *"


def test_update_build_config_daily_uses_time_of_day():
    component = CronTriggerComponent()
    config = _seed_build_config()
    config["time_of_day"]["value"] = "14:30"
    out = component.update_build_config(config, MODE_DAILY, "schedule_mode")
    assert out["time_of_day"]["show"] is True
    assert out["day_of_week"]["show"] is False
    assert out["cron_expression"]["value"] == "30 14 * * *"


def test_update_build_config_weekly_uses_day_and_time():
    component = CronTriggerComponent()
    config = _seed_build_config()
    config["day_of_week"]["value"] = "Friday"
    config["time_of_day"]["value"] = "18:00"
    out = component.update_build_config(config, MODE_WEEKLY, "schedule_mode")
    assert out["day_of_week"]["show"] is True
    assert out["time_of_day"]["show"] is True
    # Friday is day index 5 in the cron numbering (Sun=0).
    assert out["cron_expression"]["value"] == "0 18 * * 5"


def test_update_build_config_custom_mode_reveals_cron_input_and_leaves_value_alone():
    component = CronTriggerComponent()
    config = _seed_build_config()
    config["cron_expression"]["value"] = "*/15 9-17 * * 1-5"
    out = component.update_build_config(config, MODE_CUSTOM, "schedule_mode")
    assert out["cron_expression"]["show"] is True
    # User-typed cron preserved verbatim.
    assert out["cron_expression"]["value"] == "*/15 9-17 * * 1-5"
    # Other parameter fields all hidden in custom mode.
    for fname in ("minutes_interval", "hours_interval", "time_of_day", "day_of_week"):
        assert out[fname]["show"] is False


def test_update_build_config_recomputes_cron_when_interval_changes():
    """Editing an interval field also refreshes the derived cron.

    A change to ``minutes_interval`` (not ``schedule_mode``) still
    triggers ``cron_expression`` re-derivation because the active
    mode is already ``Every N minutes``.
    """
    component = CronTriggerComponent()
    config = _seed_build_config()
    config["minutes_interval"]["value"] = 15
    out = component.update_build_config(config, 15, "minutes_interval")
    assert out["cron_expression"]["value"] == "*/15 * * * *"
