"""Tests for flow data preparation and model injection.

Tests the inject_model_into_flow and load_and_prepare_flow
functions used to configure AI models in assistant flows.
"""

import json
from pathlib import Path
from unittest.mock import patch

from langflow.agentic.services.flow_preparation import (
    LFX_COMPONENTS_PATH_SENTINEL,
    inject_lfx_components_path,
    inject_model_into_flow,
    load_and_prepare_flow,
)

import lfx

MODULE = "langflow.agentic.services.flow_preparation"

OPENAI_CONFIG = {
    "model_class": "ChatOpenAI",
    "api_key_param": "api_key",
    "model_name_param": "model",
    "variable_name": "OPENAI_API_KEY",
    "icon": "OpenAI",
}


def _make_flow_data(node_types=None):
    """Create minimal flow data with nodes of given types."""
    if node_types is None:
        node_types = ["Agent"]
    nodes = []
    for i, ntype in enumerate(node_types):
        node = {
            "id": f"node-{i}",
            "data": {
                "type": ntype,
                "node": {
                    "template": {
                        "model": {"value": []},
                    },
                },
            },
        }
        nodes.append(node)
    return {"data": {"nodes": nodes}}


class TestInjectModelIntoFlow:
    """Tests for inject_model_into_flow."""

    def test_should_inject_model_into_agent_nodes(self):
        """Should set model value on Agent-type nodes."""
        flow_data = _make_flow_data(["Agent"])

        with patch(f"{MODULE}.get_provider_config", return_value=OPENAI_CONFIG):
            result = inject_model_into_flow(flow_data, "OpenAI", "gpt-4o")

        model_val = result["data"]["nodes"][0]["data"]["node"]["template"]["model"]["value"]
        assert len(model_val) == 1
        assert model_val[0]["name"] == "gpt-4o"
        assert model_val[0]["provider"] == "OpenAI"

    def test_should_not_modify_non_agent_nodes(self):
        """Non-Agent nodes should remain unchanged."""
        flow_data = _make_flow_data(["ChatInput", "Agent"])

        with patch(f"{MODULE}.get_provider_config", return_value=OPENAI_CONFIG):
            result = inject_model_into_flow(flow_data, "OpenAI", "gpt-4o")

        # ChatInput node should still have empty model
        chat_input = result["data"]["nodes"][0]
        assert chat_input["data"]["node"]["template"]["model"]["value"] == []

        # Agent node should have the injected model
        agent = result["data"]["nodes"][1]
        assert agent["data"]["node"]["template"]["model"]["value"][0]["name"] == "gpt-4o"

    def test_should_use_provided_api_key_var(self):
        """Should use provided api_key_var instead of provider default."""
        flow_data = _make_flow_data(["Agent"])

        with patch(f"{MODULE}.get_provider_config", return_value=OPENAI_CONFIG):
            inject_model_into_flow(flow_data, "OpenAI", "gpt-4o", api_key_var="MY_KEY")

        # The function doesn't set api_key on nodes directly, but api_key_var
        # is used internally. We verify it doesn't error with a custom key.

    def test_should_use_provider_default_api_key_var(self):
        """Should use provider's variable_name when api_key_var is None."""
        flow_data = _make_flow_data(["Agent"])

        with patch(f"{MODULE}.get_provider_config", return_value=OPENAI_CONFIG):
            inject_model_into_flow(flow_data, "OpenAI", "gpt-4o", api_key_var=None)

        # Should not raise — uses OPENAI_CONFIG["variable_name"]

    def test_should_include_extra_params_from_config(self):
        """Should include url_param, project_id_param when present in config."""
        config_with_extras = {
            **OPENAI_CONFIG,
            "url_param": "azure_endpoint",
            "base_url_param": "base_url",
        }
        flow_data = _make_flow_data(["Agent"])

        with patch(f"{MODULE}.get_provider_config", return_value=config_with_extras):
            result = inject_model_into_flow(flow_data, "Azure", "gpt-4o")

        metadata = result["data"]["nodes"][0]["data"]["node"]["template"]["model"]["value"][0]["metadata"]
        assert metadata["url_param"] == "azure_endpoint"
        assert metadata["base_url_param"] == "base_url"

    def test_should_handle_flow_without_agent_nodes(self):
        """Flow with no Agent nodes should return data without modification."""
        flow_data = _make_flow_data(["ChatInput", "ChatOutput"])

        with patch(f"{MODULE}.get_provider_config", return_value=OPENAI_CONFIG):
            result = inject_model_into_flow(flow_data, "OpenAI", "gpt-4o")

        # Both nodes should still have empty model arrays
        for node in result["data"]["nodes"]:
            assert node["data"]["node"]["template"]["model"]["value"] == []

    def test_should_handle_flow_without_model_in_template(self):
        """Agent node without 'model' key in template should not error."""
        flow_data = {
            "data": {
                "nodes": [
                    {
                        "id": "node-0",
                        "data": {
                            "type": "Agent",
                            "node": {"template": {}},
                        },
                    }
                ]
            }
        }

        with patch(f"{MODULE}.get_provider_config", return_value=OPENAI_CONFIG):
            result = inject_model_into_flow(flow_data, "OpenAI", "gpt-4o")

        # Should not raise, template remains without model
        assert "model" not in result["data"]["nodes"][0]["data"]["node"]["template"]


class TestLoadAndPrepareFlow:
    """Tests for load_and_prepare_flow."""

    def test_should_load_and_inject_model(self, tmp_path):
        """Should load JSON file and inject model configuration."""
        flow_data = _make_flow_data(["Agent"])
        flow_file = tmp_path / "test.json"
        flow_file.write_text(json.dumps(flow_data))

        with patch(f"{MODULE}.get_provider_config", return_value=OPENAI_CONFIG):
            result_json = load_and_prepare_flow(flow_file, "OpenAI", "gpt-4o", None)

        result = json.loads(result_json)
        model_val = result["data"]["nodes"][0]["data"]["node"]["template"]["model"]["value"]
        assert model_val[0]["name"] == "gpt-4o"

    def test_should_return_original_when_no_provider(self, tmp_path):
        """Should return original JSON when provider is None."""
        flow_data = _make_flow_data(["Agent"])
        flow_file = tmp_path / "test.json"
        flow_file.write_text(json.dumps(flow_data))

        result_json = load_and_prepare_flow(flow_file, None, None, None)
        result = json.loads(result_json)

        # Model should remain empty (no injection)
        assert result["data"]["nodes"][0]["data"]["node"]["template"]["model"]["value"] == []


def _make_directory_flow(path_value: str) -> dict:
    """Build a minimal flow dict with a single Directory node using the given path value."""
    return {
        "data": {
            "nodes": [
                {
                    "id": "Directory-test",
                    "data": {
                        "type": "Directory",
                        "node": {
                            "template": {
                                "path": {
                                    "_input_type": "MessageTextInput",
                                    "name": "path",
                                    "type": "str",
                                    "value": path_value,
                                },
                            },
                        },
                    },
                },
            ],
        },
    }


class TestInjectLfxComponentsPath:
    """Tests for inject_lfx_components_path.

    Regression guard for the Langflow Desktop bug where the LangflowAssistant
    flow embedded a relative path './src/lfx/src/lfx/components/' which only
    resolved correctly when the sidecar CWD was the monorepo root. On Desktop
    the CWD is the data dir, so the Directory component raised
    'Path ... must exist and be a directory.'
    """

    def test_should_rewrite_directory_path_to_absolute_lfx_components_when_path_matches_sentinel(self):
        flow_data = _make_directory_flow(LFX_COMPONENTS_PATH_SENTINEL)

        result = inject_lfx_components_path(flow_data)

        rewritten = result["data"]["nodes"][0]["data"]["node"]["template"]["path"]["value"]
        expected = str(Path(lfx.__file__).parent / "components")
        assert rewritten == expected
        # Must be absolute — the whole point of the fix.
        assert Path(rewritten).is_absolute()
        # The rewritten path must actually exist in the installed lfx package.
        assert Path(rewritten).is_dir()

    def test_should_not_modify_directory_path_when_value_is_not_sentinel(self):
        flow_data = _make_directory_flow("/custom/user/path")

        result = inject_lfx_components_path(flow_data)

        assert result["data"]["nodes"][0]["data"]["node"]["template"]["path"]["value"] == "/custom/user/path"

    def test_should_not_modify_non_directory_nodes(self):
        flow_data = _make_flow_data(["Agent"])

        result = inject_lfx_components_path(flow_data)

        # Agent node template untouched.
        assert "path" not in result["data"]["nodes"][0]["data"]["node"]["template"]

    def test_should_handle_flow_without_nodes(self):
        flow_data: dict = {"data": {"nodes": []}}

        result = inject_lfx_components_path(flow_data)

        assert result == {"data": {"nodes": []}}

    def test_should_rewrite_sentinel_path_when_loading_assistant_flow(self, tmp_path):
        """Rewrite the sentinel path when loading the assistant flow.

        load_and_prepare_flow must apply the lfx path injection so that
        Desktop (and any non-monorepo CWD) can execute the assistant flow.
        """
        flow_data = _make_directory_flow(LFX_COMPONENTS_PATH_SENTINEL)
        flow_file = tmp_path / "LangflowAssistant.json"
        flow_file.write_text(json.dumps(flow_data))

        result_json = load_and_prepare_flow(flow_file, None, None, None)
        result = json.loads(result_json)

        rewritten = result["data"]["nodes"][0]["data"]["node"]["template"]["path"]["value"]
        expected = str(Path(lfx.__file__).parent / "components")
        assert rewritten == expected
