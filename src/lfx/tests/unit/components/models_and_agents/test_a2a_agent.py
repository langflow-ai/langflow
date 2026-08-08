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

import contextlib
import ipaddress
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import pytest
from lfx.components.models_and_agents.a2a_agent import (
    A2AAgentComponent,
    _agent_base_url,
    _resolve_card_bounded,
    build_a2a_client,
)
from lfx.utils.ssrf_protection import SSRFProtectionError, validate_and_resolve_url


def _resolve_public(host, *_args, **_kwargs):
    """socket.getaddrinfo stub: hostnames resolve to a public IP, literal IPs to themselves."""
    try:
        ipaddress.ip_address(host)
    except ValueError:
        ip = "93.184.216.34"  # hostname -> public IP (passes SSRF, not in any blocked range)
    else:
        ip = host  # literal IP -> itself
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    return [(family, socket.SOCK_STREAM, 6, "", (ip, 0))]


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


async def test_off_origin_internal_target_blocked_with_ssrf_toggle_off(monkeypatch):
    """A card-controlled off-origin internal target is blocked even with the SSRF toggle off.

    validate_and_resolve_url returns [] with no enforcement when the toggle is off; the
    toggle-independent floor still rejects non-allowlisted internal IPs, mirroring the webhook path.
    """
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "false")
    monkeypatch.delenv("LANGFLOW_SSRF_ALLOWED_HOSTS", raising=False)

    agent_url = "http://127.0.0.1:9"  # discard port; only the off-origin hop matters here
    _url, validated_ips = validate_and_resolve_url(agent_url)  # [] (toggle off)
    client = build_a2a_client(agent_url, validated_ips, api_key="super-secret", timeout=2)
    async with client:
        with pytest.raises(SSRFProtectionError):
            await client.post("http://169.254.169.254/rpc", json={"hello": "world"})


async def test_off_origin_host_is_dns_pinned_to_validated_ip(monkeypatch):
    """An off-origin hop pins the validated IP into the transport, closing the DNS-rebind window.

    The hook validates the off-origin host and writes the cleared IPs into the transport's
    pin map before httpx connects, so the connection can't be rebound to an internal target
    between validation and connect. The connect to the (unreachable-in-test) public IP then
    fails; the recorded pin is the security-relevant effect we assert.
    """
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    # Allowlist loopback so the agent origin is trusted (validated_ips empty); the off-origin
    # host is the one that must be validated + pinned.
    monkeypatch.setenv("LANGFLOW_SSRF_ALLOWED_HOSTS", "127.0.0.1")

    agent_url = "http://127.0.0.1:9"  # discard port; only the off-origin hop matters here
    _url, validated_ips = validate_and_resolve_url(agent_url)
    client = build_a2a_client(agent_url, validated_ips, api_key="super-secret", timeout=2)

    with patch("socket.getaddrinfo", side_effect=_resolve_public):
        async with client:
            with contextlib.suppress(Exception):
                await client.post("http://remote-agent.example/rpc", json={"hello": "world"})

    assert client._transport.pinned_ips.get("remote-agent.example") == ["93.184.216.34"]


async def test_agent_url_idn_seeded_under_punycode_key():
    """An IDN agent_url is seeded under the punycode raw_host the transport connects with.

    httpcore connects to ``xn--exmple-cua.com``, not the unicode ``exämple.com``; keying the pin
    by the unicode host would store it where the transport never looks, silently bypassing the pin.
    """
    async with build_a2a_client("http://exämple.com", ["93.184.216.34"], timeout=2) as client:
        assert client._transport.pinned_ips == {"xn--exmple-cua.com": ["93.184.216.34"]}


async def test_off_origin_idn_host_pinned_under_punycode_key(monkeypatch):
    """An off-origin IDN hop pins under the punycode raw_host, so the pin matches the connect host."""
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_SSRF_ALLOWED_HOSTS", "127.0.0.1")

    agent_url = "http://127.0.0.1:9"
    _url, validated_ips = validate_and_resolve_url(agent_url)
    client = build_a2a_client(agent_url, validated_ips, api_key="super-secret", timeout=2)

    with patch("socket.getaddrinfo", side_effect=_resolve_public):
        async with client:
            with contextlib.suppress(Exception):
                await client.post("http://exämple.com/rpc", json={"hello": "world"})

    assert client._transport.pinned_ips.get("xn--exmple-cua.com") == ["93.184.216.34"]
    assert "exämple.com" not in client._transport.pinned_ips


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
        # Strict path: only the real well-known URL serves the card, so a double-appended
        # ".../.well-known/agent-card.json/.well-known/agent-card.json" 404s and is caught.
        if self.path != "/.well-known/agent-card.json":
            self.send_response(404)
            self.end_headers()
            return
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


def test_card_payload_renders_sections():
    """The card payload carries identity, the input contract (required marked), and the auth badge."""
    card = {
        "name": "Billing Agent",
        "version": "1.2.0",
        "description": "Handles refunds.",
        "skills": [
            {
                "name": "refund",
                "inputSchema": {"properties": {"input_value": {}, "session_id": {}}, "required": ["input_value"]},
            }
        ],
        "security": [{"apiKey": []}],
    }
    payload = A2AAgentComponent._card_payload(card)
    assert payload["title"] == "Billing Agent"
    assert payload["version"] == "1.2.0"
    blob = json.dumps(payload)
    assert "Handles refunds." in blob
    # input_value is a field marked required; session_id is a field that isn't.
    assert "input_value" in blob
    assert '"required": true' in blob
    assert "session_id" in blob
    # skill name renders as a card title; auth leads the quick-facts chips.
    assert "refund" in blob
    assert "Requires an API key" in blob


def test_card_payload_tolerates_malformed_card():
    """A card from a remote server may be malformed; the payload must degrade, not raise."""
    card = {
        "name": "Weird Agent",
        "capabilities": ["not-a-dict"],
        "skills": [
            1,
            2,
            {
                "name": "ok",
                # properties is a dict but a spec value is a non-dict string: rendering the field
                # list must not crash on spec.get("type") for the bad entry.
                "inputSchema": {"properties": {"q": {"type": "string"}, "bad": "notadict"}, "required": "nope"},
            },
        ],
    }
    payload = A2AAgentComponent._card_payload(card)
    assert payload["title"] == "Weird Agent"
    assert isinstance(payload["sections"], list)
    blob = json.dumps(payload)
    # Garbage skill entries are dropped; the one valid skill still surfaces.
    assert "ok" in blob
    # The valid field renders; the non-dict spec degrades to an empty type instead of raising.
    assert "q" in blob


@pytest.mark.parametrize(
    "card",
    [
        [1, 2, 3],  # not even a dict
        "a string card",
        5,
        {"skills": 5},  # a non-iterable scalar where a list is expected
        {"skills": True},
        {"skills": "abc"},  # iterable but not a list of skill dicts
        {"skills": {"a": 1}},
        # required carries an unhashable entry; properties carries a non-dict spec.
        {"skills": [{"inputSchema": {"required": [["x"]], "properties": {"q": {"type": "s"}}}}]},
        {"skills": [{"inputSchema": {"required": [1, 2], "properties": {"a": "notadict"}}}]},
        {"capabilities": 5, "security": [], "preferredTransport": {"x": 1}, "protocolVersion": ["a"]},
    ],
)
def test_card_payload_never_raises_on_malformed_card(card):
    """A remote card is untrusted input: any shape must degrade to a payload, never raise."""
    payload = A2AAgentComponent._card_payload(card)
    assert isinstance(payload, dict)
    assert isinstance(payload["sections"], list)


def test_agent_card_field_type_is_builder_accepted():
    """The agent_card display field must use a type the graph builder accepts.

    ParameterHandler.process_field_parameters rejects any field type not in DIRECT_TYPES with
    "not a valid field type". The A2A Agent shows agent_card in External mode, so building the
    component would fail unless data_display is accepted. Regression guard for the External-mode
    build failure.
    """
    from lfx.inputs.inputs import DataDisplayInput
    from lfx.utils.constants import DIRECT_TYPES

    field_type = DataDisplayInput(name="x").field_type
    assert field_type == "data_display"
    assert field_type in DIRECT_TYPES


def test_component_is_tool_mode_eligible():
    """The A2A Agent must be attachable to an Agent's Tools port like any component.

    Tool mode is opt-in via an input flagged ``tool_mode=True`` (what Component._handle_tool_mode
    keys on to wire the tool output). The component previously set it on no input, so no Tool mode
    was available.
    """
    assert any(getattr(inp, "tool_mode", False) for inp in A2AAgentComponent.inputs)


async def test_external_card_preview_fetches_and_renders(monkeypatch):
    """Entering a reachable agent URL fetches its card and loads the payload into agent_card."""
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_SSRF_ALLOWED_HOSTS", "127.0.0.1")

    with _CardServer() as server:
        url = f"http://127.0.0.1:{server.port}"
        component = A2AAgentComponent(mode="External", agent_url=url, input_value="hi")
        build_config = {"agent_card": {}}
        await component._apply_external_card(build_config, url)

    blob = json.dumps(build_config["agent_card"]["value"])
    assert "Echo" in blob
    assert "1.0.0" in blob
    assert "Requires an API key" in blob
    # A resolved card reveals the display field.
    assert build_config["agent_card"]["show"] is True


def test_agent_base_url_strips_card_suffix():
    """The card URL the UI hands out normalizes back to the agent base (no double-append)."""
    base = "http://host:7860/api/v1/a2a/abc"
    assert _agent_base_url(base) == base
    assert _agent_base_url(base + "/") == base
    assert _agent_base_url(base + "/.well-known/agent-card.json") == base
    assert _agent_base_url(base + "/.well-known/agent-card.json/") == base


async def test_external_card_preview_accepts_card_url(monkeypatch):
    """Pasting the /.well-known/agent-card.json URL (what the UI surfaces) still renders the card."""
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_SSRF_ALLOWED_HOSTS", "127.0.0.1")

    with _CardServer() as server:
        card_url = f"http://127.0.0.1:{server.port}/.well-known/agent-card.json"
        component = A2AAgentComponent(mode="External", agent_url=card_url, input_value="hi")
        build_config = {"agent_card": {}}
        await component._apply_external_card(build_config, card_url)

    assert "Echo" in json.dumps(build_config["agent_card"]["value"])


async def test_external_card_preview_bad_url_no_crash(monkeypatch):
    """A blocked/unreachable URL degrades to an empty card instead of raising in the editor."""
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    monkeypatch.delenv("LANGFLOW_SSRF_ALLOWED_HOSTS", raising=False)

    component = A2AAgentComponent(mode="External", agent_url="http://127.0.0.1:1/x", input_value="hi")
    build_config = {"agent_card": {}}
    await component._apply_external_card(build_config, "http://127.0.0.1:1/x")
    assert build_config["agent_card"]["value"] == {}
    # No card, so the display field stays hidden.
    assert build_config["agent_card"]["show"] is False


# --- The card fetch is bounded ----------------------------------------------


class _OversizedCardHandler(BaseHTTPRequestHandler):
    """Serves a card far past the fetch cap. Subclasses toggle whether the size is declared."""

    declare_length = True

    def do_GET(self):
        if self.path != "/.well-known/agent-card.json":
            self.send_response(404)
            self.end_headers()
            return
        blob = b'{"name":"Huge","description":"' + b"a" * (600 * 1024) + b'"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        if self.declare_length:
            self.send_header("Content-Length", str(len(blob)))
        self.end_headers()
        self.wfile.write(blob)

    def log_message(self, *args):
        pass


class _DeclaredOversizedHandler(_OversizedCardHandler):
    declare_length = True


class _UndeclaredOversizedHandler(_OversizedCardHandler):
    """No Content-Length, so only the streaming byte cap can stop the read."""

    declare_length = False


class _HandlerServer:
    def __init__(self, handler):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
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


@pytest.mark.parametrize("handler", [_DeclaredOversizedHandler, _UndeclaredOversizedHandler])
async def test_external_card_preview_rejects_oversized_card(monkeypatch, handler):
    """A card past the size cap degrades to no preview instead of being buffered and parsed.

    Covers both guards: the declared Content-Length early-out, and the streaming byte cap for a
    response that never declares its size.
    """
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_SSRF_ALLOWED_HOSTS", "127.0.0.1")

    with _HandlerServer(handler) as server:
        url = f"http://127.0.0.1:{server.port}"
        component = A2AAgentComponent(mode="External", agent_url=url, input_value="hi")
        build_config = {"agent_card": {}}
        await component._apply_external_card(build_config, url)

    assert build_config["agent_card"]["value"] == {}
    assert build_config["agent_card"]["show"] is False


@pytest.mark.parametrize("handler", [_DeclaredOversizedHandler, _UndeclaredOversizedHandler])
async def test_runtime_card_fetch_rejects_oversized_card(monkeypatch, handler):
    """The runtime call path bounds the card body the same way, but RAISES rather than degrading.

    create_client(url) would let the SDK resolver buffer the whole card body with no cap; the
    runtime resolves it here instead, capped. A call can't proceed without a card, so an oversized
    one raises (the editor preview degrades to no preview). Covers the declared and streamed caps.
    """
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_SSRF_ALLOWED_HOSTS", "127.0.0.1")

    with _HandlerServer(handler) as server:
        url = f"http://127.0.0.1:{server.port}"
        _url, validated_ips = validate_and_resolve_url(url)
        async with build_a2a_client(url, validated_ips, timeout=10) as client:
            with pytest.raises(ValueError, match="exceeds"):
                await _resolve_card_bounded(client, url)


def test_card_payload_clips_untrusted_strings():
    """Card text is remote input, so it is bounded before it reaches build_config and the editor."""
    card = {"name": "N" * 900, "description": "D" * 900}
    payload = A2AAgentComponent._card_payload(card)

    assert len(payload["title"]) <= 500
    assert len(payload["sections"][0]["text"]) <= 500


class TestInternalSubSessionIsolation:
    """The internal sub-run must not share the caller's LangGraph thread.

    Running the target on the caller's raw session_id makes the target's Agent inherit the
    caller's in-flight thread — which, mid tool-approval, holds the send_to_agent call as an
    orphan tool_use with no tool_result — so the target's LLM call is rejected with
    'tool_use ids were found without tool_result blocks'. The sub-run must get an isolated
    session namespaced off the caller's.
    """

    def test_sub_session_is_namespaced_off_caller_session(self):
        from types import SimpleNamespace

        component = A2AAgentComponent(mode="Internal", input_value="hi")
        component._vertex = SimpleNamespace(graph=SimpleNamespace(session_id="caller-session-abc"))

        sub = component._isolated_sub_session("flow-123")

        assert sub == "caller-session-abc:a2a:flow-123"
        assert sub != "caller-session-abc"  # never the caller's own thread

    def test_sub_session_is_unique_when_caller_has_no_session(self):
        from types import SimpleNamespace

        component = A2AAgentComponent(mode="Internal", input_value="hi")
        component._vertex = SimpleNamespace(graph=SimpleNamespace(session_id=None))

        sub = component._isolated_sub_session("flow-123")

        assert sub  # non-empty
        assert sub != "flow-123"
        assert ":a2a:" not in sub  # falls back to a fresh uuid, not a namespaced base


class TestNestedRunConfigIsolation:
    """The nested target run must not inherit the caller's LangChain RunnableConfig.

    Under tool-approval (HITL), the caller Agent runs inside a LangGraph whose config carries
    ``configurable.thread_id`` + the durable checkpointer. LangChain propagates that config to
    child runnables via ``var_child_runnable_config``, and ``graph.arun`` copies the context, so
    the target flow's Agent would checkpoint against the CALLER's HITL thread and corrupt its own
    tool loop ("tool_use ids were found without tool_result blocks"). ``_run_target_isolated``
    must reset the contextvar for the duration of the nested run and restore it after.
    """

    async def test_nested_run_sees_reset_config_and_restores_after(self, monkeypatch):
        from types import SimpleNamespace

        from langchain_core.runnables.config import var_child_runnable_config

        from lfx import helpers

        seen: dict = {}

        async def fake_run_flow(**kwargs):
            seen["config_during_run"] = var_child_runnable_config.get()
            seen["session_id"] = kwargs.get("session_id")
            return []

        monkeypatch.setattr(helpers, "run_flow", fake_run_flow)

        component = A2AAgentComponent(mode="Internal", input_value="hi")
        component._vertex = SimpleNamespace(graph=SimpleNamespace(session_id="caller-1"))
        component._user_id = "user-1"

        sentinel = {"configurable": {"thread_id": "caller-hitl-thread"}}
        token = var_child_runnable_config.set(sentinel)
        try:
            await component._run_target_isolated(graph=object(), flow_id="target-flow")
            assert seen["config_during_run"] is None  # caller's HITL thread never leaks in
            assert seen["session_id"] == "caller-1:a2a:target-flow"
            assert var_child_runnable_config.get() == sentinel  # restored for the caller loop
        finally:
            var_child_runnable_config.reset(token)
