"""Tests for flow data preparation and model injection.

Tests the inject_model_into_flow and load_and_prepare_flow
functions used to configure AI models in assistant flows.
"""

import json
from pathlib import Path
from unittest.mock import patch

from langflow.agentic.services.flow_preparation import (
    LFX_COMPONENTS_PATH_SENTINEL,
    available_model_providers,
    inject_assistant_fs_root,
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


class TestAvailableModelProviders:
    """Provider-agnostic detection of which providers have credentials.

    No OpenAI bias — whatever keys the user actually has in the
    (env-built) global variables.
    """

    def test_detects_only_providers_with_a_configured_key(self):
        assert available_model_providers({"ANTHROPIC_API_KEY": "sk-x"}) == ["Anthropic"]
        result = available_model_providers({"OPENAI_API_KEY": "a", "GROQ_API_KEY": "b"})
        assert "OpenAI" in result
        assert "Groq" in result
        assert "Anthropic" not in result

    def test_empty_or_blank_keys_yield_no_providers(self):
        assert available_model_providers({}) == []
        assert available_model_providers(None) == []
        assert available_model_providers({"OPENAI_API_KEY": ""}) == []
        # A whitespace-only key is NOT a configured key — the provider
        # would otherwise be picked and fail at run with an auth error.
        assert available_model_providers({"OPENAI_API_KEY": "   "}) == []
        assert available_model_providers({"ANTHROPIC_API_KEY": "\t\n"}) == []

    def test_does_not_hardcode_openai(self):
        # Only Google configured → OpenAI must NOT appear.
        result = available_model_providers({"GOOGLE_API_KEY": "k"})
        assert "Google Generative AI" in result
        assert "OpenAI" not in result


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

    def test_should_warn_when_an_agent_node_has_no_model_field(self, caplog):
        # Bug: injection was silently skipped for an Agent whose template
        # lacked 'model' (older serialized flow), and the function still
        # reported success — the run then failed with an opaque
        # "No model selected". It must at least leave a diagnostic.
        flow_data = {
            "data": {
                "nodes": [
                    {"id": "agent-7", "data": {"type": "Agent", "node": {"template": {}}}},
                ]
            }
        }
        with (
            patch(f"{MODULE}.get_provider_config", return_value=OPENAI_CONFIG),
            caplog.at_level("WARNING"),
        ):
            inject_model_into_flow(flow_data, "OpenAI", "gpt-4o")

        assert "agent_missing_model_field" in caplog.text
        assert "agent-7" in caplog.text

    def test_should_not_warn_on_the_normal_agent_path(self, caplog):
        flow_data = _make_flow_data(["Agent"])
        with (
            patch(f"{MODULE}.get_provider_config", return_value=OPENAI_CONFIG),
            caplog.at_level("WARNING"),
        ):
            inject_model_into_flow(flow_data, "OpenAI", "gpt-4o")

        assert "agent_missing_model_field" not in caplog.text


def _agent_flow_with_model(provider: str, name: str) -> dict:
    """A flow whose Agent already has an explicit model + api_key field set."""
    return {
        "data": {
            "nodes": [
                {
                    "id": "Agent-x",
                    "data": {
                        "type": "Agent",
                        "node": {
                            "template": {
                                "model": {"value": [{"provider": provider, "name": name}]},
                                "api_key": {"value": ""},
                            }
                        },
                    },
                }
            ]
        }
    }


class TestInjectModelPreservesExplicitModel:
    """``overwrite_existing_model=False`` must never silently swap a user-set model.

    Reproduces the production bug: the user asked for OpenAI gpt-5.4, but the
    end-of-turn RunFlow injection overwrote the Agent with the assistant's own
    verified model (gpt-5.5) and PERSISTED it on the canvas.
    """

    def test_keeps_existing_same_provider_model_and_injects_only_the_key(self):
        flow_data = _agent_flow_with_model("OpenAI", "gpt-5.4")

        with patch(f"{MODULE}.get_provider_config", return_value=OPENAI_CONFIG):
            inject_model_into_flow(
                flow_data, "OpenAI", "gpt-5.5", api_key_var="OPENAI_API_KEY", overwrite_existing_model=False
            )

        template = flow_data["data"]["nodes"][0]["data"]["node"]["template"]
        entry = template["model"]["value"][0]
        # The user's model NAME is preserved — NOT swapped to gpt-5.5.
        assert entry["name"] == "gpt-5.4"
        assert entry["provider"] == "OpenAI"
        # ...and it is rebuilt as a COMPLETE value (metadata/icon) so the run
        # resolves it exactly like a normal selection — a bare {provider,name}
        # the agent set would otherwise lack these and fail to run.
        assert "metadata" in entry
        assert entry["metadata"].get("model_class") == "ChatOpenAI"
        assert entry.get("icon") == "OpenAI"
        # ...and the credential was topped up so the same-provider run authenticates.
        assert template["api_key"]["value"] == "OPENAI_API_KEY"

    def test_does_not_touch_a_cross_provider_model(self):
        flow_data = _agent_flow_with_model("Anthropic", "claude-sonnet-4-5")

        with patch(f"{MODULE}.get_provider_config", return_value=OPENAI_CONFIG):
            inject_model_into_flow(
                flow_data, "OpenAI", "gpt-5.5", api_key_var="OPENAI_API_KEY", overwrite_existing_model=False
            )

        template = flow_data["data"]["nodes"][0]["data"]["node"]["template"]
        # Cross-provider model is left fully untouched (we don't hold its key).
        assert template["model"]["value"][0]["name"] == "claude-sonnet-4-5"
        assert template["model"]["value"][0]["provider"] == "Anthropic"
        # The OpenAI key must NOT be injected onto an Anthropic agent.
        assert template["api_key"]["value"] == ""

    def test_fills_in_an_empty_model_even_when_not_overwriting(self):
        flow_data = _make_flow_data(["Agent"])  # model value: []

        with patch(f"{MODULE}.get_provider_config", return_value=OPENAI_CONFIG):
            inject_model_into_flow(
                flow_data, "OpenAI", "gpt-5.5", api_key_var="OPENAI_API_KEY", overwrite_existing_model=False
            )

        # An Agent with NO model still gets one (run would otherwise break).
        model_val = flow_data["data"]["nodes"][0]["data"]["node"]["template"]["model"]["value"]
        assert model_val[0]["name"] == "gpt-5.5"

    def test_overwrite_default_still_swaps_the_model(self):
        # Back-compat: the default (template prep / missing-model fill) still
        # overwrites, so other callers are unaffected.
        flow_data = _agent_flow_with_model("OpenAI", "gpt-5.4")

        with patch(f"{MODULE}.get_provider_config", return_value=OPENAI_CONFIG):
            inject_model_into_flow(flow_data, "OpenAI", "gpt-5.5")

        model_val = flow_data["data"]["nodes"][0]["data"]["node"]["template"]["model"]["value"]
        assert model_val[0]["name"] == "gpt-5.5"


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

    def test_should_parse_the_flow_file_once_and_reuse_it_across_requests(self, tmp_path):
        # Bug: load_and_prepare_flow read + json.loads the bundled flow on
        # EVERY request (and x4 on validation retries) on the event loop.
        # The raw parsed template is stable per file → parse once, cached
        # by (path, mtime); a genuine file change re-parses.
        import pathlib

        flow_data = _make_flow_data(["Agent"])
        flow_file = tmp_path / "assistant.json"
        flow_file.write_text(json.dumps(flow_data))

        real_read_text = pathlib.Path.read_text
        calls = {"n": 0}

        def counting_read_text(self, *args, **kwargs):
            if str(self) == str(flow_file):
                calls["n"] += 1
            return real_read_text(self, *args, **kwargs)

        with patch.object(pathlib.Path, "read_text", counting_read_text):
            a = load_and_prepare_flow(flow_file, None, None, None)
            b = load_and_prepare_flow(flow_file, None, None, None)
            assert calls["n"] == 1  # second call served from cache

            # Per-call result is independent (no shared mutable cache).
            assert json.loads(a) == json.loads(b)

            # A genuine file change must invalidate the cache.
            changed = _make_flow_data(["Agent", "ChatInput"])
            flow_file.write_text(json.dumps(changed))
            load_and_prepare_flow(flow_file, None, None, None)
            assert calls["n"] == 2

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


def _make_filesystem_flow(root_path_value: str) -> dict:
    """Build a minimal flow with a single FileSystemTool node at the given root_path."""
    return {
        "data": {
            "nodes": [
                {
                    "data": {
                        "type": "FileSystemTool",
                        "node": {"template": {"root_path": {"value": root_path_value}}},
                    },
                }
            ],
        },
    }


class TestInjectAssistantFsRoot:
    """Tests for inject_assistant_fs_root.

    The shipped LangflowAssistant flow leaves FileSystemTool.root_path empty
    on purpose — it must be resolved at runtime to an OS-appropriate sandbox
    so the flow runs portably on macOS, Linux, Windows and Docker.
    """

    def test_should_replace_empty_root_path_for_filesystem_tool(self, tmp_path):
        flow_data = _make_filesystem_flow("")

        with patch(f"{MODULE}.resolve_assistant_fs_root", return_value=tmp_path / "ws"):
            result = inject_assistant_fs_root(flow_data)

        injected = result["data"]["nodes"][0]["data"]["node"]["template"]["root_path"]["value"]
        assert injected == str(tmp_path / "ws")

    def test_should_replace_whitespace_only_root_path(self, tmp_path):
        flow_data = _make_filesystem_flow("   ")

        with patch(f"{MODULE}.resolve_assistant_fs_root", return_value=tmp_path / "ws"):
            result = inject_assistant_fs_root(flow_data)

        injected = result["data"]["nodes"][0]["data"]["node"]["template"]["root_path"]["value"]
        assert injected == str(tmp_path / "ws")

    def test_should_not_overwrite_explicit_root_path(self, tmp_path):
        flow_data = _make_filesystem_flow("/explicit/path")

        with patch(f"{MODULE}.resolve_assistant_fs_root", return_value=tmp_path / "ws"):
            result = inject_assistant_fs_root(flow_data)

        injected = result["data"]["nodes"][0]["data"]["node"]["template"]["root_path"]["value"]
        assert injected == "/explicit/path"

    def test_should_skip_non_filesystem_nodes(self, tmp_path):
        flow_data = {
            "data": {
                "nodes": [
                    {
                        "data": {
                            "type": "Agent",
                            "node": {"template": {"root_path": {"value": ""}}},
                        },
                    }
                ],
            },
        }

        with patch(f"{MODULE}.resolve_assistant_fs_root", return_value=tmp_path / "ws"):
            result = inject_assistant_fs_root(flow_data)

        # Agent node's stray root_path field is untouched.
        unchanged = result["data"]["nodes"][0]["data"]["node"]["template"]["root_path"]["value"]
        assert unchanged == ""

    def test_should_handle_flow_without_filesystem_tool(self, tmp_path):
        flow_data: dict = {"data": {"nodes": []}}

        with patch(f"{MODULE}.resolve_assistant_fs_root", return_value=tmp_path / "ws"):
            result = inject_assistant_fs_root(flow_data)

        assert result == {"data": {"nodes": []}}

    def test_should_inject_root_path_when_loading_assistant_flow(self, tmp_path):
        """End-to-end: load_and_prepare_flow must inject the resolved root_path."""
        flow_data = _make_filesystem_flow("")
        flow_file = tmp_path / "LangflowAssistant.json"
        flow_file.write_text(json.dumps(flow_data))

        with patch(f"{MODULE}.resolve_assistant_fs_root", return_value=tmp_path / "ws"):
            result_json = load_and_prepare_flow(flow_file, None, None, None)

        result = json.loads(result_json)
        injected = result["data"]["nodes"][0]["data"]["node"]["template"]["root_path"]["value"]
        assert injected == str(tmp_path / "ws")

    def test_should_skip_injection_when_resolver_returns_none(self):
        """When PR #13031's isolation module is active the resolver returns None.

        In that mode the FileSystemTool derives its own per-user namespace at
        runtime; any value we inject would be misread as a relative sub_path
        and break the per-user boundary. Skip injection entirely.
        """
        flow_data = _make_filesystem_flow("")

        with patch(f"{MODULE}.resolve_assistant_fs_root", return_value=None):
            result = inject_assistant_fs_root(flow_data)

        # Untouched — root_path stays empty so the component self-resolves.
        unchanged = result["data"]["nodes"][0]["data"]["node"]["template"]["root_path"]["value"]
        assert unchanged == ""

    def test_should_skip_injection_for_explicit_root_path_when_resolver_returns_none(self):
        """An operator-set root_path must be preserved even in the isolation-active case."""
        flow_data = _make_filesystem_flow("/explicit/path")

        with patch(f"{MODULE}.resolve_assistant_fs_root", return_value=None):
            result = inject_assistant_fs_root(flow_data)

        # Operator override survives — the FileSystemTool will treat it as
        # sub_path under the user's namespace.
        unchanged = result["data"]["nodes"][0]["data"]["node"]["template"]["root_path"]["value"]
        assert unchanged == "/explicit/path"
