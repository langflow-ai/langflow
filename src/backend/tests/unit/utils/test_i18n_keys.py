"""Unit tests for langflow.utils.i18n_keys."""

from __future__ import annotations

import hashlib

from langflow.utils.i18n_keys import (
    component_field_key,
    content_hash,
    normalize_component_key,
    safe_flow_key,
)


def test_safe_flow_key_strips_special_chars():
    assert safe_flow_key("My Flow! @Name#") == "my_flow_name"


def test_safe_flow_key_collapses_internal_separators():
    assert safe_flow_key("a---b___c") == "a_b_c"


def test_safe_flow_key_lowercases():
    assert safe_flow_key("ABCdef") == "abcdef"


def test_normalize_component_key_removes_spaces_and_lowercases():
    assert normalize_component_key("Prompt Template") == "prompttemplate"
    assert normalize_component_key("PromptTemplate") == "prompttemplate"
    assert normalize_component_key("prompt template") == "prompttemplate"


def test_normalize_component_key_equivalence_classes():
    # the three documented spellings must converge to one key
    variants = ["Prompt Template", "PromptTemplate", "prompt template"]
    assert len({normalize_component_key(v) for v in variants}) == 1


def test_content_hash_is_8_hex_chars():
    h = content_hash("Hello")
    assert len(h) == 8
    assert all(c in "0123456789abcdef" for c in h)


def test_content_hash_stable_for_same_string():
    assert content_hash("Hello") == content_hash("Hello")


def test_content_hash_changes_with_string():
    assert content_hash("Hello") != content_hash("World")


def test_content_hash_matches_sha256_prefix():
    assert content_hash("Hello") == hashlib.sha256(b"Hello").hexdigest()[:8]


def test_component_field_key_format():
    key = component_field_key("prompttemplate", "display_name", "Title")
    assert key.startswith("components.prompttemplate.display_name.")
    suffix = key.split(".")[-1]
    assert suffix == content_hash("Title")


def test_component_field_key_changes_with_english():
    a = component_field_key("x", "display_name", "A")
    b = component_field_key("x", "display_name", "B")
    assert a != b
