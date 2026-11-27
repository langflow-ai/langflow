"""While Loop, AgentStep and ExecuteTool on real graphs, with a streaming fake chat model.

The blocks make the model and tool calls through `HarnessLoopRuntime`. A test either puts a runtime
in `graph.context["harness_loop"]` (the harness path) or wires a model component into AgentStep
(the standalone path). Nothing is mocked: the fake model is a real `BaseChatModel`. Every test reads
the loop through its outputs.
"""

import asyncio
import json

import pytest
from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, ModelCallLimitMiddleware, hook_config
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.tools import StructuredTool, tool
from lfx.base.agents.harness import HarnessRuntimeConfig
from lfx.base.agents.loop_rows import HARNESS_LOOP_KEY, rows_to_messages
from lfx.base.agents.loop_runtime import HarnessLoopRuntime
from lfx.components.flow_controls.while_loop import WhileLoopComponent
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.components.models_and_agents import AgentStepComponent, ExecuteToolComponent
from lfx.components.models_and_agents.agent_helpers.harness_middleware import HarnessCompactionMiddleware
from lfx.custom.custom_component.component import Component
from lfx.events.event_manager import create_default_event_manager
from lfx.graph import Graph
from lfx.io import HandleInput, Output
from lfx.schema.dataframe import DataFrame
from pydantic import Field


class LoopModel(BaseChatModel):
    """Calls `echo` until it has seen a tool result, then answers. It streams word by word."""

    seen: list = Field(default_factory=list)
    always_call: bool = False
    tool_name: str = "echo"
    tool_args: dict = Field(default_factory=lambda: {"text": "hi"})
    answer: str = "Final answer."
    fail_after_tools: bool = False

    @property
    def _llm_type(self):
        return "loop-model"

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self

    def _reply(self, messages) -> AIMessage:
        self.seen.append([type(m).__name__ for m in messages])
        if self.always_call or not any(isinstance(m, ToolMessage) for m in messages):
            call = {"name": self.tool_name, "args": self.tool_args, "id": f"call_{len(self.seen)}"}
            return AIMessage(content="Let me echo", tool_calls=[call])
        if self.fail_after_tools:
            msg = "provider exploded"
            raise RuntimeError(msg)
        return AIMessage(content=self.answer)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
        return ChatResult(generations=[ChatGeneration(message=self._reply(messages))])

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
        reply = self._reply(messages)
        words = reply.content.split(" ")
        for index, word in enumerate(words):
            yield ChatGenerationChunk(message=AIMessageChunk(content=word + (" " if index < len(words) - 1 else "")))
        if reply.tool_calls:
            chunks = [
                {"name": c["name"], "args": json.dumps(c["args"]), "id": c["id"], "index": i}
                for i, c in enumerate(reply.tool_calls)
            ]
            yield ChatGenerationChunk(message=AIMessageChunk(content="", tool_call_chunks=chunks))


class LoopModelComponent(Component):
    """A model component to wire into AgentStep.model, as on the canvas."""

    display_name = "Loop Model"
    outputs = [Output(display_name="Model", name="model_output", method="build_model", types=["LanguageModel"])]

    def build_model(self) -> BaseChatModel:
        model = LoopModel(**self.ctx.get("model_settings", {}))
        self.ctx["models"].append(model)
        return model


@tool
def echo(text: str) -> str:
    """Echo the text."""
    return f"echo {text}"


class ToolsComponent(Component):
    """Provides `echo`, `boom` (fails) and `send_email` (needs approval) as tools, like a tool component."""

    display_name = "Tools"
    outputs = [Output(display_name="Tools", name="tools", method="build_tools", types=["Tool"])]

    def build_tools(self) -> list:
        async def send_email(to: str) -> str:
            """Send an email."""
            self.ctx["ran"].append(to)
            return f"sent to {to}"

        async def boom(text: str) -> str:
            """Fail."""
            msg = f"tool exploded on {text}"
            raise ValueError(msg)

        email = StructuredTool.from_function(coroutine=send_email, name="send_email", description="Send an email")
        email.metadata = {"approval_actions": ["approve", "reject"]}
        failing = StructuredTool.from_function(coroutine=boom, name="boom", description="Fail")
        return [echo, email, failing]


class PassRows(Component):
    """Passes the state through, as any block in front of Agent Step would."""

    display_name = "Pass Rows"
    inputs = [HandleInput(name="rows", display_name="Rows", input_types=["DataFrame"])]
    outputs = [Output(display_name="Rows", name="out", method="pass_rows")]

    def pass_rows(self) -> DataFrame:
        return self.rows


class DoneSink(Component):
    """Reads While Loop's Done output."""

    display_name = "Done Sink"
    inputs = [HandleInput(name="rows", display_name="Rows", input_types=["DataFrame"])]
    outputs = [Output(display_name="Out", name="out", method="keep")]

    def keep(self) -> DataFrame:
        self.ctx["done"] = self.rows.to_dict(orient="records")
        return self.rows


def _loop_graph(
    *,
    toolbox=None,
    context=None,
    max_iterations=5,
    model_component=None,
    text="hi",
    answer_output=False,
    pass_through=False,
):
    """Chat Input -> While Loop <-> Agent Step / Execute Tool, with Done on a sink.

    `answer_output` also wires Agent Step's Response to a Chat Output. `pass_through` puts a block between While
    Loop and Agent Step.
    """
    chat_input = ChatInput(_id="ChatInput-ci001")
    chat_input.set(input_value=text)
    loop = WhileLoopComponent(_id="WhileLoopComponent-wl001")
    loop.set(input_value=chat_input.message_response, max_iterations=max_iterations)
    step = AgentStepComponent(_id="AgentStepComponent-as001")
    if pass_through:
        rows = PassRows(_id="pass")
        rows.set(rows=loop.loop_output)
        step.set(messages=rows.pass_rows)
    else:
        step.set(messages=loop.loop_output)
    if toolbox is not None:
        step.set(tools=toolbox.build_tools)
    if model_component is not None:
        step.set(model=model_component.build_model)
    execute = ExecuteToolComponent(_id="ExecuteToolComponent-et001")
    execute.set(messages=step.get_tool_calls)
    if toolbox is not None:
        execute.set(tools=toolbox.build_tools)
    loop.set(loop=execute.execute_tools)
    sink = DoneSink(_id="sink")
    sink.set(rows=loop.done_output)
    graph = Graph(chat_input, sink, context={"ran": [], "models": [], **(context or {})})
    if answer_output:
        chat_output = ChatOutput(_id="ChatOutput-co001")
        chat_output.set(input_value=step.get_ai_message)
        graph.add_component(chat_output)
    graph.session_id = "s1"
    return graph


def _runtime(model=None, middleware=(), tools=(echo,)):
    return HarnessLoopRuntime(
        model=model or LoopModel(), tools=list(tools), system_prompt="be brief", middleware=list(middleware)
    )


def _harness(runtime) -> dict:
    return {HARNESS_LOOP_KEY: runtime}


async def _run(graph: Graph, *, event_manager=None) -> list:
    """Run the graph and return While Loop's final state as LangChain messages."""
    async for _ in graph.async_start(event_manager=event_manager, config={"output": {"cache": False}}):
        pass
    return rows_to_messages(DataFrame(graph.context["done"]))


async def _events(graph) -> list:
    queue: asyncio.Queue = asyncio.Queue()
    await _run(graph, event_manager=create_default_event_manager(queue=queue))
    events = []
    while not queue.empty():
        _, raw, _ = queue.get_nowait()
        events.append(json.loads(raw.decode()))
    return events


def _kinds(history) -> list:
    return [type(m).__name__ for m in history]


class TestLoopThroughTheHarnessRuntime:
    async def test_the_loop_runs_the_harness_hooks_and_keeps_full_messages(self):
        seen_by_hooks: list = []

        class Recorder(AgentMiddleware):
            def before_model(self, state, runtime):  # noqa: ARG002
                seen_by_hooks.append(("before_model", len(state["messages"])))

            async def awrap_tool_call(self, request, handler):
                seen_by_hooks.append(("tool", request.tool_call["name"]))
                return await handler(request)

        model = LoopModel()

        history = await _run(_loop_graph(context=_harness(_runtime(model, [Recorder()]))))

        assert seen_by_hooks == [("before_model", 1), ("tool", "echo"), ("before_model", 3)]
        assert _kinds(history) == ["HumanMessage", "AIMessage", "ToolMessage", "AIMessage"]
        assert history[1].tool_calls[0]["id"] == history[2].tool_call_id
        assert history[3].content == "Final answer."
        # The second model call got the real tool call and result back, plus the system prompt.
        assert model.seen[1] == ["SystemMessage", "HumanMessage", "AIMessage", "ToolMessage"]

    @pytest.mark.parametrize(
        ("answer_output", "pass_through"),
        [(True, False), (False, False), (False, True)],
        ids=["response-wired", "response-unwired", "block-in-front"],
    )
    async def test_the_answer_reaches_the_state_however_the_body_is_wired(self, answer_output, pass_through):
        graph = _loop_graph(context=_harness(_runtime()), answer_output=answer_output, pass_through=pass_through)

        history = await _run(graph)

        assert [m.text for m in history] == ["hi", "Let me echo", "echo hi", "Final answer."]

    async def test_a_harness_limit_ends_the_loop_with_its_message(self):
        runtime = _runtime(LoopModel(), [ModelCallLimitMiddleware(run_limit=1)])

        history = await _run(_loop_graph(context=_harness(runtime)))

        assert isinstance(history[-1], AIMessage)
        assert "limit" in history[-1].text.lower()

    async def test_compaction_rewrites_the_state_as_often_as_in_the_packaged_loop(self):
        class Summarizer(BaseChatModel):
            reads: list = Field(default_factory=list)

            @property
            def _llm_type(self):
                return "summarizer"

            def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
                self.reads.append(len(str(messages[0].content)))
                return ChatResult(generations=[ChatGeneration(message=AIMessage(content="summary " + "s" * 40))])

        class Worker(LoopModel):
            def _reply(self, messages):
                self.seen.append(len(messages))
                if len(self.seen) <= 8:
                    call = {"name": "echo", "args": {"text": "y" * 400}, "id": f"c{len(self.seen)}"}
                    return AIMessage(content="x" * 400, tool_calls=[call])
                return AIMessage(content="Final answer.")

        def compaction(summarizer):
            policy = HarnessRuntimeConfig(compaction_trigger_tokens=1200, compaction_keep_messages=2)
            return HarnessCompactionMiddleware(summarizer, policy)

        packaged_summarizer, looped_summarizer = Summarizer(), Summarizer()
        agent = create_agent(model=Worker(), tools=[echo], middleware=[compaction(packaged_summarizer)])
        await agent.ainvoke({"messages": [HumanMessage("hi")]})
        runtime = HarnessLoopRuntime(
            model=Worker(), tools=[echo], system_prompt=None, middleware=[compaction(looped_summarizer)]
        )

        await _run(_loop_graph(context=_harness(runtime), max_iterations=20))

        assert len(looped_summarizer.reads) == len(packaged_summarizer.reads) > 1
        assert looped_summarizer.reads == packaged_summarizer.reads

    async def test_parallel_tool_results_join_the_state_in_call_order(self):
        @tool
        async def slow(text: str) -> str:
            """Slow."""
            await asyncio.sleep(0.05)
            return f"slow {text}"

        @tool
        async def fast(text: str) -> str:
            """Fast."""
            return f"fast {text}"

        class TwoCalls(LoopModel):
            def _reply(self, messages):
                self.seen.append(1)
                if not any(isinstance(m, ToolMessage) for m in messages):
                    calls = [{"name": n, "args": {"text": "x"}, "id": f"c{i}"} for i, n in enumerate(["slow", "fast"])]
                    return AIMessage(content="Two calls", tool_calls=calls)
                return AIMessage(content="Final answer.")

        history = await _run(_loop_graph(context=_harness(_runtime(TwoCalls(), tools=[slow, fast]))))

        assert [(m.type, m.text) for m in history[2:4]] == [("tool", "slow x"), ("tool", "fast x")]

    async def test_a_return_direct_tool_ends_the_loop_like_create_agent(self):
        @tool(return_direct=True)
        def lookup(text: str) -> str:
            """Look it up and end the run."""
            return f"DIRECT {text}"

        packaged_model, looped_model = LoopModel(tool_name="lookup"), LoopModel(tool_name="lookup")
        packaged = await create_agent(model=packaged_model, tools=[lookup]).ainvoke({"messages": [HumanMessage("hi")]})
        runtime = _runtime(looped_model, tools=[lookup])

        history = await _run(_loop_graph(context=_harness(runtime)))

        assert len(looped_model.seen) == len(packaged_model.seen) == 1
        assert [m.text for m in history] == [m.text for m in packaged["messages"]]

    async def test_a_middleware_that_ends_the_run_after_the_model_stops_its_tools(self):
        class EndAfterModel(AgentMiddleware):
            @hook_config(can_jump_to=["end"])
            async def aafter_model(self, state, runtime):  # noqa: ARG002
                return {"jump_to": "end"}

        graph = _loop_graph(context=_harness(_runtime(LoopModel(), [EndAfterModel()])))

        history = await _run(graph)

        assert _kinds(history) == ["HumanMessage", "AIMessage"]
        assert graph.context["ran"] == []


class TestLoopWithoutAHarness:
    async def test_the_blocks_build_their_runtime_from_their_own_inputs(self):
        graph = _loop_graph(model_component=LoopModelComponent(_id="model"), toolbox=ToolsComponent(_id="toolbox"))

        history = await _run(graph)

        assert _kinds(history) == ["HumanMessage", "AIMessage", "ToolMessage", "AIMessage"]
        assert history[2].content == "echo hi"
        assert history[3].content == "Final answer."
        # No system message was set, so the model gets none, not an empty one.
        first_call = next(model.seen[0] for model in graph.context["models"] if model.seen)
        assert first_call == ["HumanMessage"]

    async def test_a_failing_tool_returns_its_error_to_the_model(self):
        graph = _loop_graph(
            model_component=LoopModelComponent(_id="model"),
            toolbox=ToolsComponent(_id="toolbox"),
            context={"model_settings": {"tool_name": "boom"}},
        )

        history = await _run(graph)

        assert history[2].status == "error"
        assert "tool exploded on hi" in history[2].content
        assert history[-1].content == "Final answer."

    async def test_a_failing_model_call_retracts_its_partial_message_and_raises_the_model_error(self):
        graph = _loop_graph(
            model_component=LoopModelComponent(_id="model"),
            toolbox=ToolsComponent(_id="toolbox"),
            context={"model_settings": {"fail_after_tools": True}},
            answer_output=True,
        )
        queue: asyncio.Queue = asyncio.Queue()

        with pytest.raises(Exception, match="provider exploded"):
            await _run(graph, event_manager=create_default_event_manager(queue=queue))

        events = []
        while not queue.empty():
            _, raw, _ = queue.get_nowait()
            events.append(json.loads(raw.decode()))
        assert [e["event"] for e in events].count("remove_message") == 1


class TestChatDisplay:
    async def test_the_answer_is_not_doubled_when_nothing_consumes_the_stream(self):
        """`/run` and `lfx run` have no event manager. Every chunk must still appear once."""
        history = await _run(_loop_graph(context=_harness(_runtime())))

        assert history[-1].text == "Final answer."
        assert history[1].text == "Let me echo"

    async def test_tokens_reach_the_playground_once_without_a_harness(self):
        graph = _loop_graph(
            model_component=LoopModelComponent(_id="model"), toolbox=ToolsComponent(_id="toolbox"), answer_output=True
        )

        events = await _events(graph)

        tokens = "".join(e["data"]["chunk"] for e in events if e["event"] == "token")
        assert tokens == "Let me echoFinal answer."

    async def test_the_blocks_show_nothing_when_a_harness_runtime_owns_the_display(self):
        events = await _events(_loop_graph(context=_harness(_runtime()), answer_output=True))

        assert not [e for e in events if e["event"] == "token"]
        # Only the Chat Output on Agent Step's Response shows a message.
        shown = [e["data"]["text"] for e in events if e["event"] == "add_message" and e["data"]["sender"] == "Machine"]
        assert shown == ["Final answer."]


class TestToolApproval:
    SETTINGS = {"always_call": True, "tool_name": "send_email", "tool_args": {"to": "ceo@example.com"}}

    async def test_a_tool_that_requires_approval_is_refused_with_a_context_runtime_and_does_not_run(self):
        ran: list = []

        async def send_email(to: str) -> str:
            """Send an email."""
            ran.append(to)
            return f"sent to {to}"

        email = StructuredTool.from_function(coroutine=send_email, name="send_email", description="Send an email")
        email.metadata = {"approval_actions": ["approve", "reject"]}
        runtime = _runtime(LoopModel(**self.SETTINGS), tools=[email])

        with pytest.raises(Exception, match="requires approval"):
            await _run(_loop_graph(context=_harness(runtime)))

        assert ran == []

    async def test_a_tool_that_requires_approval_is_refused_without_a_harness_and_does_not_run(self):
        graph = _loop_graph(
            model_component=LoopModelComponent(_id="model"),
            toolbox=ToolsComponent(_id="toolbox"),
            context={"model_settings": self.SETTINGS},
        )

        with pytest.raises(Exception, match="requires approval"):
            await _run(graph)

        assert graph.context["ran"] == []


class TestMaxIterations:
    async def test_a_loop_that_runs_out_of_iterations_without_a_harness_raises(self):
        graph = _loop_graph(
            model_component=LoopModelComponent(_id="model"),
            toolbox=ToolsComponent(_id="toolbox"),
            context={"model_settings": {"always_call": True}},
            max_iterations=2,
        )

        with pytest.raises(Exception, match="reached max_iterations"):
            await _run(graph)


class TestExecuteToolInput:
    async def test_messages_without_tool_calls_pass_through_unchanged(self):
        rows = DataFrame([{"text": "hi", "sender": "User"}])
        execute = ExecuteToolComponent(_id="execute")
        execute.set(messages=rows)
        graph = Graph(execute, execute, context={})

        async for _ in graph.async_start():
            pass

        assert graph.get_vertex("execute").results["new_messages"].to_dict(orient="records") == rows.to_dict(
            orient="records"
        )
