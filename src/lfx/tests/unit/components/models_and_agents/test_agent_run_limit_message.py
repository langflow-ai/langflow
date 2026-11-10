"""The max_iterations limit notice must reach the final Agent message.

`ModelCallLimitMiddleware` ends the run with a synthetic AIMessage that no model call
produced. Runs through the real create_agent graph, middleware, event adapter and
`process_agent_events`; only the chat model is faked.
"""

from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from lfx.schema.content_types import TextContent, ToolContent

LIMIT_NOTICE = "Model call limits exceeded: run limit (1/1)"


class _ToolCapableFakeChat(FakeMessagesListChatModel):
    def bind_tools(self, _tools, **_kwargs):  # type: ignore[override]
        return self


@tool
def fetch_content(url: str) -> str:
    """Fetch the content of a URL."""
    return f'{{"uuid": "22771659-2cf2-4b66-8043-a1393ad20fab", "url": "{url}"}}'


def _tool_call_turn(*, narration: str | None) -> AIMessage:
    tool_input = {"url": "http://example.test/uuid"}
    content: list[dict] = []
    if narration:
        content.append({"type": "text", "text": narration})
    content.append({"type": "tool_use", "id": "toolu_1", "name": "fetch_content", "input": tool_input})
    return AIMessage(
        content=content,
        tool_calls=[{"name": "fetch_content", "args": tool_input, "id": "toolu_1", "type": "tool_call"}],
    )


async def _run_agent(responses: list[AIMessage], *, max_iterations: int):
    from lfx.components.models_and_agents.agent import AgentComponent

    fake_llm = _ToolCapableFakeChat(responses=responses)
    component = AgentComponent()
    component._user_id = None
    component.set_attributes(
        {
            "model": "fake-model",
            "api_key": None,
            "tools": [fetch_content],
            "chat_history": [],
            "input_value": 'Fetch http://example.test/uuid and tell me the "uuid" value.',
            "system_prompt": "You are a helpful agent.",
            "max_iterations": max_iterations,
            "handle_parsing_errors": True,
            "verbose": False,
        }
    )
    with (
        patch.object(type(component), "_get_llm", return_value=fake_llm),
        patch.object(
            type(component),
            "get_agent_requirements",
            new=AsyncMock(return_value=(fake_llm, [], [fetch_content])),
        ),
        patch.object(type(component), "send_message", new=AsyncMock(side_effect=lambda message, **_kw: message)),
    ):
        return await component.message_response()


@pytest.mark.asyncio
async def test_should_end_with_limit_notice_when_model_writes_text_alongside_its_tool_call() -> None:
    narration = "I'll fetch that URL for you and extract the uuid value."

    result = await _run_agent([_tool_call_turn(narration=narration)], max_iterations=1)

    tool_blocks = [block for block in result.content_blocks if isinstance(block, ToolContent)]
    assert tool_blocks, "the tool call must still be recorded"
    assert tool_blocks[0].output is not None
    assert isinstance(result.content_blocks[-1], TextContent)
    assert result.content_blocks[-1].text == LIMIT_NOTICE
    assert LIMIT_NOTICE in result.text


@pytest.mark.asyncio
async def test_should_end_with_limit_notice_when_model_turn_is_only_a_tool_call() -> None:
    result = await _run_agent([_tool_call_turn(narration=None)], max_iterations=1)

    assert result.text == LIMIT_NOTICE


@pytest.mark.asyncio
async def test_should_not_duplicate_final_answer_when_model_answers_within_the_limit() -> None:
    answer = "The uuid is 22771659-2cf2-4b66-8043-a1393ad20fab."

    result = await _run_agent(
        [_tool_call_turn(narration="Fetching it now."), AIMessage(content=answer)],
        max_iterations=5,
    )

    text_blocks = [block.text for block in result.content_blocks if isinstance(block, TextContent)]
    assert text_blocks == ["Fetching it now.", answer]
    assert LIMIT_NOTICE not in result.text
