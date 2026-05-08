"""Integration tests for the flow builder assistant.

Tests intent classification for build_flow requests and the
flow builder assistant graph construction.

Tests marked with requires_api_key are skipped in CI unless
OPENAI_API_KEY is set.
"""

import pytest
from langflow.agentic.flows.flow_builder_assistant import FLOW_BUILDER_PROMPT, get_graph
from langflow.agentic.flows.translation_flow import TRANSLATION_PROMPT

from tests.api_keys import has_api_key


class TestFlowBuilderPrompt:
    def test_should_mention_search_components_tool(self):
        assert "search_components" in FLOW_BUILDER_PROMPT

    def test_should_mention_describe_component_tool(self):
        assert "describe_component" in FLOW_BUILDER_PROMPT

    def test_should_mention_build_flow_tool(self):
        assert "build_flow" in FLOW_BUILDER_PROMPT

    def test_should_mention_build_flow_for_new_flows(self):
        assert "build_flow" in FLOW_BUILDER_PROMPT
        assert "spec" in FLOW_BUILDER_PROMPT

    def test_should_instruct_retry_on_failure(self):
        assert "retry" in FLOW_BUILDER_PROMPT.lower() or "fix" in FLOW_BUILDER_PROMPT.lower()

    def test_should_instruct_search_before_building(self):
        assert "search" in FLOW_BUILDER_PROMPT.lower()
        assert "describe" in FLOW_BUILDER_PROMPT.lower()

    # Regression guards for wiring mistakes seen in production builds where
    # the agent left orphan model components, mis-wired memory to Tools, and
    # produced agents with empty system prompts.
    def test_should_forbid_orphan_components(self):
        prompt_lower = FLOW_BUILDER_PROMPT.lower()
        assert "orphan" in prompt_lower or "every component" in prompt_lower, (
            "Prompt must instruct the agent that every added component must be connected."
        )

    def test_should_explain_tools_input_only_takes_tool_outputs(self):
        prompt_lower = FLOW_BUILDER_PROMPT.lower()
        assert "component_as_tool" in prompt_lower, (
            "Prompt must clarify that the Tools input requires `component_as_tool` outputs."
        )

    def test_should_warn_about_agents_built_in_model(self):
        prompt_lower = FLOW_BUILDER_PROMPT.lower()
        assert "built-in model" in prompt_lower and (
            "only" in prompt_lower or "unless" in prompt_lower
        ), "Prompt must say the Agent has a built-in model and external models are opt-in."

    def test_should_require_system_prompt_for_persona_use_cases(self):
        prompt_lower = FLOW_BUILDER_PROMPT.lower()
        assert "system_prompt" in prompt_lower and "persona" in prompt_lower, (
            "Prompt must instruct the agent to fill system_prompt when the user describes a persona."
        )

    def test_should_have_chatbot_or_assistant_example_with_system_prompt(self):
        # The example must show both the input wiring AND a populated system prompt.
        assert "system_prompt" in FLOW_BUILDER_PROMPT
        assert "config:" in FLOW_BUILDER_PROMPT, (
            "Prompt examples must show how to set field values via the `config:` block."
        )

    def test_should_instruct_to_swap_model_via_configure_component(self):
        """When the user says 'change the model to X', the agent must update
        the Agent's `model` field via configure_component instead of adding
        an external OpenAIModel/AnthropicModel component."""
        prompt_lower = FLOW_BUILDER_PROMPT.lower()
        # Must mention the editing path explicitly.
        assert "configure_component" in prompt_lower
        assert "change the model" in prompt_lower or "switch" in prompt_lower, (
            "Prompt must explicitly cover the 'change the model' user request."
        )

    def test_should_show_model_field_value_structure(self):
        """The agent needs the exact JSON shape for the Agent's model field
        value so it can call configure_component without guessing."""
        # The structure is `[{"provider": "...", "name": "..."}]`.
        assert "\"provider\"" in FLOW_BUILDER_PROMPT and "\"name\"" in FLOW_BUILDER_PROMPT, (
            "Prompt must show the model field value structure (provider+name)."
        )


class TestTranslationPromptBuildFlow:
    def test_should_contain_build_flow_intent(self):
        assert "build_flow" in TRANSLATION_PROMPT

    def test_should_have_build_flow_examples(self):
        assert "build me a RAG pipeline" in TRANSLATION_PROMPT

    def test_should_have_simple_chat_flow_example(self):
        assert "simple chat flow" in TRANSLATION_PROMPT

    def test_should_prefer_build_flow_when_ambiguous(self):
        assert "prefer build_flow" in TRANSLATION_PROMPT


class TestGetGraph:
    async def test_should_create_graph_with_defaults(self):
        graph = await get_graph()
        assert graph is not None

    async def test_should_accept_provider_and_model(self):
        graph = await get_graph(provider="OpenAI", model_name="gpt-4o")
        assert graph is not None

    async def test_should_accept_api_key_var(self):
        graph = await get_graph(api_key_var="OPENAI_API_KEY")  # pragma: allowlist secret
        assert graph is not None

    async def test_second_call_should_not_crash(self):
        """Regression: second get_graph call must not fail due to stale state."""
        g1 = await get_graph(provider="OpenAI", model_name="gpt-4o")
        assert g1 is not None
        g2 = await get_graph(provider="OpenAI", model_name="gpt-4o")
        assert g2 is not None

    async def test_different_providers_on_consecutive_calls(self):
        """Consecutive calls with different providers must both succeed."""
        g1 = await get_graph(provider="OpenAI", model_name="gpt-4o")
        assert g1 is not None
        g2 = await get_graph(provider="Anthropic", model_name="claude-sonnet-4-6")
        assert g2 is not None

    async def test_flow_loader_reload_simulation(self):
        """Simulate how flow_loader loads the module -- importlib reload."""
        import importlib.util
        import sys
        from pathlib import Path

        flow_path = (
            Path(__file__).resolve().parent.parent.parent.parent.parent
            / "base"
            / "langflow"
            / "agentic"
            / "flows"
            / "flow_builder_assistant.py"
        )
        assert flow_path.exists(), f"Flow file not found: {flow_path}"

        async def _load_and_call(**kwargs):
            module_name = "flow_builder_assistant_test"
            spec = importlib.util.spec_from_file_location(module_name, flow_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            try:
                return await module.get_graph(**kwargs)
            finally:
                del sys.modules[module_name]

        # First load
        g1 = await _load_and_call(provider="OpenAI", model_name="gpt-4o")
        assert g1 is not None

        # Second load -- this is where the 'dict' has no attribute 'replace' crash happened
        g2 = await _load_and_call(provider="Anthropic", model_name="claude-sonnet-4-6")
        assert g2 is not None

    async def test_load_graph_for_execution_twice(self):
        """Use the real flow_loader path -- the exact production code path."""
        from langflow.agentic.services.helpers.flow_loader import load_graph_for_execution, resolve_flow_path

        flow_path, flow_type = resolve_flow_path("flow_builder_assistant")

        g1 = await load_graph_for_execution(flow_path, flow_type, "OpenAI", "gpt-4o", "OPENAI_API_KEY")
        assert g1 is not None

        g2 = await load_graph_for_execution(flow_path, flow_type, "Anthropic", "claude-sonnet-4-6", "ANTHROPIC_API_KEY")
        assert g2 is not None

    async def test_load_graph_for_execution_with_replace_in_prompt(self):
        """Regression: .replace() on FLOW_BUILDER_PROMPT must work on second load.

        The production bug was: 'dict' object has no attribute 'replace'
        on the second call to get_graph(). This test ensures the prompt
        string is never mutated to a dict by the first call.
        """
        from langflow.agentic.services.helpers.flow_loader import load_graph_for_execution, resolve_flow_path

        flow_path, flow_type = resolve_flow_path("flow_builder_assistant")

        # Load twice in quick succession with different params
        for i in range(3):
            graph = await load_graph_for_execution(flow_path, flow_type, "OpenAI", "gpt-4o", "OPENAI_API_KEY")
            assert graph is not None, f"Failed on iteration {i}"


@pytest.mark.skipif(
    not has_api_key("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY required for intent classification test",
)
class TestIntentClassificationBuildFlow:
    """Test that the intent classifier correctly identifies build_flow requests.

    These tests call the real OpenAI API through the translation flow.
    """

    async def test_simple_chat_flow_classified_as_build_flow(self):
        from langflow.agentic.services.helpers.intent_classification import classify_intent

        result = await classify_intent(
            text="simple chat flow",
            global_variables={},
            provider="OpenAI",
            model_name="gpt-4o-mini",
            api_key_var="OPENAI_API_KEY",
        )
        assert result.intent == "build_flow", f"Expected build_flow, got {result.intent}"

    async def test_build_rag_pipeline_classified_as_build_flow(self):
        from langflow.agentic.services.helpers.intent_classification import classify_intent

        result = await classify_intent(
            text="build me a RAG pipeline",
            global_variables={},
            provider="OpenAI",
            model_name="gpt-4o-mini",
            api_key_var="OPENAI_API_KEY",
        )
        assert result.intent == "build_flow", f"Expected build_flow, got {result.intent}"

    async def test_can_you_build_a_flow_classified_as_build_flow(self):
        from langflow.agentic.services.helpers.intent_classification import classify_intent

        result = await classify_intent(
            text="can you build a flow for me?",
            global_variables={},
            provider="OpenAI",
            model_name="gpt-4o-mini",
            api_key_var="OPENAI_API_KEY",
        )
        assert result.intent == "build_flow", f"Expected build_flow, got {result.intent}"

    async def test_create_component_not_classified_as_build_flow(self):
        from langflow.agentic.services.helpers.intent_classification import classify_intent

        result = await classify_intent(
            text="create a component that calls an API",
            global_variables={},
            provider="OpenAI",
            model_name="gpt-4o-mini",
            api_key_var="OPENAI_API_KEY",
        )
        assert result.intent == "generate_component", f"Expected generate_component, got {result.intent}"
