"""find_agents_missing_model — static detection of Agents with no model.

"Agent has no model selected" only raises at RUN time
(agent.py get_agent_requirements), which is exactly what we must NOT pay
to discover. It is trivially detectable from the flow JSON: an Agent
node whose `model` field is empty and which has no legacy
agent_llm/model_name. This is the pure unit at the heart of the
auto-assign / honest-caveat decision.
"""

from __future__ import annotations

from langflow.agentic.services.flow_agent_model import find_agents_missing_model


def _flow(nodes):
    return {"name": "f", "data": {"nodes": nodes, "edges": []}}


def _agent(node_id, template):
    return {"id": node_id, "data": {"type": "Agent", "node": {"template": template}}}


class TestFindAgentsMissingModel:
    def test_should_flag_agent_with_empty_model_field(self):
        flow = _flow([_agent("Agent-1", {"model": {"value": ""}})])
        assert find_agents_missing_model(flow) == ["Agent-1"]

    def test_should_flag_agent_with_no_model_field_at_all(self):
        flow = _flow([_agent("Agent-1", {})])
        assert find_agents_missing_model(flow) == ["Agent-1"]

    def test_should_not_flag_agent_with_a_configured_model(self):
        flow = _flow([_agent("Agent-1", {"model": {"value": [{"name": "gpt-4o"}]}})])
        assert find_agents_missing_model(flow) == []

    def test_should_not_flag_agent_using_legacy_agent_llm_and_model_name(self):
        # Older serialized Agents resolve via agent_llm + model_name.
        flow = _flow(
            [
                _agent(
                    "Agent-1",
                    {"agent_llm": {"value": "OpenAI"}, "model_name": {"value": "gpt-4o"}},
                )
            ]
        )
        assert find_agents_missing_model(flow) == []

    def test_should_flag_agent_with_legacy_provider_but_no_model_name(self):
        flow = _flow([_agent("Agent-1", {"agent_llm": {"value": "OpenAI"}, "model_name": {"value": ""}})])
        assert find_agents_missing_model(flow) == ["Agent-1"]

    def test_should_ignore_non_agent_nodes_even_if_they_have_a_model_field(self):
        node = {"id": "X-1", "data": {"type": "ChatInput", "node": {"template": {"model": {"value": ""}}}}}
        assert find_agents_missing_model(_flow([node])) == []

    def test_should_flag_only_the_agents_that_lack_a_model_when_several_exist(self):
        flow = _flow(
            [
                _agent("Agent-good", {"model": {"value": [{"name": "claude"}]}}),
                _agent("Agent-bad", {"model": {"value": ""}}),
            ]
        )
        assert find_agents_missing_model(flow) == ["Agent-bad"]

    def test_should_be_resilient_to_malformed_nodes_and_empty_flow(self):
        assert find_agents_missing_model({}) == []
        assert find_agents_missing_model({"data": {}}) == []
        # A malformed Agent node (no node/template) cannot prove it has a
        # model, so it IS flagged (so the resolver/caveat handles it)
        # rather than crashing.
        flow = _flow([{"id": "x"}, {"id": "Agent-broken", "data": {"type": "Agent"}}])
        assert find_agents_missing_model(flow) == ["Agent-broken"]
