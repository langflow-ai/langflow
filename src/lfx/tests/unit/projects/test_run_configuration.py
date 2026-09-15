import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from lfx.base.agents.harness import HarnessRuntimeConfig
from lfx.components.models_and_agents.agent import AgentComponent
from lfx.components.models_and_agents.agent_helpers.source_evidence import SourceEvidenceMiddleware
from lfx.projects.bindings import BINDING_ORIGIN, flow_revision
from lfx.projects.run_configuration import CONFIGURATIONS_STATE_KEY, AgentConfiguration, capture_agent_configuration
from pydantic import Field, SecretStr


class ConfiguredModel(BaseChatModel):
    parameters: dict = Field(default_factory=dict)

    @property
    def _llm_type(self):
        return "offline-configuration-test"

    @property
    def _identifying_params(self):
        return self.parameters

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="Recorded."))])


def configured_agent(model):
    component = AgentComponent()
    component.set(model=model, tools=[], system_prompt="Use the reviewed instructions.", n_messages=4)
    return component


def test_configuration_copies_resolved_model_parameters_without_credentials_or_clients():
    model = ConfiguredModel(
        parameters={
            "temperature": 0.4,
            "max_tokens": 1234,
            "api_key": SecretStr("fixture-value"),
            "kwargs": {"Authorization": "fixture-value", "stop": ["END"]},
            "endpoint": "https://example.test/v1?token=fixture-value",
            "client": SimpleNamespace(credential="fixture-value"),
        }
    )
    component = configured_agent(model)
    record = capture_agent_configuration(component, model, HarnessRuntimeConfig())
    assert "fixture-value" not in record.model_dump_json()
    assert record.model.parameters["max_tokens"] == 1234
    assert record.model.parameters["endpoint"] == "https://example.test/v1"
    assert record.model.parameters["client"] == "[unavailable: SimpleNamespace]"
    model.parameters["kwargs"]["stop"].append("CHANGED")
    component.set(system_prompt="New project instructions.")
    assert record.system_prompt == "Use the reviewed instructions."
    assert record.model.parameters["kwargs"]["stop"] == ["END"]
    assert AgentConfiguration.model_validate_json(record.model_dump_json()) == record


def test_configuration_digest_ignores_capture_time_and_rejects_modified_record():
    model = ConfiguredModel()
    component = configured_agent(model)
    first = capture_agent_configuration(component, model, HarnessRuntimeConfig())
    second = capture_agent_configuration(component, model, HarnessRuntimeConfig())
    assert first.revision == second.revision
    corrupted = first.model_dump(mode="json")
    corrupted["runtime"]["max_iterations"] += 1
    with pytest.raises(ValueError, match="does not match"):
        AgentConfiguration.model_validate(corrupted)


@pytest.mark.parametrize("connected", [True, False])
def test_configuration_identifies_only_its_agents_instruction_connection_and_runtime_bindings(connected):
    model = ConfiguredModel()
    component = configured_agent(model)
    binding = {
        "flow_id": "reviewed-flow",
        "node_id": "Output-node",
        "output_name": "result",
        "revision": "reviewed-revision",
        "version_id": "required-version",
    }
    component.set(context_binding=json.dumps(binding))
    data = {
        "nodes": [{"id": "Instructions-adapter", "data": {BINDING_ORIGIN: {"project_id": "p", **binding}}}],
        "edges": [
            {
                "source": "Instructions-adapter",
                "target": component._id if connected else "Another-agent",
                "data": {"targetHandle": {"fieldName": "system_prompt"}},
            }
        ],
    }
    component._vertex = SimpleNamespace(
        graph=SimpleNamespace(flow_id="harness-flow", raw_graph_data=data),
        data={"node": {"template": {"code": {"value": "reviewed agent code"}}}},
    )
    record = capture_agent_configuration(component, model, HarnessRuntimeConfig())
    assert record.flow_id == "harness-flow"
    assert record.flow_revision == flow_revision(data)
    assert record.component_revision
    assert record.flow_bindings.context_strategy.version_id == "required-version"
    if connected:
        assert record.flow_bindings.system_prompt.model_dump() == binding
    else:
        assert record.flow_bindings.system_prompt is None
    data["nodes"][0]["data"][BINDING_ORIGIN]["revision"] = "changed-after-capture"
    if connected:
        assert record.flow_bindings.system_prompt.revision == "reviewed-revision"


def test_checkpoint_collection_keeps_initial_and_changed_configurations_without_duplicate_entries():
    model = ConfiguredModel(parameters={"temperature": 0.4})
    component = configured_agent(model)
    initial = capture_agent_configuration(component, model, HarnessRuntimeConfig())
    state = {"messages": [HumanMessage(content="Go.")]}
    middleware = SourceEvidenceMiddleware(configuration=initial)
    state.update(middleware.before_model(state, None))
    assert middleware.before_model(state, None) is None
    checkpoint = deepcopy(state)
    model.parameters["temperature"] = 0.7
    updated = capture_agent_configuration(component, model, HarnessRuntimeConfig())
    resumed = SourceEvidenceMiddleware(configuration=updated)
    checkpoint.update(resumed.after_agent(checkpoint, None))
    records = [AgentConfiguration.model_validate(item) for item in checkpoint[CONFIGURATIONS_STATE_KEY]]
    assert [record.model.parameters["temperature"] for record in records] == [0.4, 0.7]
    assert resumed.after_agent(checkpoint, None) is None


async def test_agent_without_tools_retains_configuration_in_its_completed_result():
    from tests.unit.components.models_and_agents.agent_helpers.test_source_evidence import emitted_result

    model = ConfiguredModel(parameters={"temperature": 0.2})
    component = configured_agent(model)
    message = await emitted_result(component.create_agent_runnable())
    record = AgentConfiguration.model_validate(message.properties.agent_run_result["configurations"][0])
    assert record.model.parameters == {"temperature": 0.2}
    assert record.tools == ()
    assert record.history_messages == 4
    assert record.system_prompt == "Use the reviewed instructions."
