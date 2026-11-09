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
        ("[]", []),
        ("[[1, 2], [3]]", [[1, 2], [3]]),
        ('See note [1]: [{"a": 1}]', [{"a": 1}]),
        ('See note [1]: [{"a": 1}] (see [2])', [{"a": 1}]),
        ('[{"text": "] [ \\"quote\\""}]', [{"text": '] [ "quote"'}]),
    ],
)
@pytest.mark.parametrize("validate_json", [False, True])
def test_keeps_top_level_array(json_str, expected, validate_json):
    assert json.loads(_clean(json_str, validate_json=validate_json)) == expected


def test_validate_json_accepts_top_level_array():
    assert json.loads(_clean('[{"a": 1}, {"b": 2}]', validate_json=True)) == [{"a": 1}, {"b": 2}]


@pytest.mark.parametrize(
    ("json_str", "expected"),
    [
        ('See note [1]: ["x", "y"]', ["x", "y"]),
        ('See note [1]: ["x", "y"] (see [2])', ["x", "y"]),
        ("See note [1]: [3, 4] (see [2])", [3, 4]),
        ("See note [123]: [7] (see [2])", [7]),
        ("See note [1]: [1] (see [2])", [1]),
        ("[1]", [1]),
        ("[1, 2]", [1, 2]),
        ('Options ["first"]: ["x", "y"]', ["x", "y"]),
        ("See note [1]: no later payload", [1]),
        ("See note [1]: label [2]: no later payload", [1]),
        ("[7]: see [2]", [7]),
        (" \n [7]: see [2]", [7]),
    ],
)
@pytest.mark.parametrize("validate_json", [False, True])
def test_extracts_primitive_array_with_notes(json_str, expected, validate_json):
    """Prefer payloads after prose labels while preserving leading arrays and fallback behavior."""
    assert json.loads(_clean(json_str, validate_json=validate_json)) == expected


@pytest.mark.parametrize(
    ("json_str", "expected"),
    [
        ('{"items": [1, 2]}', {"items": [1, 2]}),
        ('Result:\n```json\n{"a": "b"}\n```', {"a": "b"}),
        ('See note [1]: {"a": 1}', {"a": 1}),
        ('See note [1]: {"a": 1} (see [2])', {"a": 1}),
        ('{"text": "[note]", "items": [1, 2]}', {"text": "[note]", "items": [1, 2]}),
    ],
)
@pytest.mark.parametrize("validate_json", [False, True])
def test_extracts_object(json_str, expected, validate_json):
    assert json.loads(_clean(json_str, validate_json=validate_json)) == expected


@pytest.mark.parametrize("json_str", ["no json here", "text ] before [", "text [", "text ]"])
def test_raises_without_json_value(json_str):
    with pytest.raises(ValueError, match="no JSON object or array found"):
        _clean(json_str)


@pytest.mark.parametrize(
    ("json_str", "expected"),
    [
        ("[{a: 1,}]", [{"a": 1}]),
        ("['a]b', 'c[d']", ["a]b", "c[d"]),
        ("{'items': ['a]b', 'c[d']}", {"items": ["a]b", "c[d"]}),
        ("{'a': 1} {'b': 2}", [{"a": 1}, {"b": 2}]),
        ('["a", "b]', ["a", "b"]),
        ("[don't, do]", ["don't", "do"]),
        ('["a]b", "c]', ["a]b", "c"]),
        ("[don't, 'a]b']", ["don't", "a]b"]),
    ],
)
def test_repairs_malformed_json(json_str, expected):
    assert json.loads(_clean(json_str)) == expected
