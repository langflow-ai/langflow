"""Tests for flow_builder_tools components."""

import asyncio
import json

from lfx.mcp.flow_builder_tools import (
    AddComponent,
    BuildFlowFromSpec,
    ConnectComponents,
    DescribeComponentType,
    ProposePlan,
    SearchComponentTypes,
    drain_flow_events,
    get_working_flow,
    init_working_flow,
    reset_working_flow,
)


class TestSearchComponentTypes:
    def test_search_returns_results(self):
        comp = SearchComponentTypes()
        comp.set(query="Chat")
        result = comp.search_components()
        assert result.data["count"] > 0
        types = {r["type"] for r in result.data["results"]}
        assert "ChatInput" in types

    def test_search_no_query_returns_all(self):
        comp = SearchComponentTypes()
        comp.set(query="")
        result = comp.search_components()
        assert result.data["count"] > 100


def _node(nid, ntype, template=None):
    return {"data": {"id": nid, "type": ntype, "node": {"template": template or {}}}}


def _edge(src, src_handle, tgt, tgt_field):
    return {
        "source": src,
        "target": tgt,
        "data": {
            "sourceHandle": {"name": src_handle},
            "targetHandle": {"fieldName": tgt_field},
        },
    }


# Mirrors the production screenshot: ChatInput("Cat") -> Agent.input_value,
# AnimalSoundComponent (custom tool) -> Agent.tools, Agent -> ChatOutput.
_IO_FLOW = {
    "name": "Animal Sound",
    "data": {
        "nodes": [
            _node("ChatInput-1", "ChatInput", {"input_value": {"value": "Cat"}}),
            _node("Agent-1", "Agent", {}),
            _node("AnimalSoundComponent-oIAUY", "AnimalSoundComponent", {"animal_name": {"value": "cat"}}),
            _node("ChatOutput-1", "ChatOutput", {}),
        ],
        "edges": [
            _edge("ChatInput-1", "message", "Agent-1", "input_value"),
            _edge("AnimalSoundComponent-oIAUY", "component_as_tool", "Agent-1", "tools"),
            _edge("Agent-1", "response", "ChatOutput-1", "input_value"),
        ],
    },
}


class TestDescribeFlowIO:
    """Deterministic flow I/O resolution — O(1) for the agent, exact at any size.

    Refutes the production bug where 'mude o input' edited the
    AnimalSoundComponent tool instead of the ChatInput.
    """

    def setup_method(self):
        reset_working_flow()

    def teardown_method(self):
        reset_working_flow()

    def _run(self):
        from lfx.mcp.flow_builder_tools import DescribeFlowIO

        init_working_flow(_IO_FLOW, "flow-io-1")
        return DescribeFlowIO().describe_flow_io().data

    def test_identifies_chatinput_as_the_only_input_with_value_field(self):
        data = self._run()
        inputs = data["inputs"]
        assert [i["id"] for i in inputs] == ["ChatInput-1"]
        assert inputs[0]["type"] == "ChatInput"
        # The agent must know exactly which field to set.
        assert inputs[0]["value_field"] == "input_value"

    def test_excludes_tool_wired_custom_component_from_inputs(self):
        data = self._run()
        ids = {i["id"] for i in data["inputs"]}
        assert "AnimalSoundComponent-oIAUY" not in ids
        # It is surfaced as a tool so the agent knows it is NOT the input.
        assert "AnimalSoundComponent-oIAUY" in {t["id"] for t in data["tools"]}

    def test_identifies_sink_as_output(self):
        data = self._run()
        assert [o["id"] for o in data["outputs"]] == ["ChatOutput-1"]

    def test_text_summary_is_present_for_the_agent(self):
        data = self._run()
        assert "text" in data
        assert "ChatInput-1" in data["text"]

    def test_empty_canvas_returns_empty_io_not_error(self):
        from lfx.mcp.flow_builder_tools import DescribeFlowIO

        init_working_flow({"name": "e", "data": {"nodes": [], "edges": []}}, "f")
        data = DescribeFlowIO().describe_flow_io().data
        assert data["inputs"] == []
        assert data["outputs"] == []
        assert "error" not in data


class TestProposeFieldEditReadableSummary:
    r"""The diff card summary must stay human-readable.

    Production bug: a multi-line system_prompt was rendered with repr()
    (`'...\n...'`), so the card showed literal backslash-n and quotes.
    The full value is still carried in `new_value` for the diff body —
    only the one-line summary is collapsed/truncated.
    """

    def setup_method(self):
        reset_working_flow()

    def teardown_method(self):
        reset_working_flow()

    def test_summary_is_single_line_unescaped_and_capped(self):
        from lfx.mcp.flow_builder_tools import ProposeFieldEdit, drain_flow_events

        init_working_flow(_IO_FLOW, "flow-io-1")
        multiline = "You are an assistant.\nUse the tool.\n- rule one\n- rule two " + ("x" * 300)

        edit = ProposeFieldEdit()
        edit.set(component_id="ChatInput-1", field_name="input_value", new_value=multiline)
        result = edit.propose_field_edit()
        assert "error" not in result.data, result.data

        text = result.data["text"]
        # No raw newlines and no repr-escaped backslash-n in the summary.
        assert "\n" not in text
        assert "\\n" not in text
        assert "You are an assistant." in text

        ev = drain_flow_events()[-1]
        assert ev["action"] == "edit_field"
        desc = ev["description"]
        assert "\n" not in desc
        assert "\\n" not in desc
        assert "You are an assistant." in desc
        # Long value is truncated with an ellipsis (card stays compact).
        assert "…" in desc
        assert len(desc) < len(multiline)
        # The FULL value is still carried for the diff body / patch.
        assert ev["new_value"] == multiline

    def test_literal_backslash_n_is_also_collapsed(self):
        # Robust regardless of whether the LLM emitted REAL newlines or the
        # two-char escape sequence "\\n" — the card must never show "\n".
        from lfx.mcp.flow_builder_tools import ProposeFieldEdit, drain_flow_events

        init_working_flow(_IO_FLOW, "flow-io-1")
        literal = "You are an assistant.\\nUse the tool.\\n- rule one\\t- rule two"

        edit = ProposeFieldEdit()
        edit.set(component_id="ChatInput-1", field_name="input_value", new_value=literal)
        result = edit.propose_field_edit()
        assert "error" not in result.data, result.data

        ev = drain_flow_events()[-1]
        assert "\\n" not in ev["description"]
        assert "\\t" not in ev["description"]
        assert "\\n" not in result.data["text"]
        assert "You are an assistant. Use the tool." in ev["description"]
        # Full value still preserved for the diff body / patch.
        assert ev["new_value"] == literal

    def test_short_value_is_shown_in_full(self):
        from lfx.mcp.flow_builder_tools import ProposeFieldEdit, drain_flow_events

        init_working_flow(_IO_FLOW, "flow-io-1")
        edit = ProposeFieldEdit()
        edit.set(component_id="ChatInput-1", field_name="input_value", new_value="Dog")
        result = edit.propose_field_edit()
        assert "error" not in result.data, result.data

        ev = drain_flow_events()[-1]
        assert "Dog" in ev["description"]
        assert "…" not in ev["description"]


class TestDescribeComponentType:
    def test_describe_known_component(self):
        comp = DescribeComponentType()
        comp.set(component_type="ChatInput")
        result = comp.describe_component()
        assert result.data["type"] == "ChatInput"
        assert "outputs" in result.data

    def test_describe_unknown_component(self):
        comp = DescribeComponentType()
        comp.set(component_type="TotallyFakeComponent")
        result = comp.describe_component()
        assert "error" in result.data


class TestBuildFlowFromSpec:
    def test_build_success_returns_text(self):
        reset_working_flow()
        comp = BuildFlowFromSpec()
        comp.set(spec="name: Test\nnodes:\n  A: ChatInput\n  B: ChatOutput\nedges:\n  A.message -> B.input_value")
        result = comp.build_flow()
        assert "built successfully" in result.data["text"]
        assert "flow" in result.data

    def test_build_mutates_working_flow_in_place_not_rebind(self):
        # Production bug: build_flow did `_working_flow_var.set(new_dict)`
        # (REBIND). A ContextVar rebind is invisible across tool-execution
        # contexts, so run_flow (a separate tool call) saw the OLD empty
        # working flow → "There is no flow on the canvas to run". It must
        # mutate the SAME bound dict in place (like configure_component),
        # so the built flow is visible to a later run_flow in any context.
        from lfx.mcp.flow_builder_tools import _ensure_working_flow

        reset_working_flow()
        init_working_flow({"name": "X", "data": {"nodes": [], "edges": []}}, "fid")
        bound = _ensure_working_flow()  # the object every context shares
        assert not bound["data"]["nodes"]

        comp = BuildFlowFromSpec()
        comp.set(spec="name: Test\nnodes:\n  A: ChatInput\n  B: ChatOutput\nedges:\n  A.message -> B.input_value")
        result = comp.build_flow()
        assert "built successfully" in result.data["text"], result.data

        # Same object, mutated in place — NOT a rebind to a new dict.
        assert get_working_flow() is bound, "build_flow rebound the ContextVar instead of mutating in place"
        assert len(bound["data"]["nodes"]) == 2, bound["data"]["nodes"]

    def test_single_node_spec_is_not_rejected_as_orphan(self):
        # Bug: a legitimate 1-component spec (no edges possible) was
        # rejected by the orphan guard, dead-ending the agent into an
        # unsatisfiable replan loop.
        reset_working_flow()
        comp = BuildFlowFromSpec()
        comp.set(spec="name: Solo\nnodes:\n  A: ChatInput")
        result = comp.build_flow()

        assert "error" not in result.data, result.data
        assert "built successfully" in result.data["text"], result.data
        assert "flow" in result.data

    def test_multi_node_spec_with_no_edges_still_rejected_as_orphan(self):
        # The guard must still catch a genuine mistake: 2+ nodes, no wiring.
        reset_working_flow()
        comp = BuildFlowFromSpec()
        comp.set(spec="name: Bad\nnodes:\n  A: ChatInput\n  B: ChatOutput")
        result = comp.build_flow()

        assert "error" in result.data
        assert "orphan" in result.data["text"].lower()

    def test_build_error_returns_text(self):
        reset_working_flow()
        comp = BuildFlowFromSpec()
        comp.set(spec="name: Bad\nnodes:\n  A: FakeComponent")
        result = comp.build_flow()
        assert "failed" in result.data["text"].lower()
        assert "error" in result.data

    def test_build_pushes_set_flow_event(self):
        reset_working_flow()
        comp = BuildFlowFromSpec()
        comp.set(spec="name: Test\nnodes:\n  A: ChatInput\n  B: ChatOutput\nedges:\n  A.message -> B.input_value")
        comp.build_flow()

        events = drain_flow_events()
        assert len(events) == 1
        assert events[0]["action"] == "set_flow"
        assert "flow" in events[0]

    def test_build_error_does_not_push_event(self):
        reset_working_flow()
        comp = BuildFlowFromSpec()
        comp.set(spec="name: Bad\nnodes:\n  A: FakeComponent")
        comp.build_flow()

        events = drain_flow_events()
        assert len(events) == 0

    # Regression: the agent has been observed to build flows with components
    # that have no edges (e.g. an OpenAIModel sitting next to an Agent with
    # nothing wired to it). Reject those so the LLM auto-corrects via retry.
    def test_build_should_reject_orphan_components(self):
        reset_working_flow()
        comp = BuildFlowFromSpec()
        # ChatInput connects to ChatOutput, but OpenAIModel is added without
        # any edge. This must fail validation, not silently produce a flow.
        comp.set(
            spec=(
                "name: Has Orphan\n"
                "nodes:\n"
                "  A: ChatInput\n"
                "  B: ChatOutput\n"
                "  X: OpenAIModel\n"
                "edges:\n"
                "  A.message -> B.input_value\n"
            ),
        )
        result = comp.build_flow()

        assert "error" in result.data, "Orphan component must produce an error"
        assert "orphan" in result.data["error"].lower(), (
            "Error message must explain that the build was rejected because of orphans"
        )
        # No set_flow event leaked to the canvas — orphan flows must not render.
        events = drain_flow_events()
        assert events == []

    def test_build_should_accept_flows_with_no_orphans(self):
        reset_working_flow()
        comp = BuildFlowFromSpec()
        comp.set(
            spec=("name: Clean\nnodes:\n  A: ChatInput\n  B: ChatOutput\nedges:\n  A.message -> B.input_value\n"),
        )
        result = comp.build_flow()

        assert "error" not in result.data
        assert "built successfully" in result.data["text"]

    def test_build_should_pass_when_single_node_has_no_edges_only_if_lone(self):
        # Corrected contract (was pinning the orphan-rejection BUG): a lone
        # 1-node spec has no edges by definition and is a valid standalone
        # flow (the agent legitimately builds one component to run/inspect).
        # It must NOT be rejected as an orphan — see
        # test_single_node_spec_is_not_rejected_as_orphan.
        reset_working_flow()
        comp = BuildFlowFromSpec()
        comp.set(spec="name: Lone\nnodes:\n  A: ChatInput\n")
        result = comp.build_flow()

        assert "error" not in result.data, result.data
        assert "built successfully" in result.data["text"]


class TestProposePlan:
    """ProposePlan emits a markdown plan to the user as a gate BEFORE the
    agent runs search/describe/build_flow tools. The agent's next step
    depends on the user's Continue/Dismiss reply, which arrives as a new
    user turn — the tool itself does not block.
    """  # noqa: D205

    def test_should_push_propose_plan_event_when_plan_is_valid(self):
        reset_working_flow()
        comp = ProposePlan()
        comp.set(plan="I'll create a ChatInput -> Agent (GPT-4) -> ChatOutput flow.")
        comp.propose_plan()

        events = drain_flow_events()
        assert len(events) == 1
        assert events[0]["action"] == "propose_plan"
        assert events[0]["markdown"] == ("I'll create a ChatInput -> Agent (GPT-4) -> ChatOutput flow.")

    def test_should_return_wait_marker_text_when_plan_is_valid(self):
        reset_working_flow()
        comp = ProposePlan()
        comp.set(plan="Plan text.")
        result = comp.propose_plan()

        # Agent must see a marker that tells it to stop and wait for the
        # user's Continue/Dismiss reply before calling any other tools.
        text = result.data["text"].lower()
        assert "plan" in text
        assert ("wait" in text) or ("stop" in text) or ("user" in text)

    def test_should_reject_when_plan_is_empty(self):
        reset_working_flow()
        comp = ProposePlan()
        comp.set(plan="")
        result = comp.propose_plan()

        assert "error" in result.data
        # No event must leak when validation rejects the call.
        assert drain_flow_events() == []

    def test_should_reject_when_plan_is_whitespace_only(self):
        reset_working_flow()
        comp = ProposePlan()
        comp.set(plan="   \n\t  ")
        result = comp.propose_plan()

        assert "error" in result.data
        assert drain_flow_events() == []

    def test_should_preserve_markdown_verbatim_when_plan_contains_formatting(self):
        # Plan markdown must be passed through unchanged so the frontend can
        # render headings, lists, code blocks. No truncation, no escaping.
        reset_working_flow()
        comp = ProposePlan()
        plan = (
            "## Plan\n\n"
            "- Add `ChatInput`\n"
            "- Add `Agent` with `model=gpt-4o`\n"
            "- Connect them with `message -> input_value`"
        )
        comp.set(plan=plan)
        comp.propose_plan()

        events = drain_flow_events()
        assert events[0]["markdown"] == plan


class TestAddComponent:
    def test_add_component_pushes_event(self):
        reset_working_flow()
        comp = AddComponent()
        comp.set(component_type="ChatInput")
        result = comp.add_component()
        assert "id" in result.data
        assert "ChatInput" in result.data["id"]

        events = drain_flow_events()
        assert len(events) == 1
        assert events[0]["action"] == "add_component"
        assert "node" in events[0]

    def test_add_unknown_component_returns_error(self):
        reset_working_flow()
        comp = AddComponent()
        comp.set(component_type="TotallyFake")
        result = comp.add_component()
        assert "error" in result.data


class TestConfigureComponentModelField:
    """Regression: ModelInput's frontend dropdown reads `value[0].name` and
    matches it against the field's `options`. If the new model isn't in
    options the dropdown silently falls back to options[0], so the canvas
    label keeps showing the previous selection even though `value` was
    updated. The tool must mirror the new selection into `options`.
    """  # noqa: D205

    def test_configure_model_field_should_mirror_value_into_options(self):
        from lfx.mcp.flow_builder_tools import (
            AddComponent,
            ConfigureComponent,
            _ensure_working_flow,
            drain_flow_events,
            reset_working_flow,
        )

        reset_working_flow()
        agent = AddComponent()
        agent.set(component_type="Agent")
        agent_id = agent.add_component().data["id"]
        drain_flow_events()

        cfg = ConfigureComponent()
        cfg.set(
            component_id=agent_id,
            params='{"model": [{"provider": "OpenAI", "name": "gpt-4o"}]}',
        )
        result = cfg.configure_component()
        assert "error" not in result.data, f"configure failed: {result.data}"

        flow = _ensure_working_flow()
        agent_node = next(n for n in flow["data"]["nodes"] if n["data"]["id"] == agent_id)
        model_field = agent_node["data"]["node"]["template"]["model"]
        assert model_field["value"] == [{"provider": "OpenAI", "name": "gpt-4o"}]

        options = model_field.get("options") or []
        assert any(o.get("name") == "gpt-4o" and o.get("provider") == "OpenAI" for o in options), (
            f"new model must be present in options so the dropdown can match it; got options={options!r}"
        )

    def test_configure_model_field_should_not_duplicate_when_already_in_options(self):
        from lfx.mcp.flow_builder_tools import (
            AddComponent,
            ConfigureComponent,
            _ensure_working_flow,
            drain_flow_events,
            reset_working_flow,
        )

        reset_working_flow()
        agent = AddComponent()
        agent.set(component_type="Agent")
        agent_id = agent.add_component().data["id"]

        # Pre-populate options as if the frontend had already loaded them.
        flow = _ensure_working_flow()
        agent_node = next(n for n in flow["data"]["nodes"] if n["data"]["id"] == agent_id)
        agent_node["data"]["node"]["template"]["model"]["options"] = [
            {"provider": "OpenAI", "name": "gpt-4o"},
            {"provider": "OpenAI", "name": "gpt-4o-mini"},
        ]
        drain_flow_events()

        cfg = ConfigureComponent()
        cfg.set(
            component_id=agent_id,
            params='{"model": [{"provider": "OpenAI", "name": "gpt-4o"}]}',
        )
        cfg.configure_component()

        flow = _ensure_working_flow()
        agent_node = next(n for n in flow["data"]["nodes"] if n["data"]["id"] == agent_id)
        options = agent_node["data"]["node"]["template"]["model"]["options"]
        # Same model already there — no duplication.
        gpt4o_count = sum(1 for o in options if o.get("name") == "gpt-4o")
        assert gpt4o_count == 1, f"must not duplicate; got {gpt4o_count} entries for gpt-4o"

    def test_configure_non_model_field_does_not_touch_options(self):
        """The mirror-into-options behavior is specific to model-type fields."""
        from lfx.mcp.flow_builder_tools import (
            AddComponent,
            ConfigureComponent,
            _ensure_working_flow,
            drain_flow_events,
            reset_working_flow,
        )

        reset_working_flow()
        agent = AddComponent()
        agent.set(component_type="Agent")
        agent_id = agent.add_component().data["id"]
        drain_flow_events()

        cfg = ConfigureComponent()
        cfg.set(
            component_id=agent_id,
            params='{"system_prompt": "You are a helpful assistant."}',
        )
        cfg.configure_component()

        flow = _ensure_working_flow()
        agent_node = next(n for n in flow["data"]["nodes"] if n["data"]["id"] == agent_id)
        # system_prompt has no `options` field — must not have been touched.
        assert "options" not in agent_node["data"]["node"]["template"]["system_prompt"]


def _make_agent_node_for_model_test():
    """Reset the working flow and add a fresh Agent node ready for configure."""
    from lfx.mcp.flow_builder_tools import (
        AddComponent,
        drain_flow_events,
        reset_working_flow,
    )

    reset_working_flow()
    agent = AddComponent()
    agent.set(component_type="Agent")
    agent_id = agent.add_component().data["id"]
    drain_flow_events()
    return agent_id


def _read_model_field_value(agent_id):
    from lfx.mcp.flow_builder_tools import _ensure_working_flow

    flow = _ensure_working_flow()
    agent_node = next(n for n in flow["data"]["nodes"] if n["data"]["id"] == agent_id)
    return agent_node["data"]["node"]["template"]["model"]["value"]


class TestConfigureComponentModelProviderOnly:
    """Regression: assistant said one model, canvas showed another.

    When the flow-builder LLM switches provider but omits the model name
    (``[{"provider": "Anthropic"}]``), the bare value used to land on the
    node with no ``name``. The canvas dropdown then silently selected the
    provider's newest/default model, diverging from whatever the assistant
    narrated. configure_component must resolve the provider's default name
    so the applied value is complete, mirrored into options, and reported.
    """

    def test_should_resolve_provider_default_name_when_model_name_is_missing(self):
        from lfx.mcp.flow_builder_tools import ConfigureComponent, _ensure_working_flow

        agent_id = _make_agent_node_for_model_test()
        cfg = ConfigureComponent()
        cfg.set(component_id=agent_id, params='{"model": [{"provider": "Anthropic"}]}')
        result = cfg.configure_component()
        assert "error" not in result.data, f"configure failed: {result.data}"

        value = _read_model_field_value(agent_id)
        assert isinstance(value, list), f"expected a model entry, got {value!r}"
        assert value, f"expected a model entry, got {value!r}"
        resolved_name = value[0].get("name")
        assert resolved_name, f"provider-only model must be filled with a default name; got {value!r}"
        assert value[0].get("provider") == "Anthropic"

        flow = _ensure_working_flow()
        agent_node = next(n for n in flow["data"]["nodes"] if n["data"]["id"] == agent_id)
        options = agent_node["data"]["node"]["template"]["model"].get("options") or []
        assert any(o.get("name") == resolved_name and o.get("provider") == "Anthropic" for o in options), (
            f"resolved model must be mirrored into options; got {options!r}"
        )

        assert resolved_name in (result.data.get("text") or ""), (
            f"tool result must report the resolved model name; got {result.data.get('text')!r}"
        )

    def test_should_preserve_an_explicitly_named_model(self):
        from lfx.mcp.flow_builder_tools import ConfigureComponent

        agent_id = _make_agent_node_for_model_test()
        cfg = ConfigureComponent()
        cfg.set(
            component_id=agent_id,
            params='{"model": [{"provider": "Anthropic", "name": "claude-sonnet-4-5-20250929"}]}',
        )
        result = cfg.configure_component()
        assert "error" not in result.data

        value = _read_model_field_value(agent_id)
        assert value[0].get("name") == "claude-sonnet-4-5-20250929"


class TestConfigureComponentModelFieldSerializedSpec:
    r"""Regression: PR-12575 round 6 bug 2.

    The flow-builder LLM sometimes emits the model spec as a serialized
    string instead of the canonical ``[{"provider": X, "name": Y}]``
    list. Two formats observed in QA, ~30 min apart, same prompt:

      Run 1 (JSON):  ``[{"provider": "OpenAI", "name": "gpt-5.4"}]``
      Run 2 (YAML):  ``- provider: OpenAI\n  name: gpt-5.4``

    The previous code passed the string through as-is, so the canvas
    stored ``model[0].name = <serialized spec>`` and ``provider="Unknown"``
    (the catalog fallback). Downstream, ``get_llm`` raises ``ValueError:
    The selected model is missing a provider...``. ConfigureComponent must
    parse and normalize these formats before writing to the template.
    """

    def test_should_parse_provider_and_name_when_model_value_is_json_list_string(self):
        """Parse a JSON-array-of-dict string emitted as the bare value."""
        from lfx.mcp.flow_builder_tools import ConfigureComponent

        agent_id = _make_agent_node_for_model_test()
        cfg = ConfigureComponent()
        cfg.set(
            component_id=agent_id,
            # Value is a JSON-array string — exactly what QA round 6 captured.
            params='{"model": "[{\\"provider\\": \\"OpenAI\\", \\"name\\": \\"gpt-5.4\\"}]"}',
        )
        result = cfg.configure_component()
        assert "error" not in result.data, f"configure failed: {result.data}"

        value = _read_model_field_value(agent_id)
        assert isinstance(value, list)
        assert len(value) == 1, f"expected canonical 1-element list, got {value!r}"
        assert value[0].get("provider") == "OpenAI", (
            f"provider must be parsed from the JSON spec, got provider={value[0].get('provider')!r} (was the "
            f"catalog 'Unknown' fallback firing)"
        )
        assert value[0].get("name") == "gpt-5.4", f"name must be the bare model name, got {value[0].get('name')!r}"

    def test_should_parse_provider_and_name_when_model_value_is_yaml_string(self):
        """Same bug, YAML format — observed in the round 6 double-check run."""
        from lfx.mcp.flow_builder_tools import ConfigureComponent

        agent_id = _make_agent_node_for_model_test()
        cfg = ConfigureComponent()
        cfg.set(
            component_id=agent_id,
            # YAML block emitted by the LLM, embedded as a JSON string.
            params='{"model": "- provider: OpenAI\\n  name: gpt-5.4"}',
        )
        result = cfg.configure_component()
        assert "error" not in result.data, f"configure failed: {result.data}"

        value = _read_model_field_value(agent_id)
        assert isinstance(value, list)
        assert len(value) == 1, f"expected canonical 1-element list, got {value!r}"
        assert value[0].get("provider") == "OpenAI", (
            f"provider must be parsed from the YAML spec, got provider={value[0].get('provider')!r}"
        )
        assert value[0].get("name") == "gpt-5.4", f"name must be the bare model name, got {value[0].get('name')!r}"

    def test_should_parse_when_model_value_is_single_dict_json_string(self):
        """LLM emits a single object instead of a list — same parsing pipeline."""
        from lfx.mcp.flow_builder_tools import ConfigureComponent

        agent_id = _make_agent_node_for_model_test()
        cfg = ConfigureComponent()
        cfg.set(
            component_id=agent_id,
            params='{"model": "{\\"provider\\": \\"OpenAI\\", \\"name\\": \\"gpt-4o\\"}"}',
        )
        result = cfg.configure_component()
        assert "error" not in result.data, f"configure failed: {result.data}"

        value = _read_model_field_value(agent_id)
        assert isinstance(value, list)
        assert len(value) == 1
        assert value[0].get("provider") == "OpenAI"
        assert value[0].get("name") == "gpt-4o"

    def test_should_preserve_canonical_list_when_model_value_is_already_well_formed(self):
        """Regression guard: canonical input must round-trip unchanged."""
        from lfx.mcp.flow_builder_tools import ConfigureComponent

        agent_id = _make_agent_node_for_model_test()
        cfg = ConfigureComponent()
        cfg.set(
            component_id=agent_id,
            params='{"model": [{"provider": "OpenAI", "name": "gpt-4o"}]}',
        )
        result = cfg.configure_component()
        assert "error" not in result.data, f"configure failed: {result.data}"

        value = _read_model_field_value(agent_id)
        assert value == [{"provider": "OpenAI", "name": "gpt-4o"}]


class TestConnectComponents:
    def test_connect_pushes_event(self):
        reset_working_flow()

        # Add two components first
        add1 = AddComponent()
        add1.set(component_type="ChatInput")
        r1 = add1.add_component()

        add2 = AddComponent()
        add2.set(component_type="ChatOutput")
        r2 = add2.add_component()

        drain_flow_events()  # clear add events

        conn = ConnectComponents()
        conn.set(
            source_id=r1.data["id"],
            source_output="message",
            target_id=r2.data["id"],
            target_input="input_value",
        )
        result = conn.connect_components()
        assert "Connected" in result.data["text"]

        events = drain_flow_events()
        assert len(events) == 1
        assert events[0]["action"] == "connect"
        assert "edge" in events[0]

    def test_connect_updates_source_selected_output_when_multiple_outputs(self):
        """Regression: connecting via a non-default output of a multi-output
        component must update the source node's `selected_output` so the
        canvas dropdown reflects the connected output. Uses Agent's
        `structured_response` (Data) into ChatOutput, since the Agent has
        multiple outputs by default and ChatOutput.input_value accepts Data.
        """  # noqa: D205
        from lfx.mcp.flow_builder_tools import _ensure_working_flow, _find_node

        reset_working_flow()

        agent = AddComponent()
        agent.set(component_type="Agent")
        agent_id = agent.add_component().data["id"]

        chat_out = AddComponent()
        chat_out.set(component_type="ChatOutput")
        out_id = chat_out.add_component().data["id"]

        drain_flow_events()

        conn = ConnectComponents()
        conn.set(
            source_id=agent_id,
            source_output="structured_response",  # non-default; default is "response"
            target_id=out_id,
            target_input="input_value",
        )
        result = conn.connect_components()
        assert "error" not in result.data, f"connect failed: {result.data.get('error')}"

        flow = _ensure_working_flow()
        source_node = _find_node(flow, agent_id)
        assert source_node is not None
        # Frontend reads selected_output from data (top-level), NOT data.node.
        selected = source_node["data"].get("selected_output")
        assert selected == "structured_response", (
            f"selected_output must update at data.selected_output (top-level); got {selected!r}"
        )

    def test_connect_emits_select_output_event_when_source_has_multiple_outputs(self):
        """The frontend can't infer selected_output from the edge alone — the
        backend must broadcast a dedicated event so the canvas dropdown updates.
        """  # noqa: D205
        reset_working_flow()

        agent = AddComponent()
        agent.set(component_type="Agent")
        agent_id = agent.add_component().data["id"]

        chat_out = AddComponent()
        chat_out.set(component_type="ChatOutput")
        out_id = chat_out.add_component().data["id"]

        drain_flow_events()

        conn = ConnectComponents()
        conn.set(
            source_id=agent_id,
            source_output="structured_response",
            target_id=out_id,
            target_input="input_value",
        )
        conn.connect_components()

        events = drain_flow_events()
        select_events = [e for e in events if e["action"] == "select_output"]
        assert len(select_events) == 1, f"expected one select_output event; got events={events!r}"
        assert select_events[0]["component_id"] == agent_id
        assert select_events[0]["output_name"] == "structured_response"

    def test_connect_to_model_field_should_succeed_and_enable_connection_mode(self):
        """The Agent's `model` field exposes a 'Connect other models' UX that
        flips `_connectionMode=true` on the node — that's how the dropdown
        switches to displaying an external connection. The tool must
        auto-enable that flag when wiring an external model so the canvas
        renders the edge instead of the dropdown.
        """  # noqa: D205
        from lfx.mcp.flow_builder_tools import _ensure_working_flow, _find_node

        reset_working_flow()

        add_openai = AddComponent()
        add_openai.set(component_type="OpenAIModel")
        openai_id = add_openai.add_component().data["id"]

        add_agent = AddComponent()
        add_agent.set(component_type="Agent")
        agent_id = add_agent.add_component().data["id"]

        drain_flow_events()

        conn = ConnectComponents()
        conn.set(
            source_id=openai_id,
            source_output="model_output",
            target_id=agent_id,
            target_input="model",
        )
        result = conn.connect_components()
        assert "error" not in result.data, f"connect failed: {result.data!r}"

        flow = _ensure_working_flow()
        assert flow["data"]["edges"], "edge must be added"

        agent_node = _find_node(flow, agent_id)
        assert agent_node is not None
        # The flag the frontend dropdown reads to switch out of dropdown mode.
        assert agent_node["data"].get("_connectionMode") is True, (
            "connecting an external model into a ModelInput must auto-enable connection mode"
        )

    def test_connect_to_model_field_emits_set_connection_mode_event(self):
        """The frontend dropdown reads `_connectionMode` from node data.
        Backend must broadcast the flip so the canvas updates without a
        full set_flow round-trip.
        """  # noqa: D205
        reset_working_flow()

        add_openai = AddComponent()
        add_openai.set(component_type="OpenAIModel")
        openai_id = add_openai.add_component().data["id"]

        add_agent = AddComponent()
        add_agent.set(component_type="Agent")
        agent_id = add_agent.add_component().data["id"]

        drain_flow_events()

        conn = ConnectComponents()
        conn.set(
            source_id=openai_id,
            source_output="model_output",
            target_id=agent_id,
            target_input="model",
        )
        conn.connect_components()

        events = drain_flow_events()
        cm_events = [e for e in events if e["action"] == "set_connection_mode"]
        assert len(cm_events) == 1, f"expected one set_connection_mode event; got {events!r}"
        assert cm_events[0]["component_id"] == agent_id
        assert cm_events[0]["enabled"] is True

    def test_connect_to_non_model_field_does_not_emit_connection_mode(self):
        """The connection-mode flip is specific to ModelInput targets."""
        reset_working_flow()

        add_in = AddComponent()
        add_in.set(component_type="ChatInput")
        in_id = add_in.add_component().data["id"]

        add_out = AddComponent()
        add_out.set(component_type="ChatOutput")
        out_id = add_out.add_component().data["id"]

        drain_flow_events()

        conn = ConnectComponents()
        conn.set(source_id=in_id, source_output="message", target_id=out_id, target_input="input_value")
        conn.connect_components()

        events = drain_flow_events()
        assert all(e["action"] != "set_connection_mode" for e in events), (
            "non-ModelInput connections must not flip _connectionMode"
        )

    def test_connect_does_not_emit_select_output_for_single_output_source(self):
        """ChatInput has a single output — no dropdown to update, so no event."""
        reset_working_flow()

        add1 = AddComponent()
        add1.set(component_type="ChatInput")
        r1 = add1.add_component()

        add2 = AddComponent()
        add2.set(component_type="ChatOutput")
        r2 = add2.add_component()

        drain_flow_events()

        conn = ConnectComponents()
        conn.set(
            source_id=r1.data["id"],
            source_output="message",
            target_id=r2.data["id"],
            target_input="input_value",
        )
        conn.connect_components()

        events = drain_flow_events()
        assert all(e["action"] != "select_output" for e in events), (
            "ChatInput has only one output — no select_output event should fire"
        )

    def test_connect_reconciles_a_stale_selected_output(self):
        # Bug: if the source carried a `selected_output` naming an output
        # that no longer exists (e.g. tool-mode collapsed the outputs),
        # connect_components left it dangling — the node label pointed at
        # a removed output. A connect must never leave selected_output
        # naming a non-existent output.
        from lfx.mcp.flow_builder_tools import _ensure_working_flow, _find_node

        reset_working_flow()

        add1 = AddComponent()
        add1.set(component_type="ChatInput")
        src_id = add1.add_component().data["id"]
        add2 = AddComponent()
        add2.set(component_type="ChatOutput")
        tgt_id = add2.add_component().data["id"]
        drain_flow_events()

        flow = _ensure_working_flow()
        src = _find_node(flow, src_id)
        assert src is not None
        # Simulate a leftover selection from a prior wiring/tool-mode swap.
        src["data"]["selected_output"] = "ghost_output"

        conn = ConnectComponents()
        conn.set(
            source_id=src_id,
            source_output="message",
            target_id=tgt_id,
            target_input="input_value",
        )
        result = conn.connect_components()
        assert "error" not in result.data, result.data

        src_after = _find_node(_ensure_working_flow(), src_id)
        output_names = {
            o.get("name") for o in src_after["data"].get("node", {}).get("outputs", []) if isinstance(o, dict)
        }
        stale = src_after["data"].get("selected_output")
        assert stale is None or stale in output_names, (
            f"selected_output {stale!r} is not a real output of the source ({output_names})"
        )


class TestContextVarIsolation:
    """Verify that concurrent async tasks get isolated working flow state."""

    async def test_concurrent_tasks_have_isolated_state(self):
        """Two tasks running in parallel should not see each other's working flow."""
        results: dict[str, dict | None] = {}
        a_ready = asyncio.Event()
        b_ready = asyncio.Event()

        async def task_a():
            init_working_flow({"name": "flow_a", "data": {"nodes": [], "edges": []}}, "id_a")
            a_ready.set()
            await b_ready.wait()  # wait for task_b to init its flow
            # After task_b has set its own flow, task_a should still see flow_a
            flow = get_working_flow()
            results["a"] = flow
            events_before = drain_flow_events()
            results["a_events_before"] = len(events_before)
            # Add an event in task_a's context
            comp = AddComponent()
            comp.set(component_type="ChatInput")
            comp.add_component()
            results["a_events_after"] = len(drain_flow_events())
            reset_working_flow()

        async def task_b():
            init_working_flow({"name": "flow_b", "data": {"nodes": [], "edges": []}}, "id_b")
            b_ready.set()
            await a_ready.wait()  # wait for task_a to init its flow
            flow = get_working_flow()
            results["b"] = flow
            results["b_events_before"] = len(drain_flow_events())
            reset_working_flow()

        await asyncio.gather(task_a(), task_b())

        # Each task should have seen its own flow, not the other's
        assert results["a"]["name"] == "flow_a"
        assert results["b"]["name"] == "flow_b"
        # Events should be isolated too
        assert results["a_events_before"] == 0
        assert results["b_events_before"] == 0
        assert results["a_events_after"] == 1  # only task_a's AddComponent event


class TestConfigureProposeConversion:
    """Bug B: a pure-edit turn surfaces text edits as a review card, deterministically.

    A ``configure_component`` on a PRE-EXISTING component's text field must
    become a reviewable ``edit_field`` proposal — never a silent auto-apply —
    regardless of which tool the LLM picked. Default-off so builds/runs are
    untouched.
    """

    def setup_method(self):
        reset_working_flow()

    def teardown_method(self):
        reset_working_flow()

    @staticmethod
    def _flow():
        return {
            "name": "Restaurant",
            "data": {
                "nodes": [
                    _node("ChatInput-1", "ChatInput", {"input_value": {"value": "hi"}}),
                    _node(
                        "Agent-odhHB",
                        "Agent",
                        {
                            "system_prompt": {"value": "You are a restaurant attendant agent.", "type": "str"},
                            "model": {"value": [{"provider": "OpenAI", "name": "gpt-4o"}], "type": "model"},
                        },
                    ),
                    _node("ChatOutput-1", "ChatOutput", {}),
                ],
                "edges": [
                    _edge("ChatInput-1", "message", "Agent-odhHB", "input_value"),
                    _edge("Agent-odhHB", "response", "ChatOutput-1", "input_value"),
                ],
            },
        }

    def _configure(self, component_id, params):
        from lfx.mcp.flow_builder_tools import ConfigureComponent

        comp = ConfigureComponent()
        comp.set(component_id=component_id, params=json.dumps(params))
        return comp.configure_component()

    def test_text_field_edit_on_existing_component_becomes_edit_field_proposal(self):
        from lfx.mcp.flow_builder_tools import set_propose_existing_edits

        init_working_flow(self._flow(), "flow-1")
        set_propose_existing_edits(enabled=True)

        result = self._configure("Agent-odhHB", {"system_prompt": "You are a CHEERFUL restaurant agent."})

        events = drain_flow_events()
        actions = [e["action"] for e in events]
        assert "edit_field" in actions, f"expected a review proposal, got {actions}"
        assert "configure" not in actions, "text edit on an existing component must NOT auto-apply"
        edit = next(e for e in events if e["action"] == "edit_field")
        assert edit["component_id"] == "Agent-odhHB"
        assert edit["field"] == "system_prompt"
        assert edit["new_value"] == "You are a CHEERFUL restaurant agent."
        assert edit["old_value"] == "You are a restaurant attendant agent."
        assert "patch" in edit
        assert "proposed" in result.data

    def test_same_edit_is_direct_when_propose_mode_off(self):
        # propose flag defaults off → build/run/continuation behavior unchanged.
        init_working_flow(self._flow(), "flow-1")

        self._configure("Agent-odhHB", {"system_prompt": "Changed directly."})

        actions = [e["action"] for e in drain_flow_events()]
        assert "configure" in actions
        assert "edit_field" not in actions

    def test_edit_on_freshly_added_component_is_direct_even_in_propose_mode(self):
        from lfx.mcp.flow_builder_tools import set_propose_existing_edits

        # The component is NOT in the initial snapshot (added this turn).
        init_working_flow({"name": "e", "data": {"nodes": [], "edges": []}}, "flow-1")
        set_propose_existing_edits(enabled=True)
        # Seed a node directly into the working flow as if AddComponent ran.
        get_working_flow()["data"]["nodes"].append(
            _node("Agent-new", "Agent", {"system_prompt": {"value": "old", "type": "str"}})
        )

        self._configure("Agent-new", {"system_prompt": "fresh build value"})

        actions = [e["action"] for e in drain_flow_events()]
        assert "configure" in actions, "configuring a just-added component must apply live"
        assert "edit_field" not in actions

    def test_model_swap_on_existing_component_stays_direct_in_propose_mode(self):
        from lfx.mcp.flow_builder_tools import set_propose_existing_edits

        init_working_flow(self._flow(), "flow-1")
        set_propose_existing_edits(enabled=True)

        self._configure("Agent-odhHB", {"model": [{"provider": "OpenAI", "name": "gpt-4o-mini"}]})

        actions = [e["action"] for e in drain_flow_events()]
        assert "configure" in actions, "structured model swap is not a reviewable text edit"
        assert "edit_field" not in actions

    def test_mixed_params_propose_text_and_apply_nontext(self):
        from lfx.mcp.flow_builder_tools import set_propose_existing_edits

        init_working_flow(self._flow(), "flow-1")
        set_propose_existing_edits(enabled=True)

        self._configure(
            "Agent-odhHB",
            {"system_prompt": "new persona", "model": [{"provider": "OpenAI", "name": "gpt-4o-mini"}]},
        )

        events = drain_flow_events()
        actions = [e["action"] for e in events]
        # Text field → proposal; model swap → direct apply, in the same call.
        assert "edit_field" in actions
        assert "configure" in actions
        configure_ev = next(e for e in events if e["action"] == "configure")
        assert "model" in configure_ev["params"]
        assert "system_prompt" not in configure_ev["params"]


class TestConnectToolModeFlipPropagation:
    """Connecting via component_as_tool must surface the source's tool-mode flip.

    Wiring `X.component_as_tool -> Agent.tools` flips X to tool mode in the
    working flow; the canvas must be told (an `enable_tool_mode` event with the
    flipped outputs) so the source node re-renders with its Toolset handle and
    the edge actually attaches — otherwise it's the "said it connected but
    didn't" bug.
    """

    def setup_method(self):
        reset_working_flow()

    def teardown_method(self):
        reset_working_flow()

    @staticmethod
    def _flipped_source_flow():
        # Simulate the post-`_enable_tool_mode` state: tool_mode on + the
        # synthesized component_as_tool (Toolset) output.
        node = _node("MenuTool-1", "MenuTool", {"query": {"value": "", "tool_mode": True}})
        node["data"]["node"]["tool_mode"] = True
        node["data"]["node"]["outputs"] = [
            {"name": "component_as_tool", "display_name": "Toolset", "types": ["Tool"], "method": "to_toolkit"}
        ]
        return {"name": "T", "data": {"nodes": [node], "edges": []}}

    def test_emits_enable_tool_mode_with_flipped_outputs(self):
        from lfx.mcp.flow_builder_tools.mutate_tools import _emit_source_tool_mode_if_flipped

        flow = self._flipped_source_flow()
        drain_flow_events()

        _emit_source_tool_mode_if_flipped(flow, "MenuTool-1", "component_as_tool")

        events = drain_flow_events()
        assert len(events) == 1
        ev = events[0]
        assert ev["action"] == "enable_tool_mode"
        assert ev["component_id"] == "MenuTool-1"
        assert any(o.get("name") == "component_as_tool" for o in ev["outputs"]), ev["outputs"]

    def test_skips_when_source_output_is_not_the_tool_handle(self):
        from lfx.mcp.flow_builder_tools.mutate_tools import _emit_source_tool_mode_if_flipped

        flow = self._flipped_source_flow()
        drain_flow_events()

        # A normal output (e.g. "message") is not a tool-mode flip — emit nothing.
        _emit_source_tool_mode_if_flipped(flow, "MenuTool-1", "message")

        assert drain_flow_events() == []

    def test_skips_when_node_not_in_tool_mode(self):
        from lfx.mcp.flow_builder_tools.mutate_tools import _emit_source_tool_mode_if_flipped

        node = _node("Plain-1", "Plain", {})  # no tool_mode, default outputs
        flow = {"name": "T", "data": {"nodes": [node], "edges": []}}
        drain_flow_events()

        _emit_source_tool_mode_if_flipped(flow, "Plain-1", "component_as_tool")

        assert drain_flow_events() == []
