"""Pin the assistant agent iteration budget — a COST decision, not a tuning knob.

Decision (2026-06-12, user): the LangGraph budget stays at the component
default (max_iterations=15 -> recursion limit 35). Raising it doubles the
worst-case token spend per attempt on hosted models when the agent churns.
The trade-off: open-ended multi-component builds (e.g. "5 random
components", ~16+ legitimate iterations) hit the limit by design; the
recursion-limit error tells the user to break the request into parts.
"""

import json
from pathlib import Path

FLOW_PATH = Path(__file__).parents[4] / "base" / "langflow" / "agentic" / "flows" / "LangflowAssistant.json"
PY_FLOW_PATH = Path(__file__).parents[4] / "base" / "langflow" / "agentic" / "flows" / "flow_builder_assistant.py"

COMPONENT_DEFAULT_ITERATIONS = 15


def test_should_keep_json_agents_at_the_component_default_budget():
    data = json.loads(FLOW_PATH.read_text(encoding="utf-8"))
    agents = [n["data"] for n in data["data"]["nodes"] if n.get("data", {}).get("type") == "Agent"]

    assert agents, "LangflowAssistant.json must contain Agent nodes"
    for agent in agents:
        configured = agent["node"]["template"]["max_iterations"]["value"]
        assert configured == COMPONENT_DEFAULT_ITERATIONS, (
            f"Agent {agent.get('id')} has max_iterations={configured}; raising it doubles "
            "the worst-case hosted-model cost per attempt — deliberate decision, see docstring"
        )


def test_should_not_override_iterations_in_the_flow_builder_agent():
    source = PY_FLOW_PATH.read_text(encoding="utf-8")

    assert "max_iterations" not in source, (
        "flow_builder_assistant.py must not override max_iterations — cost ceiling decision 2026-06-12"
    )
