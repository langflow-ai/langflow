"""Declarative eval scenarios for the Langflow Assistant flow builder.

Every scenario's pass criteria are OBJECTIVE and STRUCTURAL (node types, edge
shapes, event presence, budgets) so a pass/fail is meaningful despite LLM
non-determinism. Budgets are generous regression tripwires, not tight SLAs.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from tests.evals.assistant.harness import (
    Event,
    FlowData,
    baseline_failures,
    edges_from_output,
    flow_updates,
    loop_feedback_edges,
    node_types,
    nodes_of_type,
    result_text,
    structural_completeness_failures,
    template_value,
)

CheckFn = Callable[[list[Event], FlowData], list[str]]
SeedFn = Callable[[], FlowData]

_STARTER_PROJECTS = Path(__file__).parents[3] / "base" / "langflow" / "initial_setup" / "starter_projects"


def basic_prompting_seed() -> FlowData:
    """Real starter-project canvas (ChatInput → Prompt → LanguageModel → ChatOutput) for edit scenarios."""
    raw = (_STARTER_PROJECTS / "Basic Prompting.json").read_text(encoding="utf-8")
    flow = json.loads(raw)
    return flow["data"]


@dataclass(frozen=True)
class Scenario:
    name: str
    prompt: str
    check: CheckFn
    token_ceiling: int
    duration_ceiling: float
    expect_flow_update: bool | None = None
    seed_flow: SeedFn | None = None
    description: str = ""

    def evaluate(self, events: list[Event], final_flow: FlowData) -> list[str]:
        failures = baseline_failures(
            events,
            expect_flow_update=self.expect_flow_update,
            token_ceiling=self.token_ceiling,
            duration_ceiling=self.duration_ceiling,
        )
        failures.extend(self.check(events, final_flow))
        return failures


def _require_types(final_flow: FlowData, required: dict[str, int]) -> list[str]:
    failures: list[str] = []
    present = node_types(final_flow)
    for type_name, count in required.items():
        if present.count(type_name) < count:
            failures.append(f"expected >= {count} {type_name} node(s), found {present.count(type_name)} in {present}")
    return failures


def _check_simple_build(_events: list[Event], final_flow: FlowData) -> list[str]:
    failures = _require_types(final_flow, {"ChatInput": 1, "Agent": 1, "ChatOutput": 1})
    if len(final_flow.get("edges", [])) < 2:
        failures.append(f"expected >= 2 edges, found {len(final_flow.get('edges', []))}")
    return failures


def _check_persona_agent(_events: list[Event], final_flow: FlowData) -> list[str]:
    failures = _require_types(final_flow, {"ChatInput": 1, "Agent": 1, "ChatOutput": 1})
    agents = nodes_of_type(final_flow, "Agent")
    persona_found = any("pirate" in str(template_value(a, "system_prompt") or "").lower() for a in agents)
    if agents and not persona_found:
        failures.append("no Agent has 'pirate' in its system_prompt (persona was not applied)")
    return failures


def _check_edit_existing_field(_events: list[Event], final_flow: FlowData) -> list[str]:
    prompts = nodes_of_type(final_flow, "Prompt")
    if not prompts:
        return ["Prompt node missing from final flow (edit destroyed the canvas?)"]
    if not any("french" in str(template_value(p, "template") or "").lower() for p in prompts):
        return ["no Prompt node's template mentions 'French' (requested edit was not applied)"]
    return []


def _check_model_swap(_events: list[Event], final_flow: FlowData) -> list[str]:
    # The assistant may configure the existing LanguageModelComponent or swap in
    # another model-bearing node — any node carrying the requested model passes.
    values = [template_value(n, "model_name") for n in final_flow.get("nodes", [])]
    if not any("gpt-4o-mini" in str(v or "") for v in values):
        return [f"no node has model_name gpt-4o-mini (found {[v for v in values if v]})"]
    return []


def _loop_has_data_source(final_flow: FlowData) -> bool:
    """A non-feedback edge lands on a LoopComponent's Inputs (the data feed)."""
    loop_ids = {n.get("id") or n.get("data", {}).get("id") for n in nodes_of_type(final_flow, "LoopComponent")}
    feedback_ids = {id(e) for e in loop_feedback_edges(final_flow)}
    for edge in final_flow.get("edges", []):
        handle = edge.get("data", {}).get("targetHandle") or {}
        if edge.get("target") in loop_ids and handle.get("fieldName") and id(edge) not in feedback_ids:
            return True
    return False


def _check_loop_flow(_events: list[Event], final_flow: FlowData) -> list[str]:
    failures = _require_types(final_flow, {"LoopComponent": 1, "ChatOutput": 1})
    feedback = loop_feedback_edges(final_flow)
    if not feedback:
        failures.append("no loop feedback edge (targetHandle with 'name' instead of 'fieldName')")
    if not _loop_has_data_source(final_flow):
        failures.append("Loop has no data source feeding its Inputs (nothing to iterate over)")
    # The APPLIED canvas — not just the proposal shape — must be runnable:
    # every required input connected/set, loop closed, no orphans.
    failures.extend(structural_completeness_failures(final_flow))
    return failures


def _check_if_else_flow(_events: list[Event], final_flow: FlowData) -> list[str]:
    failures = _require_types(final_flow, {"ConditionalRouter": 1, "ChatOutput": 2})
    if not edges_from_output(final_flow, "true_result"):
        failures.append("no edge leaving the ConditionalRouter true_result output")
    if not edges_from_output(final_flow, "false_result"):
        failures.append("no edge leaving the ConditionalRouter false_result output")
    failures.extend(structural_completeness_failures(final_flow))
    return failures


def _check_compound_build_describe(events: list[Event], final_flow: FlowData) -> list[str]:
    failures = _require_types(final_flow, {"ChatInput": 1, "ChatOutput": 1})
    if not final_flow.get("edges"):
        failures.append("expected at least one edge between ChatInput and ChatOutput")
    if len(result_text(events)) < 40:
        failures.append("final answer does not describe the flow (result text < 40 chars)")
    return failures


def _check_plain_question(events: list[Event], _final_flow: FlowData) -> list[str]:
    if len(result_text(events)) < 20:
        return ["expected a substantive text answer (result text < 20 chars)"]
    return []


def _check_off_topic(events: list[Event], _final_flow: FlowData) -> list[str]:
    text = result_text(events).lower()
    if "langflow" not in text:
        return [f"expected a Langflow-scoped refusal, got: {text[:120]!r}"]
    return []


def _check_short_input(events: list[Event], _final_flow: FlowData) -> list[str]:
    if not result_text(events) and not flow_updates(events):
        return ["short input produced neither a text answer nor canvas activity"]
    return []


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        name="simple_build",
        description="Baseline capability: build ChatInput -> Agent -> ChatOutput on an empty canvas.",
        prompt="Build a flow that connects a Chat Input to an Agent, and the Agent to a Chat Output.",
        check=_check_simple_build,
        expect_flow_update=True,
        token_ceiling=250_000,
        duration_ceiling=900,
    ),
    Scenario(
        name="persona_agent",
        description="System prompt population: the requested persona must land in the Agent's system_prompt.",
        prompt=(
            "Build a flow with a Chat Input, an Agent, and a Chat Output. "
            "Set the agent's system prompt so it always answers as a pirate."
        ),
        check=_check_persona_agent,
        expect_flow_update=True,
        token_ceiling=250_000,
        duration_ceiling=900,
    ),
    Scenario(
        name="edit_existing_field",
        description="Edit an existing canvas: change one field, keep the rest of the flow intact.",
        prompt=(
            "In the Prompt component of this flow, change the template field so the assistant "
            "always answers in French. Keep everything else unchanged."
        ),
        check=_check_edit_existing_field,
        expect_flow_update=True,
        seed_flow=basic_prompting_seed,
        token_ceiling=200_000,
        duration_ceiling=600,
    ),
    Scenario(
        name="model_swap",
        description="Model swap request on an existing canvas must set the model_name field.",
        prompt='Change the language model of this flow to use the OpenAI model "gpt-4o-mini".',
        check=_check_model_swap,
        expect_flow_update=True,
        seed_flow=basic_prompting_seed,
        token_ceiling=200_000,
        duration_ceiling=600,
    ),
    Scenario(
        name="loop_flow",
        description="Loop capability: LoopComponent plus at least one output-shaped feedback edge.",
        prompt=(
            "Build a flow that uses a Loop component to iterate over a list of items: "
            "connect a Chat Input to the Loop, process each item with an Agent, feed the agent's "
            "result back into the Loop's feedback input, and send the Loop's done output to a Chat Output."
        ),
        check=_check_loop_flow,
        expect_flow_update=True,
        token_ceiling=300_000,
        duration_ceiling=1200,
    ),
    Scenario(
        name="if_else_flow",
        description="Branching capability: ConditionalRouter with BOTH true/false branches wired to outputs.",
        prompt=(
            "Build a flow with a Chat Input connected to an If-Else (Conditional Router) component that "
            "checks whether the message contains the word 'urgent'. Route the True case to one Chat Output "
            "and the False case to a second Chat Output."
        ),
        check=_check_if_else_flow,
        expect_flow_update=True,
        token_ceiling=300_000,
        duration_ceiling=1200,
    ),
    Scenario(
        name="compound_build_describe",
        description="Compound ask: build AND describe in the same turn.",
        prompt=(
            "Build a simple flow with a Chat Input connected directly to a Chat Output, "
            "then describe in one paragraph what the flow does."
        ),
        check=_check_compound_build_describe,
        expect_flow_update=True,
        token_ceiling=250_000,
        duration_ceiling=900,
    ),
    Scenario(
        name="plain_question",
        description="Q&A path: a Langflow question must be answered with text only, never canvas mutations.",
        prompt="What does the Loop component do in Langflow?",
        check=_check_plain_question,
        expect_flow_update=False,
        token_ceiling=120_000,
        duration_ceiling=300,
    ),
    Scenario(
        name="off_topic_refusal",
        description="Off-topic guard: non-Langflow asks are refused cheaply with no canvas activity.",
        prompt="How does n8n work? Give me a tutorial about building automations in n8n.",
        check=_check_off_topic,
        expect_flow_update=False,
        token_ceiling=20_000,
        duration_ceiling=120,
    ),
    Scenario(
        name="short_input_robustness",
        description="Robustness: a near-empty greeting must not error out or mutate the canvas destructively.",
        prompt="hi",
        check=_check_short_input,
        expect_flow_update=None,
        token_ceiling=60_000,
        duration_ceiling=300,
    ),
)


def get_scenario(name: str) -> Scenario:
    for scenario in SCENARIOS:
        if scenario.name == name:
            return scenario
    known = ", ".join(s.name for s in SCENARIOS)
    msg = f"Unknown scenario {name!r}. Known: {known}"
    raise KeyError(msg)
