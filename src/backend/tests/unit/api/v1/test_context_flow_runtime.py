"""A persisted Agent loads and executes its hidden ContextManager binding."""

import json
from copy import deepcopy

from lfx.graph.graph.base import Graph
from lfx.projects.baselines import context_baseline
from lfx.projects.bindings import flow_revision
from lfx.projects.context import ContextBinding, context_outputs
from lfx.schema.message import MessageResponse

from tests.unit.api.v1.test_project_config_write_through import (
    agent_flow_data,
    create_flow,
    create_project,
    stored_flow,
)
from tests.unit.api.v1.test_project_instruction_bindings import RecordingModel


async def test_context_binding_runs_from_persisted_graph_and_publishes_its_revision(
    client, logged_in_headers, active_user
):
    project = await create_project(client, logged_in_headers, name="Context harness")
    source_data = context_baseline()["data"]
    terminal = source_data["nodes"][-1]["data"]["node"]["template"]
    terminal["code"]["value"] = terminal["code"]["value"].replace(
        "return messages_to_table(prepared)",
        'prepared[-1] = prepared[-1].model_copy(update={"content": "Use the reviewed sources."})\n'
        "        return messages_to_table(prepared)",
    )
    source = await create_flow(active_user, folder_id=project, data=source_data, name="Context")
    selected = context_outputs(source_data)[0]
    binding = ContextBinding(
        flow_id=source,
        revision=flow_revision(source_data),
        node_id=selected["node_id"],
        output_name=selected["output_name"],
    )
    data = agent_flow_data()
    data["nodes"][0]["data"]["node"]["template"]["context_binding"]["value"] = binding.model_dump_json()
    agent = await create_flow(active_user, folder_id=project, data=data, name="Agent")
    graph = Graph.from_payload(deepcopy((await stored_flow(agent)).data), user_id=str(active_user.id))
    graph.session_id = f"context-test-{agent}"
    vertex = graph.get_vertex("Agent-1")
    assert json.loads(vertex.params["context_binding"])["flow_id"] == source
    model = RecordingModel()
    vertex.update_raw_params(
        {
            "model": model,
            "input_value": "Research",
            "n_messages": 0,
            "add_current_date_tool": False,
            "add_calculator_tool": False,
        },
        overwrite=True,
    )
    results = [result async for result in graph.async_start()]
    assert all(getattr(result, "valid", True) for result in results)
    assert model.seen[-1][-1].content == "Use the reviewed sources."
    message = vertex.custom_component.get_output("response").value
    public = MessageResponse.from_message(message).model_dump()
    assert "context_prepared" in str(public)
    assert binding.revision in str(public)
    assert (await stored_flow(source)).data == source_data
