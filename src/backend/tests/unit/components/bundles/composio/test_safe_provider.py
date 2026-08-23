"""Tests for SafeLangchainProvider schema and argument hardening.

Composio's ``_substitute_file_uploads_recursively`` and
``pydantic_model_from_param_schema`` raw-subscript ``properties[name]["type"]``,
so any tool whose ``input_parameters`` schema has a property without an explicit
``"type"`` (Gmail/Calendar actions hit this) raises ``KeyError: 'type'`` at
execute time. ``_sanitize_schema`` injects a sensible ``type`` for every node so
those raw subscripts succeed.

Optional nested action inputs can also arrive as Pydantic models whose leaves
are empty strings. The provider omits those empty optional containers before
Composio validation while preserving required and meaningful values (#14715).
"""

from types import SimpleNamespace

import pytest
from pydantic import BaseModel

composio = pytest.importorskip("composio", reason="composio extra not installed in this env")
pytest.importorskip("composio_langchain", reason="composio extra not installed in this env")

from lfx.base.composio.safe_provider import (  # noqa: E402
    SafeLangchainProvider,
    _omit_empty_optional_containers,
    _sanitize_schema,
)


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

    def test_file_helper_uploads_accepts_positional_args(self):
        """Forward-compat guard: wrapper must tolerate positional invocation.

        Upstream Composio currently uses keyword args for the recursive
        self-calls, but a future release could switch to positionals. The
        wrapper uses ``*args, **kwargs`` so either calling convention works.
        """
        from composio.core.models._files import FileHelper

        helper = FileHelper.__new__(FileHelper)

        schema = {"type": "object", "properties": {"payload": {"description": "blob"}}}
        request = {"payload": {"foo": "bar"}}

        # Positional call mirrors a hypothetical upstream signature change.
        result = helper._substitute_file_uploads_recursively(None, schema, request)
        assert result == request

    def test_pydantic_builder_patched(self):
        """``pydantic_model_from_param_schema`` must be wrapped on import.

        The builder runs during ``tools.get`` for the direct-execute path that
        bypasses ``configure_tools``, so without this patch Gmail/Calendar
        actions would still KeyError on the legacy path.
        """
        from composio.utils import shared as composio_shared

        assert getattr(composio_shared, "_lfx_safe_patched", False) is True

    def test_pydantic_builder_no_keyerror_on_untyped_property(self):
        """End-to-end guard for the third KeyError site.

        Without the patch, ``prop_info["type"]`` would raise ``KeyError('type')``
        on the typeless ``payload`` property. With it, the builder returns a
        valid pydantic model.
        """
        from composio.utils.shared import pydantic_model_from_param_schema

        schema = {
            "title": "TestParams",
            "properties": {"payload": {"title": "Payload", "description": "blob"}},
        }
        model = pydantic_model_from_param_schema(schema)
        # Defaulted type is "string", which maps to ``str`` in Composio's type table.
        assert "payload" in model.model_fields


class TestOptionalContainerNormalization:
    """Empty optional objects should not become invalid Composio action input."""

    attachment_schema = {
        "type": "object",
        "properties": {
            "attachment": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "data": {"type": "string"},
                },
            }
        },
    }

    def test_empty_optional_attachment_is_omitted(self):
        arguments = {"to": "recipient@example.com", "attachment": {"name": "", "data": ""}}

        result = _omit_empty_optional_containers(arguments, self.attachment_schema)

        assert result == {"to": "recipient@example.com"}
        assert arguments["attachment"] == {"name": "", "data": ""}

    def test_nonempty_attachment_is_preserved(self):
        arguments = {"attachment": {"name": "report.pdf", "data": "base64-data"}}

        result = _omit_empty_optional_containers(arguments, self.attachment_schema)

        assert result == arguments

    def test_required_empty_attachment_is_preserved_for_validation(self):
        schema = {**self.attachment_schema, "required": ["attachment"]}
        arguments = {"attachment": {"name": "", "data": ""}}

        result = _omit_empty_optional_containers(arguments, schema)

        assert result == arguments

    def test_valid_falsy_values_keep_optional_object(self):
        schema = {
            "type": "object",
            "properties": {
                "options": {
                    "type": "object",
                    "properties": {
                        "enabled": {"type": "boolean"},
                        "retry_count": {"type": "integer"},
                    },
                }
            },
        }
        arguments = {"options": {"enabled": False, "retry_count": 0}}

        result = _omit_empty_optional_containers(arguments, schema)

        assert result == arguments

    def test_provider_omits_empty_pydantic_attachment_before_execute(self):
        captured = {}

        def execute_tool(slug, arguments):
            captured.update(slug=slug, arguments=arguments)
            return {"ok": True}

        tool = SimpleNamespace(
            slug="GMAIL_CREATE_EMAIL_DRAFT",
            description="Create a Gmail draft",
            input_parameters={"title": "GmailDraftInput", **self.attachment_schema},
        )

        wrapped = SafeLangchainProvider().wrap_tool(tool, execute_tool)
        result = wrapped.invoke({"attachment": {"name": "", "data": ""}})

        assert result == {"ok": True}
        assert captured == {"slug": "GMAIL_CREATE_EMAIL_DRAFT", "arguments": {}}

    def test_pydantic_list_item_drops_nested_empty_attachment(self):
        class Attachment(BaseModel):
            name: str
            data: str

        class Draft(BaseModel):
            subject: str
            attachment: Attachment

        draft_schema = {
            "type": "object",
            "properties": {
                "subject": {"type": "string"},
                "attachment": self.attachment_schema["properties"]["attachment"],
            },
        }
        schema = {"type": "object", "properties": {"drafts": {"type": "array", "items": draft_schema}}}
        draft = Draft(subject="test", attachment=Attachment(name="", data=""))

        result = _omit_empty_optional_containers({"drafts": [draft]}, schema)

        assert result == {"drafts": [{"subject": "test"}]}


class TestNoOpOnAlreadyTypedSchemas:
    """Regression preservation: schemas that worked pre-patch must round-trip unchanged.

    The non-overwrite invariant in ``_sanitize_schema`` is the basis for the
    "no regression" claim; these tests exercise the integration layer to
    confirm that the patch is bit-identical for fully-typed schemas.
    """

    def test_sanitize_is_no_op_on_fully_typed_schema(self):
        import copy

        schema = {
            "type": "object",
            "properties": {
                "count": {"type": "integer"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "meta": {"type": "object", "properties": {"k": {"type": "string"}}},
            },
        }
        before = copy.deepcopy(schema)
        _sanitize_schema(schema)
        assert schema == before

    def test_file_helper_uploads_unchanged_on_fully_typed_schema(self):
        from composio.core.models._files import FileHelper

        helper = FileHelper.__new__(FileHelper)
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        request = {"name": "value"}
        result = helper._substitute_file_uploads_recursively(tool=None, schema=schema, request=request)
        assert result == request


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
