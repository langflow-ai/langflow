"""Message rows keep every LangChain message whole across a loop flow's edges."""

import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from lfx.base.agents.context_messages import messages_to_table
from lfx.base.agents.loop_rows import is_answer, messages_to_rows, row_to_message, rows_to_messages
from lfx.schema.dataframe import DataFrame


def test_rows_keep_the_whole_message_through_json():
    call = {"name": "echo", "args": {"text": "hi"}, "id": "call_1"}
    messages = [
        HumanMessage(content="go"),
        AIMessage(content="Let me echo", tool_calls=[call], id="ai-1"),
        ToolMessage(content="echo hi", tool_call_id="call_1"),
    ]

    rows = messages_to_rows(messages)
    back = rows_to_messages(DataFrame(json.loads(json.dumps(rows))))

    assert [(r["sender"], r["text"]) for r in rows] == [("User", "go"), ("Machine", "Let me echo"), ("Tool", "echo hi")]
    assert back == messages


def test_an_agent_context_table_reads_as_the_same_messages():
    messages = [HumanMessage(content=[{"type": "text", "text": "look"}]), AIMessage("seen")]

    assert rows_to_messages(messages_to_table(messages)) == messages


@pytest.mark.parametrize(
    ("sender", "kind"),
    [
        ("User", HumanMessage),
        ("Machine", AIMessage),
        ("AI", AIMessage),
        ("System", SystemMessage),
        (None, HumanMessage),
    ],
)
def test_a_chat_row_becomes_the_message_of_its_sender(sender, kind):
    message = row_to_message({"text": "hello", "sender": sender})

    assert type(message) is kind
    assert message.content == "hello"


@pytest.mark.parametrize("text", [None, float("nan")])
def test_a_row_without_text_is_an_empty_message_not_the_word_none(text):
    assert row_to_message({"text": text, "sender": "User"}).content == ""


def test_only_an_ai_message_without_tool_calls_is_an_answer():
    asks = AIMessage("", tool_calls=[{"name": "echo", "args": {}, "id": "c1"}])

    assert is_answer(AIMessage(""))
    assert not is_answer(asks)
    assert not is_answer(ToolMessage("done", tool_call_id="c1"))
    assert not is_answer(HumanMessage("done"))
