"""ensure_agent_models — auto-assign a model, else report NO_PROVIDER.

When the built flow has an Agent with no model, the assistant must NOT
run the LLM to discover it. If the request itself has a usable
provider/model (it always does — that is the model the agent ran with),
inject it into the Agent node(s). If there is genuinely none, report it
so the caller can deliver an honest caveat — never loop on this.
"""

from __future__ import annotations

from langflow.agentic.services.flow_agent_model import (
    AgentModelOutcome,
    ensure_agent_models,
    find_agents_missing_model,
)


def _flow_with_modelless_agent():
    return {
        "name": "f",
        "data": {
            "nodes": [
                {
                    "id": "Agent-1",
                    "data": {
                        "type": "Agent",
                        "node": {"template": {"model": {"value": ""}}},
                    },
                }
            ],
            "edges": [],
        },
    }


class TestEnsureAgentModels:
    def test_should_return_none_needed_when_no_agent_is_missing_a_model(self):
        flow = {
            "name": "f",
            "data": {
                "nodes": [
                    {
                        "id": "Agent-1",
                        "data": {"type": "Agent", "node": {"template": {"model": {"value": [{"name": "gpt-4o"}]}}}},
                    }
                ],
                "edges": [],
            },
        }
        outcome = ensure_agent_models(flow=flow, provider="OpenAI", model_name="gpt-4o", api_key_var="OPENAI_API_KEY")
        assert outcome is AgentModelOutcome.NONE_NEEDED

    def test_should_inject_the_request_model_when_an_agent_lacks_one(self):
        flow = _flow_with_modelless_agent()

        outcome = ensure_agent_models(flow=flow, provider="OpenAI", model_name="gpt-4o", api_key_var="OPENAI_API_KEY")

        assert outcome is AgentModelOutcome.ASSIGNED
        # The Agent now resolves a model (no longer flagged).
        assert find_agents_missing_model(flow) == []

    def test_should_report_no_provider_when_request_has_no_usable_model(self):
        flow = _flow_with_modelless_agent()

        outcome = ensure_agent_models(flow=flow, provider=None, model_name=None, api_key_var=None)

        assert outcome is AgentModelOutcome.NO_PROVIDER
        # Flow is left untouched — the caller delivers an honest caveat.
        assert find_agents_missing_model(flow) == ["Agent-1"]

    def test_should_not_loop_or_raise_when_provider_is_unknown(self):
        # An unknown provider must degrade to NO_PROVIDER, never explode
        # the build (inject_model_into_flow raises ValueError on unknown).
        flow = _flow_with_modelless_agent()

        outcome = ensure_agent_models(flow=flow, provider="Nonexistent", model_name="x", api_key_var=None)

        assert outcome is AgentModelOutcome.NO_PROVIDER
        assert find_agents_missing_model(flow) == ["Agent-1"]
