"""Regression tests for the MCP install locality check (CWE-348, improper trust of X-Forwarded-For).

``POST /api/v1/mcp/project/{project_id}/install`` is restricted to local connections because it
writes MCP client config (``~/.cursor/mcp.json`` etc.) to the host filesystem. Previously
``get_client_ip`` returned the **leftmost** ``X-Forwarded-For`` entry, so a remote authenticated
caller could spoof ``X-Forwarded-For: 127.0.0.1`` and pass the ``is_local_ip`` gate. The client IP
must come from the real TCP peer unless a trusted proxy is explicitly configured, in which case the
unspoofable rightmost entry is used.
"""

from types import SimpleNamespace

from langflow.api.v1 import mcp_projects
from langflow.api.v1.mcp_projects import get_client_ip, is_local_ip
from starlette.datastructures import Headers


def _request(headers: dict | None = None, host: str | None = "203.0.113.7"):
    client = SimpleNamespace(host=host) if host is not None else None
    return SimpleNamespace(headers=Headers(headers or {}), client=client)


def _request_raw(raw_headers: list[tuple[bytes, bytes]], host: str | None = "203.0.113.7"):
    """Build a request whose headers may repeat, which ``Headers(dict)`` cannot express."""
    client = SimpleNamespace(host=host) if host is not None else None
    return SimpleNamespace(headers=Headers(raw=raw_headers), client=client)


def _set_trust_proxy(monkeypatch, *, value: bool) -> None:
    fake = SimpleNamespace(settings=SimpleNamespace(rate_limit_trust_proxy=value))
    monkeypatch.setattr(mcp_projects, "get_settings_service", lambda: fake)


def test_spoofed_xff_ignored_by_default(monkeypatch):
    """Default (no trusted proxy): a spoofed loopback XFF must not be trusted."""
    _set_trust_proxy(monkeypatch, value=False)
    req = _request(headers={"X-Forwarded-For": "127.0.0.1"}, host="203.0.113.7")
    ip = get_client_ip(req)
    assert ip == "203.0.113.7"
    # The spoof no longer bypasses the local-only install gate.
    assert is_local_ip(ip) is False


def test_real_local_peer_is_local_by_default(monkeypatch):
    """A genuine loopback TCP peer is still recognized as local."""
    _set_trust_proxy(monkeypatch, value=False)
    req = _request(headers={}, host="127.0.0.1")
    ip = get_client_ip(req)
    assert ip == "127.0.0.1"
    assert is_local_ip(ip) is True


def test_trusted_proxy_uses_rightmost_xff(monkeypatch):
    """With a trusted proxy, use the rightmost (last-hop) entry, not the client-spoofable leftmost."""
    _set_trust_proxy(monkeypatch, value=True)
    # The client spoofs 127.0.0.1 as the leftmost entry; the trusted proxy appends the real last hop.
    req = _request(headers={"X-Forwarded-For": "127.0.0.1, 203.0.113.7"}, host="10.0.0.2")
    ip = get_client_ip(req)
    assert ip == "203.0.113.7"
    assert is_local_ip(ip) is False


def test_trusted_proxy_joins_repeated_xff_lines(monkeypatch):
    """A proxy that appends its own header line must not leave the client's line as the one we read.

    HAProxy's ``option forwardfor`` adds a second ``X-Forwarded-For`` line rather than extending the
    client's. ``Headers.get`` returns only the first line, so reading it alone would take the
    rightmost entry of the attacker-supplied line — handing the attacker the value the locality gate
    assumes is unspoofable.
    """
    _set_trust_proxy(monkeypatch, value=True)
    req = _request_raw(
        [
            (b"host", b"target:7860"),
            (b"x-forwarded-for", b"127.0.0.1"),  # attacker's own line, sent first
            (b"x-forwarded-for", b"203.0.113.7"),  # line appended by the trusted proxy
        ],
        host="10.0.0.5",  # TCP peer is the proxy
    )
    ip = get_client_ip(req)
    assert ip == "203.0.113.7"
    assert is_local_ip(ip) is False


def test_repeated_xff_lines_ignored_without_trusted_proxy(monkeypatch):
    """Without the trusted-proxy opt-in, repeated lines are ignored entirely."""
    _set_trust_proxy(monkeypatch, value=False)
    req = _request_raw(
        [(b"x-forwarded-for", b"127.0.0.1"), (b"x-forwarded-for", b"127.0.0.1")],
        host="203.0.113.7",
    )
    ip = get_client_ip(req)
    assert ip == "203.0.113.7"
    assert is_local_ip(ip) is False


def test_empty_xff_falls_back_to_peer(monkeypatch):
    """A blank header must not resolve to an empty client IP."""
    _set_trust_proxy(monkeypatch, value=True)
    req = _request(headers={"X-Forwarded-For": "  "}, host="203.0.113.7")
    ip = get_client_ip(req)
    assert ip == "203.0.113.7"
    assert is_local_ip(ip) is False


def test_no_client_falls_back_to_non_local(monkeypatch):
    """When the peer cannot be determined, fall back to a non-routable, non-local IP."""
    _set_trust_proxy(monkeypatch, value=False)
    req = _request(headers={}, host=None)
    ip = get_client_ip(req)
    assert ip == "255.255.255.255"
    assert is_local_ip(ip) is False
