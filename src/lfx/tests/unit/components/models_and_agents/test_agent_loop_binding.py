"""An Agent with a bound loop flow runs that flow instead of create_agent, under every harness control.

Real graphs and a real fake chat model: Chat Input -> Agent -> Chat Output on the outside, and a loop flow
(Agent Context, While Loop, Agent Step, Execute Tool) saved on disk and run through ReviewedFlowRunner on the
inside. Most tests run the same graph with and without the binding and compare what the user and the model see.
"""

import asyncio
import json

import pytest
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import StructuredTool
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.components.models_and_agents.agent import AgentComponent
from lfx.custom.custom_component.component import Component
from lfx.events.event_manager import create_default_event_manager
from lfx.graph import Graph
from lfx.io import HandleInput, Output
from lfx.memory.flow_context import get_current_flow_id
from lfx.projects.loop import loop_outputs, parse_loop_binding, validate_loop_binding
from lfx.schema.data import Data
from lfx.schema.message import Message

from tests.unit.components.models_and_agents.loop_flow_helpers import loop_flow
from tests.unit.components.models_and_agents.test_agent_blocks import LoopModel

AGENT_FLOW_ID = "11111111-1111-1111-1111-111111111111"


class SharedModel(Component):
    """The test's model instance, so the test can read what it saw."""

    display_name = "Shared Model"
    outputs = [Output(display_name="Model", name="model_output", method="build_model", types=["LanguageModel"])]

    def build_model(self):
        return self.ctx["model"]


class EchoTools(Component):
    """`echo` records the text and the flow it ran under. `ctx["tool"]` picks another tool."""

    display_name = "Echo Tools"
    outputs = [Output(display_name="Tools", name="tools", method="build_tools", types=["Tool"])]

    def build_tools(self) -> list:
        ran, flows = self.ctx["ran"], self.ctx["tool_flows"]

        def echo(text: str) -> str:
            """Echo the text."""
            ran.append(text)
            flows.append(str(get_current_flow_id()))
            return f"echo {text}"

        kind = self.ctx.get("tool", "plain")
        built = StructuredTool.from_function(echo, name="echo", description="Echo", return_direct=kind == "direct")
        if kind == "approval":
            built.metadata = {"approval_actions": ["approve", "reject"]}
        return [built]


class Observer(AgentMiddleware):
    """Records what the harness runs, to see the harness controls reach the loop."""

    def __init__(self, log):
        super().__init__()
        self.log = log

    async def aafter_agent(self, state, runtime):  # noqa: ARG002
        self.log.append(("after_agent", [m.type for m in state["messages"]]))


class ObservedAgent(AgentComponent):
    """The Agent with one more middleware, as a harness hook would add."""

    def _build_middleware(self, llm, *, allow_interrupts=True):
        return [*super()._build_middleware(llm, allow_interrupts=allow_interrupts), Observer(self.ctx["log"])]


class FileInput(Component):
    """A user message with the files in `ctx["files"]`, as a chat upload gives the Agent."""

    display_name = "File Input"
    outputs = [Output(display_name="Message", name="message", method="build_message")]

    def build_message(self) -> Message:
        return Message(text=self.ctx["text"], sender="User", sender_name="User", files=self.ctx["files"])


class NativeStructuredModel(LoopModel):
    """Answers structured requests natively with `ok: false`, so a run that skips the loop flow shows."""

    def with_structured_output(self, schema, **kwargs):  # noqa: ARG002
        return RunnableLambda(lambda _messages: schema(ok=False))


class DataSink(Component):
    display_name = "Data Sink"
    inputs = [HandleInput(name="data", display_name="Data", input_types=["Data"])]
    outputs = [Output(display_name="Out", name="out", method="keep")]

    def keep(self) -> Data:
        return self.data


def agent_graph(
    tmp_path,
    binding,
    *,
    model=None,
    text="hi",
    max_iterations=5,
    output="message_response",
    files=None,
    tool="plain",
    with_tools=True,
    **agent_inputs,
):
    if files:
        chat_input = FileInput(_id="FileInput-outer")
        message = chat_input.build_message
    else:
        chat_input = ChatInput(_id="ChatInput-outer")
        chat_input.set(input_value=text)
        message = chat_input.message_response
    agent = ObservedAgent(_id="Agent-ag001", _user_id="test-user")
    agent.set(
        model=SharedModel(_id="model").build_model,
        **({"tools": EchoTools(_id="tools").build_tools} if with_tools else {}),
        input_value=message,
        system_prompt="be brief",
        add_current_date_tool=False,
        max_iterations=max_iterations,
        **({"loop_binding": binding.model_dump_json()} if binding else {}),
        **agent_inputs,
    )
    if output == "json_response":
        end = DataSink(_id="sink")
        end.set(data=agent.json_response)
    else:
        end = ChatOutput(_id="ChatOutput-outer")
        end.set(input_value=agent.message_response)
    context = {
        "project_dir": str(tmp_path),
        "model": model or LoopModel(),
        "ran": [],
        "tool_flows": [],
        "log": [],
        "tool": tool,
        "text": text,
        "files": files,
    }
    graph = Graph(chat_input, end, flow_id=AGENT_FLOW_ID, context=context)
    graph.session_id = "s1"
    return graph


async def run(graph):
    queue: asyncio.Queue = asyncio.Queue()
    async for _ in graph.async_start(event_manager=create_default_event_manager(queue=queue)):
        pass
    events = []
    while not queue.empty():
        _, raw, _ = queue.get_nowait()
        events.append(json.loads(raw.decode()))
    return events


def answer(graph) -> str:
    return graph.get_vertex("Agent-ag001").results["response"].text


async def both(tmp_path, *, model_class=LoopModel, model_kwargs=None, **graph_kwargs):
    """Run the packaged loop and the bound loop flow on the same input. Returns (graph, model) for each."""
    binding, _ = loop_flow(tmp_path)
    outcomes = []
    for bound in (None, binding):
        model = model_class(**(model_kwargs or {}))
        graph = agent_graph(tmp_path, bound, model=model, **graph_kwargs)
        await run(graph)
        outcomes.append((graph, model))
    return outcomes


class TestSlotContract:
    def test_discovery_lists_the_loops_last_message(self, tmp_path):
        _, flow = loop_flow(tmp_path)

        assert [(o["node_id"], o["output_name"]) for o in loop_outputs(flow["data"])] == [
            ("WhileLoop-wl001", "last_message")
        ]

    def test_an_output_nothing_reads_is_not_offered(self, tmp_path):
        _, flow = loop_flow(tmp_path)
        flow["data"]["edges"] = [e for e in flow["data"]["edges"] if e["target"] != "ChatOutput-co001"]
        flow["data"]["nodes"] = [n for n in flow["data"]["nodes"] if n["id"] != "ChatOutput-co001"]

        assert loop_outputs(flow["data"]) == []

    def test_only_a_while_loop_component_is_a_loop(self, tmp_path):
        _, flow = loop_flow(tmp_path)
        node = next(n for n in flow["data"]["nodes"] if n["id"] == "WhileLoop-wl001")
        node["data"]["type"] = "WhileLoop"

        assert loop_outputs(flow["data"]) == []

    def test_a_required_input_left_empty_is_named(self, tmp_path):
        _, flow = loop_flow(tmp_path)
        flow["data"]["edges"] = [e for e in flow["data"]["edges"] if e["target"] != "AgentStep-as001"]

        with pytest.raises(ValueError, match="Configure Agent Step: Messages"):
            loop_outputs(flow["data"])

    @pytest.mark.parametrize(
        ("node_id", "output_name"),
        [("WhileLoop-wl001", "done"), ("AgentStep-as001", "ai_message"), ("nope", "last_message")],
    )
    def test_validation_rejects_other_outputs(self, tmp_path, node_id, output_name):
        binding, flow = loop_flow(tmp_path)

        with pytest.raises(ValueError, match="Last Message"):
            validate_loop_binding(
                flow["data"], binding.model_copy(update={"node_id": node_id, "output_name": output_name})
            )

    def test_validation_rejects_a_changed_flow(self, tmp_path):
        binding, flow = loop_flow(tmp_path)
        flow["data"]["nodes"][0]["position"] = {"x": 1, "y": 2}
        flow["data"]["nodes"][0]["data"]["node"]["description"] = "edited"

        with pytest.raises(ValueError, match="changed"):
            validate_loop_binding(flow["data"], binding)

    def test_an_empty_binding_means_the_packaged_loop(self):
        assert parse_loop_binding("") is None
        assert parse_loop_binding("null") is None


class TestTheBoundLoopAnswersLikeThePackagedAgent:
    async def test_the_answer_and_what_the_model_saw_match(self, tmp_path):
        (packaged, packaged_model), (looped, looped_model) = await both(tmp_path)

        assert answer(looped) == answer(packaged) == "Let me echoFinal answer."
        assert looped.context["ran"] == ["hi"]
        assert (
            looped_model.seen
            == packaged_model.seen
            == [
                ["SystemMessage", "HumanMessage"],
                ["SystemMessage", "HumanMessage", "AIMessage", "ToolMessage"],
            ]
        )

    @pytest.mark.parametrize("first_empty", [False, True], ids=["after-a-tool", "at-once"])
    async def test_an_empty_final_answer_matches(self, tmp_path, first_empty):
        class EmptyAnswer(LoopModel):
            def _reply(self, messages):
                self.seen.append([type(m).__name__ for m in messages])
                if first_empty or any(isinstance(m, ToolMessage) for m in messages):
                    return AIMessage(content="")
                call = {"name": "echo", "args": {"text": "SECRET TOOL OUTPUT"}, "id": "c1"}
                return AIMessage(content="", tool_calls=[call])

        (packaged, _), (looped, _) = await both(tmp_path, model_class=EmptyAnswer, text="user question")

        assert answer(looped) == answer(packaged)
        assert "SECRET" not in answer(looped)
        assert "user question" not in answer(looped)

    async def test_a_blank_input_reaches_the_model_as_the_packaged_agent_sends_it(self, tmp_path):
        class SeesText(LoopModel):
            def _reply(self, messages):
                self.seen.append([(type(m).__name__, m.content) for m in messages])
                return AIMessage(content="ok")

        (_, packaged_model), (_, looped_model) = await both(tmp_path, model_class=SeesText, text="   ")

        assert looped_model.seen == packaged_model.seen
        assert looped_model.seen[0][-1] == ("HumanMessage", "Continue the conversation.")

    async def test_an_input_with_files_reaches_the_model_as_the_packaged_agent_sends_it(self, tmp_path):
        class SeesContent(LoopModel):
            def _reply(self, messages):
                self.seen.append([m.content for m in messages])
                return AIMessage(content="ok")

        attachment = tmp_path / "notes.txt"
        attachment.write_text("an attachment")

        (_, packaged_model), (_, looped_model) = await both(
            tmp_path, model_class=SeesContent, text="what is in this file?", files=[str(attachment)]
        )

        assert looped_model.seen == packaged_model.seen
        assert isinstance(looped_model.seen[0][-1], list)

    async def test_one_chat_message_with_tokens_once_and_the_tool_call_in_its_blocks(self, tmp_path):
        binding, _ = loop_flow(tmp_path)
        packaged_events = await run(agent_graph(tmp_path, None))
        events = await run(agent_graph(tmp_path, binding))

        def shape(evts):
            tokens = "".join(e["data"]["chunk"] for e in evts if e["event"] == "token")
            blocks = [
                [b["type"] for b in e["data"]["content_blocks"]]
                for e in evts
                if e["event"] == "add_message" and e["data"]["sender"] == "Machine"
            ]
            return tokens, blocks

        tokens, blocks = shape(events)
        assert tokens == "Let me echoFinal answer."
        assert any("tool_use" in kinds for kinds in blocks)
        # Same message updates as the packaged Agent, so the blocks added none of their own.
        assert shape(events) == shape(packaged_events)

    async def test_finish_runs_the_after_agent_hooks_with_the_whole_history(self, tmp_path):
        (packaged, _), (looped, _) = await both(tmp_path)

        assert looped.context["log"] == packaged.context["log"] == [("after_agent", ["human", "ai", "tool", "ai"])]

    async def test_the_agents_call_limit_ends_the_loop_with_its_message(self, tmp_path):
        (packaged, _), (looped, _) = await both(tmp_path, model_kwargs={"always_call": True}, max_iterations=1)

        assert "limit" in answer(looped).lower()
        assert answer(looped) == answer(packaged)

    async def test_the_while_loops_cap_ends_with_the_agents_limit_message_and_runs_the_hooks(self, tmp_path):
        packaged = agent_graph(tmp_path, None, model=LoopModel(always_call=True), max_iterations=2)
        await run(packaged)
        binding, _ = loop_flow(tmp_path, max_iterations=2)
        looped = agent_graph(tmp_path, binding, model=LoopModel(always_call=True), max_iterations=5)

        await run(looped)

        assert answer(looped) == answer(packaged)
        assert "Model call limits exceeded" in answer(looped)
        assert len(looped.context["log"]) == 1  # the after-agent hooks ran

    async def test_a_return_direct_tool_ends_the_run_like_the_packaged_agent(self, tmp_path):
        (packaged, packaged_model), (looped, looped_model) = await both(tmp_path, tool="direct")

        assert len(looped_model.seen) == len(packaged_model.seen) == 1
        assert answer(looped) == answer(packaged)

    async def test_the_tools_run_under_the_agents_flow(self, tmp_path):
        (packaged, _), (looped, _) = await both(tmp_path)

        assert looped.context["tool_flows"] == packaged.context["tool_flows"] == [AGENT_FLOW_ID]

    @pytest.mark.parametrize("with_tools", [True, False], ids=["prompt-fallback", "native-path"])
    async def test_structured_response_runs_the_bound_loop(self, tmp_path, monkeypatch, with_tools):
        from lfx.services.deps import get_settings_service

        monkeypatch.setattr(get_settings_service().settings, "custom_component_admin_only", False)
        binding, _ = loop_flow(tmp_path, probe=True)
        model = NativeStructuredModel(answer='{"ok": true}')
        schema = [{"name": "ok", "type": "bool", "description": "Whether it worked", "multiple": False}]
        graph = agent_graph(
            tmp_path,
            binding,
            model=model,
            output="json_response",
            output_schema=schema,
            with_tools=with_tools,
            add_calculator_tool=with_tools,
        )

        await run(graph)

        assert (tmp_path / "persist_probe.txt").exists()  # the loop flow ran
        assert graph.get_vertex("sink").results["out"].data["ok"] is True
        assert len(graph.context["log"]) == 1  # under the harness middleware


class TestTheBoundLoopRefusesWhatItCannotDoYet:
    @pytest.mark.parametrize(("tool", "settings"), [("approval", {}), ("plain", {"tool_policy": "ask"})])
    async def test_a_gated_tool_fails_before_it_runs(self, tmp_path, tool, settings):
        binding, _ = loop_flow(tmp_path)
        graph = agent_graph(tmp_path, binding, tool=tool, **settings)

        with pytest.raises(Exception, match="requires approval"):
            await run(graph)

        assert graph.context["ran"] == []


class TestTheLoopFlowRunsQuiet:
    async def test_nothing_in_the_loop_flow_persists_messages(self, tmp_path, monkeypatch):
        from lfx.services.deps import get_settings_service

        monkeypatch.setattr(get_settings_service().settings, "custom_component_admin_only", False)
        binding, _ = loop_flow(tmp_path, probe=True)
        graph = agent_graph(tmp_path, binding)

        await run(graph)

        # The probe sits in the loop flow and wrote the flag its child graph ran under. The outer graph is unchanged.
        assert (tmp_path / "persist_probe.txt").read_text().split() == ["False"]
        assert graph.persist_messages


class TestUnboundAgent:
    async def test_without_a_binding_the_packaged_loop_runs(self, tmp_path):
        graph = agent_graph(tmp_path, None)

        await run(graph)

        assert answer(graph) == "Let me echoFinal answer."  # the packaged Agent shows its narration too
        assert graph.context["log"] == [("after_agent", ["human", "ai", "tool", "ai"])]
