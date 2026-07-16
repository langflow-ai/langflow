"""The assistant's step budget must survive a compound build turn.

QA: "I can't create a flow with 4 components" — the assistant flow pinned the
Agent's ``max_iterations`` at 15, and LangGraph derives its recursion limit from
it (``max_iterations * 2 + 5`` = 35). A build-then-report turn exhausts that and
dies with "Recursion limit of 35 reached without hitting a stop condition".
"""

import json
from pathlib import Path

import pytest
from langflow.agentic.services.flow_preparation import (
    DEFAULT_ASSISTANT_ITERATIONS,
    MAX_ASSISTANT_ITERATIONS,
    inject_iterations_into_flow,
)

_ASSISTANT_FLOW = Path(__file__).parents[4] / "base" / "langflow" / "agentic" / "flows" / "LangflowAssistant.json"


def _builder_agent_max_iterations(graph) -> int | None:
    for vertex in graph.vertices:
        if type(vertex.custom_component).__name__ == "AgentComponent":
            return vertex.custom_component.max_iterations
    return None


def _agent_max_iterations(flow: dict) -> int | None:
    for node in flow["data"]["nodes"]:
        if node["data"].get("type") == "Agent":
            return node["data"]["node"]["template"]["max_iterations"]["value"]
    return None


def _flow_with_agent(max_iterations: int = 15) -> dict:
    return {
        "data": {
            "nodes": [
                {
                    "data": {
                        "type": "Agent",
                        "node": {"template": {"max_iterations": {"value": max_iterations}}},
                    }
                },
                {"data": {"type": "ChatOutput", "node": {"template": {}}}},
            ]
        }
    }


def test_shipped_assistant_flow_has_headroom_for_a_compound_turn():
    """Regression pin for the reported failure: 15 iterations => recursion limit 35."""
    flow = json.loads(_ASSISTANT_FLOW.read_text(encoding="utf-8"))
    pinned = _agent_max_iterations(flow)

    assert pinned is not None, "the assistant flow must pin the Agent's step budget"
    assert pinned >= 30, f"max_iterations={pinned} derives recursion_limit={pinned * 2 + 5}, too low to build a flow"


def test_injects_the_runtime_budget_onto_every_agent():
    flow = inject_iterations_into_flow(_flow_with_agent(), 50)
    assert _agent_max_iterations(flow) == 50


def test_none_leaves_the_flow_default_untouched():
    flow = inject_iterations_into_flow(_flow_with_agent(15), None)
    assert _agent_max_iterations(flow) == 15


@pytest.mark.parametrize(
    ("requested", "expected"),
    [(0, 1), (-5, 1), (10_000, MAX_ASSISTANT_ITERATIONS)],
)
def test_clamps_out_of_range_budgets(requested, expected):
    """A bad input can neither disable the cap nor run away."""
    flow = inject_iterations_into_flow(_flow_with_agent(), requested)
    assert _agent_max_iterations(flow) == expected


def test_ignores_flows_without_an_agent():
    flow = {"data": {"nodes": [{"data": {"type": "ChatInput", "node": {"template": {}}}}]}}
    assert inject_iterations_into_flow(flow, 40) == flow


async def test_builder_graph_honors_the_runtime_budget():
    """QA AC2: the runtime budget must reach the Python builder flow's Agent.

    The build intent runs the PYTHON builder flow, which bypasses the JSON
    injection entirely — the budget only arrives through get_graph.
    """
    from langflow.agentic.flows.flow_builder_assistant import get_graph

    graph = await get_graph(iterations_limit=3)
    assert _builder_agent_max_iterations(graph) == 3


async def test_builder_graph_defaults_to_the_assistant_budget():
    from langflow.agentic.flows.flow_builder_assistant import get_graph

    graph = await get_graph()
    assert _builder_agent_max_iterations(graph) == DEFAULT_ASSISTANT_ITERATIONS


async def test_python_loader_forwards_the_runtime_budget():
    from langflow.agentic.services.helpers.flow_loader import load_graph_for_execution, resolve_flow_path

    flow_path, flow_type = resolve_flow_path("flow_builder_assistant")
    assert flow_type == "python"
    graph = await load_graph_for_execution(flow_path, flow_type, provider_vars={"ITERATIONS_LIMIT": "3"})
    assert _builder_agent_max_iterations(graph) == 3


async def test_python_loader_clamps_runaway_budgets():
    from langflow.agentic.services.helpers.flow_loader import load_graph_for_execution, resolve_flow_path

    flow_path, flow_type = resolve_flow_path("flow_builder_assistant")
    graph = await load_graph_for_execution(flow_path, flow_type, provider_vars={"ITERATIONS_LIMIT": "99999"})
    assert _builder_agent_max_iterations(graph) == MAX_ASSISTANT_ITERATIONS
