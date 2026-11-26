"""Real components and flow payloads for pause tests: Run Flow, an asking Agent, and Loop body steps.

The module is the components' code, so everything they need is defined here.
"""

from __future__ import annotations

import json
from pathlib import Path

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from lfx.base.tools.run_flow import RunFlowBaseComponent
from lfx.components.flow_controls.human_input import HumanInput
from lfx.components.flow_controls.loop import LoopComponent
from lfx.components.flow_controls.run_flow import RunFlowComponent
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.components.models_and_agents.agent import AgentComponent
from lfx.custom import Component
from lfx.graph.graph.base import Graph
from lfx.inputs.inputs import HandleInput, MessageTextInput, StrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message
from lfx.template.field.base import Output

CHILD_ID = "00000000-0000-0000-0000-0000000000c1"
PARENT_ID = "00000000-0000-0000-0000-0000000000a1"


def node(component) -> dict:
    frontend = component.to_frontend_node()
    return {"id": frontend["id"], "data": frontend["data"]}


def edge(source: str, target: str, handle: str, field: str = "input_value", types: tuple = ("Message",)) -> dict:
    return {
        "source": source,
        "target": target,
        "id": f"{source}-{handle}-{target}",
        "data": {
            "sourceHandle": {"dataType": "x", "id": source, "name": handle, "output_types": list(types)},
            "targetHandle": {"fieldName": field, "id": target, "inputTypes": list(types), "type": "str"},
        },
    }


def payload(nodes: list[dict], edges: list[dict]) -> dict:
    return {"nodes": nodes, "edges": edges}


def graph_from(flow: dict) -> Graph:
    graph = Graph.from_payload(flow, flow_id=PARENT_ID)
    graph.prepare()
    return graph


def write_flow(flows_dir: Path, name: str, flow: dict) -> None:
    (flows_dir / f"{name}.json").write_text(json.dumps({"data": flow}))


def hitl_payload(*, approved=None, early: bool = False) -> dict:
    """Chat Input -> Human Input -> one Chat Output per branch, through ``approved`` on the approve branch.

    ``early`` adds a Chat Output fed by the Chat Input, which is built before the pause.
    """
    chat_input = node(ChatInput(_id="c_in", should_store_message=False))
    # Run Flow exposes this field to an Agent that calls the flow as a tool.
    chat_input["data"]["node"]["field_order"] = ["input_value"]
    nodes = [
        chat_input,
        node(HumanInput(_id="hitl")),
        node(ChatOutput(_id="out_approve", should_store_message=False)),
        node(ChatOutput(_id="out_reject", should_store_message=False)),
    ]
    edges = [edge("c_in", "hitl", "message", field="prompt"), edge("hitl", "out_reject", "branch_reject")]
    if approved is None:
        edges.append(edge("hitl", "out_approve", "branch_approve"))
    else:
        nodes.append(node(approved))
        edges += [edge("hitl", approved._id, "branch_approve"), edge(approved._id, "out_approve", "message")]
    if early:
        nodes.append(node(ChatOutput(_id="out_early", should_store_message=False)))
        edges.append(edge("c_in", "out_early", "message"))
    return payload(nodes, edges)


def agent_payload(*, terminal: bool = False) -> dict:
    """Chat Input -> an Agent that asks before each tool call [-> Chat Output]."""
    nodes = [
        node(ChatInput(_id="c_in", should_store_message=False)),
        node(ScriptedAgent(_id="agent", tool_policy="ask")),
    ]
    edges = [edge("c_in", "agent", "message")]
    if not terminal:
        nodes.append(node(ChatOutput(_id="c_out", should_store_message=False)))
        edges.append(edge("agent", "c_out", "response"))
    return payload(nodes, edges)


def wrapper_payload(child: str, flows_dir: Path, *, runner: type | None = None, terminal: bool = False) -> dict:
    """Chat Input -> Run Flow (running ``child``) [-> Chat Output]."""
    runner = (runner or NestedRunFlow)(
        _id="runner", flow_name_selected=child, flow_id_selected=CHILD_ID, flows_dir=str(flows_dir)
    )
    nodes = [node(ChatInput(_id="w_in", should_store_message=False)), node(runner)]
    edges = [edge("w_in", "runner", "message")]
    if not terminal:
        nodes.append(node(ChatOutput(_id="w_out", should_store_message=False)))
        edges.append(edge("runner", "w_out", "text"))
    return payload(nodes, edges)


def parent_graph(flows_dir: Path, levels: int) -> Graph:
    """A parent whose Run Flow nests ``levels`` deep above the Human Input flow (written under ``flows_dir``)."""
    write_flow(flows_dir, "level0", hitl_payload())
    for level in range(1, levels):
        write_flow(flows_dir, f"level{level}", wrapper_payload(f"level{level - 1}", flows_dir))
    return graph_from(wrapper_payload(f"level{levels - 1}", flows_dir))


def tool_payload(child: str, flows_dir: Path) -> dict:
    """Run Flow (running ``child``) as the tool of a Tool Caller -> Chat Output."""
    runner = NestedRunFlow(_id="runner", flow_name_selected=child, flow_id_selected=CHILD_ID, flows_dir=str(flows_dir))
    runner_node = node(runner)
    runner_node["data"]["node"]["outputs"].append(runner._build_tool_output().model_dump())
    runner_node["data"]["node"]["tool_mode"] = True
    return payload(
        [runner_node, node(ToolCaller(_id="caller")), node(ChatOutput(_id="w_out", should_store_message=False))],
        [
            edge("runner", "caller", "component_as_tool", field="tools", types=("Tool",)),
            edge("caller", "w_out", "text"),
        ],
    )


def candidate_runner_node(child_id: str) -> dict:
    """The real Run Flow running ``child_id``, with the output and input the Human Input flow exposes."""
    runner = node(RunFlowComponent(_id="runner", flow_id_selected=child_id, flow_name_selected="child"))
    runner["data"]["node"]["outputs"] = [
        {
            "name": "out_approve~message",
            "display_name": "Message",
            "method": "_resolve_flow_output__out_approve__message",
            "types": ["Message"],
            "selected": "Message",
            "allows_loop": False,
            "cache": True,
            "tool_mode": True,
        }
    ]
    runner["data"]["node"]["template"]["c_in~input_value"] = {
        "name": "c_in~input_value",
        "value": "hello",
        "type": "str",
        "_input_type": "MessageTextInput",
        "show": True,
        "tool_mode": True,
    }
    return runner


def loop_body_payload(step: str, marker: Path) -> dict:
    """Chat Input -> one row -> Loop, whose body asks for a decision with ``step`` ("human_input" or "agent").

    The body is To Message -> the step -> Marker -> back to the Loop, and the Loop's done output feeds a
    second Marker. Each Marker appends its tag to ``marker`` when it runs.
    """
    if step == "human_input":
        asking, into, out = HumanInput(_id="step"), "prompt", "branch_approve"
    else:
        asking, into, out = ScriptedAgent(_id="step", tool_policy="ask"), "input_value", "response"
    feedback = {
        "source": "after",
        "target": "loop",
        "id": "after-out-loop",
        "data": {
            "sourceHandle": {"dataType": "Marker", "id": "after", "name": "out", "output_types": ["Data"]},
            "targetHandle": {"dataType": "LoopComponent", "id": "loop", "name": "item", "output_types": ["Data"]},
        },
    }
    return payload(
        [
            node(ChatInput(_id="c_in", should_store_message=False)),
            node(Rows(_id="rows")),
            node(LoopComponent(_id="loop")),
            node(ToMessage(_id="to_message")),
            node(asking),
            node(Marker(_id="after", path=str(marker), tag="after-step")),
            node(Marker(_id="done", path=str(marker), tag="loop-done")),
        ],
        [
            edge("c_in", "rows", "message"),
            edge("rows", "loop", "rows", field="data", types=("DataFrame",)),
            edge("loop", "to_message", "item", types=("Data",)),
            edge("to_message", "step", "message", field=into),
            edge("step", "after", out),
            feedback,
            edge("loop", "done", "done", types=("DataFrame",)),
        ],
    )


class NestedRunFlow(RunFlowBaseComponent):
    """Run Flow over a flow saved as JSON under ``flows_dir``."""

    display_name = "Nested Run Flow"
    name = "NestedRunFlow"
    inputs = [
        *RunFlowBaseComponent.get_base_inputs(),
        MessageTextInput(name="input_value", display_name="In"),
        StrInput(name="flows_dir", advanced=True),
    ]
    outputs = [Output(display_name="Text", name="text", method="run_text")]

    async def get_graph(self, *_args, **_kwargs) -> Graph:
        flow = json.loads((Path(self.flows_dir) / f"{self.flow_name_selected}.json").read_text())["data"]
        return Graph.from_payload(flow, flow_id=self.flow_id_selected)

    def _build_flow_tweak_data(self) -> dict:
        return {}

    def _build_inputs(self, _tweaks) -> dict:
        return {"input_value": self.input_value}

    async def run_text(self) -> Message:
        run_outputs = await self._run_flow_with_cached_graph(user_id=str(self.user_id))
        if not run_outputs:
            return Message(text="")
        results = [r for r in run_outputs[0].outputs if r]
        return Message(text="|".join(f"{r.component_id}:{r.results['message'].get_text()}" for r in results))


class StatefulRunFlow(NestedRunFlow):
    """Attaches caller state to the fresh child graph, as RunFlowBaseComponent.get_graph does."""

    display_name = "Stateful Run Flow"
    name = "StatefulRunFlow"

    async def get_graph(self, *args, **kwargs) -> Graph:
        graph = await super().get_graph(*args, **kwargs)
        graph.flow_name = self.flow_name_selected
        graph.context["caller"] = "run-flow"
        graph.frozen_tool_flows = {CHILD_ID: {}}
        graph.authorized_extra_file_scopes = frozenset({"extra-scope"})
        return graph


class CallerState(Component):
    """Shows the caller state of the graph it runs in."""

    display_name = "Caller State"
    name = "CallerState"
    inputs = [MessageTextInput(name="input_value", display_name="In")]
    outputs = [Output(display_name="Message", name="message", method="show")]

    def show(self) -> Message:
        graph = self.graph
        frozen = sorted(graph.frozen_tool_flows or {})
        scopes = sorted(graph.authorized_extra_file_scopes)
        return Message(text=f"{graph.context.get('caller')}|{frozen}|{scopes}|{graph.flow_name}")


class ToolCaller(Component):
    """Stands in for an Agent: calls its first tool once and shows what the tool returned."""

    display_name = "Tool Caller"
    name = "ToolCaller"
    inputs = [HandleInput(name="tools", display_name="Tools", input_types=["Tool"], is_list=True)]
    outputs = [Output(display_name="Text", name="text", method="call_tool")]

    async def call_tool(self) -> Message:
        result = await self.tools[0].ainvoke({"flow_tweak_data": {"c_in~input_value": "hello"}})
        return Message(text=str(result))


class Marker(Component):
    """Appends ``tag`` to the file at ``path`` when it runs."""

    display_name = "Marker"
    name = "Marker"
    inputs = [
        HandleInput(name="input_value", display_name="In", input_types=["Message", "Data", "DataFrame"]),
        StrInput(name="path", display_name="Path"),
        StrInput(name="tag", display_name="Tag"),
    ]
    outputs = [Output(display_name="Out", name="out", method="mark")]

    def mark(self) -> Data:
        with Path(self.path).open("a") as handle:
            handle.write(self.tag + "\n")
        return Data(text=self.tag)


class Rows(Component):
    display_name = "Rows"
    name = "Rows"
    inputs = [HandleInput(name="input_value", display_name="In", input_types=["Message"], required=False)]
    outputs = [Output(display_name="Rows", name="rows", method="rows")]

    def rows(self) -> DataFrame:
        return DataFrame([Data(text="row0")])


class ToMessage(Component):
    display_name = "To Message"
    name = "ToMessage"
    inputs = [HandleInput(name="input_value", display_name="In", input_types=["Message", "Data", "DataFrame"])]
    outputs = [Output(display_name="Message", name="message", method="convert")]

    def convert(self) -> Message:
        return Message(text=str(getattr(self.input_value, "text", None) or self.input_value))


class ScriptedModel(BaseChatModel):
    """Calls ``record`` once, then answers with what the tool returned."""

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
        results = [m for m in messages if isinstance(m, ToolMessage)]
        if results:
            message = AIMessage(content=f"done:{results[-1].content}")
        else:
            call = {"name": "record", "args": {"value": "effect"}, "id": "call-1", "type": "tool_call"}
            message = AIMessage(content="", tool_calls=[call])
        return ChatResult(generations=[ChatGeneration(message=message)])


class ScriptedAgent(AgentComponent):
    """A real Agent that asks before each tool call, with a scripted model and tool."""

    display_name = "Scripted Agent"
    name = "ScriptedAgent"

    def _get_llm(self):
        return ScriptedModel()

    async def get_agent_requirements(self):
        @tool
        def record(value: str) -> str:
            """Record a value."""
            return value

        record.metadata = {}
        return ScriptedModel(), [], [record]
