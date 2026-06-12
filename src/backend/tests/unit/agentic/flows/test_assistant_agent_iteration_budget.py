"""The assistant Agent must have enough iterations for multi-component builds.

Reproduced live (2026-06-12, gpt-oss:20b): "crie um flow com 5 componentes
aleatorios" needs ~16+ legitimate iterations (search + describe + 5x add +
4x connect + run); max_iterations=15 (recursion_limit 35) killed a healthy,
progressing run.
"""

import json
from pathlib import Path

from langflow.agentic.flows.flow_builder_assistant import AGENT_MAX_ITERATIONS

FLOW_PATH = Path(__file__).parents[4] / "base" / "langflow" / "agentic" / "flows" / "LangflowAssistant.json"
PY_FLOW_PATH = Path(__file__).parents[4] / "base" / "langflow" / "agentic" / "flows" / "flow_builder_assistant.py"

MIN_AGENT_ITERATIONS = 30


def test_should_give_the_flow_builder_agent_enough_iterations():
    """Build-intent requests run flow_builder_assistant.py, not the JSON flow."""
    assert AGENT_MAX_ITERATIONS >= MIN_AGENT_ITERATIONS

    source = PY_FLOW_PATH.read_text(encoding="utf-8")
    assert '"max_iterations": AGENT_MAX_ITERATIONS' in source, (
        "get_graph's agent_config must wire AGENT_MAX_ITERATIONS, or the component default (15) wins"
    )


def test_should_give_assistant_agents_enough_iterations_for_multi_component_builds():
    data = json.loads(FLOW_PATH.read_text(encoding="utf-8"))
    agents = [n["data"] for n in data["data"]["nodes"] if n.get("data", {}).get("type") == "Agent"]

    assert agents, "LangflowAssistant.json must contain Agent nodes"
    for agent in agents:
        configured = agent["node"]["template"]["max_iterations"]["value"]
        assert configured >= MIN_AGENT_ITERATIONS, (
            f"Agent {agent.get('id')} has max_iterations={configured}; "
            f"a 5-component build legitimately needs ~16+ iterations plus retries"
        )
