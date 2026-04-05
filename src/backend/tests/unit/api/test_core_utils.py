"""Tests for pure utility functions in langflow.api.utils.core module."""

import pytest

from langflow.api.utils.core import (
    _get_provider_from_template,
    _join_code_from_lines,
    _split_code_to_lines,
    format_elapsed_time,
    format_exception_message,
    format_syntax_error_message,
    get_causing_exception,
    get_is_component_from_data,
    get_suggestion_message,
    has_api_terms,
    normalize_code_for_import,
    normalize_flow_for_export,
    parse_exception,
    parse_value,
    remove_api_keys,
)


class TestHasApiTerms:
    def test_api_key(self):
        assert has_api_terms("api_key") is True

    def test_api_token(self):
        assert has_api_terms("api_token") is True

    def test_api_tokens_excluded(self):
        # "tokens" plural is excluded
        assert has_api_terms("api_tokens") is False

    def test_no_api(self):
        assert has_api_terms("username") is False

    def test_just_api(self):
        assert has_api_terms("api") is False

    def test_openai_api_key(self):
        assert has_api_terms("openai_api_key") is True


class TestGetProviderFromTemplate:
    def test_with_provider(self):
        template = {"model": {"value": [{"provider": "OpenAI"}]}}
        assert _get_provider_from_template(template) == "OpenAI"

    def test_no_model_field(self):
        assert _get_provider_from_template({}) is None

    def test_model_not_dict(self):
        assert _get_provider_from_template({"model": "string"}) is None

    def test_value_not_list(self):
        assert _get_provider_from_template({"model": {"value": "string"}}) is None

    def test_empty_list(self):
        assert _get_provider_from_template({"model": {"value": []}}) is None

    def test_first_item_not_dict(self):
        assert _get_provider_from_template({"model": {"value": ["str"]}}) is None


class TestRemoveApiKeys:
    def test_removes_api_key(self):
        flow = {
            "data": {
                "nodes": [{
                    "data": {
                        "node": {
                            "template": {
                                "api_key": {"name": "api_key", "password": True, "value": "secret123"},
                                "model_name": {"name": "model_name", "value": "gpt-4"},
                            }
                        }
                    }
                }]
            }
        }
        result = remove_api_keys(flow)
        assert result["data"]["nodes"][0]["data"]["node"]["template"]["api_key"]["value"] is None
        assert result["data"]["nodes"][0]["data"]["node"]["template"]["model_name"]["value"] == "gpt-4"

    def test_no_nodes(self):
        flow = {"data": {"nodes": []}}
        result = remove_api_keys(flow)
        assert result == flow

    def test_missing_data(self):
        flow = {}
        result = remove_api_keys(flow)
        assert result == flow

    def test_non_dict_node_data(self):
        flow = {"data": {"nodes": [{"data": "not_a_dict"}]}}
        result = remove_api_keys(flow)
        assert result == flow


class TestSplitCodeToLines:
    def test_splits_code_string(self):
        flow = {
            "data": {
                "nodes": [{
                    "data": {
                        "node": {
                            "template": {
                                "code_field": {"type": "code", "value": "line1\nline2\nline3"},
                            }
                        }
                    }
                }]
            }
        }
        _split_code_to_lines(flow)
        assert flow["data"]["nodes"][0]["data"]["node"]["template"]["code_field"]["value"] == ["line1", "line2", "line3"]

    def test_ignores_non_code_type(self):
        flow = {
            "data": {
                "nodes": [{
                    "data": {
                        "node": {
                            "template": {
                                "text_field": {"type": "text", "value": "line1\nline2"},
                            }
                        }
                    }
                }]
            }
        }
        _split_code_to_lines(flow)
        assert flow["data"]["nodes"][0]["data"]["node"]["template"]["text_field"]["value"] == "line1\nline2"

    def test_already_list_ignored(self):
        flow = {
            "data": {
                "nodes": [{
                    "data": {
                        "node": {
                            "template": {
                                "code_field": {"type": "code", "value": ["already", "split"]},
                            }
                        }
                    }
                }]
            }
        }
        _split_code_to_lines(flow)
        assert flow["data"]["nodes"][0]["data"]["node"]["template"]["code_field"]["value"] == ["already", "split"]


class TestJoinCodeFromLines:
    def test_joins_lines(self):
        flow = {
            "data": {
                "nodes": [{
                    "data": {
                        "node": {
                            "template": {
                                "code_field": {"type": "code", "value": ["line1", "line2"]},
                            }
                        }
                    }
                }]
            }
        }
        _join_code_from_lines(flow)
        assert flow["data"]["nodes"][0]["data"]["node"]["template"]["code_field"]["value"] == "line1\nline2"

    def test_string_value_unchanged(self):
        flow = {
            "data": {
                "nodes": [{
                    "data": {
                        "node": {
                            "template": {
                                "code_field": {"type": "code", "value": "already string"},
                            }
                        }
                    }
                }]
            }
        }
        _join_code_from_lines(flow)
        assert flow["data"]["nodes"][0]["data"]["node"]["template"]["code_field"]["value"] == "already string"


class TestSplitJoinRoundTrip:
    def test_roundtrip(self):
        original_code = "def hello():\n    return 'hi'\n"
        flow = {
            "data": {
                "nodes": [{
                    "data": {
                        "node": {
                            "template": {
                                "code_field": {"type": "code", "value": original_code},
                            }
                        }
                    }
                }]
            }
        }
        _split_code_to_lines(flow)
        _join_code_from_lines(flow)
        assert flow["data"]["nodes"][0]["data"]["node"]["template"]["code_field"]["value"] == original_code


class TestNormalizeFlowForExport:
    def test_strips_volatile_fields(self):
        flow = {
            "name": "test",
            "updated_at": "2024-01-01",
            "created_at": "2024-01-01",
            "user_id": "user123",
            "folder_id": "folder123",
            "access_type": "public",
            "gradient": "blue",
            "data": {"nodes": [], "edges": []},
        }
        result = normalize_flow_for_export(flow)
        assert "name" in result
        assert "updated_at" not in result
        assert "created_at" not in result
        assert "user_id" not in result

    def test_strips_node_ui_state(self):
        flow = {
            "data": {
                "nodes": [{
                    "id": "1",
                    "positionAbsolute": {"x": 0, "y": 0},
                    "dragging": False,
                    "selected": True,
                    "data": {"node": {"template": {}}},
                }]
            }
        }
        result = normalize_flow_for_export(flow)
        node = result["data"]["nodes"][0]
        assert "positionAbsolute" not in node
        assert "dragging" not in node
        assert "selected" not in node
        assert "id" in node

    def test_does_not_mutate_original(self):
        flow = {"updated_at": "2024-01-01", "data": {"nodes": []}}
        normalize_flow_for_export(flow)
        assert "updated_at" in flow


class TestNormalizeCodeForImport:
    def test_joins_code_lines(self):
        flow = {
            "data": {
                "nodes": [{
                    "data": {
                        "node": {
                            "template": {
                                "code": {"type": "code", "value": ["a", "b"]},
                            }
                        }
                    }
                }]
            }
        }
        result = normalize_code_for_import(flow)
        assert result["data"]["nodes"][0]["data"]["node"]["template"]["code"]["value"] == "a\nb"

    def test_does_not_mutate_original(self):
        flow = {"data": {"nodes": []}}
        normalize_code_for_import(flow)
        assert flow == {"data": {"nodes": []}}


class TestFormatElapsedTime:
    def test_milliseconds(self):
        assert format_elapsed_time(0.5) == "500 ms"

    def test_zero(self):
        assert format_elapsed_time(0) == "0 ms"

    def test_seconds(self):
        assert format_elapsed_time(5.3) == "5.3 seconds"

    def test_one_second(self):
        assert format_elapsed_time(1.0) == "1.0 second"

    def test_minutes(self):
        result = format_elapsed_time(90.0)
        assert "1 minute" in result
        assert "seconds" in result

    def test_multiple_minutes(self):
        result = format_elapsed_time(150.0)
        assert "2 minutes" in result


class TestFormatSyntaxErrorMessage:
    def test_with_text(self):
        exc = SyntaxError("msg", ("file.py", 5, 3, "bad code here"))
        result = format_syntax_error_message(exc)
        assert "line 5" in result
        assert "bad code here" in result

    def test_without_text(self):
        exc = SyntaxError("msg")
        exc.lineno = 10
        exc.text = None
        result = format_syntax_error_message(exc)
        assert "line 10" in result


class TestGetCausingException:
    def test_no_cause(self):
        exc = ValueError("test")
        assert get_causing_exception(exc) is exc

    def test_with_cause(self):
        cause = TypeError("root cause")
        exc = ValueError("wrapper")
        exc.__cause__ = cause
        assert get_causing_exception(exc) is cause

    def test_nested_causes(self):
        root = RuntimeError("root")
        mid = TypeError("mid")
        mid.__cause__ = root
        top = ValueError("top")
        top.__cause__ = mid
        assert get_causing_exception(top) is root


class TestFormatExceptionMessage:
    def test_syntax_error_cause(self):
        cause = SyntaxError("msg", ("file.py", 5, 3, "bad code"))
        exc = ValueError("wrapper")
        exc.__cause__ = cause
        result = format_exception_message(exc)
        assert "line 5" in result

    def test_regular_exception(self):
        exc = ValueError("something went wrong")
        result = format_exception_message(exc)
        assert result == "something went wrong"


class TestGetSuggestionMessage:
    def test_no_outdated(self):
        result = get_suggestion_message([])
        assert "no outdated" in result

    def test_one_outdated(self):
        result = get_suggestion_message(["ChatInput"])
        assert "1 outdated" in result
        assert "ChatInput" in result

    def test_multiple_outdated(self):
        result = get_suggestion_message(["ChatInput", "OpenAIModel"])
        assert "2 outdated" in result
        assert "ChatInput" in result
        assert "OpenAIModel" in result


class TestParseValue:
    def test_empty_string_dict_input(self):
        assert parse_value("", "DictInput") == {}

    def test_empty_string_other(self):
        assert parse_value("", "TextInput") == ""

    def test_int_input(self):
        assert parse_value("42", "IntInput") == 42

    def test_int_input_none(self):
        assert parse_value(None, "IntInput") is None

    def test_float_input(self):
        assert parse_value("3.14", "FloatInput") == 3.14

    def test_dict_input_string(self):
        result = parse_value('{"key": "value"}', "DictInput")
        assert result == {"key": "value"}

    def test_dict_input_dict(self):
        result = parse_value({"key": "value"}, "DictInput")
        assert result == {"key": "value"}

    def test_dict_input_invalid_json(self):
        assert parse_value("not json", "DictInput") == {}

    def test_dict_input_non_dict_json(self):
        assert parse_value("[1, 2]", "DictInput") == {}

    def test_passthrough(self):
        assert parse_value("hello", "TextInput") == "hello"


class TestParseException:
    def test_with_body(self):
        exc = Exception("test")
        exc.body = {"message": "API Error"}
        assert parse_exception(exc) == "API Error"

    def test_without_body(self):
        exc = Exception("plain error")
        assert parse_exception(exc) == "plain error"


class TestGetIsComponentFromData:
    def test_with_is_component_true(self):
        assert get_is_component_from_data({"is_component": True}) is True

    def test_with_is_component_false(self):
        assert get_is_component_from_data({"is_component": False}) is False

    def test_without_is_component(self):
        assert get_is_component_from_data({}) is None
