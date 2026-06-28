"""Lothal LLM gateway tests (Story U.3).

The gateway is an OpenAI-compatible `/v1/chat/completions` pass-through Open
Design's agent calls. These pin its contract: it forwards the request body
verbatim (model/tools/stream untouched), swaps in the upstream credential,
streams the reply back, carries its own optional bearer (not the Lothal session
auth), and 503s until the upstream is configured.
"""

import json

import httpx
import pytest
import respx
from fastapi import status
from httpx import AsyncClient

GATEWAY_PATH = "api/v1/lothal/gateway/v1/chat/completions"
UPSTREAM_BASE = "https://upstream.test/v1"
UPSTREAM_URL = f"{UPSTREAM_BASE}/chat/completions"

# A representative OpenAI request carrying tools + a tool-call turn — the exact
# shape the pass-through must relay byte-for-byte (model, tools, history intact).
SAMPLE_REQUEST = {
    "model": "claude-opus-4-8",
    "messages": [{"role": "user", "content": "design a login screen"}],
    "tools": [{"type": "function", "function": {"name": "write_file", "parameters": {}}}],
    "tool_choice": "auto",
    "stream": False,
}


@pytest.fixture
def _configured(monkeypatch):
    """Configure a working upstream (no inbound token → auth disabled)."""
    monkeypatch.setenv("LOTHAL_GATEWAY_UPSTREAM_BASE_URL", UPSTREAM_BASE)
    monkeypatch.setenv("LOTHAL_GATEWAY_UPSTREAM_API_KEY", "upstream-secret-key")
    monkeypatch.delenv("LOTHAL_GATEWAY_TOKEN", raising=False)


@pytest.mark.usefixtures("_configured")
async def test_forwards_request_verbatim_with_upstream_key(client: AsyncClient):
    """The body is relayed unchanged and the upstream sees the upstream credential."""
    with respx.mock:
        route = respx.post(UPSTREAM_URL).mock(return_value=httpx.Response(200, json={"id": "cmpl-1", "choices": []}))
        raw = json.dumps(SAMPLE_REQUEST).encode()
        resp = await client.post(GATEWAY_PATH, content=raw, headers={"content-type": "application/json"})

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == {"id": "cmpl-1", "choices": []}

    sent = route.calls.last.request
    # Verbatim: the forwarded bytes equal what we posted — model, tools, and the
    # tool-call turn all survive unmodified (no re-serialization, no injection).
    assert sent.content == raw
    assert json.loads(sent.content) == SAMPLE_REQUEST
    # The inbound Authorization is replaced by the upstream key, never relayed.
    assert sent.headers["authorization"] == "Bearer upstream-secret-key"


@pytest.mark.usefixtures("_configured")
async def test_streams_sse_response_through(client: AsyncClient):
    """A `stream: true` reply flows back as text/event-stream, chunk for chunk."""
    sse_body = b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\ndata: [DONE]\n\n'
    with respx.mock:
        respx.post(UPSTREAM_URL).mock(
            return_value=httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=sse_body,
            )
        )
        resp = await client.post(
            GATEWAY_PATH,
            content=json.dumps({**SAMPLE_REQUEST, "stream": True}).encode(),
            headers={"content-type": "application/json"},
        )

    assert resp.status_code == status.HTTP_200_OK
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert resp.content == sse_body


@pytest.mark.usefixtures("_configured")
async def test_upstream_status_and_error_body_pass_through(client: AsyncClient):
    """A non-2xx upstream reply (status + body) is relayed unchanged, not masked."""
    with respx.mock:
        respx.post(UPSTREAM_URL).mock(return_value=httpx.Response(429, json={"error": {"message": "rate limited"}}))
        resp = await client.post(
            GATEWAY_PATH,
            content=json.dumps(SAMPLE_REQUEST).encode(),
            headers={"content-type": "application/json"},
        )

    assert resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert resp.json() == {"error": {"message": "rate limited"}}


async def test_503_when_no_backend_configured(client: AsyncClient, monkeypatch):
    """Neither metered upstream nor subscription token → a 503 (setup gap), never a 500."""
    monkeypatch.delenv("LOTHAL_GATEWAY_UPSTREAM_BASE_URL", raising=False)
    monkeypatch.delenv("LOTHAL_GATEWAY_UPSTREAM_API_KEY", raising=False)
    monkeypatch.delenv("LOTHAL_GATEWAY_TOKEN", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    resp = await client.post(
        GATEWAY_PATH,
        content=json.dumps(SAMPLE_REQUEST).encode(),
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


@pytest.mark.usefixtures("_configured")
async def test_502_when_upstream_unreachable(client: AsyncClient):
    """A transport failure to the upstream surfaces as a 502, not a 500."""
    with respx.mock:
        respx.post(UPSTREAM_URL).mock(side_effect=httpx.ConnectError("boom"))
        resp = await client.post(
            GATEWAY_PATH,
            content=json.dumps(SAMPLE_REQUEST).encode(),
            headers={"content-type": "application/json"},
        )
    assert resp.status_code == status.HTTP_502_BAD_GATEWAY


async def test_inbound_token_enforced_when_set(client: AsyncClient, monkeypatch):
    """With LOTHAL_GATEWAY_TOKEN set, a missing/bad bearer is 401; the match is 200."""
    monkeypatch.setenv("LOTHAL_GATEWAY_UPSTREAM_BASE_URL", UPSTREAM_BASE)
    monkeypatch.setenv("LOTHAL_GATEWAY_UPSTREAM_API_KEY", "upstream-secret-key")
    monkeypatch.setenv("LOTHAL_GATEWAY_TOKEN", "od-inbound-token")
    raw = json.dumps(SAMPLE_REQUEST).encode()
    json_ct = {"content-type": "application/json"}

    # No bearer → 401.
    resp = await client.post(GATEWAY_PATH, content=raw, headers=json_ct)
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    # Wrong bearer → 401.
    resp = await client.post(GATEWAY_PATH, content=raw, headers={**json_ct, "authorization": "Bearer nope"})
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    # Correct bearer → forwarded.
    with respx.mock:
        respx.post(UPSTREAM_URL).mock(return_value=httpx.Response(200, json={"ok": True}))
        resp = await client.post(
            GATEWAY_PATH, content=raw, headers={**json_ct, "authorization": "Bearer od-inbound-token"}
        )
    assert resp.status_code == status.HTTP_200_OK


@pytest.mark.usefixtures("_configured")
async def test_no_inbound_token_means_auth_disabled(client: AsyncClient):
    """With no LOTHAL_GATEWAY_TOKEN, a call with no Authorization still forwards.

    Access then rests on the private compose network (OD's own posture) — the
    gateway must not hard-require a bearer when none is configured.
    """
    with respx.mock:
        respx.post(UPSTREAM_URL).mock(return_value=httpx.Response(200, json={"ok": True}))
        resp = await client.post(
            GATEWAY_PATH,
            content=json.dumps(SAMPLE_REQUEST).encode(),
            headers={"content-type": "application/json"},
        )
    assert resp.status_code == status.HTTP_200_OK


async def test_openapi_lists_gateway_route(client: AsyncClient):
    """The pass-through is advertised on the OpenAPI surface."""
    schema = (await client.get("openapi.json")).json()
    assert "/api/v1/lothal/gateway/v1/chat/completions" in schema["paths"]
