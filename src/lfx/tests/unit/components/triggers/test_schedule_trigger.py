"""The schedule trigger component: what it declares, and what it refuses."""

from __future__ import annotations

import pytest
from lfx.base.triggers.base import TRIGGER_EVENT_KEY, BaseTriggerComponent, TriggerDefinition
from lfx.components.triggers import ScheduleTriggerComponent
from lfx.components.triggers.schedule_trigger import (
    CATCHUP_COALESCE,
    CATCHUP_SKIP,
    ScheduleTriggerError,
    validate_cron_expression,
    validate_timezone,
)


def _component(**overrides) -> ScheduleTriggerComponent:
    component = ScheduleTriggerComponent()
    defaults = {
        "cron_expression": "0 8 * * 1-5",
        "timezone": "Europe/Lisbon",
        "catchup_policy": CATCHUP_COALESCE,
        "share_session": False,
    }
    defaults.update(overrides)
    for name, value in defaults.items():
        setattr(component, name, value)
    return component


def test_the_component_declares_the_schedule_kind() -> None:
    component = _component()
    definition = component.trigger_definition()

    assert isinstance(definition, TriggerDefinition)
    assert definition.kind == "schedule"
    assert definition.provider is None
    assert definition.needs_connection is False
    assert definition.config == {
        "cron": "0 8 * * 1-5",
        "timezone": "Europe/Lisbon",
        "catchup_policy": CATCHUP_COALESCE,
        "share_session": False,
    }


def test_share_session_is_carried_into_the_config() -> None:
    assert _component(share_session=True).trigger_config()["share_session"] is True
    assert _component(catchup_policy=CATCHUP_SKIP).trigger_config()["catchup_policy"] == CATCHUP_SKIP


@pytest.mark.parametrize("expression", ["", "   ", "0 8 * *", "0 8 * * 1-5 extra"])
def test_a_malformed_cron_expression_is_refused_on_the_canvas(expression) -> None:
    """The editor gets an answer without a round trip to the server."""
    with pytest.raises(ScheduleTriggerError):
        validate_cron_expression(expression)


def test_cron_whitespace_is_normalised_not_rejected() -> None:
    assert validate_cron_expression("0   8 * *   1-5") == "0 8 * * 1-5"


@pytest.mark.parametrize("zone", ["", "  ", "Europe/Atlantis", "PST"])
def test_an_unknown_timezone_is_refused(zone) -> None:
    """A bad zone must fail here, not silently fall back to UTC and fire an hour off."""
    with pytest.raises(ScheduleTriggerError):
        validate_timezone(zone)


@pytest.mark.parametrize("zone", ["UTC", "Europe/Lisbon", "America/New_York", "Asia/Tokyo"])
def test_real_iana_zones_are_accepted(zone) -> None:
    assert validate_timezone(zone) == zone


def test_a_manual_run_yields_an_empty_event_rather_than_failing() -> None:
    """An owner can build and test the downstream flow before arming anything."""
    component = _component()
    assert component.build_event().data == {}


def test_the_firing_event_reaches_the_flow() -> None:
    component = _component()
    event = {"trigger_id": "t", "event_id": "e", "kind": "schedule", "payload": {"scheduled_at": "2026-09-07T08:00"}}
    component._attributes = {TRIGGER_EVENT_KEY: event}

    assert component.build_event().data == event


def test_a_subclass_without_a_kind_is_a_programming_error() -> None:
    class NamelessTrigger(BaseTriggerComponent):
        display_name = "Nameless"

    with pytest.raises(ValueError, match="trigger_kind"):
        NamelessTrigger().trigger_definition()
