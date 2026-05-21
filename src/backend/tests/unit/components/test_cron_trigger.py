"""Unit tests for the CronTrigger component.

Pure instantiation tests — no graph wiring, no DB. The component is
a config-only marker (no outputs, no execution side-effects); tests
verify the immutable identifier, the expected toggle-based inputs,
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
    INTERVAL_UNITS,
    UNIT_HOURS,
    UNIT_MINUTES,
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
        "at_specific_time",
        "interval_value",
        "interval_unit",
        "time_of_day",
        "timezone",
        "cron_expression",
        "max_attempts",
    }


def test_component_has_no_outputs():
    """A CronTrigger is a marker, not a data source.

    Pinning ``outputs == []`` keeps the contract that the node has no
    handle on the canvas. Adding an output later would mean reverting
    a deliberate UX decision.
    """
    assert CronTriggerComponent.outputs == []


def test_initial_visibility_matches_default_toggle_off():
    """Default ``at_specific_time = False`` → interval branch visible."""
    component = CronTriggerComponent()
    by_name = {i.name: i for i in component.inputs}
    # Interval branch
    assert by_name["interval_value"].show is True
    assert by_name["interval_unit"].show is True
    # Specific-time branch — hidden until toggle flips
    assert by_name["time_of_day"].show is False
    assert by_name["timezone"].show is False
    # Derived field — never visible to the user
    assert by_name["cron_expression"].show is False


def test_inputs_carry_sensible_defaults():
    component = CronTriggerComponent()
    by_name = {i.name: i for i in component.inputs}
    assert by_name["at_specific_time"].value is False
    assert by_name["interval_value"].value == 5
    assert by_name["interval_unit"].value == UNIT_MINUTES
    assert by_name["time_of_day"].value == "09:00"
    assert by_name["timezone"].value == DEFAULT_TIMEZONE
    assert by_name["cron_expression"].value == DEFAULT_CRON_EXPRESSION
    assert by_name["max_attempts"].value == DEFAULT_MAX_ATTEMPTS


def test_interval_unit_dropdown_lists_minutes_and_hours_only():
    component = CronTriggerComponent()
    by_name = {i.name: i for i in component.inputs}
    assert set(by_name["interval_unit"].options) == set(INTERVAL_UNITS)


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
        "at_specific_time": {"value": False},
        "interval_value": {"value": 5, "show": True},
        "interval_unit": {"value": UNIT_MINUTES, "show": True},
        "time_of_day": {"value": "09:00", "show": False},
        "timezone": {"value": "UTC", "show": False},
        "cron_expression": {"value": DEFAULT_CRON_EXPRESSION, "show": False},
    }


def test_toggle_off_shows_interval_hides_specific_time():
    component = CronTriggerComponent()
    config = _seed_build_config()
    out = component.update_build_config(config, field_value=False, field_name="at_specific_time")
    assert out["interval_value"]["show"] is True
    assert out["interval_unit"]["show"] is True
    assert out["time_of_day"]["show"] is False
    assert out["timezone"]["show"] is False


def test_toggle_on_hides_interval_shows_specific_time():
    component = CronTriggerComponent()
    config = _seed_build_config()
    out = component.update_build_config(config, field_value=True, field_name="at_specific_time")
    assert out["interval_value"]["show"] is False
    assert out["interval_unit"]["show"] is False
    assert out["time_of_day"]["show"] is True
    assert out["timezone"]["show"] is True


def test_toggle_off_derives_minutes_cron():
    component = CronTriggerComponent()
    config = _seed_build_config()
    config["interval_value"]["value"] = 10
    out = component.update_build_config(config, field_value=False, field_name="at_specific_time")
    assert out["cron_expression"]["value"] == "*/10 * * * *"


def test_toggle_off_with_hours_unit_derives_hour_cron():
    component = CronTriggerComponent()
    config = _seed_build_config()
    config["interval_unit"]["value"] = UNIT_HOURS
    config["interval_value"]["value"] = 3
    out = component.update_build_config(config, field_value=False, field_name="at_specific_time")
    assert out["cron_expression"]["value"] == "0 */3 * * *"


def test_toggle_on_derives_time_of_day_cron():
    component = CronTriggerComponent()
    config = _seed_build_config()
    config["time_of_day"]["value"] = "14:30"
    out = component.update_build_config(config, field_value=True, field_name="at_specific_time")
    assert out["cron_expression"]["value"] == "30 14 * * *"


def test_editing_interval_value_recomputes_cron_without_flipping_the_toggle():
    """Editing an interval field also refreshes the derived cron.

    A change to ``interval_value`` (not ``at_specific_time``) still
    updates ``cron_expression`` because the toggle is read from the
    current build_config when ``field_name`` is anything else.
    """
    component = CronTriggerComponent()
    config = _seed_build_config()
    config["interval_value"]["value"] = 15
    out = component.update_build_config(config, 15, "interval_value")
    assert out["cron_expression"]["value"] == "*/15 * * * *"


def test_editing_time_of_day_when_toggle_on_recomputes_cron():
    component = CronTriggerComponent()
    config = _seed_build_config()
    config["at_specific_time"]["value"] = True
    config["time_of_day"]["show"] = True
    config["timezone"]["show"] = True
    config["interval_value"]["show"] = False
    config["interval_unit"]["show"] = False
    config["time_of_day"]["value"] = "07:15"
    out = component.update_build_config(config, "07:15", "time_of_day")
    assert out["cron_expression"]["value"] == "15 7 * * *"
