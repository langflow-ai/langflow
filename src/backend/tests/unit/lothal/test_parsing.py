"""Shared LLM-reply parsing helpers (`langflow.lothal.engines.parsing`).

`strip_code_fences`, `extract_json_object`, and `parse_json_object` are pure
string functions both phase engines lean on, so these tests pin their behaviour
directly at the function boundary (the engines only exercised them transitively).
The key contract is the split between the two parsers: `extract_json_object` is
lenient and will slice a `{...}` out of surrounding prose, while
`parse_json_object` is strict — it parses the reply only when the *whole* reply
is a JSON object, so a free-form PRD that merely contains a JSON example is never
truncated to that fragment.
"""

from langflow.lothal.engines.parsing import (
    extract_json_object,
    parse_json_object,
    strip_code_fences,
)

# --- strip_code_fences -------------------------------------------------------


def test_strip_code_fences_no_fence_returns_trimmed_text():
    assert strip_code_fences("  hello world  ") == "hello world"


def test_strip_code_fences_removes_language_tagged_fence():
    assert strip_code_fences('```json\n{"a": 1}\n```') == '{"a": 1}'


def test_strip_code_fences_removes_bare_fence():
    assert strip_code_fences('```\n{"a": 1}\n```') == '{"a": 1}'


def test_strip_code_fences_opener_without_closer_drops_only_the_opener():
    # Only the leading-fence regex matches; the text after it is returned trimmed.
    assert strip_code_fences('```json\n{"a": 1}') == '{"a": 1}'


# --- extract_json_object (lenient: tolerates prose around the object) ---------


def test_extract_json_object_parses_a_plain_object():
    assert extract_json_object('{"message": "hi", "n": 2}') == {"message": "hi", "n": 2}


def test_extract_json_object_parses_a_fenced_object():
    assert extract_json_object('```json\n{"message": "hi"}\n```') == {"message": "hi"}


def test_extract_json_object_slices_object_out_of_surrounding_prose():
    # The lenient fallback: leading/trailing prose around a single object.
    assert extract_json_object('Sure, here you go: {"message": "hi"} — done!') == {"message": "hi"}


def test_extract_json_object_returns_none_when_no_braces_present():
    # start == -1 guard.
    assert extract_json_object("just some prose, no json at all") is None


def test_extract_json_object_returns_none_when_closing_brace_precedes_opening():
    # end <= start guard: a '}' before any '{'.
    assert extract_json_object("} oops {") is None


def test_extract_json_object_returns_none_when_brace_slice_is_invalid_json():
    # Braces present, but the {...} slice still doesn't parse.
    assert extract_json_object("noise {not: valid json} more") is None


def test_extract_json_object_returns_none_for_non_object_json():
    # Valid JSON that decodes to a list / scalar is not an object.
    assert extract_json_object("[1, 2, 3]") is None
    assert extract_json_object("42") is None
    assert extract_json_object('"just a string"') is None


# --- parse_json_object (strict: whole reply must be the object) --------------


def test_parse_json_object_parses_a_whole_object():
    assert parse_json_object('{"message": "the spec"}') == {"message": "the spec"}


def test_parse_json_object_parses_a_fenced_whole_object():
    assert parse_json_object('```json\n{"message": "the spec"}\n```') == {"message": "the spec"}


def test_parse_json_object_does_not_slice_an_embedded_object_out_of_prose():
    # The anti-truncation guarantee behind the clarity-branch fix: a PRD that
    # merely *contains* a `{"message": ...}` example must parse to None (so the
    # whole PRD is kept) rather than being collapsed to the embedded fragment.
    prd = '# PRD\n\n## Overview\nMessages look like {"message": "hello team"} on the socket.'
    assert parse_json_object(prd) is None


def test_parse_json_object_returns_none_for_prose():
    assert parse_json_object("Tell me more about your idea.") is None


def test_parse_json_object_returns_none_for_non_object_json():
    assert parse_json_object("[1, 2, 3]") is None
    assert parse_json_object("42") is None


def test_parse_json_object_returns_none_for_empty_or_whitespace():
    assert parse_json_object("") is None
    assert parse_json_object("   \n  ") is None
