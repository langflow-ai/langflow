"""Tests for the A2A Agent component's SSRF / api-key hardening.

The a2a SDK lives in ``langflow-base`` (not ``lfx``), so the SDK flow itself is not
exercised here. What matters for security is the httpx client the component hands to the
SDK, so these tests drive that client directly against real localhost servers:

- it pins the configured ``x-api-key`` to the ``agent_url`` origin (card GET + same-origin
  POST carry it),
- it blocks any off-origin hop (a card declaring an RPC url on a different host/port), so
  the api key can never leak there,
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


async def test_api_key_pinned_to_agent_origin_and_off_origin_blocked(monkeypatch):
    """The api key reaches the agent origin (card + RPC) but never an off-origin RPC url."""
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    # Allowlist loopback so the legit path is reachable; origins still differ by port,
    # which is what the off-origin guard must catch.
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

            # Card-declared RPC url on a DIFFERENT origin: blocked before it leaves.
            with pytest.raises(SSRFProtectionError):
                await client.post(f"http://127.0.0.1:{attacker.port}/rpc", json={"hello": "world"})

    assert [m for m, _p, _h in agent.received] == ["GET", "POST"]
    assert all(h.get("x-api-key") == "super-secret" for _m, _p, h in agent.received)
    # The off-origin host was never contacted, so the key never leaked there.
    assert attacker.received == []


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
