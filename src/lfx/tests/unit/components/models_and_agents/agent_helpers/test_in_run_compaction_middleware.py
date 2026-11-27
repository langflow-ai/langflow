"""In-run compaction: it bounds one run, fails open, stays out of the chat stream and keeps tool approval working."""

from __future__ import annotations

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from lfx.base.agents.events import process_agent_events
from lfx.components.models_and_agents.agent_helpers.graph_event_adapter import adapt_graph_events_to_executor_shape
from lfx.components.models_and_agents.agent_helpers.in_run_compaction_middleware import InRunCompactionMiddleware
from lfx.schema.message import Message

WINDOW = 2_000  # compact at 1,600 tokens, keep 500
SUMMARY = "SUMMARY-OF-EARLIER-TOOL-CALLS"


class ToolCapableFakeChat(FakeMessagesListChatModel):
    def bind_tools(self, _tools, **_kwargs):  # type: ignore[override]
        return self


class BrokenChat(FakeMessagesListChatModel):
    async def _agenerate(self, *_args, **_kwargs):
        msg = "provider down"
        raise RuntimeError(msg)


@tool
def read_page(page: int) -> str:
    """Return one page of a long document."""
    return f"page {page} " + "x" * 2_400


@tool
def publish(text: str) -> str:
    """Publish the text. Needs approval."""
    return f"published {text}"


def _call(name: str, args: dict, call_id: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"id": call_id, "name": name, "args": args, "type": "tool_call"}])


def _main_model(final: list[AIMessage]) -> ToolCapableFakeChat:
    pages = [_call("read_page", {"page": i}, f"call_{i}") for i in range(4)]
    return ToolCapableFakeChat(responses=[*pages, *final])


def _compacted(messages) -> bool:
    return any(
        isinstance(m, HumanMessage) and m.additional_kwargs.get("lc_source") == "summarization" for m in messages
    )


async def test_should_compact_a_long_run_and_keep_the_summary_out_of_the_chat_stream():
    summarizer = FakeMessagesListChatModel(responses=[AIMessage(content=SUMMARY)])
    agent = create_agent(
        model=_main_model([AIMessage(content="done")]),
        tools=[read_page],
        middleware=[InRunCompactionMiddleware(summarizer, WINDOW)],
    )
    raw_events = []

    async def record(stream):
        async for event in stream:
            raw_events.append(event)
            yield event

    adapted = [
        e
        async for e in adapt_graph_events_to_executor_shape(
            record(agent.astream_events({"messages": [("user", "read the pages")]}, version="v2"))
        )
    ]

    final = next(e for e in raw_events if e["event"] == "on_chain_end" and e.get("parent_ids") == [])
    messages = final["data"]["output"]["messages"]
    assert _compacted(messages)
    assert len([m for m in messages if isinstance(m, ToolMessage)]) < 4  # older tool results were replaced
    assert messages[-1].content == "done"
    assert messages[0].content == "read the pages"  # the request stays word for word
    assert messages[1].additional_kwargs.get("lc_source") == "summarization"
    # The raw stream has the summary call; the stream the Agent turns into the chat message does not.
    assert any(SUMMARY in str(e["data"].get("output", "")) for e in raw_events if e["event"] == "on_chat_model_end")
    assert not any(SUMMARY in str(e["data"].get("output", "")) for e in adapted if e["event"] == "on_chat_model_end")


async def test_should_keep_the_messages_when_the_summary_call_fails():
    agent = create_agent(
        model=_main_model([AIMessage(content="done")]),
        tools=[read_page],
        middleware=[InRunCompactionMiddleware(BrokenChat(responses=[]), WINDOW)],
    )
    state = await agent.ainvoke({"messages": [("user", "read the pages")]})
    assert not _compacted(state["messages"])
    assert len([m for m in state["messages"] if isinstance(m, ToolMessage)]) == 4
    assert state["messages"][-1].content == "done"


async def test_should_pause_and_resume_tool_approval_after_a_compaction():
    summarizer = FakeMessagesListChatModel(responses=[AIMessage(content=SUMMARY)])
    agent = create_agent(
        model=_main_model([_call("publish", {"text": "report"}, "call_pub"), AIMessage(content="published")]),
        tools=[read_page, publish],
        middleware=[
            InRunCompactionMiddleware(summarizer, WINDOW),
            HumanInTheLoopMiddleware(interrupt_on={"publish": True}),
        ],
        checkpointer=InMemorySaver(),
    )
    config = {"configurable": {"thread_id": "t1"}}

    paused = await agent.ainvoke({"messages": [("user", "read, then publish")]}, config=config)
    assert "__interrupt__" in paused
    assert _compacted(paused["messages"])

    resumed = await agent.ainvoke(Command(resume={"decisions": [{"type": "approve"}]}), config=config)
    tool_results = [m.content for m in resumed["messages"] if isinstance(m, ToolMessage)]
    assert "published report" in tool_results
    assert resumed["messages"][-1].content == "published"


async def test_should_show_the_compaction_in_the_chat_message_while_the_run_streams():
    summarizer = FakeMessagesListChatModel(responses=[AIMessage(content=SUMMARY)])
    agent = create_agent(
        model=_main_model([AIMessage(content="done")]),
        tools=[read_page],
        middleware=[InRunCompactionMiddleware(summarizer, WINDOW)],
    )
    seen: list[list[str]] = []

    async def send_message(message, *, skip_db_update=False):
        seen.append([e.state for e in message.properties.context_events or []])
        if skip_db_update:
            return message
        # A stored publish comes back from the database row. The v1 projection drops flat content blocks of
        # a run without tools, so the indicator must not depend on content_blocks.
        return Message(
            text=message.text,
            sender=message.sender,
            sender_name=message.sender_name,
            properties=message.properties.model_dump(),
            content_blocks=[],
        )

    stream = adapt_graph_events_to_executor_shape(
        agent.astream_events({"messages": [("user", "read the pages")]}, version="v2")
    )
    final = await process_agent_events(
        stream, Message(text="", sender="Machine", sender_name="AI", content_blocks=[]), send_message
    )

    # The chat sees the compaction while it runs, then the same event when it is done.
    assert ["running"] in seen
    (event,) = final.properties.context_events
    assert event.kind == "compaction"
    assert event.state == "done"
    assert event.tokens_after < event.tokens_before
    assert SUMMARY not in final.text
