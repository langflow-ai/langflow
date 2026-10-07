"""The schedule trigger component: what it declares, and what it refuses."""

from __future__ import annotations

import json

import pytest
from lfx.base.triggers.base import TRIGGER_EVENT_FIELD, BaseTriggerComponent, TriggerDefinition
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
    """The event arrives as the JSON string the dispatcher tweaks onto the node."""
    event = {"trigger_id": "t", "event_id": "e", "kind": "schedule", "payload": {"scheduled_at": "2026-09-07T08:00"}}
    component = _component(**{TRIGGER_EVENT_FIELD: json.dumps(event)})

    assert component.build_event().data == event


def test_the_event_field_is_on_the_template_every_trigger_declares() -> None:
    """Prepended by the base class, so a provider trigger cannot forget it.

    The dispatcher tweaks this field by name; a subclass whose own ``inputs``
    list replaced the base one would have no such template entry, the tweak
    would be skipped as an unknown key, and the trigger would fire into an empty
    flow with nothing to show for it.
    """
    assert TRIGGER_EVENT_FIELD in {entry.name for entry in ScheduleTriggerComponent.inputs}
    # The trigger's own fields survive the prepend.
    assert {"cron_expression", "timezone"} <= {entry.name for entry in ScheduleTriggerComponent.inputs}

    class ProviderTrigger(BaseTriggerComponent):
        display_name = "Provider"
        trigger_kind = "provider"
        inputs = []  # a subclass that declares its own list

    assert [entry.name for entry in ProviderTrigger.inputs] == [TRIGGER_EVENT_FIELD]


def test_an_unreadable_event_is_reported_not_raised() -> None:
    """A provider payload that will not parse must not kill the run before it starts."""
    component = _component(**{TRIGGER_EVENT_FIELD: "{not json"})

    assert component.build_event().data == {}
    assert "not valid JSON" in component.status


def test_a_subclass_without_a_kind_is_a_programming_error() -> None:
    class NamelessTrigger(BaseTriggerComponent):
        display_name = "Nameless"

    with pytest.raises(ValueError, match="trigger_kind"):
        NamelessTrigger().trigger_definition()
