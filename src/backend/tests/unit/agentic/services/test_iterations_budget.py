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
    MAX_ASSISTANT_ITERATIONS,
    inject_iterations_into_flow,
)

_ASSISTANT_FLOW = Path(__file__).parents[4] / "base" / "langflow" / "agentic" / "flows" / "LangflowAssistant.json"


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
