"""Tests for how the Webhook component turns a request body into JSON output."""

import pytest
from lfx.components.input_output.webhook import WebhookComponent


def _build(payload: str):
    component = WebhookComponent()
    component.set_attributes({"data": payload})
    return component.build_data()


def test_json_object_payload_becomes_the_data():
    assert _build('{"event": "open", "id": 1}').data == {"event": "open", "id": 1}


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ('[{"event": "open"}, {"event": "click"}]', [{"event": "open"}, {"event": "click"}]),
        ("42", 42),
        ('"hello"', "hello"),
        ("true", True),
    ],
)
def test_valid_json_that_is_not_an_object_is_wrapped_in_payload(payload, expected):
    assert _build(payload).data == {"payload": expected}


def test_json_array_payload_reaches_a_table():
    rows = _build('[{"event": "open"}, {"event": "click"}]').to_dataframe()

    assert rows.to_dict(orient="records") == [{"event": "open"}, {"event": "click"}]


def test_invalid_json_payload_is_wrapped_in_payload():
    assert _build("not json").data == {"payload": "not json"}


def test_json_null_payload_gives_empty_data():
    assert _build("null").data == {}
