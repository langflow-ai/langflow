"""Subscription-backed LLM gateway tests (Story U.3).

Two layers: the pure OpenAI ⇄ Anthropic translation functions, and the gateway
endpoint running its subscription backend against a mocked Anthropic Messages API.
The subscription path lets Open Design's OpenAI agent run on the Claude Code
subscription (`CLAUDE_CODE_OAUTH_TOKEN`) with tool-calls and streaming intact.
"""

import json

import httpx
import pytest
import respx
from fastapi import status
from httpx import AsyncClient
from langflow.lothal.subscription_gateway import (
    ANTHROPIC_MESSAGES_URL,
    anthropic_message_to_openai,
    build_anthropic_request,
    translate_stream,
)

GATEWAY_PATH = "api/v1/lothal/gateway/v1/chat/completions"


# --- pure translation: OpenAI request → Anthropic request --------------------


def test_build_request_lifts_system_and_defaults_max_tokens():
    out = build_anthropic_request(
        {
            "model": "claude-opus-4-8",
            "messages": [
                {"role": "system", "content": "You design UIs."},
                {"role": "user", "content": "a login screen"},
            ],
        }
    )
    assert out["model"] == "claude-opus-4-8"
    assert out["system"] == "You design UIs."  # lifted out of messages
    assert out["messages"] == [{"role": "user", "content": "a login screen"}]
    assert out["max_tokens"] == 4096  # Anthropic requires it; defaulted when absent


def test_build_request_maps_tools_and_tool_choice():
    out = build_anthropic_request(
        {
            "model": "m",
            "max_tokens": 100,
            "messages": [{"role": "user", "content": "hi"}],
            "tools": [
                {
                    "type": "function",
                    "function": {"name": "write_file", "description": "Write", "parameters": {"type": "object"}},
                }
            ],
            "tool_choice": "required",
        }
    )
    assert out["tools"] == [{"name": "write_file", "description": "Write", "input_schema": {"type": "object"}}]
    assert out["tool_choice"] == {"type": "any"}  # OpenAI "required" → Anthropic "any"
    assert out["max_tokens"] == 100


def test_build_request_translates_assistant_tool_calls_and_tool_results():
    """An OpenAI tool-call turn + tool result round-trips into Anthropic blocks."""
    out = build_anthropic_request(
        {
            "model": "m",
            "messages": [
                {"role": "user", "content": "weather in Paris?"},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "get_weather", "arguments": '{"city": "Paris"}'},
                        }
                    ],
                },
                {"role": "tool", "tool_call_id": "call_1", "content": "sunny, 22C"},
            ],
        }
    )
    assert out["messages"] == [
        {"role": "user", "content": "weather in Paris?"},
        {
            "role": "assistant",
            "content": [{"type": "tool_use", "id": "call_1", "name": "get_weather", "input": {"city": "Paris"}}],
        },
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "call_1", "content": "sunny, 22C"}]},
    ]


def test_build_request_maps_stop_to_stop_sequences():
    out = build_anthropic_request({"model": "m", "messages": [{"role": "user", "content": "x"}], "stop": "END"})
    assert out["stop_sequences"] == ["END"]


# --- pure translation: Anthropic reply → OpenAI completion --------------------


def test_anthropic_reply_to_openai_text():
    openai = anthropic_message_to_openai(
        {
            "id": "msg_1",
            "model": "claude-opus-4-8",
            "content": [{"type": "text", "text": "Hello!"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 3},
        }
    )
    assert openai["object"] == "chat.completion"
    assert openai["id"] == "chatcmpl-msg_1"
    choice = openai["choices"][0]
    assert choice["message"] == {"role": "assistant", "content": "Hello!"}
    assert choice["finish_reason"] == "stop"
    assert openai["usage"] == {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13}


def test_anthropic_reply_to_openai_tool_use():
    openai = anthropic_message_to_openai(
        {
            "id": "msg_2",
            "model": "m",
            "content": [{"type": "tool_use", "id": "toolu_1", "name": "get_weather", "input": {"city": "Paris"}}],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 5, "output_tokens": 8},
        }
    )
    choice = openai["choices"][0]
    assert choice["finish_reason"] == "tool_calls"
    assert choice["message"]["content"] is None
    assert choice["message"]["tool_calls"] == [
        {"id": "toolu_1", "type": "function", "function": {"name": "get_weather", "arguments": '{"city": "Paris"}'}}
    ]


# --- pure translation: streaming ---------------------------------------------


async def _lines(*events: dict) -> "object":
    """Yield Anthropic SSE `data:` lines for the given event dicts."""
    for event in events:
        yield f"data: {json.dumps(event)}"


async def _collect(stream) -> list[dict]:
    """Decode an OpenAI chunk stream into parsed JSON payloads (dropping [DONE])."""
    out = []
    async for raw in stream:
        text = raw.decode().removeprefix("data: ").strip()
        if text and text != "[DONE]":
            out.append(json.loads(text))
    return out


async def test_translate_stream_text():
    chunks = await _collect(
        translate_stream(
            _lines(
                {"type": "message_start", "message": {"id": "msg_1", "model": "m"}},
                {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
                {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Hi"}},
                {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": " there"}},
                {"type": "message_delta", "delta": {"stop_reason": "end_turn"}},
                {"type": "message_stop"},
            )
        )
    )
    # role chunk, two content deltas, final finish chunk.
    assert chunks[0]["choices"][0]["delta"] == {"role": "assistant"}
    assert "".join(c["choices"][0]["delta"].get("content", "") for c in chunks) == "Hi there"
    assert chunks[-1]["choices"][0]["finish_reason"] == "stop"
    assert all(c["object"] == "chat.completion.chunk" for c in chunks)


async def test_translate_stream_tool_use():
    chunks = await _collect(
        translate_stream(
            _lines(
                {"type": "message_start", "message": {"id": "msg_2", "model": "m"}},
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {"type": "tool_use", "id": "toolu_1", "name": "get_weather"},
                },
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "input_json_delta", "partial_json": '{"city"'},
                },
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "input_json_delta", "partial_json": ': "Paris"}'},
                },
                {"type": "message_delta", "delta": {"stop_reason": "tool_use"}},
                {"type": "message_stop"},
            )
        )
    )
    tool_deltas = [tc for c in chunks for tc in c["choices"][0]["delta"].get("tool_calls", [])]
    # First carries id+name at index 0; the rest stream the arguments JSON.
    assert tool_deltas[0]["index"] == 0
    assert tool_deltas[0]["id"] == "toolu_1"
    assert tool_deltas[0]["function"]["name"] == "get_weather"
    args = "".join(tc["function"].get("arguments", "") for tc in tool_deltas)
    assert json.loads(args) == {"city": "Paris"}
    assert chunks[-1]["choices"][0]["finish_reason"] == "tool_calls"


# --- endpoint: subscription backend (mocked Anthropic) -----------------------


@pytest.fixture
def _subscription(monkeypatch):
    """Subscription backend on, metered upstream off."""
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "sub-oauth-token")
    monkeypatch.delenv("LOTHAL_GATEWAY_UPSTREAM_BASE_URL", raising=False)
    monkeypatch.delenv("LOTHAL_GATEWAY_UPSTREAM_API_KEY", raising=False)
    monkeypatch.delenv("LOTHAL_GATEWAY_TOKEN", raising=False)


@pytest.mark.usefixtures("_subscription")
async def test_subscription_non_stream_translates_both_ways(client: AsyncClient):
    """A non-stream call hits Anthropic with the OAuth bearer and returns OpenAI JSON."""
    with respx.mock:
        route = respx.post(ANTHROPIC_MESSAGES_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "msg_9",
                    "model": "claude-opus-4-8",
                    "content": [{"type": "text", "text": "pong"}],
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 4, "output_tokens": 1},
                },
            )
        )
        resp = await client.post(
            GATEWAY_PATH,
            content=json.dumps(
                {"model": "claude-opus-4-8", "messages": [{"role": "user", "content": "ping"}]}
            ).encode(),
            headers={"content-type": "application/json"},
        )

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["object"] == "chat.completion"
    assert data["choices"][0]["message"]["content"] == "pong"

    sent = route.calls.last.request
    assert sent.headers["authorization"] == "Bearer sub-oauth-token"
    assert sent.headers["anthropic-beta"] == "oauth-2025-04-20"
    # Body was translated to Anthropic shape (messages preserved, max_tokens added).
    body = json.loads(sent.content)
    assert body["messages"] == [{"role": "user", "content": "ping"}]
    assert "max_tokens" in body


@pytest.mark.usefixtures("_subscription")
async def test_subscription_streams_translated_chunks(client: AsyncClient):
    """A stream call returns OpenAI SSE chunks translated from Anthropic events."""
    events = [
        {"type": "message_start", "message": {"id": "m", "model": "x"}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "hi"}},
        {"type": "message_delta", "delta": {"stop_reason": "end_turn"}},
        {"type": "message_stop"},
    ]
    sse = "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()
    with respx.mock:
        respx.post(ANTHROPIC_MESSAGES_URL).mock(
            return_value=httpx.Response(200, headers={"content-type": "text/event-stream"}, content=sse)
        )
        resp = await client.post(
            GATEWAY_PATH,
            content=json.dumps(
                {"model": "x", "stream": True, "messages": [{"role": "user", "content": "hi"}]}
            ).encode(),
            headers={"content-type": "application/json"},
        )

    assert resp.status_code == status.HTTP_200_OK
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert "chat.completion.chunk" in resp.text
    assert "data: [DONE]" in resp.text


async def test_metered_upstream_takes_precedence_over_subscription(client: AsyncClient, monkeypatch):
    """When both are configured, the metered upstream wins (Anthropic is not called)."""
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "sub-oauth-token")
    monkeypatch.setenv("LOTHAL_GATEWAY_UPSTREAM_BASE_URL", "https://metered.test/v1")
    monkeypatch.setenv("LOTHAL_GATEWAY_UPSTREAM_API_KEY", "metered-key")
    monkeypatch.delenv("LOTHAL_GATEWAY_TOKEN", raising=False)
    with respx.mock:
        metered = respx.post("https://metered.test/v1/chat/completions").mock(
            return_value=httpx.Response(200, json={"id": "x", "choices": []})
        )
        anthropic = respx.post(ANTHROPIC_MESSAGES_URL).mock(return_value=httpx.Response(200, json={}))
        resp = await client.post(
            GATEWAY_PATH,
            content=json.dumps({"model": "m", "messages": [{"role": "user", "content": "hi"}]}).encode(),
            headers={"content-type": "application/json"},
        )

    assert resp.status_code == status.HTTP_200_OK
    assert metered.called
    assert not anthropic.called
