"""Tests for the JSON Cleaner component."""

import json

import pytest
from lfx.components.processing.json_cleaner import JSONCleaner


def _clean(json_str: str, *, validate_json: bool = False) -> str:
    component = JSONCleaner(
        json_str=json_str,
        remove_control_chars=False,
        normalize_unicode=False,
        validate_json=validate_json,
    )
    return component.clean_json().text


@pytest.mark.parametrize(
    ("json_str", "expected"),
    [
        ('[{"a": 1}]', [{"a": 1}]),
        ('[{"a": 1}, {"b": 2}]', [{"a": 1}, {"b": 2}]),
        ('["x", "y"]', ["x", "y"]),
        ("Here is the list: [1, 2, 3]. Done.", [1, 2, 3]),
    ],
)
def test_keeps_top_level_array(json_str, expected):
    assert json.loads(_clean(json_str)) == expected


def test_validate_json_accepts_top_level_array():
    assert json.loads(_clean('[{"a": 1}, {"b": 2}]', validate_json=True)) == [{"a": 1}, {"b": 2}]


@pytest.mark.parametrize(
    ("json_str", "expected"),
    [
        ('{"items": [1, 2]}', {"items": [1, 2]}),
        ('Result:\n```json\n{"a": "b"}\n```', {"a": "b"}),
        ('See note [1]: {"a": 1}', {"a": 1}),
    ],
)
def test_extracts_object(json_str, expected):
    assert json.loads(_clean(json_str)) == expected


def test_raises_without_json_value():
    with pytest.raises(ValueError, match="no JSON object or array found"):
        _clean("no json here")
