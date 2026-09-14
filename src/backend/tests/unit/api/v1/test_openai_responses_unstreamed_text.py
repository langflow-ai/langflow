"""Text that was never token-streamed must still reach OpenAI Responses stream consumers.

The stream converter blanks the ``text`` of an ``add_message`` whose ``state`` is
``complete`` on the assumption that token events already delivered it. That holds only
for the message that actually streamed: the token events and the complete message of
one producer share a message id. Blanking every complete message dropped the answer of
runs that never streamed (a Chat Output fed by a Prompt or any other non-streaming
component, an agent driven by a model whose Stream toggle is off); blanking on any
earlier token dropped the Chat Output that re-publishes a streamed agent answer through
a Prompt under its own id. These tests drive the real event pipeline (event manager ->
v1 projection -> converter) and pin the contract:

- no tokens streamed: the complete message's text is emitted, once;
- tokens streamed: the complete message carrying the same id is never repeated, even
  when its text differs from the concatenated tokens (the duplication the skip was
  written for); a Chat Output wired straight to the agent re-publishes under that id;
- a complete message under another id is new content, unless its text is what the
  client already has (exactly, or modulo whitespace);
- tool steps and usage carried by a complete message are handled either way;
- a Language Model streaming into Chat Output: the first chunk, which Chat Output
  publishes both as a partial add_message and as the first token event, goes out once.
"""

from __future__ import annotations

import json
import time
from types import SimpleNamespace
from typing import TYPE_CHECKING
from uuid import uuid4

from langflow.api.v1 import openai_responses
from langflow.schema import OpenAIResponsesRequest
from lfx.schema.content_types import TextContent, ToolContent
from lfx.schema.message import Message

from tests.unit.build_utils import create_flow

if TYPE_CHECKING:
    import pytest

FLOW_INPUT = "what is in openrag?"
ANSWER = "OpenRAG indexes 3 documents."
USAGE = {"input_tokens": 12, "output_tokens": 7, "total_tokens": 19}
AGENT_MESSAGE_ID = str(uuid4())
CHAT_OUTPUT_MESSAGE_ID = str(uuid4())


class Token:
    """A ``token`` event frame. Plain ``Message`` frames are ``add_message`` events.

    Token events carry the id of the stored message they belong to (``Component._process_chunk``
    for a streaming model feeding Chat Output, ``lfx.base.agents.events`` for an agent);
    ``id_=None`` models a producer that streams without one.
    """

    def __init__(self, chunk: str, *, id_: str | None = AGENT_MESSAGE_ID) -> None:
        self.chunk = chunk
        self.message_id = id_


def _flow(owner_id):
    return SimpleNamespace(
        id=uuid4(),
        user_id=owner_id,
        workspace_id=None,
        folder_id=None,
        data={"nodes": [{"data": {"type": "ChatInput"}}, {"data": {"type": "ChatOutput"}}]},
    )


def _user_message() -> Message:
    return Message(sender="User", sender_name="User", text=FLOW_INPUT, session_id="session-1", id=str(uuid4()))


def _ai_message(
    text: str,
    *,
    state: str,
    sender_name: str = "AI",
    blocks: list | None = None,
    usage: dict | None = None,
    id_: str | None = CHAT_OUTPUT_MESSAGE_ID,
) -> Message:
    properties: dict = {"icon": "Bot", "state": state}
    if usage is not None:
        properties["usage"] = usage
    return Message(
        sender="Machine",
        sender_name=sender_name,
        text=text,
        content_blocks=list(blocks or []),
        properties=properties,
        session_id="session-1",
        **({"id": id_} if id_ is not None else {}),
    )


def _agent_message(blocks: list, *, state: str) -> Message:
    """The agent's live shape: ``text=""`` and the answer carried as a ``TextContent`` block."""
    return _ai_message("", state=state, sender_name="Agent", blocks=blocks, id_=AGENT_MESSAGE_ID)


def _finished_tool() -> ToolContent:
    return ToolContent(name="search_docs", tool_input={"query": "openrag"}, output="3 documents", error=None)


def _pending_tool() -> ToolContent:
    """The tool step as on_chat_model_end appends it: decided by the model, not yet run."""
    return ToolContent(name="search_docs", tool_input={"query": "openrag"}, output=None, error=None)


def _fake_run_flow_generator(frames: list[Message | Token]):
    """Stand in for run_flow_generator: publish the frames through the real event manager."""

    async def run(**kwargs):
        event_manager = kwargs["event_manager"]
        for frame in frames:
            if isinstance(frame, Token):
                token_data: dict = {"chunk": frame.chunk}
                if frame.message_id is not None:
                    token_data["id"] = frame.message_id
                event_manager.on_token(data=token_data)
            else:
                # Mirror Component._send_message_event: the stored id is lifted to the top level.
                message_data = frame.model_dump()
                if frame.get_id() and not message_data.get("id"):
                    message_data["id"] = str(frame.get_id())
                event_manager.on_message(data=message_data)
        await event_manager.queue.put((None, None, time.time()))

    return run


def _parse_sse(wire: str) -> list[dict]:
    events = []
    for chunk in wire.split("\n\n"):
        lines = [line for line in chunk.splitlines() if line.strip()]
        if not lines:
            continue
        event_name = None
        data = None
        for line in lines:
            if line.startswith("event: "):
                event_name = line[len("event: ") :]
            elif line.startswith("data: "):
                payload = line[len("data: ") :]
                data = None if payload == "[DONE]" else json.loads(payload)
        events.append({"event": event_name, "data": data})
    return events


async def _stream(monkeypatch: pytest.MonkeyPatch, frames: list[Message | Token]) -> list[dict]:
    owner_id = uuid4()
    flow = _flow(owner_id)
    monkeypatch.setattr(openai_responses, "run_flow_generator", _fake_run_flow_generator(frames))
    request = OpenAIResponsesRequest(model=str(flow.id), input=FLOW_INPUT, stream=True)
    response = await openai_responses.run_flow_for_openai_responses(
        flow=flow, request=request, api_key_user=SimpleNamespace(id=owner_id), stream=True
    )
    wire = "".join([chunk async for chunk in response.body_iterator])
    return _parse_sse(wire)


def _deltas(events: list[dict]) -> list[str]:
    """The non-empty ``delta.content`` chunks, in wire order."""
    return [
        e["data"]["delta"]["content"]
        for e in events
        if e["event"] is None and e["data"] and e["data"].get("delta", {}).get("content")
    ]


def _content(events: list[dict]) -> str:
    """The text a Responses client assembles from the ``delta.content`` chunks."""
    return "".join(_deltas(events))


def _completed_usage(events: list[dict]):
    completed = [e["data"] for e in events if e["event"] == "response.completed"]
    assert len(completed) == 1
    return completed[0]["response"]["usage"]


def _function_calls(events: list[dict]) -> tuple[list[dict], list[dict]]:
    added = [e["data"]["item"] for e in events if e["event"] == "response.output_item.added"]
    done = [e["data"]["item"] for e in events if e["event"] == "response.output_item.done"]
    return added, done


# --- nothing was token-streamed: the complete message is the only carrier of the text ---


async def test_stream_emits_complete_message_text_when_nothing_was_streamed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prompt -> Chat Output, or any non-streaming producer: one complete message, no tokens."""
    frames = [_user_message(), _ai_message(ANSWER, state="complete", usage=USAGE)]

    events = await _stream(monkeypatch, frames)

    assert _content(events) == ANSWER
    assert _completed_usage(events) == USAGE
    assert events[-1] == {"event": None, "data": None}  # [DONE]


async def test_stream_emits_complete_message_text_exactly_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Chat Output republishes the same complete message once usage is attached; no repeat."""
    frames = [_ai_message(ANSWER, state="complete"), _ai_message(ANSWER, state="complete", usage=USAGE)]

    events = await _stream(monkeypatch, frames)

    assert _content(events) == ANSWER
    assert _completed_usage(events) == USAGE


async def test_stream_emits_complete_message_text_after_empty_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty token events deliver no text and must not suppress the completed answer."""
    frames = [Token(""), Token(""), _ai_message(ANSWER, state="complete", usage=USAGE)]

    events = await _stream(monkeypatch, frames)

    assert _content(events) == ANSWER
    assert _completed_usage(events) == USAGE
    assert events[-1] == {"event": None, "data": None}  # [DONE]


async def test_stream_agent_without_token_stream_emits_text_and_tool_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Agent on a non-streaming model: partial frames carry the tool step, the answer lands on complete."""
    tool = _finished_tool()
    frames = [
        _agent_message([], state="partial"),
        _agent_message([tool], state="partial"),
        _agent_message([tool, TextContent(text=ANSWER)], state="complete"),
        _ai_message(ANSWER, state="complete"),  # downstream Chat Output republishes the answer
    ]

    events = await _stream(monkeypatch, frames)
    added, done = _function_calls(events)

    assert _content(events) == ANSWER
    assert len(added) == 1
    assert len(done) == 1
    assert done[0]["status"] == "completed"


# --- tokens were streamed: the complete message only repeats what the client already has ---


async def test_stream_does_not_repeat_complete_message_after_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    frames = [
        _agent_message([], state="partial"),
        Token(""),
        Token("OpenRAG indexes "),
        Token(""),
        Token("3 documents."),
        Token(""),
        _agent_message([_finished_tool(), TextContent(text=ANSWER)], state="complete"),
        _ai_message(ANSWER, state="complete", usage=USAGE),
    ]

    events = await _stream(monkeypatch, frames)
    added, _done = _function_calls(events)

    assert _content(events) == ANSWER
    assert _completed_usage(events) == USAGE
    assert len(added) == 1  # tool steps on the complete frame are still projected


async def test_stream_skips_complete_message_whose_text_differs_from_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    """The case the skip was written for: a final text that is not a prefix-extension of the tokens.

    The agent's complete message and the Chat Output wired straight to it both carry the
    agent's message id: Chat Output stores the very ``Message`` it received, so
    ``astore_message`` updates the existing row instead of minting one. Re-emitting either
    would append the whole answer to the end of the stream a second time.
    """
    frames = [
        Token("OpenRAG indexes "),
        Token("3 documents."),
        _agent_message([TextContent(text=ANSWER.strip("."))], state="complete"),
        _ai_message(ANSWER.strip("."), state="complete", id_=AGENT_MESSAGE_ID),
    ]

    events = await _stream(monkeypatch, frames)

    assert _content(events) == ANSWER


# --- tokens were streamed by one message; a complete message under another id is its own carrier ---

REFORMATTED = f"Final answer: {ANSWER}"


async def test_stream_emits_chat_output_text_reformatted_downstream_of_streamed_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Agent (streaming) -> Prompt -> Chat Output: the Chat Output stores a new row under its own id.

    Its text is the answer the flow declares and is new to the client, so it follows the
    agent tokens. Those tokens are already on the wire when the Chat Output message arrives;
    holding them back would mean buffering the whole response, so the stream carries both.
    """
    frames = [
        _agent_message([], state="partial"),
        Token("OpenRAG indexes "),
        Token("3 documents."),
        _agent_message([TextContent(text=ANSWER)], state="complete"),
        _ai_message(REFORMATTED, state="complete"),
        _ai_message(REFORMATTED, state="complete", usage=USAGE),  # re-sent once usage is attached
    ]

    events = await _stream(monkeypatch, frames)

    assert _content(events) == ANSWER + REFORMATTED
    assert _completed_usage(events) == USAGE


async def test_stream_does_not_repeat_streamed_text_stored_under_new_id_modulo_whitespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Chat Output that mints its own row for an unchanged upstream answer is not new content.

    Token concatenation and the stored text can differ by whitespace alone; that must not
    trip the full-text reset and append the answer a second time.
    """
    frames = [
        Token("OpenRAG indexes "),
        Token("3 documents."),
        _agent_message([TextContent(text=ANSWER)], state="complete"),
        _ai_message(f"  {ANSWER}\n", state="complete", usage=USAGE),
    ]

    events = await _stream(monkeypatch, frames)

    assert _content(events) == ANSWER
    assert _completed_usage(events) == USAGE


async def test_stream_does_not_repeat_last_round_text_stored_under_new_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """An agent's tokens span every model round; its final text is the last round only.

    A Chat Output storing that final text under a new id has nothing the client lacks. The
    text-less partial frame between the rounds (a tool step) must not reset the delta
    baseline, or the last round would be re-sent in full.
    """
    frames = [
        _agent_message([], state="partial"),
        Token("Let me check. "),
        _agent_message([_finished_tool()], state="partial"),
        Token("OpenRAG indexes "),
        Token("3 documents."),
        _agent_message([_finished_tool(), TextContent(text=ANSWER)], state="complete"),
        _ai_message(ANSWER, state="complete", usage=USAGE),
    ]

    events = await _stream(monkeypatch, frames)

    assert _content(events) == "Let me check. " + ANSWER
    assert _completed_usage(events) == USAGE


async def test_stream_blanks_only_the_message_that_streamed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Language Model (streaming) -> Chat Output: tokens and the complete message share the Chat Output's id.

    A further complete message in the same run keeps its text.
    """
    frames = [
        Token("OpenRAG indexes ", id_=CHAT_OUTPUT_MESSAGE_ID),
        Token("3 documents.", id_=CHAT_OUTPUT_MESSAGE_ID),
        _ai_message(ANSWER, state="complete", usage=USAGE),
        _ai_message("Sources: 3.", state="complete", id_=str(uuid4())),
    ]

    events = await _stream(monkeypatch, frames)

    assert _content(events) == ANSWER + "Sources: 3."
    assert _completed_usage(events) == USAGE


async def test_stream_pairs_id_less_tokens_with_id_less_complete_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """A producer streaming outside ``send_message`` carries no id on either event; they still pair up."""
    frames = [
        Token("OpenRAG indexes ", id_=None),
        Token("3 documents.", id_=None),
        _ai_message(ANSWER.strip("."), state="complete", id_=None),
    ]

    events = await _stream(monkeypatch, frames)

    assert _content(events) == ANSWER


# --- a Language Model streams into Chat Output: the first chunk is published twice ---


async def test_stream_emits_first_streamed_chunk_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Language Model -> Chat Output: the first chunk is published twice, the client gets it once.

    Chat Output publishes the first chunk as a partial add_message (text=chunk) and, right after,
    as the first token event of the same message. The partial goes out as soon as it arrives, so
    the client never waits; the token repeating it is dropped.
    """
    frames = [
        _ai_message("Hel", state="partial"),
        Token("Hel", id_=CHAT_OUTPUT_MESSAGE_ID),
        Token("lo", id_=CHAT_OUTPUT_MESSAGE_ID),
        _ai_message("Hello", state="complete", usage=USAGE),
    ]

    events = await _stream(monkeypatch, frames)

    assert _deltas(events) == ["Hel", "lo"]
    assert _completed_usage(events) == USAGE


async def test_stream_forwards_tokens_that_diverge_from_partial_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """A token stream that does not repeat the partial text is forwarded whole: never drop text."""
    frames = [
        _ai_message("Hel", state="partial"),
        Token("Xy", id_=CHAT_OUTPUT_MESSAGE_ID),
        Token("z", id_=CHAT_OUTPUT_MESSAGE_ID),
        _ai_message("HelXyz", state="complete"),
    ]

    events = await _stream(monkeypatch, frames)

    assert _deltas(events) == ["Hel", "Xy", "z"]


# --- agent interim text: published after its tokens (streaming) or as the only carrier (not) ---


async def test_stream_agent_interim_text_after_tokens_is_not_repeated(monkeypatch: pytest.MonkeyPatch) -> None:
    """Agent on a streaming model: each round's text is republished as a partial after its tokens.

    Neither that partial nor the next round's tokens may be repeated or dropped.
    """
    frames = [
        _agent_message([], state="partial"),
        Token("Let me check."),
        _agent_message([TextContent(text="Let me check."), _pending_tool()], state="partial"),
        _agent_message([TextContent(text="Let me check."), _finished_tool()], state="partial"),
        Token(" 3 documents."),
        _agent_message(
            [TextContent(text="Let me check."), _finished_tool(), TextContent(text=" 3 documents.")],
            state="partial",
        ),
        _agent_message(
            [TextContent(text="Let me check."), _finished_tool(), TextContent(text=" 3 documents.")],
            state="complete",
        ),
        _ai_message("Let me check. 3 documents.", state="complete", usage=USAGE),
    ]

    events = await _stream(monkeypatch, frames)
    added, done = _function_calls(events)

    assert _deltas(events) == ["Let me check.", " 3 documents."]
    assert _completed_usage(events) == USAGE
    assert len(added) == 1
    assert done[0]["status"] == "completed"


async def test_stream_agent_without_token_stream_emits_interim_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """Agent on a non-streaming model: the partials are the only carrier of each round's text."""
    frames = [
        _agent_message([], state="partial"),
        _agent_message([TextContent(text="Let me check."), _pending_tool()], state="partial"),
        _agent_message([TextContent(text="Let me check."), _finished_tool()], state="partial"),
        _agent_message(
            [TextContent(text="Let me check."), _finished_tool(), TextContent(text=" 3 documents.")],
            state="partial",
        ),
        _agent_message(
            [TextContent(text="Let me check."), _finished_tool(), TextContent(text=" 3 documents.")],
            state="complete",
        ),
        _ai_message("Let me check. 3 documents.", state="complete", usage=USAGE),
    ]

    events = await _stream(monkeypatch, frames)
    added, _done = _function_calls(events)

    assert _deltas(events) == ["Let me check.", " 3 documents."]
    assert _completed_usage(events) == USAGE
    assert len(added) == 1


# --- end to end: the real event pipeline on an LLM-free flow ---


async def _responses_stream_content(client, api_key: str, flow_id: str, input_text: str) -> tuple[str, list[str]]:
    payload = {"model": flow_id, "input": input_text, "stream": True}
    content: list[str] = []
    raw_lines: list[str] = []
    async with client.stream("POST", "/api/v1/responses", json=payload, headers={"x-api-key": api_key}) as response:
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("text/event-stream")
        async for line in response.aiter_lines():
            raw_lines.append(line)
            if not line.startswith("data: ") or line == "data: [DONE]":
                continue
            data = json.loads(line[len("data: ") :])
            chunk = (data.get("delta") or {}).get("content")
            if chunk:
                content.append(chunk)
    return "".join(content), raw_lines


async def test_responses_stream_delivers_non_streamed_chat_output_text(
    client, created_api_key, json_memory_chatbot_no_llm, logged_in_headers
) -> None:
    """Chat Input -> Prompt -> Chat Output: no model, no tokens, the answer arrives as one complete message."""
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)

    content, raw_lines = await _responses_stream_content(
        client, created_api_key.api_key, str(flow_id), "hello from the responses api"
    )

    assert "User: hello from the responses api" in content, raw_lines
    assert content.rstrip().endswith("AI:"), content
    assert "data: [DONE]" in raw_lines
