"""Tests for SafeLangchainProvider schema sanitization (issues #12894/#12895).

Composio's ``_substitute_file_uploads_recursively`` and
``pydantic_model_from_param_schema`` raw-subscript ``properties[name]["type"]``,
so any tool whose ``input_parameters`` schema has a property without an explicit
``"type"`` (Gmail/Calendar actions hit this) raises ``KeyError: 'type'`` at
execute time. ``_sanitize_schema`` injects a sensible ``type`` for every node so
those raw subscripts succeed.
"""

import pytest

composio = pytest.importorskip("composio", reason="composio extra not installed in this env")
pytest.importorskip("composio_langchain", reason="composio extra not installed in this env")

from lfx.base.composio.safe_provider import SafeLangchainProvider, _sanitize_schema  # noqa: E402


class TestSanitizeSchema:
    def test_object_with_typeless_property_gets_string_type(self):
        schema = {"properties": {"foo": {}}}
        _sanitize_schema(schema)
        assert schema["type"] == "object"
        assert schema["properties"]["foo"]["type"] == "string"

    def test_nested_object_inferred_from_properties(self):
        schema = {"properties": {"outer": {"properties": {"inner": {}}}}}
        _sanitize_schema(schema)
        assert schema["properties"]["outer"]["type"] == "object"
        assert schema["properties"]["outer"]["properties"]["inner"]["type"] == "string"

    def test_array_inferred_from_items(self):
        schema = {"properties": {"tags": {"items": {}}}}
        _sanitize_schema(schema)
        assert schema["properties"]["tags"]["type"] == "array"
        assert schema["properties"]["tags"]["items"]["type"] == "string"

    def test_anyof_property_gets_default_type(self):
        # Composio's _files.py:308 raw-subscripts ["type"] without resolving
        # anyOf, so a default ``type`` must be injected even on union schemas.
        schema = {"properties": {"x": {"anyOf": [{"type": "string"}, {"type": "null"}]}}}
        _sanitize_schema(schema)
        assert schema["properties"]["x"]["type"] == "string"
        # Union arms must still be walked + sanitized.
        assert all("type" in arm for arm in schema["properties"]["x"]["anyOf"])

    def test_ref_only_property_gets_default_type(self):
        schema = {"properties": {"x": {"$ref": "#/$defs/Foo"}}}
        _sanitize_schema(schema)
        assert schema["properties"]["x"]["type"] == "string"

    def test_existing_types_preserved(self):
        schema = {
            "type": "object",
            "properties": {"count": {"type": "integer"}, "name": {"type": "string"}},
        }
        _sanitize_schema(schema)
        assert schema["type"] == "object"
        assert schema["properties"]["count"]["type"] == "integer"
        assert schema["properties"]["name"]["type"] == "string"

    def test_defs_walked(self):
        schema = {
            "$defs": {"Item": {"properties": {"id": {}}}},
            "properties": {"thing": {"$ref": "#/$defs/Item"}},
        }
        _sanitize_schema(schema)
        assert schema["$defs"]["Item"]["type"] == "object"
        assert schema["$defs"]["Item"]["properties"]["id"]["type"] == "string"

    def test_non_dict_input_no_op(self):
        _sanitize_schema(None)
        _sanitize_schema("not a dict")
        _sanitize_schema(42)


class TestSafeLangchainProviderRegression:
    """Reproduces the GMAIL_FETCH_EMAILS / GOOGLECALENDAR_* failure mode."""

    def test_substitute_file_uploads_no_longer_keyerrors_after_sanitize(self):
        # Schema shape that triggers KeyError("type") in
        # composio.core.models._files._substitute_file_uploads_recursively:
        # property "attachment" lacks a "type" key but request supplies a dict.
        schema = {"properties": {"attachment": {"description": "binary blob"}}}

        # Without sanitize -> raw subscript would KeyError on params["attachment"]["type"]
        # because the property has no "type". Sanitize first, then assert lookup is safe.
        _sanitize_schema(schema)
        params = schema["properties"]
        # Composio's raw expression: params[_param]["type"] == "object"
        # After sanitize, lookup must succeed and (correctly) be False here.
        assert params["attachment"]["type"] == "string"

    def test_provider_subclass_instantiable(self):
        provider = SafeLangchainProvider()
        assert provider is not None
        # Confirms LangchainProvider's metaclass-required `name` kwarg is satisfied.
        assert getattr(provider.__class__, "name", None) == "langchain"

    def test_file_helper_methods_patched(self):
        """FileHelper must be monkey-patched on import.

        Direct execute_action paths bypass wrap_tool, so the patch on
        FileHelper is the only place that catches them.
        """
        from composio.core.models._files import FileHelper

        assert getattr(FileHelper, "_lfx_safe_patched", False) is True

    def test_file_helper_uploads_no_keyerror_on_untyped_property(self):
        """End-to-end guard against the original KeyError site.

        Drives Composio's upload walker with a schema whose property has no
        ``type`` key. Without the patch this raises ``KeyError('type')``; with
        it, the call returns the request unchanged.
        """
        from composio.core.models._files import FileHelper

        helper = FileHelper.__new__(FileHelper)  # bypass __init__ — no client needed for this code path

        schema = {"type": "object", "properties": {"payload": {"description": "blob"}}}
        request = {"payload": {"foo": "bar"}}

        # ``tool`` argument is unused on this happy path
        result = helper._substitute_file_uploads_recursively(tool=None, schema=schema, request=request)
        assert result == request


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
