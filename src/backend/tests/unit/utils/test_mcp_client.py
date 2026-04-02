"""Unit tests for lfx.mcp — redact, registry, and client modules.

These test pure functions only (no network, no server).
"""

import pytest
from lfx.mcp.client import LangflowClient
from lfx.mcp.redact import (
    is_sensitive_field,
    redact_node,
    redact_template,
)
from lfx.mcp.registry import (
    describe_component,
    search_registry,
)

# ---------------------------------------------------------------------------
# Redact
# ---------------------------------------------------------------------------


class TestIsSensitiveField:
    def test_api_key(self):
        assert is_sensitive_field("api_key") is True

    def test_openai_api_key(self):
        assert is_sensitive_field("openai_api_key") is True

    def test_password(self):
        assert is_sensitive_field("password") is True

    def test_secret_token(self):
        assert is_sensitive_field("secret_token") is True

    def test_private_key(self):
        assert is_sensitive_field("private_key") is True

    def test_access_key(self):
        assert is_sensitive_field("access_key_id") is True

    def test_input_value_not_sensitive(self):
        assert is_sensitive_field("input_value") is False

    def test_model_name_not_sensitive(self):
        assert is_sensitive_field("model_name") is False

    def test_temperature_not_sensitive(self):
        assert is_sensitive_field("temperature") is False


class TestRedactTemplate:
    def test_masks_sensitive_values(self):
        template = {
            "api_key": {"value": "sk-secret-123", "type": "str"},
            "model_name": {"value": "gpt-4o", "type": "str"},
            "password": {"value": "hunter2", "type": "str"},
        }
        result = redact_template(template)
        assert result["api_key"]["value"] == "***REDACTED***"
        assert result["model_name"]["value"] == "gpt-4o"
        assert result["password"]["value"] == "***REDACTED***"

    def test_preserves_empty_sensitive(self):
        template = {"api_key": {"value": "", "type": "str"}}
        result = redact_template(template)
        assert result["api_key"]["value"] == ""

    def test_preserves_none_sensitive(self):
        template = {"api_key": {"value": None, "type": "str"}}
        result = redact_template(template)
        assert result["api_key"]["value"] is None

    def test_preserves_non_dict_fields(self):
        template = {
            "code": "print('hello')",
            "api_key": {"value": "sk-123", "type": "str"},
        }
        result = redact_template(template)
        assert result["code"] == "print('hello')"
        assert result["api_key"]["value"] == "***REDACTED***"

    def test_does_not_modify_original(self):
        template = {"api_key": {"value": "sk-123", "type": "str"}}
        redact_template(template)
        assert template["api_key"]["value"] == "sk-123"


class TestRedactNode:
    def test_redacts_node_template(self):
        node_data = {
            "type": "OpenAIModel",
            "node": {
                "template": {
                    "api_key": {"value": "sk-real-key", "type": "str"},
                    "model_name": {"value": "gpt-4o", "type": "str"},
                },
            },
        }
        result = redact_node(node_data)
        assert result["node"]["template"]["api_key"]["value"] == "***REDACTED***"
        assert result["node"]["template"]["model_name"]["value"] == "gpt-4o"

    def test_does_not_modify_original(self):
        node_data = {
            "type": "OpenAIModel",
            "node": {
                "template": {
                    "api_key": {"value": "sk-real-key", "type": "str"},
                },
            },
        }
        redact_node(node_data)
        assert node_data["node"]["template"]["api_key"]["value"] == "sk-real-key"

    def test_handles_node_without_template(self):
        node_data = {"type": "Simple", "node": {}}
        result = redact_node(node_data)
        assert result["type"] == "Simple"


# ---------------------------------------------------------------------------
# Registry (pure functions)
# ---------------------------------------------------------------------------

SAMPLE_REGISTRY = {
    "ChatInput": {
        "display_name": "Chat Input",
        "description": "Get chat inputs from the user",
        "category": "inputs",
        "outputs": [{"name": "message", "types": ["Message"]}],
        "template": {
            "input_value": {"type": "str", "input_types": ["Message"], "required": False},
            "sender": {"type": "str"},
        },
    },
    "ChatOutput": {
        "display_name": "Chat Output",
        "description": "Display chat outputs",
        "category": "outputs",
        "outputs": [{"name": "message", "types": ["Message"], "tool_mode": True}],
        "template": {
            "input_value": {"type": "str", "input_types": ["Message"], "required": True},
        },
    },
    "OpenAIModel": {
        "display_name": "OpenAI",
        "description": "OpenAI language model",
        "category": "models",
        "outputs": [
            {"name": "text_output", "types": ["Message"]},
            {"name": "model_output", "types": ["LanguageModel"]},
        ],
        "template": {
            "model_name": {"type": "str", "real_time_refresh": True},
            "api_key": {"type": "str", "input_types": ["SecretStr"], "required": True},
            "input_value": {"type": "str", "input_types": ["Message"], "required": False},
        },
    },
}


class TestSearchRegistry:
    def test_no_filters_returns_all(self):
        results = search_registry(SAMPLE_REGISTRY)
        assert len(results) == 3

    def test_query_filters_by_name(self):
        results = search_registry(SAMPLE_REGISTRY, query="Chat")
        types = {r["type"] for r in results}
        assert types == {"ChatInput", "ChatOutput"}

    def test_query_filters_by_category(self):
        results = search_registry(SAMPLE_REGISTRY, query="models")
        assert len(results) == 1
        assert results[0]["type"] == "OpenAIModel"

    def test_category_exact_filter(self):
        results = search_registry(SAMPLE_REGISTRY, category="inputs")
        assert len(results) == 1
        assert results[0]["type"] == "ChatInput"

    def test_query_and_category_combined(self):
        results = search_registry(SAMPLE_REGISTRY, query="Chat", category="outputs")
        assert len(results) == 1
        assert results[0]["type"] == "ChatOutput"

    def test_no_matches(self):
        results = search_registry(SAMPLE_REGISTRY, query="Nonexistent")
        assert results == []

    def test_case_insensitive_query(self):
        results = search_registry(SAMPLE_REGISTRY, query="chat")
        assert len(results) == 2

    def test_result_fields(self):
        results = search_registry(SAMPLE_REGISTRY, query="OpenAI")
        assert len(results) == 1
        r = results[0]
        assert r["type"] == "OpenAIModel"
        assert r["category"] == "models"
        assert r["display_name"] == "OpenAI"
        assert r["description"] == "OpenAI language model"


class TestDescribeComponent:
    def test_describe_chat_input(self):
        info = describe_component(SAMPLE_REGISTRY, "ChatInput")
        assert info["type"] == "ChatInput"
        assert info["display_name"] == "Chat Input"
        assert info["category"] == "inputs"
        assert len(info["outputs"]) == 1
        assert info["outputs"][0]["name"] == "message"

    def test_describe_inputs(self):
        info = describe_component(SAMPLE_REGISTRY, "OpenAIModel")
        input_names = {i["name"] for i in info["inputs"]}
        # Only fields with input_types are listed as inputs
        assert "api_key" in input_names
        assert "input_value" in input_names
        assert "model_name" not in input_names  # no input_types

    def test_describe_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown component"):
            describe_component(SAMPLE_REGISTRY, "TotallyFake")

    def test_describe_outputs(self):
        info = describe_component(SAMPLE_REGISTRY, "OpenAIModel")
        output_names = {o["name"] for o in info["outputs"]}
        assert output_names == {"text_output", "model_output"}

    def test_describe_component_as_tool_output(self):
        info = describe_component(SAMPLE_REGISTRY, "ChatOutput")
        output_names = {o["name"] for o in info["outputs"]}
        assert "component_as_tool" in output_names
        tool_out = next(o for o in info["outputs"] if o["name"] == "component_as_tool")
        assert tool_out["types"] == ["Tool"]
        assert "message" in tool_out["description"]

    def test_describe_no_tool_output_without_tool_mode(self):
        info = describe_component(SAMPLE_REGISTRY, "OpenAIModel")
        output_names = {o["name"] for o in info["outputs"]}
        assert "component_as_tool" not in output_names

    def test_describe_required_field(self):
        info = describe_component(SAMPLE_REGISTRY, "ChatOutput")
        input_field = next(i for i in info["inputs"] if i["name"] == "input_value")
        assert input_field["required"] is True


# ---------------------------------------------------------------------------
# LangflowClient — pure method tests (no network)
# ---------------------------------------------------------------------------


class TestClientHeaders:
    def test_no_credentials(self):
        client = LangflowClient(server_url="http://test:7860")
        client.api_key = None
        client.access_token = None
        headers = client._headers()
        assert headers == {"Content-Type": "application/json"}
        assert "Authorization" not in headers
        assert "x-api-key" not in headers

    def test_api_key_only(self):
        client = LangflowClient(server_url="http://test:7860", api_key="sk-test-key")
        headers = client._headers()
        assert headers["Authorization"] == "Bearer sk-test-key"
        assert headers["x-api-key"] == "sk-test-key"

    def test_access_token_only(self):
        client = LangflowClient(server_url="http://test:7860")
        token = "jwt-token-123"  # noqa: S105
        client.access_token = token
        headers = client._headers()
        assert headers["Authorization"] == f"Bearer {token}"
        assert "x-api-key" not in headers

    def test_both_token_and_api_key(self):
        """access_token takes precedence for Bearer, api_key still sent as x-api-key."""
        client = LangflowClient(server_url="http://test:7860", api_key="sk-key")
        token = "jwt-token"  # noqa: S105
        client.access_token = token
        headers = client._headers()
        assert headers["Authorization"] == f"Bearer {token}"
        assert headers["x-api-key"] == "sk-key"

    def test_content_type_always_present(self):
        client = LangflowClient(server_url="http://test:7860")
        headers = client._headers()
        assert headers["Content-Type"] == "application/json"


class TestClientUrl:
    def test_basic_path(self):
        client = LangflowClient(server_url="http://localhost:7860")
        assert client._url("/flows/") == "http://localhost:7860/api/v1/flows/"

    def test_trailing_slash_stripped(self):
        client = LangflowClient(server_url="http://localhost:7860/")
        assert client._url("/flows/") == "http://localhost:7860/api/v1/flows/"

    def test_nested_path(self):
        client = LangflowClient(server_url="http://host:8000")
        assert client._url("/flows/abc-123") == "http://host:8000/api/v1/flows/abc-123"

    def test_default_server_url(self):
        client = LangflowClient()
        assert client._url("/test") == f"{client.server_url}/api/v1/test"


class TestClientInit:
    def test_default_values(self):
        client = LangflowClient()
        assert client.server_url.startswith("http")
        assert client.access_token is None

    def test_custom_server_url(self):
        client = LangflowClient(server_url="http://custom:9000")
        assert client.server_url == "http://custom:9000"

    def test_http_client_starts_none(self):
        client = LangflowClient()
        assert client._http is None
