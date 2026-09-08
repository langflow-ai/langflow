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

from lfx.base.composio.safe_provider import (  # noqa: E402
    SafeLangchainProvider,
    _harden_schema,
    _relax_attachment_requirements,
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


class TestRelaxAttachmentRequirements:
    """Reproduces the GMAIL_CREATE_EMAIL_DRAFT / GMAIL_SEND_EMAIL bug report.

    Composio's raw schema for these actions marks "attachment" required even
    though a real send/draft never needs one, you just omit it. Left alone,
    an LLM building a tool call fabricates an empty placeholder
    ({"name": "", "data": ""}) to satisfy the schema, which the real Gmail
    API then rejects: "Tool input validation error".
    """

    def test_gmail_create_email_draft_shaped_schema(self):
        # Modeled on the real GMAIL_CREATE_EMAIL_DRAFT input_parameters shape
        # from the bug report: recipient/subject/body genuinely required,
        # attachment required only because of the upstream schema defect.
        schema = {
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "recipient_email": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "is_html": {"type": "boolean"},
                "attachment": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}, "data": {"type": "string"}},
                },
            },
            "required": ["user_id", "recipient_email", "attachment"],
        }
        _relax_attachment_requirements(schema)
        assert schema["required"] == ["user_id", "recipient_email"]
        # The property itself is untouched — only its false "required" status is dropped.
        assert "attachment" in schema["properties"]

    def test_pydantic_model_no_longer_requires_attachment(self):
        """End-to-end: after hardening, the built Pydantic model accepts a call with no attachment."""
        from composio.utils.shared import pydantic_model_from_param_schema

        schema = {
            "title": "GmailCreateEmailDraft",
            "type": "object",
            "properties": {
                "subject": {"type": "string", "title": "Subject"},
                "attachment": {"type": "string", "title": "Attachment"},
            },
            "required": ["subject", "attachment"],
        }
        _harden_schema(schema)
        model = pydantic_model_from_param_schema(schema)
        # subject is still mandatory; attachment must now be optional.
        assert model.model_fields["subject"].is_required() is True
        assert model.model_fields["attachment"].is_required() is False
        # Confirms the model can actually be built with attachment omitted —
        # the exact call shape an LLM should now be free to make.
        instance = model(subject="test")
        assert instance.subject == "test"

    def test_wrap_tool_calls_harden_schema_on_input_parameters(self):
        """``wrap_tool`` must route through ``_harden_schema``, not just ``_sanitize_schema``.

        Avoids constructing a full ``composio.types.Tool`` (its nested
        ``ItemDeprecated``/``ItemToolkit`` shape is version-coupled and brittle
        to pin in a test); a lightweight stand-in with the one attribute
        ``wrap_tool`` reads (``input_parameters``) is enough to prove the
        dispatch is wired to the attachment-relaxing patch, not just the
        original type-defaulting one.
        """

        class _FakeTool:
            input_parameters = {
                "type": "object",
                "properties": {"subject": {"type": "string"}, "attachment": {"type": "string"}},
                "required": ["subject", "attachment"],
            }

        provider = SafeLangchainProvider()
        fake_tool = _FakeTool()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(SafeLangchainProvider.__bases__[0], "wrap_tool", lambda self, tool, execute_tool: tool)  # noqa: ARG005
            result = provider.wrap_tool(tool=fake_tool, execute_tool=lambda **_kwargs: None)
        assert result.input_parameters["required"] == ["subject"]

    def test_wrap_tool_strips_blank_attachment_before_the_real_execute_call(self):
        """End-to-end reproduction of the follow-up bug: schema-optional isn't enough.

        Making "attachment" optional in the schema stops an LLM from being
        *forced* to supply it, but doesn't stop one from submitting the exact
        {"name": "", "data": ""} placeholder anyway "to be safe" — that now
        passes local validation (the field is optional) and would reach the
        real Gmail API, which rejects it there instead: "the email tool
        rejected its attachment parameter, although no attachment was
        requested". This drives the real ``wrap_tool``/``safe_execute_tool``
        path with exactly that placeholder and asserts it never reaches the
        underlying ``execute_tool`` call.
        """
        received_args: dict = {}

        def fake_execute_tool(slug: str, arguments: dict) -> dict:
            received_args["slug"] = slug
            received_args["arguments"] = arguments
            return {"successful": True, "data": {}}

        def fake_base_wrap_tool(self, tool, execute_tool):  # noqa: ARG001
            # Stand-in for composio_langchain's real wrap_tool: it eventually
            # calls execute_tool with whatever kwargs the LLM's tool call
            # produced. Drive it with the bug report's exact payload.
            execute_tool(
                "GMAIL_CREATE_EMAIL_DRAFT",
                {"subject": "test", "attachment": {"name": "", "data": ""}},
            )
            return tool

        class _FakeTool:
            input_parameters = {
                "type": "object",
                "properties": {"subject": {"type": "string"}, "attachment": {"type": "string"}},
                "required": ["subject", "attachment"],
            }

        provider = SafeLangchainProvider()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(SafeLangchainProvider.__bases__[0], "wrap_tool", fake_base_wrap_tool)
            provider.wrap_tool(tool=_FakeTool(), execute_tool=fake_execute_tool)

        assert received_args["slug"] == "GMAIL_CREATE_EMAIL_DRAFT"
        assert received_args["arguments"] == {"subject": "test"}

    def test_wrap_tool_preserves_a_real_attachment_through_execute_call(self):
        """Negative case: a genuine attachment must still reach the real call."""
        received_args: dict = {}

        def fake_execute_tool(_slug: str, arguments: dict) -> dict:
            received_args["arguments"] = arguments
            return {"successful": True, "data": {}}

        def fake_base_wrap_tool(self, tool, execute_tool):  # noqa: ARG001
            execute_tool(
                "GMAIL_CREATE_EMAIL_DRAFT",
                {"subject": "test", "attachment": {"name": "invoice.pdf", "data": "base64=="}},
            )
            return tool

        class _FakeTool:
            input_parameters = {
                "type": "object",
                "properties": {"subject": {"type": "string"}, "attachment": {"type": "string"}},
                "required": ["subject", "attachment"],
            }

        provider = SafeLangchainProvider()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(SafeLangchainProvider.__bases__[0], "wrap_tool", fake_base_wrap_tool)
            provider.wrap_tool(tool=_FakeTool(), execute_tool=fake_execute_tool)

        assert received_args["arguments"]["attachment"] == {"name": "invoice.pdf", "data": "base64=="}


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
