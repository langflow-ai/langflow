"""Stored PermissionGate flows use scoped source resolution and the durable Agent path."""

import json
from copy import deepcopy
from uuid import UUID, uuid4

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from langflow.services.deps import get_job_service
from lfx.graph.graph.base import Graph
from lfx.projects.baselines import permission_baseline
from lfx.projects.bindings import flow_revision
from lfx.projects.permissions import PermissionBinding, permission_outputs
from lfx.schema.message import MessageResponse

from tests.unit.api.v1.test_project_config_write_through import (
    agent_flow_data,
    create_flow,
    create_project,
    stored_flow,
)


class StoredPermissionModel(BaseChatModel):
    @property
    def _llm_type(self):
        return "stored-permission-test"

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
        answer = (
            AIMessage(content="Done")
            if any(isinstance(message, ToolMessage) for message in messages)
            else AIMessage(content="", tool_calls=[{"name": "record", "args": {"value": "evidence"}, "id": "call-1"}])
        )
        return ChatResult(generations=[ChatGeneration(message=answer)])


@pytest.mark.parametrize(("policy", "expected"), [("tool_defaults", ["evidence"]), ("deny", []), ("ask", ["evidence"])])
async def test_permission_binding_executes_from_stored_graph(client, logged_in_headers, active_user, policy, expected):
    project = await create_project(client, logged_in_headers, name="Permission harness")
    source_data = permission_baseline({"tool_policy": policy})["data"]
    source = await create_flow(active_user, folder_id=project, data=source_data, name="Permissions")
    selected = permission_outputs(source_data)[0]
    binding = PermissionBinding(
        flow_id=source,
        revision=flow_revision(source_data),
        node_id=selected["node_id"],
        output_name=selected["output_name"],
    )
    data = agent_flow_data()
    data["nodes"][0]["data"]["node"]["template"]["permission_binding"]["value"] = binding.model_dump_json()
    agent = await create_flow(active_user, folder_id=project, data=data, name="Agent")
    job_id = uuid4()
    jobs = get_job_service()
    await jobs.create_job(job_id=job_id, flow_id=UUID(agent), user_id=active_user.id)
    effects = []

    @tool
    def record(value: str) -> str:
        """Record the permitted value."""
        effects.append(value)
        return value

    async def build():
        graph = Graph.from_payload(
            deepcopy((await stored_flow(agent)).data), flow_id=agent, user_id=str(active_user.id)
        )
        graph.set_run_id(job_id)
        graph.session_id = f"permission-test-{agent}"
        vertex = graph.get_vertex("Agent-1")
        assert json.loads(vertex.params["permission_binding"])["flow_id"] == source
        vertex.update_raw_params(
            {
                "model": StoredPermissionModel(),
                "tools": [record],
                "input_value": "Record evidence",
                "n_messages": 0,
                "add_current_date_tool": False,
                "add_calculator_tool": False,
            },
            overwrite=True,
        )
        return graph, vertex

    graph, vertex = await build()
    results = [result async for result in graph.async_start()]
    assert all(getattr(result, "valid", True) for result in results)
    if policy == "ask":
        assert effects == []
        assert graph.pause_requested
        request = graph.pause_info["data"]
        assert request["action_requests"][0]["tool_call_id"] == "call-1"
        assert await jobs.load_checkpoint(job_id, "agent")
        # Rebuild the stored graph and Agent with a new saver; only DB checkpoint
        # data carries the pending task and completed permission decision forward.
        graph, vertex = await build()
        graph.human_input_decisions = {request["request_id"]: {"action_id": "approve"}}
        results = [result async for result in graph.async_start()]
        assert all(getattr(result, "valid", True) for result in results)
        assert not graph.pause_requested
    assert effects == expected
    public = MessageResponse.from_message(vertex.custom_component.get_output("response").value).model_dump()
    assert "permission_decision" in str(public)
    assert binding.revision in str(public)
    assert source in str(public)
    assert await jobs.load_checkpoint(job_id, "agent")
    assert (await stored_flow(source)).data == source_data
