"""Instruction-only skills execute without Langflow project storage."""

from uuid import uuid4

from fastapi.testclient import TestClient
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from lfx.cli.serve_app import FlowMeta, FlowRegistry, create_multi_serve_app
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.components.models_and_agents.agent import AgentComponent
from lfx.graph import Graph
from lfx.projects.skills import HarnessSkills, skill_pack_manifest
from pydantic import Field


class StandaloneSkillModel(BaseChatModel):
    key: str
    seen: list = Field(default_factory=list)

    @property
    def _llm_type(self):
        return "standalone-skill-test"

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
        self.seen.append(messages)
        if any(isinstance(message, ToolMessage) for message in messages):
            message = AIMessage(content="Standalone skill complete")
        else:
            message = AIMessage(
                content="", tool_calls=[{"name": "activate_skill", "args": {"skill": self.key}, "id": "activate"}]
            )
        return ChatResult(generations=[ChatGeneration(message=message)])


def test_standalone_workflows_can_activate_embedded_instruction_skill(monkeypatch):
    manifest = skill_pack_manifest(
        uuid4(),
        "Writing",
        {"skills": [{"name": "write", "description": "Write clearly", "instructions": "Be precise."}]},
    )
    model = StandaloneSkillModel(key=f"{manifest.reference.project_id}:write")
    monkeypatch.setattr("lfx.base.models.unified_models.get_llm", lambda **_kwargs: model)
    monkeypatch.setattr("lfx.components.models_and_agents.agent.get_llm", lambda **_kwargs: model)
    api_key = "skill-test-key"  # pragma: allowlist secret
    monkeypatch.setenv("LANGFLOW_API_KEY", api_key)
    source = ChatInput(_id="ChatInput-source")
    agent = AgentComponent(_id="Agent-skills")
    agent.set(
        input_value=source.message_response,
        model=[{"name": "gpt-4o-mini", "provider": "OpenAI", "metadata": {}}],
        add_current_date_tool=False,
        skill_bindings=HarnessSkills(packs=(manifest,)).model_dump_json(),
    )
    target = ChatOutput(_id="ChatOutput-target")
    target.set(input_value=agent.message_response)
    graph = Graph(source, target)
    graph.prepare()
    flow_id = str(uuid4())
    registry = FlowRegistry()
    registry.add(graph, FlowMeta(id=flow_id, relative_path=f"{flow_id}.json", title="Skills", description=None))
    with TestClient(create_multi_serve_app(registry=registry)) as client:
        response = client.post(
            "/api/v2/workflows",
            headers={"x-api-key": api_key},
            json={"flow_id": flow_id, "mode": "sync", "input_value": "Write a report"},
        )
    assert response.status_code == 200, response.text
    assert response.json()["output"]["text"] == "Standalone skill complete"
    assert "Be precise." not in str(model.seen[0])
    assert "Be precise." in str(model.seen[-1])
