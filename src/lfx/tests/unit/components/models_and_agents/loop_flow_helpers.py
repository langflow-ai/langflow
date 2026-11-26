"""A reviewed loop flow on disk: Agent Context -> While Loop <-> Agent Step and Execute Tool -> Chat Output."""

import json
from uuid import uuid4

from lfx.components.flow_controls.while_loop import WhileLoopComponent
from lfx.components.input_output import ChatOutput
from lfx.components.models_and_agents import AgentContextComponent, AgentStepComponent, ExecuteToolComponent
from lfx.custom.custom_component.component import Component
from lfx.custom.utils import build_custom_component_template
from lfx.graph import Graph
from lfx.graph.flow_builder import add_component, add_connection
from lfx.projects.bindings import FlowBinding, flow_revision

PROBE_SOURCE = """
from pathlib import Path

from lfx.custom.custom_component.component import Component
from lfx.io import HandleInput, Output
from lfx.schema.dataframe import DataFrame


class PersistProbe(Component):
    display_name = "Persist Probe"
    inputs = [HandleInput(name="rows", display_name="Rows", input_types=["DataFrame"])]
    outputs = [Output(display_name="Out", name="out", method="run")]

    def run(self) -> DataFrame:
        # Records what the runner set on this child graph, in a file a test can read from outside it.
        with Path(self.ctx["project_dir"], "persist_probe.txt").open("a") as probe:
            probe.write(f"{self.graph.persist_messages}\\n")
        return self.rows
"""


def loop_flow(tmp_path, *, max_iterations=5, probe=False) -> tuple[FlowBinding, dict]:
    """Write the loop flow next to `tmp_path` and return its reviewed binding.

    `probe` adds a custom component that records the child graph's persist flag, which a regular user may only run
    when custom components are not admin-only.
    """
    context = AgentContextComponent(_id="AgentContext-ac001")
    loop = WhileLoopComponent(_id="WhileLoop-wl001")
    loop.set(input_value=context.build_messages, max_iterations=max_iterations)
    step = AgentStepComponent(_id="AgentStep-as001")
    step.set(messages=loop.loop_output)
    execute = ExecuteToolComponent(_id="ExecuteTool-et001")
    execute.set(messages=step.get_tool_calls)
    loop.set(loop=execute.execute_tools)
    chat_output = ChatOutput(_id="ChatOutput-co001")
    chat_output.set(input_value=loop.last_message_output)
    flow = {"id": str(uuid4()), "name": "Loop", **Graph(context, chat_output).dump()}
    if probe:
        node, _ = build_custom_component_template(Component(_code=PROBE_SOURCE))
        added = add_component(flow, "PersistProbe", {"PersistProbe": node})
        add_connection(flow, "AgentContext-ac001", "messages", added["id"], "rows")
    (tmp_path / f"{flow['id']}.json").write_text(json.dumps(flow))
    binding = FlowBinding(
        flow_id=flow["id"],
        node_id="WhileLoop-wl001",
        output_name="last_message",
        revision=flow_revision(flow["data"]),
        version_id="reviewed-version",
    )
    return binding, flow
