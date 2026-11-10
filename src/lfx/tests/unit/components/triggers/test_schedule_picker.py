"""The Schedule component's guided picker: which fields it shows and the cron it runs on."""

from __future__ import annotations

import pytest
from lfx.base.triggers.schedule import INTERVALS, ScheduleTriggerError, picker_cron, schedule_cron, timezone_options
from lfx.components.triggers import ScheduleTriggerComponent
from lfx.components.triggers.schedule_trigger import validate_cron_expression


def _build_config(**values) -> dict:
    config = {entry.name: {"value": entry.value, "show": entry.show} for entry in ScheduleTriggerComponent.inputs}
    for name, value in values.items():
        config[name]["value"] = value
    return config


def _shown(config: dict) -> set[str]:
    picker = {"interval", "time_of_day", "days_of_week", "days_of_month", "cron_expression"}
    return {name for name in picker if config[name]["show"]}


def _saved_node(*, cron: str, timezone: str) -> dict:
    """A node saved before the picker: only the cron and timezone fields, and its frozen code."""
    return {
        "display_name": "Schedule",
        "template": {
            "code": {"value": "class ScheduleTriggerComponent: ..."},
            "cron_expression": {"type": "str", "value": cron},
            "timezone": {"type": "str", "value": timezone},
        },
    }


def _pick(config: dict, field: str, value) -> dict:
    return ScheduleTriggerComponent().update_build_config(config, value, field)


def test_a_new_node_starts_on_weekdays_at_eight_matching_the_old_default_cron() -> None:
    config = _build_config()

    assert config["schedule_type"]["value"] == "Weekly"
    assert config["cron_expression"]["value"] == "0 8 * * 1-5"
    assert picker_cron({name: field["value"] for name, field in config.items()}) == "0 8 * * 1-5"
    assert _shown(config) == {"days_of_week", "time_of_day"}


@pytest.mark.parametrize(
    ("schedule_type", "shown"),
    [
        ("At regular intervals", {"interval"}),
        ("Daily", {"time_of_day"}),
        ("Weekly", {"days_of_week", "time_of_day"}),
        ("Monthly", {"days_of_month", "time_of_day"}),
        ("Custom (cron)", {"cron_expression"}),
    ],
)
def test_each_schedule_type_shows_only_the_fields_it_needs(schedule_type, shown) -> None:
    assert _shown(_pick(_build_config(), "schedule_type", schedule_type)) == shown


def _component(**values) -> ScheduleTriggerComponent:
    component = ScheduleTriggerComponent()
    defaults = {entry.name: entry.value for entry in ScheduleTriggerComponent.inputs}
    for name, value in {**defaults, **values}.items():
        setattr(component, name, value)
    return component


def test_the_trigger_runs_on_the_picked_schedule_not_the_stored_cron() -> None:
    component = _component(schedule_type="Daily", time_of_day="17:45", cron_expression="0 8 * * 1-5")

    assert component.trigger_config()["cron"] == "45 17 * * *"


def test_weekly_and_monthly_days_become_cron_lists() -> None:
    weekly = {"schedule_type": "Weekly", "time_of_day": "09:30", "days_of_week": ["Sunday", "Wednesday"]}
    monthly = {"schedule_type": "Monthly", "time_of_day": "06:00", "days_of_month": ["15", "1"]}

    assert picker_cron(weekly) == "30 9 * * 0,3"
    assert picker_cron(monthly) == "0 6 1,15 * *"


def test_runs_of_three_or_more_days_are_written_as_ranges() -> None:
    days = ["1", "2", "3", "10", "11", "20", "21", "22", "23"]

    assert picker_cron({"schedule_type": "Monthly", "time_of_day": "00:00", "days_of_month": days}) == (
        "0 0 1-3,10,11,20-23 * *"
    )


@pytest.mark.parametrize(("interval", "cron"), list(INTERVALS.items()))
def test_every_interval_compiles_to_a_five_field_cron(interval, cron) -> None:
    assert picker_cron({"schedule_type": "At regular intervals", "interval": interval}) == cron
    assert validate_cron_expression(cron) == cron


def test_a_pick_never_overwrites_a_hand_written_cron() -> None:
    """Custom, then Weekly, then Custom again must still show the cron the user typed."""
    config = _build_config(schedule_type="Custom (cron)", cron_expression="*/7 * * * *")

    config = _pick(config, "schedule_type", "Weekly")
    config = _pick(config, "days_of_week", ["Monday"])
    config = _pick(config, "schedule_type", "Custom (cron)")

    assert config["cron_expression"]["value"] == "*/7 * * * *"
    assert config["cron_expression"]["show"] is True


def test_an_unusable_pick_still_shows_the_fields_to_fix_it() -> None:
    config = _pick(_build_config(days_of_week=[]), "schedule_type", "Weekly")

    assert _shown(config) == {"days_of_week", "time_of_day"}


@pytest.mark.parametrize(
    ("values", "cron"),
    [
        ({"schedule_type": "Custom (cron)", "time_of_day": "09:00"}, "*/7 * * * *"),
        ({}, "*/7 * * * *"),
        ({"schedule_type": "Daily", "time_of_day": "09:00"}, "0 9 * * *"),
    ],
)
def test_custom_and_pre_picker_nodes_run_on_their_stored_cron(values, cron) -> None:
    assert schedule_cron(values, "*/7 * * * *") == cron


@pytest.mark.parametrize("time_of_day", ["8", "24:00", "08:60", "eight", ""])
def test_a_malformed_time_of_day_is_refused(time_of_day) -> None:
    with pytest.raises(ScheduleTriggerError, match="HH:MM"):
        picker_cron({"schedule_type": "Daily", "time_of_day": time_of_day})


def test_a_weekly_or_monthly_schedule_needs_a_day() -> None:
    with pytest.raises(ScheduleTriggerError, match="day of the week"):
        picker_cron({"schedule_type": "Weekly", "time_of_day": "08:00", "days_of_week": []})
    with pytest.raises(ScheduleTriggerError, match="day of the month"):
        picker_cron({"schedule_type": "Monthly", "time_of_day": "08:00", "days_of_month": []})


def test_an_interval_outside_the_list_is_refused() -> None:
    with pytest.raises(ScheduleTriggerError, match="interval"):
        picker_cron({"schedule_type": "At regular intervals", "interval": "45 minutes"})


def test_days_saved_as_numbers_are_still_picked() -> None:
    values = {"schedule_type": "Monthly", "time_of_day": "08:00", "days_of_month": ["1", 15]}
    assert picker_cron(values) == "0 8 1,15 * *"


@pytest.mark.parametrize(
    "values",
    [
        {"schedule_type": "Daily", "time_of_day": 1730},
        {"schedule_type": "At regular intervals", "interval": ["15 minutes"]},
        {"schedule_type": "Monthly", "time_of_day": "08:00", "days_of_month": 15},
    ],
)
def test_a_value_that_is_not_text_is_refused_not_crashed_on(values) -> None:
    with pytest.raises(ScheduleTriggerError):
        picker_cron(values)


def test_the_timezone_is_picked_from_real_iana_zones_utc_first() -> None:
    zones = timezone_options()

    assert zones[0] == "UTC"
    assert {"Europe/Lisbon", "America/New_York", "Asia/Tokyo"} <= set(zones)
    assert zones.count("UTC") == 1


async def test_updating_a_node_saved_before_the_picker_opens_it_on_its_own_cron() -> None:
    """The Update button carries the old values over; the picker defaults must not mask the cron."""
    component = ScheduleTriggerComponent()
    new_node = component.to_frontend_node()["data"]["node"]
    saved_node = _saved_node(cron="0 3 * * *", timezone="Asia/Tokyo")

    node = await component.update_frontend_node(new_node, saved_node)

    template = node["template"]
    assert template["schedule_type"]["value"] == "Custom (cron)"
    assert template["cron_expression"]["value"] == "0 3 * * *"
    assert template["cron_expression"]["show"] is True
    assert template["days_of_week"]["show"] is False


async def test_updating_a_picker_node_keeps_its_pick() -> None:
    """Only nodes saved before the picker fall back to Custom; a pick with a stale stored cron stays."""
    component = ScheduleTriggerComponent()
    new_node = component.to_frontend_node()["data"]["node"]
    saved_node = _saved_node(cron="0 8 * * 1-5", timezone="UTC")
    saved_node["template"]["schedule_type"] = {"type": "str", "value": "Daily"}
    saved_node["template"]["time_of_day"] = {"type": "str", "value": "17:30"}

    node = await component.update_frontend_node(new_node, saved_node)

    assert node["template"]["schedule_type"]["value"] == "Daily"
    assert node["template"]["time_of_day"]["value"] == "17:30"


async def test_updating_a_node_on_the_old_default_cron_keeps_the_weekly_picker() -> None:
    component = ScheduleTriggerComponent()
    new_node = component.to_frontend_node()["data"]["node"]
    saved_node = _saved_node(cron="0 8 * * 1-5", timezone="UTC")

    node = await component.update_frontend_node(new_node, saved_node)

    assert node["template"]["schedule_type"]["value"] == "Weekly"
    assert node["template"]["cron_expression"]["show"] is False
