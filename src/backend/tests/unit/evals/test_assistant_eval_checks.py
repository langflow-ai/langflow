"""Deterministic tests for the assistant eval harness.

These run in the normal unit suite (no LLM, no network) and prove each
scenario check catches the failure class it claims to gate on.
"""

from __future__ import annotations

from typing import Any

from tests.evals.assistant.harness import (
    baseline_failures,
    is_loop_feedback_edge,
    parse_sse_payloads,
    replay_final_flow,
    template_value,
)
from tests.evals.assistant.scenarios import basic_prompting_seed, get_scenario


def make_node(type_: str, node_id: str, **fields: Any) -> dict[str, Any]:
    template = {key: {"value": value} for key, value in fields.items()}
    return {"id": node_id, "data": {"id": node_id, "type": type_, "node": {"template": template}}}


def make_edge(
    source: str,
    target: str,
    *,
    field_name: str = "input_value",
    source_output: str = "message",
    loop_feedback: bool = False,
) -> dict[str, Any]:
    target_handle: dict[str, Any] = (
        {"name": "item", "id": target} if loop_feedback else {"fieldName": field_name, "id": target}
    )
    return {
        "id": f"{source}->{target}",
        "source": source,
        "target": target,
        "data": {"sourceHandle": {"name": source_output, "id": source}, "targetHandle": target_handle},
    }


def set_flow_event(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "event": "flow_update",
        "action": "set_flow",
        "flow": {"name": "eval", "data": {"nodes": nodes, "edges": edges}},
    }


def complete_event(tokens: int = 1_000, duration: float = 3.0, result: str = "done") -> dict[str, Any]:
    return {
        "event": "complete",
        "data": {
            "result": result,
            "usage": {"input_tokens": tokens // 2, "output_tokens": tokens // 2, "total_tokens": tokens},
            "duration_seconds": duration,
        },
    }


def progress_event(step: str = "building", attempt: int = 1) -> dict[str, Any]:
    return {"event": "progress", "step": step, "attempt": attempt, "max_attempts": 3}


def _simple_build_stream() -> list[dict[str, Any]]:
    nodes = [
        make_node("ChatInput", "ChatInput-1"),
        make_node("Agent", "Agent-1", system_prompt="You are a helpful assistant."),
        make_node("ChatOutput", "ChatOutput-1"),
    ]
    edges = [make_edge("ChatInput-1", "Agent-1"), make_edge("Agent-1", "ChatOutput-1")]
    return [progress_event(), set_flow_event(nodes, edges), complete_event(result="Flow is ready.")]


def _evaluate(scenario_name: str, events: list[dict[str, Any]], seed: dict[str, Any] | None = None) -> list[str]:
    scenario = get_scenario(scenario_name)
    return scenario.evaluate(events, replay_final_flow(seed, events))


class TestBaselineFailures:
    def test_passes_on_clean_stream(self):
        failures = baseline_failures(
            _simple_build_stream(), expect_flow_update=True, token_ceiling=10_000, duration_ceiling=60
        )
        assert failures == []

    def test_fails_on_error_event(self):
        events = [*_simple_build_stream(), {"event": "error", "message": "boom"}]
        failures = baseline_failures(events, expect_flow_update=True, token_ceiling=10_000, duration_ceiling=60)
        assert any("error event" in f for f in failures)

    def test_fails_without_complete_event(self):
        events = [progress_event()]
        failures = baseline_failures(events, expect_flow_update=None, token_ceiling=10_000, duration_ceiling=60)
        assert any("no complete event" in f for f in failures)

    def test_fails_on_retry_attempts(self):
        events = [progress_event(attempt=2), *_simple_build_stream()]
        failures = baseline_failures(events, expect_flow_update=True, token_ceiling=10_000, duration_ceiling=60)
        assert any("attempts" in f for f in failures)

    def test_fails_when_token_budget_exceeded(self):
        events = [set_flow_event([], []), complete_event(tokens=99_999)]
        failures = baseline_failures(events, expect_flow_update=True, token_ceiling=10_000, duration_ceiling=60)
        assert any("token budget" in f for f in failures)

    def test_fails_when_duration_budget_exceeded(self):
        events = [set_flow_event([], []), complete_event(duration=999.0)]
        failures = baseline_failures(events, expect_flow_update=True, token_ceiling=10_000, duration_ceiling=60)
        assert any("duration budget" in f for f in failures)

    def test_fails_when_flow_update_expected_but_missing(self):
        failures = baseline_failures(
            [complete_event()], expect_flow_update=True, token_ceiling=10_000, duration_ceiling=60
        )
        assert any("expected flow_update" in f for f in failures)

    def test_fails_when_flow_update_forbidden_but_present(self):
        events = [set_flow_event([], []), complete_event()]
        failures = baseline_failures(events, expect_flow_update=False, token_ceiling=10_000, duration_ceiling=60)
        assert any("NO flow_update" in f for f in failures)


class TestSimpleBuildScenario:
    def test_passes_on_valid_build(self):
        assert _evaluate("simple_build", _simple_build_stream()) == []

    def test_fails_when_agent_missing(self):
        nodes = [make_node("ChatInput", "ChatInput-1"), make_node("ChatOutput", "ChatOutput-1")]
        edges = [make_edge("ChatInput-1", "ChatOutput-1"), make_edge("ChatInput-1", "ChatOutput-1")]
        events = [set_flow_event(nodes, edges), complete_event()]
        assert any("Agent" in f for f in _evaluate("simple_build", events))


class TestPersonaScenario:
    def test_passes_when_pirate_prompt_set(self):
        nodes = [
            make_node("ChatInput", "ChatInput-1"),
            make_node("Agent", "Agent-1", system_prompt="You are a PIRATE poet. Arr!"),
            make_node("ChatOutput", "ChatOutput-1"),
        ]
        edges = [make_edge("ChatInput-1", "Agent-1"), make_edge("Agent-1", "ChatOutput-1")]
        events = [set_flow_event(nodes, edges), complete_event()]
        assert _evaluate("persona_agent", events) == []

    def test_fails_when_system_prompt_left_default(self):
        assert any("pirate" in f for f in _evaluate("persona_agent", _simple_build_stream()))


class TestLoopScenario:
    def _loop_nodes(self) -> list[dict[str, Any]]:
        return [
            make_node("ChatInput", "ChatInput-1"),
            make_node("LoopComponent", "LoopComponent-1"),
            make_node("Agent", "Agent-1"),
            make_node("ChatOutput", "ChatOutput-1"),
        ]

    def test_passes_with_feedback_edge(self):
        edges = [
            make_edge("ChatInput-1", "LoopComponent-1"),
            make_edge("LoopComponent-1", "Agent-1", source_output="item"),
            make_edge("Agent-1", "LoopComponent-1", loop_feedback=True),
            make_edge("LoopComponent-1", "ChatOutput-1", source_output="done"),
        ]
        events = [set_flow_event(self._loop_nodes(), edges), complete_event()]
        assert _evaluate("loop_flow", events) == []

    def test_fails_without_feedback_edge(self):
        edges = [
            make_edge("ChatInput-1", "LoopComponent-1"),
            make_edge("LoopComponent-1", "Agent-1", source_output="item"),
            make_edge("LoopComponent-1", "ChatOutput-1", source_output="done"),
        ]
        events = [set_flow_event(self._loop_nodes(), edges), complete_event()]
        assert any("feedback edge" in f for f in _evaluate("loop_flow", events))

    def test_fails_without_loop_component(self):
        events = [set_flow_event([make_node("ChatOutput", "ChatOutput-1")], []), complete_event()]
        assert any("LoopComponent" in f for f in _evaluate("loop_flow", events))

    def test_fails_when_loop_has_no_data_source(self):
        # The exact manual-failure shape: body wired + feedback, but nothing
        # feeds Loop.Inputs — the eval must now catch what the proposal check missed.
        edges = [
            make_edge("LoopComponent-1", "Agent-1", source_output="item"),
            make_edge("Agent-1", "LoopComponent-1", loop_feedback=True),
            make_edge("LoopComponent-1", "ChatOutput-1", source_output="done"),
        ]
        nodes = [
            make_node("LoopComponent", "LoopComponent-1"),
            make_node("Agent", "Agent-1"),
            make_node("ChatOutput", "ChatOutput-1"),
        ]
        events = [set_flow_event(nodes, edges), complete_event()]
        failures = _evaluate("loop_flow", events)
        assert any("data source" in f for f in failures)


class TestIfElseScenario:
    def _router_nodes(self) -> list[dict[str, Any]]:
        return [
            make_node("ChatInput", "ChatInput-1"),
            make_node("ConditionalRouter", "ConditionalRouter-1"),
            make_node("ChatOutput", "ChatOutput-1"),
            make_node("ChatOutput", "ChatOutput-2"),
        ]

    def test_passes_with_both_branches(self):
        edges = [
            make_edge("ChatInput-1", "ConditionalRouter-1"),
            make_edge("ConditionalRouter-1", "ChatOutput-1", source_output="true_result"),
            make_edge("ConditionalRouter-1", "ChatOutput-2", source_output="false_result"),
        ]
        events = [set_flow_event(self._router_nodes(), edges), complete_event()]
        assert _evaluate("if_else_flow", events) == []

    def test_fails_when_false_branch_unwired(self):
        edges = [
            make_edge("ChatInput-1", "ConditionalRouter-1"),
            make_edge("ConditionalRouter-1", "ChatOutput-1", source_output="true_result"),
        ]
        events = [set_flow_event(self._router_nodes(), edges), complete_event()]
        assert any("false_result" in f for f in _evaluate("if_else_flow", events))


class TestTextOnlyScenarios:
    def test_plain_question_passes_text_only(self):
        events = [complete_event(result="The Loop component iterates over a list of Data items.")]
        assert _evaluate("plain_question", events) == []

    def test_plain_question_fails_when_canvas_mutated(self):
        events = [set_flow_event([], []), complete_event(result="The Loop component iterates.")]
        assert any("NO flow_update" in f for f in _evaluate("plain_question", events))

    def test_off_topic_passes_on_refusal(self):
        events = [complete_event(result="I can only help with Langflow-related topics.")]
        assert _evaluate("off_topic_refusal", events) == []

    def test_off_topic_fails_when_it_answers_the_question(self):
        events = [complete_event(result="n8n is a workflow automation tool; here is a tutorial...")]
        assert any("refusal" in f for f in _evaluate("off_topic_refusal", events))

    def test_short_input_fails_when_nothing_happens(self):
        events = [complete_event(result="")]
        assert any("neither" in f for f in _evaluate("short_input_robustness", events))


class TestEditScenarios:
    def _seed(self) -> dict[str, Any]:
        nodes = [
            make_node("ChatInput", "ChatInput-1"),
            make_node("Prompt", "Prompt-1", template="Answer the user."),
            make_node("LanguageModelComponent", "LanguageModelComponent-1", model_name="gpt-4o"),
            make_node("ChatOutput", "ChatOutput-1"),
        ]
        return {"nodes": nodes, "edges": [make_edge("Prompt-1", "LanguageModelComponent-1")]}

    def test_edit_passes_when_edit_field_event_applied(self):
        events = [
            {
                "event": "flow_update",
                "action": "edit_field",
                "component_id": "Prompt-1",
                "field": "template",
                "new_value": "Always answer in French.",
            },
            complete_event(),
        ]
        assert _evaluate("edit_existing_field", events, seed=self._seed()) == []

    def test_edit_fails_when_field_untouched(self):
        events = [
            {
                "event": "flow_update",
                "action": "configure",
                "component_id": "Prompt-1",
                "params": {"tool_placeholder": "x"},
            },
            complete_event(),
        ]
        assert any("French" in f for f in _evaluate("edit_existing_field", events, seed=self._seed()))

    def test_model_swap_passes_via_configure_replay(self):
        events = [
            {
                "event": "flow_update",
                "action": "configure",
                "component_id": "LanguageModelComponent-1",
                "params": {"model_name": "gpt-4o-mini"},
            },
            complete_event(),
        ]
        assert _evaluate("model_swap", events, seed=self._seed()) == []

    def test_model_swap_fails_when_model_unchanged(self):
        events = [set_flow_event(self._seed()["nodes"], []), complete_event()]
        assert any("gpt-4o-mini" in f for f in _evaluate("model_swap", events, seed=self._seed()))


class TestReplayFinalFlow:
    def test_set_flow_replaces_canvas(self):
        seed = {"nodes": [make_node("Prompt", "Prompt-1")], "edges": []}
        final = replay_final_flow(seed, [set_flow_event([make_node("Agent", "Agent-1")], [])])
        assert [n["data"]["type"] for n in final["nodes"]] == ["Agent"]

    def test_add_component_and_connect_accumulate(self):
        events = [
            {"event": "flow_update", "action": "add_component", "node": make_node("ChatInput", "ChatInput-1")},
            {"event": "flow_update", "action": "add_component", "node": make_node("ChatOutput", "ChatOutput-1")},
            {"event": "flow_update", "action": "connect", "edge": make_edge("ChatInput-1", "ChatOutput-1")},
        ]
        final = replay_final_flow(None, events)
        assert len(final["nodes"]) == 2
        assert len(final["edges"]) == 1

    def test_remove_component_drops_node_and_edges(self):
        seed = {
            "nodes": [make_node("ChatInput", "ChatInput-1"), make_node("ChatOutput", "ChatOutput-1")],
            "edges": [make_edge("ChatInput-1", "ChatOutput-1")],
        }
        events = [{"event": "flow_update", "action": "remove_component", "component_id": "ChatOutput-1"}]
        final = replay_final_flow(seed, events)
        assert len(final["nodes"]) == 1
        assert final["edges"] == []

    def test_edit_field_sets_template_value(self):
        seed = {"nodes": [make_node("Prompt", "Prompt-1", template="old")], "edges": []}
        events = [
            {
                "event": "flow_update",
                "action": "edit_field",
                "component_id": "Prompt-1",
                "field": "template",
                "new_value": "new",
            }
        ]
        final = replay_final_flow(seed, events)
        assert template_value(final["nodes"][0], "template") == "new"


class TestHelpers:
    def test_parse_sse_payloads_ignores_noise(self):
        raw = (
            'data: {"event": "token", "chunk": "hi"}\n\n'
            "not-a-data-line\ndata: not-json\n\n"
            'data: {"event": "complete", "data": {}}\n\n'
        )
        events = parse_sse_payloads(raw)
        assert [e["event"] for e in events] == ["token", "complete"]

    def test_loop_feedback_edge_detection(self):
        assert is_loop_feedback_edge(make_edge("A", "B", loop_feedback=True))
        assert not is_loop_feedback_edge(make_edge("A", "B"))

    def test_basic_prompting_seed_loads_expected_nodes(self):
        # Guards the starter-project path the seeded scenarios rely on.
        data = basic_prompting_seed()
        types = [n.get("data", {}).get("type") for n in data["nodes"]]
        assert "Prompt" in types
        assert "LanguageModelComponent" in types
