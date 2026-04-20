"""Tests for :mod:`lfx.serialization.redaction`."""

from __future__ import annotations

import pytest
from lfx.serialization.redaction import build_redaction_map, redact_values
from pydantic import BaseModel


class _Nested(BaseModel):
    note: str
    binding: str


def test_redacts_string_occurrences():
    redaction_map = {"sk-abc-123": "[REDACTED: OPENAI_API_KEY]"}
    assert redact_values("token=sk-abc-123!", redaction_map) == "token=[REDACTED: OPENAI_API_KEY]!"


def test_redacts_nested_dict_values():
    redaction_map = {"my-secret": "[REDACTED: MY_VAR]"}
    payload = {
        "message": {"text": "using my-secret in prompt"},
        "type": "message",
        "metadata": {"note": "my-secret appears here too"},
    }
    redacted = redact_values(payload, redaction_map)
    assert redacted["message"]["text"] == "using [REDACTED: MY_VAR] in prompt"
    assert redacted["metadata"]["note"] == "[REDACTED: MY_VAR] appears here too"
    # Non-sensitive fields untouched
    assert redacted["type"] == "message"


def test_redacts_inside_lists_and_tuples():
    redaction_map = {"s3cret": "[REDACTED: TOK]"}
    obj = ["safe", "s3cret value", ("also s3cret", "ok"), {"inner": "s3cret"}]
    redacted = redact_values(obj, redaction_map)
    assert redacted[0] == "safe"
    assert redacted[1] == "[REDACTED: TOK] value"
    assert redacted[2] == ("also [REDACTED: TOK]", "ok")
    assert redacted[3]["inner"] == "[REDACTED: TOK]"


def test_handles_pydantic_models():
    redaction_map = {"pii-value": "[REDACTED: PII]"}
    model = _Nested(note="value is pii-value", binding="pii-value")
    redacted = redact_values(model, redaction_map)
    # Pydantic models are dumped to dicts so redaction is visible to callers
    # that serialize the result.
    assert redacted["note"] == "value is [REDACTED: PII]"
    assert redacted["binding"] == "[REDACTED: PII]"


def test_empty_map_returns_input_unchanged():
    payload = {"a": "b"}
    assert redact_values(payload, {}) is payload


def test_does_not_mutate_input():
    redaction_map = {"leak": "[REDACTED: V]"}
    payload = {"items": [{"text": "leak here"}]}
    redact_values(payload, redaction_map)
    assert payload["items"][0]["text"] == "leak here"


def test_longest_match_wins_over_substring():
    # "sk-abc" is a prefix of "sk-abc-123"; we must redact the longer value
    # first to avoid producing "[REDACTED: SHORT]-123".
    redaction_map = {
        "sk-abc": "[REDACTED: SHORT]",
        "sk-abc-123": "[REDACTED: LONG]",
    }
    result = redact_values("token=sk-abc-123", redaction_map)
    assert result == "token=[REDACTED: LONG]"


def test_build_redaction_map_skips_empty_values():
    assert build_redaction_map({"": "NAME"}) == {}
    assert build_redaction_map({"value": "NAME"}) == {"value": "[REDACTED: NAME]"}


def test_build_redaction_map_uses_generic_placeholder_when_name_missing():
    redaction_map = build_redaction_map({"value": ""})
    assert "value" in redaction_map
    assert "REDACTED" in redaction_map["value"]


def test_non_string_scalars_pass_through():
    redaction_map = {"leak": "[REDACTED: V]"}
    assert redact_values(42, redaction_map) == 42
    flag = True
    assert redact_values(flag, redaction_map) is True
    assert redact_values(None, redaction_map) is None


@pytest.mark.parametrize(
    ("secret", "placeholder"),
    [
        ("short", "[REDACTED: A]"),
        ("a" * 64, "[REDACTED: LONG]"),
    ],
)
def test_replaces_every_occurrence(secret: str, placeholder: str):
    text = f"{secret} and {secret} again"
    result = redact_values(text, {secret: placeholder})
    assert secret not in result
    assert result.count(placeholder) == 2
