"""Pin the assistant agent iteration budget -- a COST decision, not a tuning knob.

Decision (2026-07-09, user): the assistant agents' LangGraph budget is pinned at
``max_iterations = 30`` (recursion limit = 30*2+5 = 65), raised from the original
component default of 15. Rationale: compound one-turn tasks ("create a component,
build a flow with it, run it, and report") legitimately need more than 15 steps and
were dying with ``Recursion limit of 35 reached``. The trade-off -- a higher worst-case
token spend per attempt on hosted models -- was accepted deliberately, and a per-session
``/iterations N`` command lets a user tune it further (1-200) without editing the flows.

This test is a tripwire: any future change to the pinned budget must be a conscious
decision that also updates ``ASSISTANT_ITERATION_BUDGET`` here (and re-runs the eval
suite for a cost/pass-rate check).
"""

import json
from pathlib import Path

FLOW_PATH = Path(__file__).parents[4] / "base" / "langflow" / "agentic" / "flows" / "LangflowAssistant.json"
PY_FLOW_PATH = Path(__file__).parents[4] / "base" / "langflow" / "agentic" / "flows" / "flow_builder_assistant.py"

ASSISTANT_ITERATION_BUDGET = 30


def test_should_pin_json_agents_at_the_assistant_budget():
    data = json.loads(FLOW_PATH.read_text(encoding="utf-8"))
    agents = [n["data"] for n in data["data"]["nodes"] if n.get("data", {}).get("type") == "Agent"]

    assert agents, "LangflowAssistant.json must contain Agent nodes"
    for agent in agents:
        configured = agent["node"]["template"]["max_iterations"]["value"]
        assert configured == ASSISTANT_ITERATION_BUDGET, (
            f"Agent {agent.get('id')} has max_iterations={configured}, expected "
            f"{ASSISTANT_ITERATION_BUDGET}; changing the pinned budget is a cost decision -- "
            "update ASSISTANT_ITERATION_BUDGET and see the docstring"
        )


def test_should_not_hardcode_iterations_in_the_flow_builder_agent():
    """The budget lives in the flow JSON and the /iterations runtime injection.

    It is never hardcoded in the assistant's Python -- one source of truth.
    """
    source = PY_FLOW_PATH.read_text(encoding="utf-8")

    assert "max_iterations" not in source, (
        "flow_builder_assistant.py must not hardcode max_iterations -- the sanctioned "
        "override is inject_iterations_into_flow (runtime /iterations command)"
    )
