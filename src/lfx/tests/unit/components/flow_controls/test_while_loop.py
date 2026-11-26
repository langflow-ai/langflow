"""While Loop on real graphs.

The loop body runs through the same single-iteration runner as Loop, so these tests build graphs
with `.set()`, run them with `async_start`, and read the loop's outputs through sink components.
Body components record into `graph.context["seen"]`, which the body's subgraph shares by reference.
"""

import json
from pathlib import Path

import pytest
from langchain.agents.middleware import ModelCallLimitMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from lfx.base.agents.loop_rows import HARNESS_LOOP_KEY, messages_to_rows, rows_to_messages
from lfx.base.agents.loop_runtime import HarnessLoopRuntime
from lfx.components.flow_controls.while_loop import WhileLoopComponent
from lfx.custom.custom_component.component import Component
from lfx.graph import Graph
from lfx.inputs.inputs import HandleInput
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message
from lfx.template.field.base import Output

OWNER = "11111111-1111-1111-1111-111111111111"
CALLER = "22222222-2222-2222-2222-222222222222"


def _tool_row(rows) -> dict:
    return {"text": f"result {len(rows)}", "sender": "Tool"}


class GrowingBody(Component):
    """Feeds back the state plus one tool row until it holds `stop_at` rows, then the state plus an answer.

    With `stop_branch` in the context it stops its branch at `stop_at` instead, so it feeds nothing back.
    """

    display_name = "Growing Body"
    inputs = [HandleInput(name="messages", display_name="Messages", input_types=["DataFrame"])]
    outputs = [Output(display_name="Again", name="again", method="again", group_outputs=True)]

    async def arequire_model_provider_policy(self, purpose, *, user_id=None, parameters=None):  # noqa: ARG002
        # The build calls this with the user it runs for, before the body method runs.
        self.ctx["policy_users"].add(str(user_id))

    def again(self) -> DataFrame:
        json.dumps(self._vertex.data["node"]["template"]["messages"]["value"])  # the node data holds JSON
        self.ctx["seen"].append({"kind": "body", "rows": len(self.messages), "is_dataframe": True})
        rows = self.messages.to_dict(orient="records")
        if len(rows) < self.ctx["stop_at"]:
            return DataFrame([*rows, _tool_row(rows)])
        if self.ctx.get("stop_branch"):
            self.stop("again")
            self.graph.exclude_branch_conditionally(self._id, output_name="again")
            return DataFrame([])
        return DataFrame([*rows, *messages_to_rows([AIMessage("the answer")])])


class KeepLastTwo(Component):
    """Feeds back only the last two rows of the state plus a numbered step, as compaction would."""

    display_name = "Keep Last Two"
    inputs = [HandleInput(name="messages", display_name="Messages", input_types=["DataFrame"])]
    outputs = [Output(display_name="Rows", name="rows", method="feed")]

    def feed(self) -> DataFrame:
        rows = self.messages.to_dict(orient="records")
        self.ctx["seen"].append({"kind": "compact", "rows": len(rows)})
        step = {"text": f"step {len(self.ctx['seen'])}", "sender": "Tool"}
        return DataFrame([*rows[-2:], step])


class AsksOnce(Component):
    """Answers with a tool call first, then with text."""

    display_name = "Asks Once"
    inputs = [HandleInput(name="messages", display_name="Messages", input_types=["DataFrame"])]
    outputs = [Output(display_name="Rows", name="rows", method="feed")]

    def feed(self) -> DataFrame:
        rows = self.messages.to_dict(orient="records")
        call = {"name": "echo", "args": {}, "id": f"c{len(rows)}"}
        reply = AIMessage("", tool_calls=[call]) if len(rows) == 1 else AIMessage("done")
        return DataFrame([*rows, *messages_to_rows([reply])])


class EmptyAnswer(Component):
    """Feeds back a tool row and then an answer with no text."""

    display_name = "Empty Answer"
    inputs = [HandleInput(name="messages", display_name="Messages", input_types=["DataFrame"])]
    outputs = [Output(display_name="Rows", name="rows", method="feed")]

    def feed(self) -> DataFrame:
        rows = self.messages.to_dict(orient="records")
        return DataFrame([*rows, _tool_row(rows), *messages_to_rows([AIMessage("")])])


class Relay(Component):
    """The end of a two-vertex body. It is not built when the vertex before it stops its branch."""

    display_name = "Relay"
    inputs = [HandleInput(name="messages", display_name="Messages", input_types=["DataFrame"])]
    outputs = [Output(display_name="Rows", name="rows", method="feed")]

    def feed(self) -> DataFrame:
        return self.messages


class TwoOutputs(Component):
    """`preview` is declared first and left unconnected. `rows` feeds back the state plus a tool row."""

    display_name = "Two Outputs"
    inputs = [HandleInput(name="messages", display_name="Messages", input_types=["DataFrame"])]
    outputs = [
        Output(display_name="Preview", name="preview", method="preview", group_outputs=True),
        Output(display_name="Rows", name="rows", method="feed", group_outputs=True),
    ]

    def preview(self) -> Message:
        return Message(text="preview")

    def feed(self) -> DataFrame:
        rows = self.messages.to_dict(orient="records")
        return DataFrame([*rows, _tool_row(rows)])


class Observer(Component):
    """A second consumer of the loop output that does not feed back."""

    display_name = "Observer"
    inputs = [HandleInput(name="messages", display_name="Messages", input_types=["DataFrame"])]
    outputs = [Output(display_name="Output", name="output", method="process")]

    def process(self) -> DataFrame:
        self.ctx["seen"].append(
            {"kind": "observer", "is_dataframe": isinstance(self.messages, DataFrame), "rows": len(self.messages)}
        )
        return DataFrame([])


class Failing(Component):
    display_name = "Failing"
    inputs = [HandleInput(name="messages", display_name="Messages", input_types=["DataFrame"])]
    outputs = [Output(display_name="Output", name="output", method="process")]

    def process(self) -> DataFrame:
        msg = "body exploded"
        raise ValueError(msg)


class DoneSink(Component):
    """Reads the Done output."""

    display_name = "Done Sink"
    inputs = [HandleInput(name="rows", display_name="Rows", input_types=["DataFrame"])]
    outputs = [Output(display_name="Output", name="output", method="process")]

    def process(self) -> DataFrame:
        self.ctx["done"] = self.rows.to_dict(orient="records")
        return self.rows


class MessageSink(Component):
    """Reads the Last Message output."""

    display_name = "Message Sink"
    inputs = [HandleInput(name="message", display_name="Message", input_types=["Message"])]
    outputs = [Output(display_name="Output", name="output", method="process")]

    def process(self) -> Message:
        self.ctx["seen"].append({"kind": "sink", "text": self.message.text, "data": dict(self.message.data)})
        return self.message


def _loop(body_class=GrowingBody, *, input_value=None, max_iterations=10, initial_state=None):
    wl = WhileLoopComponent(_id="while_loop")
    body = body_class(_id="body")
    body.set(messages=wl.loop_output)
    wl.set(
        input_value=Message(text="Start", sender="User") if input_value is None else input_value,
        max_iterations=max_iterations,
        loop=body.again if body_class is GrowingBody else body.feed,
    )
    if initial_state is not None:
        wl.set(initial_state=initial_state)
    return wl, body


def _graph(wl, *, sink="done", stop_at=3, **context):
    end = DoneSink(_id="sink") if sink == "done" else MessageSink(_id="sink")
    end.set(**({"rows": wl.done_output} if sink == "done" else {"message": wl.last_message_output}))
    return Graph(wl, end, context={"seen": [], "policy_users": set(), "stop_at": stop_at, **context})


async def _run(graph: Graph, **kwargs) -> dict:
    async for _ in graph.async_start(**kwargs):
        pass
    return graph.context


def _idle_runtime() -> HarnessLoopRuntime:
    """A harness runtime that never stops a run, so the loop runs to its cap and ends with the limit message."""
    return HarnessLoopRuntime(model=None, tools=[], system_prompt=None, middleware=[])


def _texts(rows) -> list:
    return [row["text"] for row in rows]


def _bodies(context) -> list[int]:
    return [s["rows"] for s in context["seen"] if s["kind"] == "body"]


class TestTheStateTravelsOnTheFeedbackEdge:
    async def test_the_loop_ends_when_the_new_state_ends_in_an_answer(self):
        wl, _ = _loop()

        context = await _run(_graph(wl, stop_at=3))

        assert _bodies(context) == [1, 2, 3]
        assert _texts(context["done"]) == ["Start", "result 1", "result 2", "the answer"]

    async def test_the_fed_back_rows_replace_the_state(self):
        wl, _ = _loop(KeepLastTwo, max_iterations=4)

        context = await _run(_graph(wl, **{HARNESS_LOOP_KEY: _idle_runtime()}))

        # Each iteration gets what the previous one fed back, so the state stays at three rows.
        assert [s["rows"] for s in context["seen"]] == [1, 2, 3, 3]
        assert _texts(context["done"])[:3] == ["step 2", "step 3", "step 4"]

    async def test_an_ai_message_that_asks_for_tools_does_not_end_the_loop(self):
        wl, _ = _loop(AsksOnce)

        context = await _run(_graph(wl))

        assert [m.type for m in rows_to_messages(DataFrame(context["done"]))] == ["human", "ai", "ai"]

    async def test_a_body_that_feeds_nothing_back_ends_the_loop_with_the_state_so_far(self):
        wl = WhileLoopComponent(_id="while_loop")
        body, relay = GrowingBody(_id="body"), Relay(_id="relay")
        body.set(messages=wl.loop_output)
        relay.set(messages=body.again)
        wl.set(input_value=Message(text="Start", sender="User"), loop=relay.feed)

        context = await _run(_graph(wl, stop_at=2, stop_branch=True))

        assert _bodies(context) == [1, 2]
        assert _texts(context["done"]) == ["Start", "result 1"]

    async def test_a_stopped_harness_runtime_ends_the_loop(self):
        @tool(return_direct=True)
        def answer(text: str) -> str:
            """Answer and end the run."""
            return text

        runtime = HarnessLoopRuntime(model=None, tools=[answer], system_prompt=None, middleware=[])
        call = {"name": "answer", "args": {"text": "final"}, "id": "a1"}
        await runtime.tool_calls([call], [HumanMessage("hi"), AIMessage("", tool_calls=[call])])
        assert runtime.stopped
        wl, _ = _loop()

        context = await _run(_graph(wl, stop_at=5, **{HARNESS_LOOP_KEY: runtime}))

        assert _bodies(context) == [1]
        assert _texts(context["done"]) == ["Start", "result 1"]

    async def test_the_loop_reads_the_output_wired_to_its_feedback_input(self):
        wl, _ = _loop(TwoOutputs, max_iterations=2)

        context = await _run(_graph(wl, **{HARNESS_LOOP_KEY: _idle_runtime()}))

        assert _texts(context["done"])[:3] == ["Start", "result 1", "result 2"]
        assert "preview" not in _texts(context["done"])


class TestLastMessage:
    async def test_last_message_is_the_last_row_with_its_whole_message_and_runs_the_body_once(self):
        wl, _ = _loop()

        context = await _run(_graph(wl, sink="message", stop_at=3))

        assert _bodies(context) == [1, 2, 3]
        (seen,) = [s for s in context["seen"] if s["kind"] == "sink"]
        assert seen["text"] == "the answer"
        assert seen["data"]["lc_message"]["type"] == "ai"

    async def test_an_empty_final_answer_is_an_empty_message(self):
        wl, _ = _loop(EmptyAnswer)

        context = await _run(_graph(wl, sink="message"))

        (seen,) = [s for s in context["seen"] if s["kind"] == "sink"]
        assert seen["text"] == ""
        assert seen["data"]["lc_message"]["type"] == "ai"

    async def test_both_outputs_connected_run_the_body_once(self):
        wl, _ = _loop()
        done_sink = Observer(_id="done_sink")
        done_sink.set(messages=wl.done_output)
        message_sink = MessageSink(_id="message_sink")
        message_sink.set(message=wl.last_message_output)
        context = {"seen": [], "policy_users": set(), "stop_at": 3}

        await _run(Graph(wl, done_sink, context=context))

        assert _bodies(context) == [1, 2, 3]
        assert [s for s in context["seen"] if s["kind"] == "observer"] == [
            {"kind": "observer", "is_dataframe": True, "rows": 4}
        ]


class TestMaxIterations:
    async def test_without_a_harness_it_raises_instead_of_returning_a_state_without_an_answer(self):
        wl, _ = _loop(max_iterations=2)
        graph = _graph(wl, stop_at=100)

        with pytest.raises(Exception, match="reached max_iterations"):
            await _run(graph)

        assert _bodies(graph.context) == [1, 2]

    @pytest.mark.parametrize("max_iterations", [0, -3])
    async def test_a_cap_below_one_runs_the_body_once_like_the_agents_clamp(self, max_iterations):
        wl, _ = _loop(max_iterations=max_iterations)
        graph = _graph(wl, stop_at=100)

        with pytest.raises(Exception, match=r"reached max_iterations \(1\)"):
            await _run(graph)

        assert _bodies(graph.context) == [1]

    async def test_under_a_harness_it_ends_with_the_agents_limit_message(self):
        class AlwaysCalls(BaseChatModel):
            @property
            def _llm_type(self):
                return "always-calls"

            def bind_tools(self, tools, **kwargs):  # noqa: ARG002
                return self

            def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
                call = {"name": "echo", "args": {}, "id": f"c{len(messages)}"}
                return ChatResult(generations=[ChatGeneration(message=AIMessage("", tool_calls=[call]))])

        limited = HarnessLoopRuntime(
            model=AlwaysCalls(), tools=[], system_prompt=None, middleware=[ModelCallLimitMiddleware(run_limit=2)]
        )
        messages = [HumanMessage("hi")]
        for _ in range(3):
            messages = await limited.model_call(messages)
        agents_limit = messages[-1].content

        wl, _ = _loop(max_iterations=2)
        context = await _run(_graph(wl, stop_at=100, **{HARNESS_LOOP_KEY: _idle_runtime()}))

        assert _bodies(context) == [1, 2]
        assert context["done"][-1]["text"] == agents_limit
        assert context["done"][-1]["sender"] == "Machine"


class TestTheState:
    async def test_the_state_is_json_with_exact_numbers_and_the_body_gets_a_dataframe(self):
        call = {"name": "pay", "args": {"amount": 0.1 + 0.2, "tiny": 1.5e-12, "big": 12345678901234567890}, "id": "c1"}
        state = DataFrame(messages_to_rows([HumanMessage("pay"), AIMessage("", tool_calls=[call])]))
        wl, _ = _loop(input_value=state)

        context = await _run(_graph(wl, stop_at=3))

        json.dumps(context["done"])
        assert rows_to_messages(DataFrame(context["done"]))[1].tool_calls[0]["args"] == call["args"]

    async def test_an_unset_input_adds_no_row(self):
        history = DataFrame(messages_to_rows([HumanMessage("earlier")]))
        wl = WhileLoopComponent(_id="while_loop")
        wl.set(initial_state=history)
        graph = Graph(wl, wl)

        await _run(graph)

        assert graph.get_vertex("while_loop").results["done"].to_dict(orient="records") == [
            *messages_to_rows([HumanMessage("earlier")])
        ]

    def test_a_message_input_becomes_the_message_the_packaged_agent_sends(self, tmp_path: Path):
        image = tmp_path / "pixel.png"
        image.write_bytes(b"an attachment")
        message = Message(text="what is this?", sender="User", files=[str(image)])

        (human,) = rows_to_messages(WhileLoopComponent()._to_dataframe(message))

        # The Agent sends `to_lc_message()`, which carries the files the run may read, so the loop gets the same.
        assert isinstance(human.content, list)
        assert human.content == message.to_lc_message().content

    async def test_a_failing_body_raises(self):
        wl = WhileLoopComponent(_id="while_loop")
        body = Failing(_id="body")
        body.set(messages=wl.loop_output)
        wl.set(input_value=Message(text="Start", sender="User"), loop=body.process)
        graph = Graph(wl, wl, context={"seen": []})

        with pytest.raises(Exception, match="body exploded"):
            await _run(graph)

    async def test_without_a_body_it_returns_the_initial_state(self):
        wl = WhileLoopComponent(_id="while_loop")
        wl.set(input_value=Message(text="Hello", sender="User"))
        graph = Graph(wl, wl)

        await _run(graph)

        assert _texts(graph.get_vertex("while_loop").results["done"].to_dict(orient="records")) == ["Hello"]


class TestWhileLoopUsesTheLoopRunner:
    async def test_every_branch_from_the_loop_output_gets_the_state(self):
        """Loop.item fans out to all its branches. While Loop does the same."""
        wl, _ = _loop()
        observer = Observer(_id="observer")
        observer.set(messages=wl.loop_output)
        context = {"seen": [], "policy_users": set(), "stop_at": 2}

        await _run(Graph(wl, observer, context=context))

        observed = [s for s in context["seen"] if s["kind"] == "observer"]
        assert observed
        assert all(s["is_dataframe"] for s in observed)
        assert [s["rows"] for s in observed] == _bodies(context)

    async def test_the_body_runs_as_the_caller_not_the_graph_owner(self):
        wl, _ = _loop()
        graph = _graph(wl, stop_at=2)
        graph.user_id = OWNER

        await _run(graph, user_id=CALLER)

        # The While Loop vertex itself is built as CALLER; so is every body vertex it runs.
        assert graph.context["policy_users"] == {CALLER}
