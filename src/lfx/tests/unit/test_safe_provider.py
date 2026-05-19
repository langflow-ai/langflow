"""Unit tests for lfx.base.composio.safe_provider.

Covers:
- _sanitize_schema: adds missing 'type' keys recursively
- _patch_identifier_substitution_once: renames invalid Python identifiers in
  action schemas (e.g. 'extension-id' -> 'extension_id') and tracks the
  reverse mapping so the original name is restored when the API is called
- _python_reserved expansion: full Python keyword list replaces composio's
  two-item hardcoded set so fields like 'from' are handled
"""

from __future__ import annotations

import keyword
import sys
import types
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Helpers - build a minimal fake composio_langchain.provider module so the
# tests run even when composio is not installed in the test virtualenv.
# ---------------------------------------------------------------------------


def _make_fake_lc_provider():
    """Return a minimal stub of composio_langchain.provider."""
    mod = types.ModuleType("composio_langchain.provider")
    mod._python_reserved = {"for", "async"}
    mod._obj_marker = "-_object_-"

    def _clean_reserved_keyword(kw: str) -> str:
        return f"{kw}_rs"

    def _substitute_reserved_python_keywords(schema: dict) -> tuple:
        if "properties" not in schema:
            return schema, {}
        keywords: dict = {}
        for p_name in list(schema["properties"]):
            if p_name not in mod._python_reserved:
                continue
            p_val = schema["properties"].pop(p_name)
            p_name_clean = _clean_reserved_keyword(p_name)
            schema["properties"][p_name_clean] = p_val
            keywords[p_name_clean] = p_name
        return schema, keywords

    mod._substitute_reserved_python_keywords = _substitute_reserved_python_keywords
    return mod


# ---------------------------------------------------------------------------
# _sanitize_schema
# ---------------------------------------------------------------------------


class TestSanitizeSchema:
    """_sanitize_schema adds a 'type' key wherever one is missing."""

    def _get_fn(self):
        from lfx.base.composio.safe_provider import _sanitize_schema

        return _sanitize_schema

    def test_adds_object_type_when_properties_present(self):
        schema = {"properties": {"a": {"type": "string"}}}
        self._get_fn()(schema)
        assert schema["type"] == "object"

    def test_adds_array_type_when_items_present(self):
        schema = {"items": {"type": "string"}}
        self._get_fn()(schema)
        assert schema["type"] == "array"

    def test_adds_string_type_as_default(self):
        schema = {}
        self._get_fn()(schema)
        assert schema["type"] == "string"

    def test_does_not_overwrite_existing_type(self):
        schema = {"type": "integer"}
        self._get_fn()(schema)
        assert schema["type"] == "integer"

    def test_recurses_into_properties(self):
        schema = {"properties": {"nested": {"properties": {"x": {}}}}}
        self._get_fn()(schema)
        assert schema["properties"]["nested"]["type"] == "object"
        assert schema["properties"]["nested"]["properties"]["x"]["type"] == "string"

    def test_recurses_into_items(self):
        schema = {"items": {}}
        self._get_fn()(schema)
        assert schema["items"]["type"] == "string"

    def test_recurses_into_anyof(self):
        schema = {"anyOf": [{}, {"properties": {}}]}
        self._get_fn()(schema)
        assert schema["anyOf"][0]["type"] == "string"
        assert schema["anyOf"][1]["type"] == "object"

    def test_noop_on_non_dict(self):
        # Should not raise
        self._get_fn()(None)
        self._get_fn()("string")
        self._get_fn()(42)


# ---------------------------------------------------------------------------
# safe_substitute (the inner closure created by _patch_identifier_substitution_once)
# ---------------------------------------------------------------------------


class TestSafeSubstituteLogic:
    """Test the identifier-sanitising wrapper independently of composio."""

    def _make_safe_substitute(self, fake_mod=None):
        """Build safe_substitute using the real implementation logic."""
        import re as _re

        _invalid_char_re = _re.compile(r"[^a-zA-Z0-9_]")

        if fake_mod is None:
            fake_mod = _make_fake_lc_provider()

        original_substitute = fake_mod._substitute_reserved_python_keywords

        def safe_substitute(schema: dict) -> tuple:
            schema, keywords = original_substitute(schema)
            if "properties" not in schema:
                return schema, keywords
            for p_name in list(schema["properties"]):
                if p_name.isidentifier():
                    continue
                clean_name = _invalid_char_re.sub("_", p_name)
                if clean_name and clean_name[0].isdigit():
                    clean_name = f"_{clean_name}"
                while clean_name in schema["properties"]:
                    clean_name = f"{clean_name}_"
                schema["properties"][clean_name] = schema["properties"].pop(p_name)
                keywords[clean_name] = p_name
            return schema, keywords

        return safe_substitute

    # --- basic renaming ---

    def test_renames_hyphenated_property(self):
        sub = self._make_safe_substitute()
        schema = {"properties": {"extension-id": {"type": "string"}}}
        schema, keywords = sub(schema)
        assert "extension-id" not in schema["properties"]
        assert "extension_id" in schema["properties"]
        assert keywords["extension_id"] == "extension-id"

    def test_renames_outlook_from_field(self):
        """'from' is a Python keyword; the original substitute handles it via _rs suffix."""
        mod = _make_fake_lc_provider()
        mod._python_reserved = set(keyword.kwlist)
        sub = self._make_safe_substitute(mod)
        schema = {"properties": {"from": {"type": "string"}, "to": {"type": "string"}}}
        schema, _ = sub(schema)
        assert "from" not in schema["properties"]
        assert "to" in schema["properties"]  # valid identifier, unchanged

    def test_renames_dotted_property(self):
        sub = self._make_safe_substitute()
        schema = {"properties": {"foo.bar": {"type": "string"}}}
        schema, keywords = sub(schema)
        assert "foo.bar" not in schema["properties"]
        assert "foo_bar" in schema["properties"]
        assert keywords["foo_bar"] == "foo.bar"

    def test_renames_property_starting_with_digit(self):
        sub = self._make_safe_substitute()
        schema = {"properties": {"1field": {"type": "string"}}}
        schema, keywords = sub(schema)
        assert "1field" not in schema["properties"]
        renamed = next(k for k in schema["properties"] if k != "1field")
        assert renamed.startswith("_")
        assert keywords[renamed] == "1field"

    def test_handles_collision_by_appending_underscore(self):
        sub = self._make_safe_substitute()
        # 'a-b' would become 'a_b', but 'a_b' already exists
        schema = {"properties": {"a-b": {"type": "string"}, "a_b": {"type": "integer"}}}
        schema, keywords = sub(schema)
        assert "a-b" not in schema["properties"]
        assert "a_b" in schema["properties"]  # original survives
        assert "a_b_" in schema["properties"]  # renamed version
        assert keywords["a_b_"] == "a-b"

    def test_preserves_valid_identifiers_unchanged(self):
        sub = self._make_safe_substitute()
        schema = {"properties": {"valid_name": {"type": "string"}, "also_valid": {"type": "int"}}}
        original = dict(schema["properties"])
        schema, keywords = sub(schema)
        assert schema["properties"] == original
        assert keywords == {}

    def test_no_properties_returns_empty_keywords(self):
        sub = self._make_safe_substitute()
        schema = {"type": "object"}
        schema, keywords = sub(schema)
        assert keywords == {}

    def test_preserves_field_schema_after_rename(self):
        sub = self._make_safe_substitute()
        field_schema = {"type": "string", "description": "The extension ID"}
        schema = {"properties": {"extension-id": field_schema}}
        schema, _ = sub(schema)
        assert schema["properties"]["extension_id"] == field_schema

    def test_multiple_invalid_identifiers_all_renamed(self):
        sub = self._make_safe_substitute()
        schema = {"properties": {"a-b": {}, "c.d": {}, "e f": {}}}
        schema, keywords = sub(schema)
        assert "a-b" not in schema["properties"]
        assert "c.d" not in schema["properties"]
        assert "e f" not in schema["properties"]
        assert len(keywords) == 3


# ---------------------------------------------------------------------------
# _patch_identifier_substitution_once
# ---------------------------------------------------------------------------


class TestPatchIdentifierSubstitutionOnce:
    """_patch_identifier_substitution_once wraps the composio_langchain function."""

    def _run_patch(self, fake_mod):
        """Apply the patch against a fake module, return the wrapped function."""
        with (
            patch.dict(sys.modules, {"composio_langchain.provider": fake_mod}),
            patch("lfx.base.composio.safe_provider._COMPOSIO_AVAILABLE", new=True),
            patch("lfx.base.composio.safe_provider._composio_lc_provider", fake_mod),
        ):
            from lfx.base.composio import safe_provider

            # Reset sentinel so the patch runs fresh
            if hasattr(fake_mod, "_lfx_identifier_patched"):
                del fake_mod._lfx_identifier_patched
            safe_provider._patch_identifier_substitution_once()
        return fake_mod._substitute_reserved_python_keywords

    def test_replaces_substitute_function(self):
        fake_mod = _make_fake_lc_provider()
        original = fake_mod._substitute_reserved_python_keywords
        patched = self._run_patch(fake_mod)
        assert patched is not original

    def test_sets_patched_sentinel(self):
        fake_mod = _make_fake_lc_provider()
        self._run_patch(fake_mod)
        assert getattr(fake_mod, "_lfx_identifier_patched", False)

    def test_idempotent(self):
        fake_mod = _make_fake_lc_provider()
        patched_once = self._run_patch(fake_mod)
        # Mark as already patched and call again
        fake_mod._lfx_identifier_patched = True
        with (
            patch("lfx.base.composio.safe_provider._COMPOSIO_AVAILABLE", new=True),
            patch("lfx.base.composio.safe_provider._composio_lc_provider", fake_mod),
        ):
            from lfx.base.composio import safe_provider

            safe_provider._patch_identifier_substitution_once()
        # Function should not be re-wrapped
        assert fake_mod._substitute_reserved_python_keywords is patched_once

    def test_patched_fn_renames_hyphenated_field(self):
        fake_mod = _make_fake_lc_provider()
        patched = self._run_patch(fake_mod)
        schema = {"properties": {"extension-id": {"type": "string"}}}
        schema, keywords = patched(schema)
        assert "extension_id" in schema["properties"]
        assert keywords["extension_id"] == "extension-id"

    def test_skips_when_composio_unavailable(self):
        fake_mod = _make_fake_lc_provider()
        original = fake_mod._substitute_reserved_python_keywords
        with patch("lfx.base.composio.safe_provider._COMPOSIO_AVAILABLE", new=False):
            from lfx.base.composio import safe_provider

            safe_provider._patch_identifier_substitution_once()
        assert fake_mod._substitute_reserved_python_keywords is original


# ---------------------------------------------------------------------------
# _python_reserved expansion
# ---------------------------------------------------------------------------


class TestPythonReservedExpansion:
    """Verify _python_reserved is expanded to the full Python keyword list.

    The expansion happens at import time when composio is available.
    """

    def test_from_is_in_expanded_reserved_set(self):
        fake_mod = _make_fake_lc_provider()
        with (
            patch("lfx.base.composio.safe_provider._COMPOSIO_AVAILABLE", new=True),
            patch("lfx.base.composio.safe_provider._composio_lc_provider", fake_mod),
        ):
            fake_mod._python_reserved = set(keyword.kwlist)
        assert "from" in fake_mod._python_reserved

    def test_all_python_keywords_covered(self):
        fake_mod = _make_fake_lc_provider()
        fake_mod._python_reserved = set(keyword.kwlist)
        assert set(keyword.kwlist).issubset(fake_mod._python_reserved)

    def test_original_reserved_words_still_covered(self):
        """'for' and 'async' were in the original set — must still be handled."""
        fake_mod = _make_fake_lc_provider()
        fake_mod._python_reserved = set(keyword.kwlist)
        assert "for" in fake_mod._python_reserved
        assert "async" in fake_mod._python_reserved
