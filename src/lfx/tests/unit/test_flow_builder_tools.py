"""Tests for flow_builder_tools components."""

import asyncio

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
            spec=(
                "name: Clean\n"
                "nodes:\n"
                "  A: ChatInput\n"
                "  B: ChatOutput\n"
                "edges:\n"
                "  A.message -> B.input_value\n"
            ),
        )
        result = comp.build_flow()

        assert "error" not in result.data
        assert "built successfully" in result.data["text"]

    def test_build_should_pass_when_single_node_has_no_edges_only_if_lone(self):
        # Edge case: a 1-node spec is technically all-orphans, but it is a
        # malformed flow regardless — the validator can still reject it for
        # the same reason. Pin the chosen behavior.
        reset_working_flow()
        comp = BuildFlowFromSpec()
        comp.set(spec="name: Lone\nnodes:\n  A: ChatInput\n")
        result = comp.build_flow()

        assert "error" in result.data
        assert "orphan" in result.data["error"].lower()


class TestProposePlan:
    """ProposePlan emits a markdown plan to the user as a gate BEFORE the
    agent runs search/describe/build_flow tools. The agent's next step
    depends on the user's Continue/Dismiss reply, which arrives as a new
    user turn — the tool itself does not block.
    """

    def test_should_push_propose_plan_event_when_plan_is_valid(self):
        reset_working_flow()
        comp = ProposePlan()
        comp.set(plan="I'll create a ChatInput -> Agent (GPT-4) -> ChatOutput flow.")
        comp.propose_plan()

        events = drain_flow_events()
        assert len(events) == 1
        assert events[0]["action"] == "propose_plan"
        assert events[0]["markdown"] == (
            "I'll create a ChatInput -> Agent (GPT-4) -> ChatOutput flow."
        )

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
    """

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
        """
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
        backend must broadcast a dedicated event so the canvas dropdown updates."""
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
        renders the edge instead of the dropdown."""
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
        full set_flow round-trip."""
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
