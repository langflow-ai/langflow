"""Tests for Composio tool schema sanitization."""

from types import SimpleNamespace

import pytest
from lfx.base.composio.schema_utils import (
    sanitize_tool_args_schema,
    sanitize_tool_args_schema_safe,
    sanitize_tools_with_fallback,
)


class BrokenArgsSchema:
    """Mimics an args schema class emitted by external tool providers."""

    @classmethod
    def model_json_schema(cls):
        return {
            "type": "object",
            "properties": {
                "recipient": {
                    "description": "Email recipient",
                    "anyOf": [{"type": "string"}, {"type": "null"}],
                }
            },
        }


class ValidArgsSchema:
    @classmethod
    def model_json_schema(cls):
        return {
            "type": "object",
            "properties": {
                "subject": {
                    "type": "string",
                    "description": "Email subject",
                }
            },
        }


@pytest.mark.unit
def test_sanitize_tool_args_schema_adds_missing_type_in_tool_args_and_repairs_schema_class():
    tool = SimpleNamespace(
        args={
            "recipient": {
                "description": "Email recipient",
                "anyOf": [{"type": "string"}, {"type": "null"}],
            }
        },
        args_schema=BrokenArgsSchema,
    )

    changed = sanitize_tool_args_schema(tool)

    assert changed is True
    assert tool.args["recipient"]["type"] == ["string", "null"]

    repaired_schema = tool.args_schema.model_json_schema()
    assert repaired_schema["type"] == "object"
    assert "recipient" in repaired_schema["properties"]
    # Pydantic renders str | None as anyOf in model_json_schema(), not type: ["string", "null"]
    recipient_prop = repaired_schema["properties"]["recipient"]
    any_of_types = {v.get("type") for v in recipient_prop.get("anyOf", []) if isinstance(v, dict)}
    assert any_of_types == {"string", "null"}


@pytest.mark.unit
def test_sanitize_tool_args_schema_repairs_none_type_in_tool_args():
    tool = SimpleNamespace(
        args={"body": {"type": None, "description": "Email body"}},
        args_schema=None,
    )

    changed = sanitize_tool_args_schema(tool)

    assert changed is True
    assert tool.args["body"]["type"] == "string"


@pytest.mark.unit
def test_sanitize_tool_args_schema_is_noop_for_valid_schema():
    tool = SimpleNamespace(
        args={"subject": {"type": "string", "description": "Email subject"}},
        args_schema=ValidArgsSchema,
    )

    changed = sanitize_tool_args_schema(tool)

    assert changed is False
    assert tool.args["subject"]["type"] == "string"


@pytest.mark.unit
def test_sanitize_tool_args_schema_handles_complex_nested_schemas():
    """Test that sanitization works through the public API for complex nested structures."""
    tool = SimpleNamespace(
        args={
            "items_field": {
                "description": "Items array",
                "items": {
                    "description": "An item",
                    "anyOf": [{"type": "integer"}, {"type": "null"}],
                },
            }
        },
        args_schema=None,
    )

    changed = sanitize_tool_args_schema(tool)

    assert changed is True
    assert tool.args["items_field"]["type"] == "array"
    # items has anyOf: [{type: integer}, {type: null}] — nullability is preserved
    assert tool.args["items_field"]["items"]["type"] == ["integer", "null"]


@pytest.mark.unit
def test_sanitize_tool_args_schema_handles_enum_inference():
    """Test that type inference from enum values works through the public API."""
    tool = SimpleNamespace(
        args={
            "status": {
                "description": "A string value",
                "oneOf": [
                    {"enum": ["a", "b"]},
                    {"type": "null"},
                ],
            }
        },
        args_schema=None,
    )

    changed = sanitize_tool_args_schema(tool)

    assert changed is True
    assert tool.args["status"]["oneOf"][0]["type"] == "string"
    assert isinstance(tool.args["status"]["type"], list)
    assert set(tool.args["status"]["type"]) == {"string", "null"}


@pytest.mark.unit
def test_sanitize_tool_args_schema_handles_object_and_array_enum_inference():
    """Enum inference should include object/array when enum members use those shapes."""
    tool = SimpleNamespace(
        args={
            "payload": {
                "description": "Mixed enum payload",
                "enum": [{"k": "v"}, [1, 2]],
            }
        },
        args_schema=None,
    )

    changed = sanitize_tool_args_schema(tool)

    assert changed is True
    inferred = tool.args["payload"]["type"]
    assert isinstance(inferred, list)
    assert set(inferred) == {"array", "object"}


@pytest.mark.unit
def test_sanitize_tool_args_schema_handles_allof_schemas():
    """Test that allOf variants are recursively sanitized through the public API."""
    tool = SimpleNamespace(
        args={
            "nested": {
                "allOf": [
                    {"properties": {"x": {"description": "x coord"}}},
                ]
            }
        },
        args_schema=None,
    )

    changed = sanitize_tool_args_schema(tool)

    assert changed is True
    # Top-level allOf composition should infer object, not default string.
    assert tool.args["nested"]["type"] == "object"
    # Verify nested sanitization occurred
    nested_schema = tool.args["nested"]["allOf"][0]
    assert nested_schema.get("type") == "object"
    if "properties" in nested_schema and "x" in nested_schema["properties"]:
        assert nested_schema["properties"]["x"]["type"] == "string"


@pytest.mark.unit
def test_sanitize_tool_args_schema_normalizes_none_properties_to_empty_dict():
    """properties: None on an object schema should be normalized to {} (not left as None)."""
    for type_value in ("object", ["object", "null"]):
        tool = SimpleNamespace(
            args={
                "payload": {
                    "type": type_value,
                    "properties": None,
                }
            },
            args_schema=None,
        )

        changed = sanitize_tool_args_schema(tool)

        assert changed is True, f"Expected change for type={type_value!r}"
        assert tool.args["payload"]["properties"] == {}, (
            f"Expected properties to be {{}} for type={type_value!r}, got {tool.args['payload']['properties']!r}"
        )


@pytest.mark.unit
def test_sanitize_tool_args_schema_safe_returns_true_and_does_not_call_log_fn_on_success():
    """sanitize_tool_args_schema_safe returns True and never calls log_fn when no exception occurs."""
    tool = SimpleNamespace(
        name="my_tool",
        args={"subject": {"type": "string"}},
        args_schema=ValidArgsSchema,
    )
    log_messages: list[str] = []

    result = sanitize_tool_args_schema_safe(tool, log_messages.append)

    assert result is True
    assert log_messages == []


@pytest.mark.unit
def test_sanitize_tool_args_schema_safe_returns_false_and_calls_log_fn_on_type_error():
    """sanitize_tool_args_schema_safe returns False and calls log_fn when sanitization raises TypeError."""

    class RaisingArgsSchema:
        @classmethod
        def model_json_schema(cls) -> dict:
            msg = "simulated schema error"
            raise TypeError(msg)

    tool = SimpleNamespace(
        name="failing_tool",
        args={},
        args_schema=RaisingArgsSchema,
    )
    log_messages: list[str] = []

    result = sanitize_tool_args_schema_safe(tool, log_messages.append)

    assert result is False
    assert len(log_messages) == 1
    assert "failing_tool" in log_messages[0]
    assert "TypeError" in log_messages[0]


@pytest.mark.unit
def test_sanitize_tool_args_schema_safe_returns_false_and_calls_log_fn_on_attribute_error():
    """sanitize_tool_args_schema_safe returns False and calls log_fn when sanitization raises AttributeError."""

    class BadArgsSchema:
        @classmethod
        def model_json_schema(cls) -> dict:
            msg = "missing attribute"
            raise AttributeError(msg)

    tool = SimpleNamespace(
        name="bad_tool",
        args={},
        args_schema=BadArgsSchema,
    )
    log_messages: list[str] = []

    result = sanitize_tool_args_schema_safe(tool, log_messages.append)

    assert result is False
    assert len(log_messages) == 1
    assert "bad_tool" in log_messages[0]
    assert "AttributeError" in log_messages[0]


@pytest.mark.unit
def test_sanitize_tool_args_schema_safe_returns_false_and_calls_log_fn_on_unexpected_exception():
    """sanitize_tool_args_schema_safe catches any Exception, not only the originally listed types."""

    class UnexpectedErrorSchema:
        @classmethod
        def model_json_schema(cls) -> dict:
            msg = "unexpected provider error"
            raise RuntimeError(msg)

    tool = SimpleNamespace(
        name="unexpected_tool",
        args={},
        args_schema=UnexpectedErrorSchema,
    )
    log_messages: list[str] = []

    result = sanitize_tool_args_schema_safe(tool, log_messages.append)

    assert result is False
    assert len(log_messages) == 1
    assert "unexpected_tool" in log_messages[0]
    assert "RuntimeError" in log_messages[0]


class _RaisingArgsSchema:
    """Shared helper: model_json_schema() always raises TypeError."""

    @classmethod
    def model_json_schema(cls) -> dict:
        msg = "bad schema"
        raise TypeError(msg)


@pytest.mark.unit
def test_sanitize_tools_with_fallback_excludes_failing_tools_and_calls_log_fn_per_failure():
    """Failing tools are excluded, log_fn is called exactly once per failure."""
    good_tool = SimpleNamespace(name="good", args={"x": {"type": "string"}}, args_schema=None)
    bad_tool = SimpleNamespace(name="bad", args={}, args_schema=_RaisingArgsSchema)
    log_messages: list[str] = []

    sanitized, excluded_summary = sanitize_tools_with_fallback([good_tool, bad_tool], log_messages.append)

    assert sanitized == [good_tool]
    assert excluded_summary == "bad"
    # log_fn called once for the one failing tool
    assert len(log_messages) == 1
    assert "bad" in log_messages[0]


@pytest.mark.unit
def test_sanitize_tools_with_fallback_returns_none_summary_when_all_succeed():
    """excluded_summary is None when no tools fail sanitization."""
    tool = SimpleNamespace(name="ok", args={"x": {"type": "string"}}, args_schema=None)
    log_messages: list[str] = []

    sanitized, excluded_summary = sanitize_tools_with_fallback([tool], log_messages.append)

    assert sanitized == [tool]
    assert excluded_summary is None
    assert log_messages == []


@pytest.mark.unit
def test_sanitize_tools_with_fallback_formats_and_n_more_when_failures_exceed_cap():
    """excluded_summary includes 'and N more' when failures exceed max_summary_examples."""
    # Build 3 failing tools but cap at 2 logged examples
    bad_tools = [SimpleNamespace(name=f"bad_{i}", args={}, args_schema=_RaisingArgsSchema) for i in range(3)]
    log_messages: list[str] = []

    sanitized, excluded_summary = sanitize_tools_with_fallback(bad_tools, log_messages.append, max_summary_examples=2)

    assert sanitized == []
    assert excluded_summary == "bad_0, bad_1, and 1 more"
    # log_fn called once per failure regardless of cap
    assert len(log_messages) == 3
