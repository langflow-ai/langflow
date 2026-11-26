"""Flow edges preserve executable values rather than display/transport artifacts."""

import json

import pytest
from lfx.components.flow_controls.run_flow import RunFlowComponent
from lfx.components.input_output.text_output import TextOutputComponent
from lfx.graph.graph.base import Graph
from lfx.schema.message import Message


@pytest.mark.asyncio
async def test_standalone_run_flow_returns_original_text_output(tmp_path):
    source = TextOutputComponent()
    source.set(input_value="Use the original instructions.")
    source_node = source.to_frontend_node()["data"]
    source_node["id"] = "TextOutput-source"
    data = {"nodes": [{"id": source_node["id"], "data": source_node}], "edges": []}
    (tmp_path / "instructions.json").write_text(
        json.dumps({"id": "instructions", "name": "Instructions", "data": data})
    )
    adapter = RunFlowComponent().to_frontend_node()["data"]
    adapter["id"] = "RunFlow-reference"
    graph = Graph.from_payload(
        {"nodes": [{"id": adapter["id"], "data": adapter}], "edges": []},
        instantiate_components=False,
        user_id="standalone-test",
        context={"project_dir": str(tmp_path)},
    )
    component = RunFlowComponent(_vertex=graph.get_vertex(adapter["id"]))
    component.set_attributes({"flow_id_selected": "instructions", "flow_name_selected": "Instructions"})
    value = await component._resolve_flow_output(vertex_id=source_node["id"], output_name="text")
    assert isinstance(value, Message)
    assert value.text == "Use the original instructions."
