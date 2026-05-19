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
        assert "built-in model" in prompt_lower, "Prompt must mention the Agent has a built-in model."
        assert "only" in prompt_lower or "unless" in prompt_lower, (
            "Prompt must say external models are opt-in (use 'only' or 'unless')."
        )

    def test_should_require_system_prompt_for_persona_use_cases(self):
        prompt_lower = FLOW_BUILDER_PROMPT.lower()
        assert "system_prompt" in prompt_lower, (
            "Prompt must instruct the agent to fill system_prompt for persona use cases."
        )
        assert "persona" in prompt_lower, "Prompt must reference the persona use case explicitly."

    def test_should_have_chatbot_or_assistant_example_with_system_prompt(self):
        # The example must show both the input wiring AND a populated system prompt.
        assert "system_prompt" in FLOW_BUILDER_PROMPT
        assert "config:" in FLOW_BUILDER_PROMPT, (
            "Prompt examples must show how to set field values via the `config:` block."
        )

    def test_should_teach_the_edit_continuation_contract(self):
        """After an approved edit, the silent continuation turn must make the
        agent finish the original request (e.g. run) WITHOUT re-editing or
        re-planning. Drift between the protocol string and the prompt's
        recognizer phrase would break the whole 'execution stack'.
        """  # noqa: D205
        from langflow.agentic.services.flow_types import EDIT_CONTINUATION_INPUT

        # The prompt must quote enough of the protocol string for the agent
        # to recognize the signal (cross-consistency with the constant).
        recognizer = "The proposed canvas edits were applied. Continue with the remaining steps"
        assert recognizer in EDIT_CONTINUATION_INPUT
        assert recognizer in FLOW_BUILDER_PROMPT

        lower = FLOW_BUILDER_PROMPT.lower()
        # It must instruct: don't re-edit / don't propose_plan on continuation.
        assert "do not re-propose" in lower or "do not re-apply" in lower
        # It must instruct: perform the originally-requested follow-up (run).
        assert "run_flow" in FLOW_BUILDER_PROMPT
        # It must instruct: brief confirmation + stop when edit was the whole ask.
        assert "one-line confirmation" in lower or "confirm" in lower

    def test_should_require_a_model_on_any_agent_that_will_run(self):
        """Production bug: built a flow with an Agent but no model →
        run failed "No model selected". The prompt must make configuring
        the Agent's model mandatory before running.
        """  # noqa: D205
        lower = FLOW_BUILDER_PROMPT.lower()
        assert "no model selected" in lower
        assert "available language model" in lower
        assert "never run a flow whose agent has no model" in lower

    def test_should_run_in_same_turn_after_a_directly_applied_edit(self):
        """Production bug: for "change X and run", the agent used
        configure_component (applies immediately, NO approval gate) but then
        deferred the run as if waiting for an approval that never comes.
        Only propose_field_edit is man-in-the-loop; direct-apply edit tools
        must be followed by run_flow in the SAME turn.
        """  # noqa: D205
        lower = FLOW_BUILDER_PROMPT.lower()
        # The prompt must name the immediate-apply tools and tie them to a
        # same-turn run when the user also asked to run.
        assert "configure_component" in FLOW_BUILDER_PROMPT
        assert "same turn" in lower
        # It must call out that only propose_field_edit defers (the gate).
        assert "propose_field_edit" in FLOW_BUILDER_PROMPT
        # It must forbid the "I'll run once the edits are applied" stall for
        # the direct path.
        assert "nothing to wait for" in lower or "do not defer" in lower

    def test_should_resolve_target_component_by_role_not_name(self):
        """Production bug: "mude o input" → agent edited a custom tool
        component instead of the flow's ChatInput, so the run used the old
        value. The prompt must pin "the input" to ChatInput.input_value
        (resolved via connections), never a tool/custom component.
        """  # noqa: D205
        lower = FLOW_BUILDER_PROMPT.lower()
        assert "targeting the right component" in lower
        # Must resolve deterministically via the dedicated tool, not by
        # eyeballing connections / matching names.
        assert "describe_flow_io" in FLOW_BUILDER_PROMPT
        assert "value_field" in FLOW_BUILDER_PROMPT
        # A tools-wired / custom component is explicitly NEVER the flow input.
        assert "never" in lower
        assert "tool" in lower
        # Ambiguity (more than one input) must be asked, not guessed.
        assert "more than one input" in lower
        assert "ask the user" in lower

    def test_should_self_verify_run_reflects_the_edit(self):
        """The agent must detect "edited X but the run still shows the OLD
        value" (it targeted the wrong component) and self-correct once,
        instead of reporting a contradictory success.
        """  # noqa: D205
        lower = FLOW_BUILDER_PROMPT.lower()
        assert "old value" in lower
        assert "self-correction" in lower or "run once more" in lower
        # Must not present it as success when the change had no effect.
        assert "do not report success" in lower or "wrong component" in lower

    def test_should_instruct_to_swap_model_via_configure_component(self):
        """When the user says 'change the model to X', the agent must update
        the Agent's `model` field via configure_component instead of adding
        an external OpenAIModel/AnthropicModel component.
        """  # noqa: D205
        prompt_lower = FLOW_BUILDER_PROMPT.lower()
        # Must mention the editing path explicitly.
        assert "configure_component" in prompt_lower
        assert "change the model" in prompt_lower or "switch" in prompt_lower, (
            "Prompt must explicitly cover the 'change the model' user request."
        )

    def test_should_show_model_field_value_structure(self):
        """The agent needs the exact JSON shape for the Agent's model field
        value so it can call configure_component without guessing.
        """  # noqa: D205
        # The structure is `[{"provider": "...", "name": "..."}]`.
        assert '"provider"' in FLOW_BUILDER_PROMPT, "Prompt must show the `provider` key of the model field value."
        assert '"name"' in FLOW_BUILDER_PROMPT, "Prompt must show the `name` key of the model field value."


class TestFlowBuilderPromptBehaviorContract:
    """WS-2 / RC-2 — prompt forbids the hallucination/confirmation anti-pattern.

    Production (screenshots 2/6/7/8): the agent asked to confirm an action the
    user already requested, or claimed an action without calling the tool. It
    must also keep the reply in the user's language (report #7).
    """

    def test_should_forbid_asking_confirmation_for_already_requested_action(self):
        prompt_lower = FLOW_BUILDER_PROMPT.lower()
        assert "confirm" in prompt_lower or "confirmation" in prompt_lower, (
            "Prompt must address the 'asking to confirm an already-requested action' anti-pattern"
        )
        assert "never ask" in prompt_lower or "do not ask" in prompt_lower or "without asking" in prompt_lower, (
            "Prompt must explicitly forbid asking the user to confirm an action they already requested"
        )

    def test_should_forbid_claiming_action_without_calling_the_tool(self):
        prompt_lower = FLOW_BUILDER_PROMPT.lower()
        forbids_claim = (
            "never claim" in prompt_lower or "do not claim" in prompt_lower or "without actually" in prompt_lower
        )
        assert forbids_claim, "Prompt must forbid claiming an action was done without calling the tool that performs it"

    def test_should_instruct_reply_in_user_language(self):
        prompt_lower = FLOW_BUILDER_PROMPT.lower()
        assert "same language" in prompt_lower or "user's language" in prompt_lower, (
            "Prompt must instruct the agent to reply in the language the user wrote in (report #7)"
        )


class TestFlowBuilderPromptUserComponents:
    """WS-3 / RC-3 — prompt tells the agent user-generated components are registered and searchable.

    They are discoverable via search_components by class name, so the agent
    uses them in build_flow instead of refusing ("custom components must be
    added manually outside the flow builder" — screenshot 2).
    """

    def test_should_mention_user_generated_components_are_registered(self):
        prompt_lower = FLOW_BUILDER_PROMPT.lower()
        assert "search_components" in prompt_lower
        assert (
            "user-generated" in prompt_lower
            or "user-created" in prompt_lower
            or "previously generated component" in prompt_lower
            or "components you generated" in prompt_lower
        ), "Prompt must state that components the user generated this session are searchable by class name"

    def test_should_forbid_refusing_to_use_user_components_in_a_flow(self):
        prompt_lower = FLOW_BUILDER_PROMPT.lower()
        assert "manually" in prompt_lower, (
            "Prompt must explicitly counter the 'must be added manually outside the flow builder' refusal"
        )


class TestFlowBuilderPromptLegacyComponents:
    """WS-5 / RC-5 — prompt tells the agent not to use legacy/beta components unless asked."""

    def test_should_warn_against_legacy_components(self):
        prompt_lower = FLOW_BUILDER_PROMPT.lower()
        assert "legacy" in prompt_lower, (
            "Prompt must instruct the agent not to add legacy/beta components unless explicitly requested"
        )


class TestFlowBuilderPromptProposePlan:
    """propose_plan is OPTIONAL — used only for genuinely ambiguous or
    large/destructive whole-canvas replacements. Clear/specified requests
    (including multi-step ones) are executed directly, no plan gate. When a
    plan IS proposed the Continue/Dismiss loop still applies.
    """  # noqa: D205

    def test_should_mention_propose_plan_tool(self):
        assert "propose_plan" in FLOW_BUILDER_PROMPT, (
            "Prompt must reference the propose_plan tool so the LLM knows to use it."
        )

    def test_should_make_propose_plan_optional_not_mandatory(self):
        prompt_lower = FLOW_BUILDER_PROMPT.lower()
        # The new contract: optional, reserved for ambiguous/destructive.
        assert "optional" in prompt_lower
        assert "ambiguous" in prompt_lower or "destructive" in prompt_lower
        # And it must NOT carry the old mandatory-first wording.
        assert "always your first tool call" not in prompt_lower
        assert "mandatory in build mode" not in prompt_lower
        # It must tell the agent to act directly for clear requests.
        assert "directly" in prompt_lower

    def test_should_explain_user_continue_vs_dismiss_loop(self):
        # After propose_plan, the next user turn is either an approval signal or
        # refinement feedback. The agent needs to know how to act on each.
        prompt_lower = FLOW_BUILDER_PROMPT.lower()
        assert "continue" in prompt_lower or "approve" in prompt_lower, (
            "Prompt must describe what to do when the user continues/approves the plan."
        )
        assert "dismiss" in prompt_lower or "refine" in prompt_lower or "feedback" in prompt_lower, (
            "Prompt must describe what to do when the user dismisses/refines the plan."
        )


class TestRunFlowToolWiring:
    """The agent must be able to run the canvas flow and discuss the result."""

    async def test_toolkit_should_include_run_flow_tool(self):
        from langflow.agentic.flows.flow_builder_assistant import build_toolkit

        tools = await build_toolkit()
        names = {getattr(t, "name", None) for t in tools}
        assert "run_flow" in names, f"run_flow must be in the toolkit, got: {sorted(n for n in names if n)}"

    def test_prompt_should_document_run_flow(self):
        prompt_lower = FLOW_BUILDER_PROMPT.lower()
        assert "run_flow" in prompt_lower, "Prompt must describe the run_flow tool"
        assert "run" in prompt_lower, "Prompt must mention running"
        assert "result" in prompt_lower, "Prompt must say run_flow returns the result for the agent to discuss"

    def test_prompt_should_say_run_is_not_a_build_no_plan_gate(self):
        """A run calls run_flow directly — never propose_plan (the "rode o flow → Generating plan…" bug)."""
        prompt_lower = FLOW_BUILDER_PROMPT.lower()
        assert "not a build" in prompt_lower or "is not build" in prompt_lower, (
            "Prompt must state running the flow is NOT a build"
        )
        # The run_flow guidance must forbid propose_plan for a pure run.
        assert "propose_plan" in prompt_lower
        assert "run_flow" in prompt_lower


class TestProposePlanInToolkit:
    """The propose_plan tool must be present in the agent's toolkit and be
    callable by name through the standard tool interface.
    """  # noqa: D205

    async def test_toolkit_should_include_propose_plan_tool(self):
        from langflow.agentic.flows.flow_builder_assistant import build_toolkit

        tools = await build_toolkit()
        names = {getattr(t, "name", None) for t in tools}

        assert "propose_plan" in names, f"propose_plan must be in the toolkit, got: {sorted(n for n in names if n)}"


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


class TestFilesystemToolsInToolkit:
    """B3 — the agent gets the FileSystemTool's 5 tools, wrapped to emit events.

    These tests exercise the wrapped tools directly (bypassing the LLM): given
    the user's `manage_files` intent, the same agent must be able to write
    files. The wrapper emits ``file_written`` only on successful writes.
    """

    async def test_toolkit_should_include_filesystem_tools(self):
        from langflow.agentic.flows.flow_builder_assistant import build_toolkit

        tools = await build_toolkit()
        names = {getattr(t, "name", None) for t in tools}

        assert {"read_file", "write_file", "edit_file", "glob_search", "grep_search"}.issubset(names), (
            f"FileSystem tools must be present in the toolkit, got: {names}"
        )

    async def test_toolkit_should_keep_existing_canvas_tools(self):
        """Regression — adding filesystem tools must not drop the existing toolkit."""
        from langflow.agentic.flows.flow_builder_assistant import build_toolkit

        tools = await build_toolkit()
        names = {getattr(t, "name", None) for t in tools}

        assert {
            "search_components",
            "describe_component",
            "get_field_value",
            "add_component",
            "build_flow",
        }.issubset(names)

    async def test_write_file_through_toolkit_should_emit_file_written_event(self, tmp_path, monkeypatch):
        from langflow.agentic.flows.flow_builder_assistant import build_toolkit
        from langflow.agentic.services.file_events import drain_file_events, reset_file_events

        monkeypatch.setenv("LANGFLOW_FS_TOOL_BASE_DIR", str(tmp_path))
        reset_file_events()

        tools = await build_toolkit()
        write_tool = next(t for t in tools if t.name == "write_file")

        result_json = write_tool.func(path="DOCS.md", content="# Hello")
        import json

        result = json.loads(result_json)
        assert result.get("status") in {"created", "updated"}, result

        events = drain_file_events()
        assert len(events) == 1
        assert events[0]["action"] == "write_file"
        assert events[0]["path"] == "DOCS.md"
        assert events[0]["size"] == len(b"# Hello")

    async def test_edit_file_through_toolkit_should_emit_file_written_event(self, tmp_path, monkeypatch):
        from langflow.agentic.flows.flow_builder_assistant import build_toolkit
        from langflow.agentic.services.file_events import drain_file_events, reset_file_events

        monkeypatch.setenv("LANGFLOW_FS_TOOL_BASE_DIR", str(tmp_path))
        reset_file_events()

        tools = await build_toolkit()
        write_tool = next(t for t in tools if t.name == "write_file")
        edit_tool = next(t for t in tools if t.name == "edit_file")

        # Arrange — write then drain the write event so only the edit event is observed.
        write_tool.func(path="DOCS.md", content="hello world")
        drain_file_events()

        # Act
        edit_tool.func(path="DOCS.md", old_string="hello", new_string="hi")

        # Assert
        events = drain_file_events()
        assert len(events) == 1
        assert events[0]["action"] == "edit_file"

    async def test_write_file_event_path_should_not_leak_base_dir(self, tmp_path, monkeypatch):
        from langflow.agentic.flows.flow_builder_assistant import build_toolkit
        from langflow.agentic.services.file_events import drain_file_events, reset_file_events

        monkeypatch.setenv("LANGFLOW_FS_TOOL_BASE_DIR", str(tmp_path))
        reset_file_events()

        tools = await build_toolkit()
        write_tool = next(t for t in tools if t.name == "write_file")
        write_tool.func(path="DOCS.md", content="x")

        [event] = drain_file_events()
        path = event["path"]
        assert not path.startswith("/"), f"BASE_DIR leak: {path!r}"
        assert not path.startswith("\\"), f"BASE_DIR leak (Windows): {path!r}"
        assert not (len(path) >= 2 and path[1] == ":"), f"Drive-letter leak: {path!r}"
        assert str(tmp_path) not in path, f"Full sandbox path leak: {path!r}"

    async def test_failed_write_should_not_emit_event(self, tmp_path, monkeypatch):
        """Path traversal is refused by FileSystemTool — no event must follow."""
        from langflow.agentic.flows.flow_builder_assistant import build_toolkit
        from langflow.agentic.services.file_events import drain_file_events, reset_file_events

        monkeypatch.setenv("LANGFLOW_FS_TOOL_BASE_DIR", str(tmp_path))
        reset_file_events()

        tools = await build_toolkit()
        write_tool = next(t for t in tools if t.name == "write_file")
        import json

        result = json.loads(write_tool.func(path="../escape.md", content="x"))
        assert "error" in result

        assert drain_file_events() == []

    async def test_read_file_should_not_emit_event(self, tmp_path, monkeypatch):
        from langflow.agentic.flows.flow_builder_assistant import build_toolkit
        from langflow.agentic.services.file_events import drain_file_events, reset_file_events

        monkeypatch.setenv("LANGFLOW_FS_TOOL_BASE_DIR", str(tmp_path))
        reset_file_events()

        tools = await build_toolkit()
        write_tool = next(t for t in tools if t.name == "write_file")
        read_tool = next(t for t in tools if t.name == "read_file")

        write_tool.func(path="DOCS.md", content="content")
        drain_file_events()  # discard write event

        read_tool.func(path="DOCS.md")
        assert drain_file_events() == []


class TestFlowBuilderPromptFilesystem:
    """B3 — the prompt mentions the filesystem tools so the agent uses them."""

    def test_prompt_should_mention_write_file(self):
        from langflow.agentic.flows.flow_builder_assistant import FLOW_BUILDER_PROMPT

        assert "write_file" in FLOW_BUILDER_PROMPT, (
            "Prompt must describe write_file so the LLM knows it can persist documentation files"
        )

    def test_prompt_should_mention_sandbox(self):
        from langflow.agentic.flows.flow_builder_assistant import FLOW_BUILDER_PROMPT

        prompt_lower = FLOW_BUILDER_PROMPT.lower()
        assert "sandbox" in prompt_lower or "workspace" in prompt_lower, (
            "Prompt should clarify that paths are sandbox-relative so the LLM doesn't use absolute paths"
        )


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
