"""The inbound webhook trigger: what it declares, and what stays off the canvas."""

from __future__ import annotations

import json

import pytest
from lfx.base.triggers.base import TRIGGER_EVENT_FIELD, TriggerDefinition
from lfx.components.triggers import InboundWebhookTriggerComponent
from lfx.components.triggers.inbound_webhook_trigger import (
    InboundWebhookTriggerError,
    validate_payload_schema,
)


def _component(**overrides) -> InboundWebhookTriggerComponent:
    component = InboundWebhookTriggerComponent()
    defaults = {"payload_schema": "", "share_session": False}
    defaults.update(overrides)
    for name, value in defaults.items():
        setattr(component, name, value)
    return component


def test_the_component_declares_the_inbound_webhook_kind() -> None:
    definition = _component().trigger_definition()

    assert isinstance(definition, TriggerDefinition)
    assert definition.kind == "inbound_webhook"
    assert definition.provider is None


def test_the_url_and_the_secret_are_not_canvas_fields() -> None:
    """A secret on the canvas travels in every flow export and screenshot."""
    field_names = {field.name for field in InboundWebhookTriggerComponent.inputs}

    assert "signing_secret" not in field_names
    assert "url" not in field_names
    assert "public_id" not in field_names
    # The event field the server writes into is prepended by the base class.
    assert TRIGGER_EVENT_FIELD in field_names


def test_an_empty_schema_accepts_any_body() -> None:
    assert validate_payload_schema("") is None
    assert validate_payload_schema("   ") is None
    assert "payload_schema" not in _component().trigger_config()


def test_a_json_object_schema_is_carried_on_the_config() -> None:
    schema = {"type": "object", "properties": {"order": {"type": "integer"}}}
    config = _component(payload_schema=json.dumps(schema)).trigger_config()

    assert config["payload_schema"] == schema
    assert config["share_session"] is False


def test_a_malformed_schema_is_refused_on_the_canvas_not_at_delivery_time() -> None:
    with pytest.raises(InboundWebhookTriggerError, match="valid JSON"):
        _component(payload_schema="{not json").trigger_config()


def test_a_schema_that_is_not_an_object_is_refused() -> None:
    with pytest.raises(InboundWebhookTriggerError, match="JSON object"):
        validate_payload_schema("[1, 2, 3]")


def test_sharing_a_session_is_opt_in() -> None:
    assert _component().trigger_config()["share_session"] is False
    assert _component(share_session=True).trigger_config()["share_session"] is True
