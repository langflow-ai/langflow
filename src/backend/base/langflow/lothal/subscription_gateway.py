"""Subscription-backed LLM gateway — OpenAI ⇄ Anthropic translation (Story U.3).

This is the gateway path that lets Open Design's OpenAI-compatible agent run on the
Claude Code **subscription** (the `CLAUDE_CODE_OAUTH_TOKEN`) instead of a metered
key. The subscription OAuth token can't be proxied verbatim — it speaks Anthropic's
Messages API, not OpenAI's chat-completions — so this module translates:

    OpenAI /v1/chat/completions request  ──►  Anthropic /v1/messages request
    Anthropic Messages reply (or SSE)    ──►  OpenAI chat-completion (or SSE chunks)

and authenticates the Anthropic call with the OAuth token as a Bearer plus the
`anthropic-beta: oauth-2025-04-20` header (the same credential the chat provider's
Agent SDK uses, here driven over raw HTTP). Function-calling is preserved end to
end: OpenAI `tools`/`tool_calls`/`tool` turns map to Anthropic
`tools`/`tool_use`/`tool_result`, so the agent's tool loop stays intact. No
system-prompt injection is needed — the OAuth path accepts the caller's system
prompt as-is, so OD's design-system prompt is forwarded unchanged.

The translation functions are pure and unit-tested; `proxy_subscription` wires them
to the live Anthropic endpoint.
"""

from __future__ import annotations

import json
import os
import time
from typing import TYPE_CHECKING, Any

import httpx
from fastapi import status
from fastapi.responses import JSONResponse, Response, StreamingResponse
from lfx.log.logger import logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
# Anthropic requires max_tokens; OpenAI treats it as optional. Default when absent.
_DEFAULT_MAX_TOKENS = 4096
# Connect fast, never time out the read (agentic completions stream for minutes).
_TIMEOUT = httpx.Timeout(connect=10.0, read=None, write=None, pool=None)

# Anthropic stop_reason → OpenAI finish_reason.
_FINISH_REASON = {
    "end_turn": "stop",
    "stop_sequence": "stop",
    "max_tokens": "length",
    "tool_use": "tool_calls",
}


def resolve_subscription_token() -> str | None:
    """The Claude Code subscription OAuth token, or `None` if not set.

    Reads `CLAUDE_CODE_OAUTH_TOKEN` — the same long-lived `claude setup-token`
    credential the chat provider uses (so the gateway and the phase engines share
    one subscription config). Returned stripped; blank is treated as unset.
    """
    token = (os.getenv("CLAUDE_CODE_OAUTH_TOKEN") or "").strip()
    return token or None


def _text_of(content: Any) -> str:
    """Flatten OpenAI message content (string or content-part list) to plain text.

    OpenAI content is either a string or a list of typed parts; we keep the text
    parts (the shape codex sends). Non-text parts (e.g. images) are dropped here —
    the prototype agent's traffic is text — rather than failing the call.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"
        )
    return ""


def _tool_to_anthropic(tool: dict[str, Any]) -> dict[str, Any]:
    """OpenAI function tool → Anthropic tool (`parameters` becomes `input_schema`)."""
    fn = tool.get("function", {})
    return {
        "name": fn.get("name"),
        "description": fn.get("description", ""),
        "input_schema": fn.get("parameters") or {"type": "object", "properties": {}},
    }


def _tool_choice_to_anthropic(choice: Any) -> dict[str, Any] | None:
    """OpenAI `tool_choice` → Anthropic `tool_choice`.

    `auto`→auto, `required`→any, `none`→none, and a named function → that tool.
    An unrecognised value yields `None` (omit), so Anthropic falls back to auto.
    """
    if choice == "auto":
        return {"type": "auto"}
    if choice == "required":
        return {"type": "any"}
    if choice == "none":
        return {"type": "none"}
    if isinstance(choice, dict) and choice.get("type") == "function":
        return {"type": "tool", "name": choice.get("function", {}).get("name")}
    return None


def build_anthropic_request(openai_body: dict[str, Any]) -> dict[str, Any]:
    """Translate an OpenAI chat-completions body into an Anthropic Messages body.

    Handles the full conversation shape codex sends: system turns are lifted into
    Anthropic's top-level `system`; assistant `tool_calls` become `tool_use`
    blocks; and `tool` result turns are merged into a single following `user` turn
    of `tool_result` blocks (Anthropic groups tool results that way). Sampling
    params and `stream` pass through; `stop` maps to `stop_sequences`.
    """
    out: dict[str, Any] = {
        "model": openai_body.get("model"),
        "max_tokens": openai_body.get("max_tokens") or openai_body.get("max_completion_tokens") or _DEFAULT_MAX_TOKENS,
    }

    system_texts: list[str] = []
    messages: list[dict[str, Any]] = []
    pending_tool_results: list[dict[str, Any]] = []

    def flush_tool_results() -> None:
        if pending_tool_results:
            messages.append({"role": "user", "content": list(pending_tool_results)})
            pending_tool_results.clear()

    for message in openai_body.get("messages", []):
        role = message.get("role")
        if role == "system":
            text = _text_of(message.get("content"))
            if text:
                system_texts.append(text)
        elif role == "tool":
            pending_tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": message.get("tool_call_id"),
                    "content": _text_of(message.get("content")),
                }
            )
        elif role == "assistant":
            flush_tool_results()
            blocks: list[dict[str, Any]] = []
            text = _text_of(message.get("content"))
            if text:
                blocks.append({"type": "text", "text": text})
            for call in message.get("tool_calls") or []:
                fn = call.get("function", {})
                try:
                    parsed = json.loads(fn.get("arguments") or "{}")
                except (ValueError, TypeError):
                    parsed = {}
                blocks.append({"type": "tool_use", "id": call.get("id"), "name": fn.get("name"), "input": parsed})
            messages.append({"role": "assistant", "content": blocks or ""})
        else:  # user (and any other role treated as user input)
            flush_tool_results()
            messages.append({"role": "user", "content": _text_of(message.get("content"))})

    flush_tool_results()
    out["messages"] = messages

    if system_texts:
        out["system"] = "\n\n".join(system_texts)
    if openai_body.get("tools"):
        out["tools"] = [_tool_to_anthropic(t) for t in openai_body["tools"]]
    tool_choice = _tool_choice_to_anthropic(openai_body.get("tool_choice"))
    if tool_choice is not None:
        out["tool_choice"] = tool_choice
    for key in ("temperature", "top_p"):
        if key in openai_body:
            out[key] = openai_body[key]
    if "stop" in openai_body and openai_body["stop"] is not None:
        stop = openai_body["stop"]
        out["stop_sequences"] = [stop] if isinstance(stop, str) else stop
    if openai_body.get("stream"):
        out["stream"] = True
    return out


def anthropic_message_to_openai(adata: dict[str, Any]) -> dict[str, Any]:
    """Translate a (non-streaming) Anthropic Messages reply into an OpenAI completion."""
    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    for block in adata.get("content", []):
        if block.get("type") == "text":
            text_parts.append(block.get("text", ""))
        elif block.get("type") == "tool_use":
            tool_calls.append(
                {
                    "id": block.get("id"),
                    "type": "function",
                    "function": {"name": block.get("name"), "arguments": json.dumps(block.get("input", {}))},
                }
            )

    message: dict[str, Any] = {"role": "assistant", "content": "".join(text_parts) or None}
    if tool_calls:
        message["tool_calls"] = tool_calls

    usage = adata.get("usage", {})
    prompt_tokens = usage.get("input_tokens", 0)
    completion_tokens = usage.get("output_tokens", 0)
    return {
        "id": f"chatcmpl-{adata.get('id', '')}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": adata.get("model"),
        "choices": [
            {"index": 0, "message": message, "finish_reason": _FINISH_REASON.get(adata.get("stop_reason"), "stop")}
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def _chunk(cid: str, created: int, model: str | None, delta: dict[str, Any], finish: str | None) -> bytes:
    """One OpenAI `chat.completion.chunk` SSE frame."""
    payload = {
        "id": cid,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }
    return f"data: {json.dumps(payload)}\n\n".encode()


async def translate_stream(lines: AsyncIterator[str]) -> AsyncIterator[bytes]:
    """Translate an Anthropic Messages SSE stream into OpenAI chat-completion chunks.

    Consumes Anthropic events (`message_start`, `content_block_start/delta/stop`,
    `message_delta`, `message_stop`) and emits OpenAI `chat.completion.chunk`
    frames, ending with `data: [DONE]`. Text deltas become `delta.content`;
    `tool_use` blocks become `delta.tool_calls` (the Anthropic content-block index
    is remapped to OpenAI's separate tool-call index space, and `input_json_delta`
    fragments stream as incremental `function.arguments`).
    """
    cid = "chatcmpl-stream"
    created = int(time.time())
    model: str | None = None
    finish: str | None = None
    tool_index_for_block: dict[int, int] = {}
    next_tool_index = 0
    role_sent = False

    for_each: AsyncIterator[str] = lines
    async for line in for_each:
        if not line.startswith("data:"):
            continue
        raw = line[len("data:") :].strip()
        if not raw:
            continue
        try:
            event = json.loads(raw)
        except ValueError:
            continue
        etype = event.get("type")

        if etype == "message_start":
            msg = event.get("message", {})
            model = msg.get("model")
            if msg.get("id"):
                cid = f"chatcmpl-{msg['id']}"
            yield _chunk(cid, created, model, {"role": "assistant"}, None)
            role_sent = True
        elif etype == "content_block_start":
            block = event.get("content_block", {})
            if block.get("type") == "tool_use":
                oi = next_tool_index
                next_tool_index += 1
                tool_index_for_block[event.get("index")] = oi
                delta = {
                    "tool_calls": [
                        {
                            "index": oi,
                            "id": block.get("id"),
                            "type": "function",
                            "function": {"name": block.get("name"), "arguments": ""},
                        }
                    ]
                }
                yield _chunk(cid, created, model, delta, None)
        elif etype == "content_block_delta":
            delta = event.get("delta", {})
            if delta.get("type") == "text_delta":
                if not role_sent:
                    yield _chunk(cid, created, model, {"role": "assistant"}, None)
                    role_sent = True
                yield _chunk(cid, created, model, {"content": delta.get("text", "")}, None)
            elif delta.get("type") == "input_json_delta":
                oi = tool_index_for_block.get(event.get("index"), 0)
                tool_delta = {"tool_calls": [{"index": oi, "function": {"arguments": delta.get("partial_json", "")}}]}
                yield _chunk(cid, created, model, tool_delta, None)
        elif etype == "message_delta":
            stop_reason = event.get("delta", {}).get("stop_reason")
            if stop_reason:
                finish = _FINISH_REASON.get(stop_reason, "stop")
        elif etype == "message_stop":
            yield _chunk(cid, created, model, {}, finish or "stop")
            yield b"data: [DONE]\n\n"
            return

    # Stream ended without an explicit message_stop — still terminate cleanly.
    yield _chunk(cid, created, model, {}, finish or "stop")
    yield b"data: [DONE]\n\n"


def _anthropic_headers(token: str) -> dict[str, str]:
    """Auth + version headers for an OAuth-subscription Messages call."""
    return {
        "authorization": f"Bearer {token}",
        "anthropic-version": "2023-06-01",
        "anthropic-beta": "oauth-2025-04-20",
        "content-type": "application/json",
    }


async def proxy_subscription(openai_body: dict[str, Any], token: str) -> Response:
    """Run an OpenAI chat-completions request against Anthropic on the subscription.

    Translates the request, calls the Messages API with the OAuth token, and
    translates the reply back — streaming (`text/event-stream`) when the caller
    asked for it, a single JSON completion otherwise. A non-200 from Anthropic is
    relayed with its status and body (so the agent sees the real error).
    """
    stream = bool(openai_body.get("stream"))
    anthropic_body = build_anthropic_request(openai_body)
    headers = _anthropic_headers(token)

    client = httpx.AsyncClient(timeout=_TIMEOUT)
    try:
        request = client.build_request("POST", ANTHROPIC_MESSAGES_URL, headers=headers, json=anthropic_body)
        upstream = await client.send(request, stream=True)
    except httpx.HTTPError as exc:
        await client.aclose()
        # Log the detail (operator-visible) but don't leak the exception string —
        # which can carry the upstream URL/host — into the client-facing body.
        logger.warning(f"lothal subscription gateway request failed: {exc}")
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"error": {"message": "Gateway upstream request failed.", "type": "upstream_error"}},
        )

    if upstream.status_code != status.HTTP_200_OK:
        body = await upstream.aread()
        await upstream.aclose()
        await client.aclose()
        return Response(content=body, status_code=upstream.status_code, media_type="application/json")

    if not stream:
        body = await upstream.aread()
        await upstream.aclose()
        await client.aclose()
        return JSONResponse(content=anthropic_message_to_openai(json.loads(body)))

    async def _gen() -> AsyncIterator[bytes]:
        try:
            async for chunk in translate_stream(upstream.aiter_lines()):
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    return StreamingResponse(_gen(), media_type="text/event-stream")


async def proxy_anthropic_passthrough(
    body: bytes,
    token: str,
    *,
    anthropic_beta: str | None = None,
    accept: str = "application/json",
) -> Response:
    """Forward a native Anthropic Messages request, injecting the subscription auth.

    Open Design's `claude` agent (the Claude Code CLI) speaks the Anthropic Messages
    API directly, so — unlike `proxy_subscription` — there is nothing to translate.
    This is a thin reverse proxy: it strips the caller's placeholder credential and
    injects the real OAuth subscription token (+ the `oauth-2025-04-20` beta), then
    forwards the body **verbatim** to the Messages API and relays the reply (SSE or
    JSON) unchanged — `stream` is whatever the caller put in the body. The caller's
    own `anthropic-beta` values are preserved and the oauth beta is added.
    """
    betas = ["oauth-2025-04-20"]
    if anthropic_beta:
        for raw in anthropic_beta.split(","):
            beta = raw.strip()
            if beta and beta not in betas:
                betas.append(beta)
    headers = {
        "authorization": f"Bearer {token}",
        "anthropic-version": "2023-06-01",
        "anthropic-beta": ",".join(betas),
        "content-type": "application/json",
        "accept": accept,
    }

    client = httpx.AsyncClient(timeout=_TIMEOUT)
    try:
        request = client.build_request("POST", ANTHROPIC_MESSAGES_URL, headers=headers, content=body)
        upstream = await client.send(request, stream=True)
    except httpx.HTTPError as exc:
        await client.aclose()
        logger.warning(f"lothal anthropic passthrough request failed: {exc}")
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"error": {"message": "Gateway upstream request failed.", "type": "upstream_error"}},
        )

    async def _gen() -> AsyncIterator[bytes]:
        try:
            # `aiter_bytes` yields the decompressed body (Anthropic gzips JSON
            # replies); relaying raw bytes without the `content-encoding` header
            # would hand the client undecodable gzip.
            async for chunk in upstream.aiter_bytes():
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    # Relay the upstream Content-Type (text/event-stream for a streamed reply,
    # application/json otherwise) and status. Also relay backoff/debug headers on
    # 429/5xx (retry-after, anthropic rate-limit, request-id) so callers keep the
    # same retry signal as the native Messages endpoint. Drop hop-by-hop / framing
    # headers and content-encoding/length (the body is decompressed; Starlette
    # re-frames). Content-Type is passed via media_type, so skip it here.
    drop_headers = {
        "content-encoding",
        "content-length",
        "content-type",
        "transfer-encoding",
        "connection",
        "keep-alive",
    }
    passthrough = {k: v for k, v in upstream.headers.items() if k.lower() not in drop_headers}
    return StreamingResponse(
        _gen(),
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/json"),
        headers=passthrough,
    )
