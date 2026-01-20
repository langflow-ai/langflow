"""Tests for flow execution service."""

import json
from pathlib import Path
from unittest.mock import patch

from langflow.agentic.services.flow_executor import (
    FLOWS_BASE_PATH,
    FlowExecutionResult,
    _load_and_prepare_flow,
    _parse_event_data,
    extract_response_text,
    inject_model_into_flow,
)


class TestFlowExecutionResult:
    """Tests for FlowExecutionResult dataclass."""

    def test_should_initialize_with_defaults(self):
        result = FlowExecutionResult()

        assert result.result == {}
        assert result.error is None
        assert result.has_error is False
        assert result.has_result is False

    def test_should_detect_error(self):
        result = FlowExecutionResult(error=ValueError("test error"))

        assert result.has_error is True
        assert result.has_result is False

    def test_should_detect_result(self):
        result = FlowExecutionResult(result={"key": "value"})

        assert result.has_error is False
        assert result.has_result is True

    def test_should_handle_both_result_and_error(self):
        result = FlowExecutionResult(result={"key": "value"}, error=ValueError("test"))

        assert result.has_error is True
        assert result.has_result is True


class TestInjectModelIntoFlow:
    """Tests for inject_model_into_flow function."""

    def test_should_inject_model_into_agent_node(self):
        flow_data = {"data": {"nodes": [{"data": {"type": "Agent", "node": {"template": {"model": {"value": None}}}}}]}}

        with patch("langflow.agentic.services.flow_executor.get_provider_config") as mock_config:
            mock_config.return_value = {
                "api_key_param": "api_key",
                "model_class": "ChatOpenAI",
                "model_name_param": "model_name",
                "variable_name": "OPENAI_API_KEY",
                "icon": "OpenAI",
            }

            result = inject_model_into_flow(
                flow_data, provider="OpenAI", model_name="gpt-4o", api_key_var="OPENAI_API_KEY"
            )

        model_value = result["data"]["nodes"][0]["data"]["node"]["template"]["model"]["value"]
        assert len(model_value) == 1
        assert model_value[0]["provider"] == "OpenAI"
        assert model_value[0]["name"] == "gpt-4o"

    def test_should_not_modify_non_agent_nodes(self):
        flow_data = {"data": {"nodes": [{"data": {"type": "TextInput", "node": {"template": {}}}}]}}

        with patch("langflow.agentic.services.flow_executor.get_provider_config") as mock_config:
            mock_config.return_value = {
                "api_key_param": "api_key",
                "model_class": "ChatOpenAI",
                "model_name_param": "model_name",
                "variable_name": "OPENAI_API_KEY",
                "icon": "OpenAI",
            }

            result = inject_model_into_flow(flow_data, provider="OpenAI", model_name="gpt-4o")

        assert "model" not in result["data"]["nodes"][0]["data"]["node"]["template"]

    def test_should_inject_into_multiple_agent_nodes(self):
        flow_data = {
            "data": {
                "nodes": [
                    {"data": {"type": "Agent", "node": {"template": {"model": {"value": None}}}}},
                    {"data": {"type": "Agent", "node": {"template": {"model": {"value": None}}}}},
                ]
            }
        }

        with patch("langflow.agentic.services.flow_executor.get_provider_config") as mock_config:
            mock_config.return_value = {
                "api_key_param": "api_key",
                "model_class": "ChatAnthropic",
                "model_name_param": "model",
                "variable_name": "ANTHROPIC_API_KEY",
                "icon": "Anthropic",
            }

            result = inject_model_into_flow(flow_data, provider="Anthropic", model_name="claude-sonnet-4-5-20250514")

        for node in result["data"]["nodes"]:
            model_value = node["data"]["node"]["template"]["model"]["value"]
            assert model_value[0]["provider"] == "Anthropic"

    def test_should_handle_empty_nodes_list(self):
        flow_data = {"data": {"nodes": []}}

        with patch("langflow.agentic.services.flow_executor.get_provider_config") as mock_config:
            mock_config.return_value = {
                "api_key_param": "api_key",
                "model_class": "ChatOpenAI",
                "model_name_param": "model_name",
                "variable_name": "OPENAI_API_KEY",
                "icon": "OpenAI",
            }

            result = inject_model_into_flow(flow_data, provider="OpenAI", model_name="gpt-4o")

        assert result["data"]["nodes"] == []

    def test_should_include_extra_params_from_provider_config(self):
        flow_data = {"data": {"nodes": [{"data": {"type": "Agent", "node": {"template": {"model": {"value": None}}}}}]}}

        with patch("langflow.agentic.services.flow_executor.get_provider_config") as mock_config:
            mock_config.return_value = {
                "api_key_param": "api_key",
                "model_class": "ChatOpenAI",
                "model_name_param": "model_name",
                "variable_name": "OPENAI_API_KEY",
                "icon": "OpenAI",
                "base_url_param": "base_url",
            }

            result = inject_model_into_flow(flow_data, provider="OpenAI", model_name="gpt-4o")

        model_metadata = result["data"]["nodes"][0]["data"]["node"]["template"]["model"]["value"][0]["metadata"]
        assert "base_url_param" in model_metadata


class TestParseEventData:
    """Tests for _parse_event_data function."""

    def test_should_parse_valid_event_data(self):
        event_data = b'{"event": "token", "data": {"chunk": "Hello"}}'

        event_type, data = _parse_event_data(event_data)

        assert event_type == "token"
        assert data["chunk"] == "Hello"

    def test_should_return_none_for_empty_data(self):
        event_data = b""

        event_type, data = _parse_event_data(event_data)

        assert event_type is None
        assert data == {}

    def test_should_return_none_for_whitespace_data(self):
        event_data = b"   \n  "

        event_type, data = _parse_event_data(event_data)

        assert event_type is None
        assert data == {}

    def test_should_handle_end_event(self):
        event_data = b'{"event": "end", "data": {}}'

        event_type, data = _parse_event_data(event_data)

        assert event_type == "end"
        assert data == {}

    def test_should_return_empty_data_if_not_provided(self):
        event_data = b'{"event": "token"}'

        event_type, data = _parse_event_data(event_data)

        assert event_type == "token"
        assert data == {}


class TestExtractResponseText:
    """Tests for extract_response_text function."""

    def test_should_extract_from_result_key(self):
        result = {"result": "This is the response text"}

        text = extract_response_text(result)

        assert text == "This is the response text"

    def test_should_extract_from_text_key(self):
        result = {"text": "This is the text"}

        text = extract_response_text(result)

        assert text == "This is the text"

    def test_should_extract_from_exception_message(self):
        result = {"exception_message": "An error occurred"}

        text = extract_response_text(result)

        assert text == "An error occurred"

    def test_should_prefer_result_over_text(self):
        result = {"result": "from result", "text": "from text"}

        text = extract_response_text(result)

        assert text == "from result"

    def test_should_convert_to_string_if_no_known_keys(self):
        result = {"unknown_key": "some value"}

        text = extract_response_text(result)

        assert "unknown_key" in text
        assert "some value" in text

    def test_should_handle_empty_dict(self):
        result = {}

        text = extract_response_text(result)

        assert text == "{}"


class TestLoadAndPrepareFlow:
    """Tests for _load_and_prepare_flow function."""

    def test_should_load_and_return_json_string(self, tmp_path):
        flow_data = {"data": {"nodes": []}}
        flow_file = tmp_path / "test_flow.json"
        flow_file.write_text(json.dumps(flow_data))

        result = _load_and_prepare_flow(flow_file, None, None, None)

        assert json.loads(result) == flow_data

    def test_should_inject_model_when_provider_and_model_provided(self, tmp_path):
        flow_data = {"data": {"nodes": [{"data": {"type": "Agent", "node": {"template": {"model": {"value": None}}}}}]}}
        flow_file = tmp_path / "test_flow.json"
        flow_file.write_text(json.dumps(flow_data))

        with patch("langflow.agentic.services.flow_executor.get_provider_config") as mock_config:
            mock_config.return_value = {
                "api_key_param": "api_key",
                "model_class": "ChatOpenAI",
                "model_name_param": "model_name",
                "variable_name": "OPENAI_API_KEY",
                "icon": "OpenAI",
            }

            result = _load_and_prepare_flow(
                flow_file, provider="OpenAI", model_name="gpt-4o", api_key_var="OPENAI_API_KEY"
            )

        parsed = json.loads(result)
        model_value = parsed["data"]["nodes"][0]["data"]["node"]["template"]["model"]["value"]
        assert model_value[0]["provider"] == "OpenAI"


class TestFlowsBasePath:
    """Tests for FLOWS_BASE_PATH constant."""

    def test_should_be_a_path_object(self):
        assert isinstance(FLOWS_BASE_PATH, Path)

    def test_should_end_with_flows_directory(self):
        assert FLOWS_BASE_PATH.name == "flows"

    def test_should_be_under_agentic_directory(self):
        assert "agentic" in str(FLOWS_BASE_PATH)
