"""Lothal LLM gateway — an OpenAI-compatible endpoint for Open Design (Story U.3).

Open Design (OD) drives the prototype stage by spawning a coding agent that runs
a tool loop and makes its own LLM calls. To keep *every* model call observable
and centrally controlled by Lothal (rather than letting OD's agent talk to a
provider directly), OD's OpenAI-compatible agent (`codex`) is pointed at this
endpoint via `agentCliEnv.codex.OPENAI_BASE_URL` + `OPENAI_API_KEY`.

The endpoint has **two backends**, chosen by config at call time:

1. **Subscription** (default) — when no metered upstream is configured, requests
   run on the Claude Code subscription (`CLAUDE_CODE_OAUTH_TOKEN`, the same
   credential the chat provider uses). The subscription speaks Anthropic's
   Messages API, not OpenAI's, so `subscription_gateway` translates OpenAI ⇄
   Anthropic (incl. `tools`/tool-calls and streaming). This is the no-extra-cost
   path: OD runs on the existing subscription.
2. **Metered pass-through** — when ``LOTHAL_GATEWAY_UPSTREAM_BASE_URL`` is set,
   the request body is relayed **verbatim** (model/`tools`/tool-calls/`stream`
   untouched, no injection) to that OpenAI-compatible upstream with
   ``LOTHAL_GATEWAY_UPSTREAM_API_KEY``. Use this to run OD on a metered key
   (OpenAI, Anthropic's OpenAI-compat endpoint, a local model, …) instead.

Both are distinct from the Lothal *chat* provider (`langflow.lothal.llm`, Story
0.1, `LOTHAL_LLM_PROVIDER`/`LOTHAL_MODEL_NAME`), which runs Lothal's own phase
engines via the Agent SDK — that two-path split is the Story 0.1 reconciliation
U.3 calls for.

Configuration (env, read at call time):

- ``CLAUDE_CODE_OAUTH_TOKEN`` — subscription token; enables backend (1).
- ``LOTHAL_GATEWAY_UPSTREAM_BASE_URL`` / ``LOTHAL_GATEWAY_UPSTREAM_API_KEY`` —
  metered upstream; when both set, takes precedence (backend 2).
- ``LOTHAL_GATEWAY_TOKEN`` — inbound bearer the caller (OD's ``OPENAI_API_KEY``)
  must present. When unset, inbound auth is disabled and access rests on the
  private compose network (the same posture OD itself ships with); set it for
  defense-in-depth.

With neither backend configured the endpoint returns ``503``.

Auth model: this router does **not** use the Lothal session auth
(``get_current_active_user``) — OD's agent is an internal service client with no
user session. It carries its own optional bearer check instead.
"""

from __future__ import annotations

import json
import os
import secrets
from typing import TYPE_CHECKING

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response, StreamingResponse
from lfx.log.logger import logger

from langflow.lothal.subscription_gateway import proxy_subscription, resolve_subscription_token

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

# Mounted at /api/v1 → /api/v1/lothal/gateway/v1. OpenAI clients append
# `/chat/completions` to their configured base URL, so OD's `OPENAI_BASE_URL` is
# `http://<backend>/api/v1/lothal/gateway/v1` and the call lands on the route
# below — i.e. the `/v1/chat/completions` pass-through the contract specifies.
router = APIRouter(prefix="/lothal/gateway/v1", tags=["Lothal"])

# Connect quickly, but never time out the read: an agentic streaming completion
# can run for minutes and the gateway must not sever it mid-tool-loop.
_TIMEOUT = httpx.Timeout(connect=10.0, read=None, write=None, pool=None)

# Hop-by-hop / framing headers we must NOT relay: they describe a single
# connection's transport, and re-emitting them across the proxy corrupts the
# response (e.g. a stale Content-Length on a re-streamed body). Lowercased.
_HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
        "content-length",
        "content-encoding",
    }
)


def _metered_upstream() -> tuple[str, str] | None:
    """The metered upstream (base URL, key) if both are configured, else `None`.

    A configured metered upstream takes precedence over the subscription backend.
    `None` means "not configured" — the caller falls back to the subscription.
    """
    base_url = (os.getenv("LOTHAL_GATEWAY_UPSTREAM_BASE_URL") or "").strip()
    api_key = (os.getenv("LOTHAL_GATEWAY_UPSTREAM_API_KEY") or "").strip()
    if not base_url or not api_key:
        return None
    return base_url.rstrip("/"), api_key


def _check_inbound_auth(request: Request) -> None:
    """Enforce the optional inbound bearer (`LOTHAL_GATEWAY_TOKEN`).

    When the token is unset, auth is disabled and access rests on the private
    compose network — the same model OD ships with (`OD_DISABLE_API_AUTH`). When
    set, the caller must present it as `Authorization: Bearer <token>` (this is
    OD's `OPENAI_API_KEY`); a missing or mismatched token is a 401. Compared with
    `secrets.compare_digest` to avoid leaking the token via timing.
    """
    expected = (os.getenv("LOTHAL_GATEWAY_TOKEN") or "").strip()
    if not expected:
        return
    header = request.headers.get("authorization", "")
    scheme, _, presented = header.partition(" ")
    if scheme.lower() != "bearer" or not secrets.compare_digest(presented.strip(), expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing gateway token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _model_for_log(body: bytes) -> str:
    """Best-effort `model` from the request body, for the transit log only.

    Parsed from a copy purely to log; the forwarded bytes are never touched, so a
    malformed/odd body still passes through verbatim and just logs as `unknown`.
    """
    try:
        return str(json.loads(body).get("model", "unknown"))
    except (ValueError, AttributeError, TypeError):
        return "unknown"


def _response_headers(upstream: httpx.Response) -> dict[str, str]:
    """Relay the upstream response headers minus hop-by-hop/framing ones.

    Content-Type is preserved so the client sees `text/event-stream` for a
    streamed reply and `application/json` otherwise; Starlette sets the framing
    headers (Content-Length / Transfer-Encoding) itself.
    """
    return {k: v for k, v in upstream.headers.items() if k.lower() not in _HOP_BY_HOP}


@router.post("/chat/completions", summary="OpenAI-compatible chat completions for Open Design")
async def chat_completions(request: Request) -> Response:
    """Serve an OpenAI chat-completions call on the configured backend.

    Dispatches by config: a metered upstream (if set) forwards the call verbatim;
    otherwise the subscription backend translates it to Anthropic and runs it on
    `CLAUDE_CODE_OAUTH_TOKEN`. With neither configured, returns `503`. Streaming
    and tool-calls work on both paths. Every call is logged as it transits (the
    U.3 verification hook).
    """
    _check_inbound_auth(request)
    body = await request.body()

    metered = _metered_upstream()
    if metered is not None:
        logger.info(f"lothal gateway (metered) → model={_model_for_log(body)}, {len(body)} bytes")
        return await _proxy_verbatim(body, request.headers.get("accept", "application/json"), metered)

    token = resolve_subscription_token()
    if token is not None:
        try:
            openai_body = json.loads(body)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Request body must be valid JSON.",
            ) from exc
        logger.info(f"lothal gateway (subscription) → model={_model_for_log(body)}, {len(body)} bytes")
        return await proxy_subscription(openai_body, token)

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=(
            "The LLM gateway is not configured: set CLAUDE_CODE_OAUTH_TOKEN (subscription) "
            "or LOTHAL_GATEWAY_UPSTREAM_BASE_URL + LOTHAL_GATEWAY_UPSTREAM_API_KEY (metered)."
        ),
    )


async def _proxy_verbatim(body: bytes, accept: str, upstream_cfg: tuple[str, str]) -> Response:
    """Relay the request body unchanged to a metered OpenAI-compatible upstream.

    The body is forwarded byte-for-byte (model/`tools`/tool-calls/`stream` intact);
    only the `Authorization` header is swapped for the upstream key. The reply is
    streamed back raw, so SSE and plain JSON both pass through untouched.
    """
    base_url, api_key = upstream_cfg
    upstream_url = f"{base_url}/chat/completions"
    headers = {
        "authorization": f"Bearer {api_key}",
        "content-type": "application/json",
        "accept": accept,
    }

    # One client owned by the request; closed when the stream generator finishes
    # (or on an early send failure below).
    client = httpx.AsyncClient(timeout=_TIMEOUT)
    try:
        upstream_req = client.build_request("POST", upstream_url, headers=headers, content=body)
        upstream = await client.send(upstream_req, stream=True)
    except httpx.HTTPError as exc:
        await client.aclose()
        # Log the detail (operator-visible) but don't leak the exception string —
        # which can carry the upstream URL/host — into the client-facing response.
        logger.warning(f"lothal gateway upstream request failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gateway upstream request failed.",
        ) from exc

    async def _stream() -> AsyncIterator[bytes]:
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    return StreamingResponse(
        _stream(),
        status_code=upstream.status_code,
        headers=_response_headers(upstream),
    )
