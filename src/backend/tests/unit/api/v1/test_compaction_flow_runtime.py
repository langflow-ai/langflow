"""Persisted compaction uses real scoped flow resolution, memory, and published evidence."""

import json
from copy import deepcopy
from uuid import UUID

from lfx.graph.graph.base import Graph
from lfx.memory import aget_messages, astore_message
from lfx.projects.baselines import compaction_baseline
from lfx.projects.bindings import flow_revision
from lfx.projects.compaction import CompactionBinding, compaction_outputs
from lfx.schema.message import Message, MessageResponse

from tests.unit.api.v1.test_project_config_write_through import (
    agent_flow_data,
    create_flow,
    create_project,
    stored_flow,
)
from tests.unit.api.v1.test_project_instruction_bindings import RecordingModel


async def test_compaction_binding_executes_from_stored_graph_without_rewriting_memory(
    client, logged_in_headers, active_user
):
    project = await create_project(client, logged_in_headers, name="Compaction harness")
    source_data = compaction_baseline({"compaction_keep_messages": 1})["data"]
    source = await create_flow(active_user, folder_id=project, data=source_data, name="Compaction")
    selected = compaction_outputs(source_data)[0]
    binding = CompactionBinding(
        flow_id=source,
        revision=flow_revision(source_data),
        node_id=selected["node_id"],
        output_name=selected["output_name"],
        trigger_tokens=80,
    )
    data = agent_flow_data()
    data["nodes"][0]["data"]["node"]["template"]["compaction_binding"]["value"] = binding.model_dump_json()
    agent = await create_flow(active_user, folder_id=project, data=data, name="Agent")
    session_id = f"compaction-test-{agent}"
    for sender, text in [("User", "Old question " * 90), ("Machine", "Old answer " * 90)]:
        await astore_message(
            Message(text=text, sender=sender, sender_name=sender, session_id=session_id),
            flow_id=agent,
            user_id=str(active_user.id),
        )
    graph = Graph.from_payload(deepcopy((await stored_flow(agent)).data), flow_id=agent, user_id=str(active_user.id))
    graph.session_id = session_id
    vertex = graph.get_vertex("Agent-1")
    assert json.loads(vertex.params["compaction_binding"])["flow_id"] == source
    model = RecordingModel()
    vertex.update_raw_params(
        {
            "model": model,
            "input_value": "Latest question",
            "n_messages": 10,
            "add_current_date_tool": False,
            "add_calculator_tool": False,
        },
        overwrite=True,
    )
    results = [result async for result in graph.async_start()]
    assert all(getattr(result, "valid", True) for result in results)
    assert len(model.seen) == 2
    assert model.seen[-1][-1].content == "Latest question"
    public = MessageResponse.from_message(vertex.custom_component.get_output("response").value).model_dump()
    assert "compacted" in str(public)
    assert binding.revision in str(public)
    assert (await stored_flow(source)).data == source_data
    saved = await aget_messages(session_id=session_id, flow_id=UUID(agent), user_id=active_user.id)
    assert any(message.text == "Old question " * 90 for message in saved)
    assert any(message.text == "Old answer " * 90 for message in saved)
