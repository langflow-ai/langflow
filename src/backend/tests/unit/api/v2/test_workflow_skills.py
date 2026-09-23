"""Saved and imported harnesses run through the public Workflows API.

Only the provider model is replaced: routing, authorization, graphs, Run Flow
tools, runtime middleware, event serialization and checkpoints remain real.
"""

import asyncio
import json
from copy import deepcopy
from uuid import UUID

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import session_scope
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph.flow_builder import add_component, add_connection
from pydantic import Field

from tests.unit.api.v1.test_harness_skill_packs import skill_harness, skills_of  # noqa: F401
from tests.unit.api.v1.test_project_config_write_through import save_config, stored_flow


class WorkflowSkillModel(BaseChatModel):
    """A deterministic provider whose sequence survives graph reconstruction."""

    skill_key: str
    tool_name: str = ""
    tool_args: dict = Field(default_factory=dict)
    seen: list = Field(default_factory=list)
    probe_scope: bool = True

    @property
    def _llm_type(self):
        return "workflow-skill-test"

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        for tool in tools:
            if (tool.metadata or {}).get("harness_tool_pack"):
                self.tool_name = tool.name
                self.tool_args = {"flow_tweak_data": {"ChatInput-echo~input_value": "SOURCE RESULT"}}
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
        self.seen.append(deepcopy(messages))
        step = len([m for m in messages if isinstance(m, ToolMessage)])
        sequence = [("activate_skill", {"skill": self.skill_key}), (self.tool_name, self.tool_args)]
        if self.probe_scope:
            sequence = [
                (self.tool_name, self.tool_args),
                *sequence,
                ("finish_skill", {}),
                (self.tool_name, self.tool_args),
            ]
        if step < len(sequence):
            name, args = sequence[step]
            message = AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"call-{step}"}])
        else:
            results = [m.content for m in messages if isinstance(m, ToolMessage) and m.name == self.tool_name]
            message = AIMessage(content="Research complete: " + json.dumps(results))
        return ChatResult(generations=[ChatGeneration(message=message)])


@pytest.fixture
async def workflow_harness(skill_harness):  # noqa: F811
    project, agent, pack, tools, config, definition = skill_harness
    async with session_scope() as session:
        flow = await session.get(Flow, UUID(agent))
        data = deepcopy(flow.data)
        registry = {}
        for component in (ChatInput, ChatOutput):
            frontend = component().to_frontend_node()
            node = frontend.get("data", frontend)["node"]
            node["field_order"] = [item.name for item in component.inputs]
            registry[component.name] = node
        payload = {"data": data}
        source = add_component(payload, "ChatInput", registry, component_id="ChatInput-request")
        target = add_component(payload, "ChatOutput", registry, component_id="ChatOutput-answer")
        add_connection(payload, source["id"], "message", "Agent-1", "input_value")
        add_connection(payload, "Agent-1", "response", target["id"], "input_value")
        template = next(n for n in data["nodes"] if n["id"] == "Agent-1")["data"]["node"]["template"]
        template["model"]["value"] = [{"name": "gpt-4o-mini", "provider": "OpenAI", "metadata": {}}]
        template["add_current_date_tool"]["value"] = False
        template["max_iterations"]["value"] = 10
        flow.data = data
        session.add(flow)
        await session.commit()
    return project, agent, pack, tools, config, definition


def provider(monkeypatch, flow, *, probe_scope=True):
    pack = skills_of(flow).packs[0]
    model = WorkflowSkillModel(skill_key=f"{pack.reference.project_id}:{pack.skills[0].name}", probe_scope=probe_scope)
    monkeypatch.setattr("lfx.base.models.unified_models.get_llm", lambda **_kwargs: model)
    monkeypatch.setattr("lfx.components.models_and_agents.agent.get_llm", lambda **_kwargs: model)
    return model


@pytest.mark.parametrize(
    ("mode", "protocol", "expose_graph_state"),
    [("sync", "langflow", None), ("stream", "langflow", None), ("stream", "agui", None), ("stream", "agui", True)],
)
async def test_workflows_execute_imported_skill_composition(
    client, logged_in_headers, created_api_key, workflow_harness, monkeypatch, mode, protocol, expose_graph_state
):
    project, _, _, _, _, _ = workflow_harness
    archive = await client.get(f"/api/v1/projects/download/{project}", headers=logged_in_headers)
    assert archive.status_code == 200, archive.text
    uploaded = await client.post(
        "/api/v1/projects/upload/",
        headers=logged_in_headers,
        files={"file": ("skills.zip", archive.content, "application/zip")},
    )
    assert uploaded.status_code == 201, uploaded.text
    flow = await stored_flow(uploaded.json()[0]["id"])
    model = provider(monkeypatch, flow)
    response = await client.post(
        "/api/v2/workflows",
        headers={"x-api-key": created_api_key.api_key},
        json={
            "flow_id": str(flow.id),
            "input_value": "Research this question",
            "mode": mode,
            "stream_protocol": protocol,
            "expose_graph_state": expose_graph_state,
        },
    )
    assert response.status_code == 200, response.text
    assert "Research complete" in response.text, response.text
    final = model.seen[-1]
    results = [m for m in final if isinstance(m, ToolMessage) and m.name == model.tool_name]
    assert [m.status for m in results] == ["error", "success", "error"], results
    assert "SOURCE RESULT" in results[1].content
    assert "Use original sources." not in str(model.seen[0])
    assert "Use original sources." in str(model.seen[2])
    assert "Use original sources." not in str(model.seen[-1])
    if mode == "sync":
        assert "Research complete" in response.json()["output"]["text"]
    else:
        # AG-UI now hides graph diagnostics by default; the canvas opts in.
        assert ("Skill activated" in response.text) is (protocol != "agui" or expose_graph_state is True)
        if protocol == "agui":
            assert "RUN_FINISHED" in response.text


async def wait_status(client, headers, job_id, expected):
    async with asyncio.timeout(30):
        while True:
            response = await client.get("/api/v2/workflows", params={"job_id": job_id}, headers=headers)
            assert response.status_code == 200, response.text
            data = response.json()
            if data["status"] in expected:
                return data
            assert data["status"] not in {"failed", "cancelled", "timed_out"}, data
            await asyncio.sleep(0.1)


@pytest.mark.parametrize("decision", ["approve", "reject"])
async def test_workflows_skill_approval_resume(
    client, logged_in_headers, created_api_key, workflow_harness, monkeypatch, decision
):
    project, agent, _, _, config, _ = workflow_harness
    await save_config(client, logged_in_headers, project, {**config, "tool_policy": "ask"})
    model = provider(monkeypatch, await stored_flow(agent), probe_scope=False)
    headers = {"x-api-key": created_api_key.api_key}
    response = await client.post(
        "/api/v2/workflows",
        headers=headers,
        json={"flow_id": agent, "input_value": "Research", "mode": "background"},
    )
    assert response.status_code == 200, response.text
    job_id = response.json()["job_id"]
    await wait_status(client, headers, job_id, {"suspended"})
    pending = await client.get("/api/v2/workflows/pending", params={"flow_id": agent}, headers=headers)
    assert pending.status_code == 200, pending.text
    request_id = pending.json()[0]["request_id"]
    resumed = await client.post(
        f"/api/v2/workflows/{job_id}/resume",
        headers=headers,
        json={"request_id": request_id, "decision": {"action_id": decision}},
    )
    assert resumed.status_code == 200, resumed.text
    await wait_status(client, headers, job_id, {"completed"})
    final = model.seen[-1]
    assert "Use original sources." in str(final)
    results = [m for m in final if isinstance(m, ToolMessage) and m.name == model.tool_name]
    assert len(results) == 1
    assert ("SOURCE RESULT" in results[0].content) == (decision == "approve")
    duplicate = await client.post(
        f"/api/v2/workflows/{job_id}/resume",
        headers=headers,
        json={"request_id": request_id, "decision": {"action_id": decision}},
    )
    assert duplicate.status_code == 409


async def test_workflows_recheck_skill_tool_access_before_execution(
    client, created_api_key, workflow_harness, monkeypatch
):
    from fastapi import HTTPException

    _, agent, _, _, _, _ = workflow_harness
    model = provider(monkeypatch, await stored_flow(agent))

    async def deny_execute(_user, action, **_scope):
        if action.value == "execute":
            raise HTTPException(403)

    monkeypatch.setattr("langflow.services.database.models.folder.tool_packs.ensure_flow_permission", deny_execute)
    response = await client.post(
        "/api/v2/workflows",
        headers={"x-api-key": created_api_key.api_key},
        json={"flow_id": agent, "input_value": "Research", "mode": "sync"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["has_errors"] is True
    assert model.seen == []
    assert "Research complete" not in response.text
