"""The tool result cap: the model sees a capped result, the tool event keeps the full one."""

from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.types import Command
from lfx.base.memory.context_budget import cap_text, estimate_tokens
from lfx.components.models_and_agents.agent_helpers.tool_result_cap_middleware import ToolResultCapMiddleware

BIG = "HEAD-MARK " + "x" * 200_000 + " TAIL-MARK"


class ToolCapableFakeChat(FakeMessagesListChatModel):
    def bind_tools(self, _tools, **_kwargs):  # type: ignore[override]
        return self


@tool
def big_log() -> str:
    """Return a very large log."""
    return BIG


def _agent(cap_tokens: int):
    model = ToolCapableFakeChat(
        responses=[
            AIMessage(content="", tool_calls=[{"id": "call_1", "name": "big_log", "args": {}, "type": "tool_call"}]),
            AIMessage(content="done"),
        ]
    )
    return create_agent(model=model, tools=[big_log], middleware=[ToolResultCapMiddleware(max_tokens=cap_tokens)])


async def test_should_cap_tool_result_in_run_state_and_keep_full_result_in_tool_event():
    agent = _agent(cap_tokens=1_000)
    tool_outputs = []
    final_state = None
    async for event in agent.astream_events({"messages": [("user", "go")]}, version="v2"):
        if event["event"] == "on_tool_end":
            tool_outputs.append(event["data"]["output"])
        if event["event"] == "on_chain_end" and event.get("parent_ids") == []:
            final_state = event["data"]["output"]

    tool_message = next(m for m in final_state["messages"] if isinstance(m, ToolMessage))
    assert estimate_tokens(tool_message.content) <= 1_000 + 30  # the cap plus the marker
    assert tool_message.content.startswith("HEAD-MARK")
    assert tool_message.content.endswith("TAIL-MARK")
    assert "cut here" in tool_message.content
    # The UI builds the tool block from on_tool_end, which still has the full result.
    assert tool_outputs[0].content == BIG


async def test_should_leave_small_tool_result_unchanged():
    agent = _agent(cap_tokens=100_000)
    state = await agent.ainvoke({"messages": [("user", "go")]})
    tool_message = next(m for m in state["messages"] if isinstance(m, ToolMessage))
    assert tool_message.content == BIG


def test_should_cap_text_blocks_together_and_keep_other_blocks():
    image = {"type": "image", "url": "https://example.com/a.png"}
    message = ToolMessage(
        content=[{"type": "text", "text": "a" * 8_000}, image, {"type": "text", "text": "b" * 8_000}],
        tool_call_id="call_1",
    )
    capped = ToolResultCapMiddleware(max_tokens=1_000)._cap(message)
    texts = [b["text"] for b in capped.content if b.get("type") == "text"]
    assert image in capped.content
    assert len(texts) == 1
    assert texts[0].startswith("a")
    assert texts[0].endswith("b")
    assert estimate_tokens(texts[0]) <= 1_030


def test_cap_text_returns_same_object_inside_the_cap():
    text = "short"
    assert cap_text(text, 10) is text


def test_should_cap_a_tool_message_inside_a_command():
    message = ToolMessage(content=BIG, tool_call_id="call_1")
    command = Command(update={"messages": [message], "other": 1})
    capped = ToolResultCapMiddleware(max_tokens=1_000)._cap(command)
    (inner,) = capped.update["messages"]
    assert estimate_tokens(inner.content) <= 1_030
    assert capped.update["other"] == 1
    assert message.content == BIG  # the tool's own result is not changed
