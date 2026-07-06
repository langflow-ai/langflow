"""Tests for the A2A Agent component's SSRF / api-key hardening.

The a2a SDK lives in ``langflow-base`` (not ``lfx``), so the SDK flow itself is not
exercised here. What matters for security is the httpx client the component hands to the
SDK, so these tests drive that client directly against real localhost servers:

- it pins the configured ``x-api-key`` to the ``agent_url`` origin (card GET + same-origin
  POST carry it),
- it strips the configured ``x-api-key`` on any off-origin hop (a card declaring an RPC url
  on a different host/port), so the key can never leak there, while still SSRF-validating that
  off-origin target (an internal/metadata target is blocked),
- an internal/loopback ``agent_url`` is rejected by SSRF protection before any call.
"""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from lfx.components.models_and_agents.a2a_agent import A2AAgentComponent, build_a2a_client
from lfx.utils.ssrf_protection import SSRFProtectionError, validate_and_resolve_url


class _RecordingHandler(BaseHTTPRequestHandler):
    """Records every request's path + headers and replies 200 with an empty JSON body."""

    def _handle(self):
        self.server.received.append((self.command, self.path, dict(self.headers)))
        body = b"{}"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._handle()

    def do_POST(self):
        self._handle()

    def log_message(self, *args):  # silence test server logging
        pass


class _Server:
    def __init__(self):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _RecordingHandler)
        self.httpd.received = []
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()

    @property
    def port(self):
        return self.httpd.server_address[1]

    @property
    def received(self):
        return self.httpd.received


async def test_api_key_pinned_to_agent_origin_off_origin_stripped(monkeypatch):
    """The api key reaches the agent origin (card + RPC) but is stripped on any off-origin hop."""
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    # Allowlist loopback so both servers are reachable; the two origins still differ by port,
    # which is what the off-origin guard keys on to strip the api key.
    monkeypatch.setenv("LANGFLOW_SSRF_ALLOWED_HOSTS", "127.0.0.1")

    with _Server() as agent, _Server() as attacker:
        agent_url = f"http://127.0.0.1:{agent.port}"
        _url, validated_ips = validate_and_resolve_url(agent_url)

        client = build_a2a_client(agent_url, validated_ips, api_key="super-secret", timeout=10)
        async with client:
            # Card fetch (same origin) carries the api key.
            card = await client.get(f"{agent_url}/.well-known/agent-card.json")
            assert card.status_code == 200

            # Same-origin message/send POST also carries the api key.
            ok = await client.post(f"{agent_url}/rpc", json={"hello": "world"})
            assert ok.status_code == 200

            # Card-declared RPC url on a DIFFERENT origin: spec allows a cross-origin service
            # url, so the call goes through, but the api key is stripped first.
            off = await client.post(f"http://127.0.0.1:{attacker.port}/rpc", json={"hello": "world"})
            assert off.status_code == 200

    assert [m for m, _p, _h in agent.received] == ["GET", "POST"]
    assert all(h.get("x-api-key") == "super-secret" for _m, _p, h in agent.received)
    # The off-origin host was contacted, but the key was stripped, so it never leaked.
    assert [m for m, _p, _h in attacker.received] == ["POST"]
    assert all(h.get("x-api-key") is None for _m, _p, h in attacker.received)


async def test_off_origin_internal_target_blocked(monkeypatch):
    """An off-origin hop to an internal/metadata IP is SSRF-validated by the hook and blocked."""
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    # Allowlist only loopback, so the agent is reachable but the metadata IP is not.
    monkeypatch.setenv("LANGFLOW_SSRF_ALLOWED_HOSTS", "127.0.0.1")

    with _Server() as agent:
        agent_url = f"http://127.0.0.1:{agent.port}"
        _url, validated_ips = validate_and_resolve_url(agent_url)

        client = build_a2a_client(agent_url, validated_ips, api_key="super-secret", timeout=10)
        async with client:
            # The transport never pins this host, so the hook is the only SSRF check; it must
            # block the metadata IP before any connection opens.
            with pytest.raises(SSRFProtectionError):
                await client.post("http://169.254.169.254/rpc", json={"hello": "world"})


async def test_loopback_agent_url_rejected_by_ssrf(monkeypatch):
    """A loopback / metadata agent_url is rejected before any outbound call."""
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    monkeypatch.delenv("LANGFLOW_SSRF_ALLOWED_HOSTS", raising=False)

    component = A2AAgentComponent(
        agent_url="http://169.254.169.254/latest/meta-data/",
        input_value="hi",
    )
    with pytest.raises(ValueError, match="SSRF"):
        await component.send_to_agent()


# --- External mode: agent card preview -------------------------------------


class _CardHandler(BaseHTTPRequestHandler):
    """Serves a fixed agent card for any GET (the preview fetches /.well-known/agent-card.json)."""

    _CARD = (
        b'{"name":"Echo","version":"1.0.0","description":"Echoes messages.",'
        b'"skills":[{"inputSchema":{"properties":{"input_value":{},"session_id":{}},"required":["input_value"]}}],'
        b'"security":[{"apiKey":[]}]}'
    )

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(self._CARD)))
        self.end_headers()
        self.wfile.write(self._CARD)

    def log_message(self, *args):
        pass


class _CardServer:
    def __init__(self):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _CardHandler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()

    @property
    def port(self):
        return self.httpd.server_address[1]


def test_card_html_renders_summary():
    """The card summary shows identity, the input contract (required marked), and the auth hint."""
    card = {
        "name": "Billing Agent",
        "version": "1.2.0",
        "description": "Handles refunds.",
        "skills": [{"inputSchema": {"properties": {"input_value": {}, "session_id": {}}, "required": ["input_value"]}}],
        "security": [{"apiKey": []}],
    }
    html = A2AAgentComponent._card_html(card)
    assert "<b>Billing Agent</b>" in html
    assert "v1.2.0" in html
    assert "Handles refunds." in html
    assert "input_value*" in html
    assert "session_id" in html
    assert "Requires an API key" in html


async def test_external_card_preview_fetches_and_renders(monkeypatch):
    """Entering a reachable agent URL fetches its card and renders the summary under the field."""
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_SSRF_ALLOWED_HOSTS", "127.0.0.1")

    with _CardServer() as server:
        url = f"http://127.0.0.1:{server.port}"
        component = A2AAgentComponent(mode="External", agent_url=url, input_value="hi")
        build_config = {"agent_url": {}}
        await component._apply_external_card(build_config, url)

    helper_text = build_config["agent_url"]["helper_text"]
    assert "<b>Echo</b>" in helper_text
    assert "v1.0.0" in helper_text
    assert "Requires an API key" in helper_text


async def test_external_card_preview_bad_url_no_crash(monkeypatch):
    """A blocked/unreachable URL degrades to no preview instead of raising in the editor."""
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    monkeypatch.delenv("LANGFLOW_SSRF_ALLOWED_HOSTS", raising=False)

    component = A2AAgentComponent(mode="External", agent_url="http://127.0.0.1:1/x", input_value="hi")
    build_config = {"agent_url": {}}
    await component._apply_external_card(build_config, "http://127.0.0.1:1/x")
    assert build_config["agent_url"]["helper_text"] == ""
