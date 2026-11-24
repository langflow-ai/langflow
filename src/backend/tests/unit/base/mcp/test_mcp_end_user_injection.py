"""MCP end-user identity: inbound scoping seam + outbound fail-closed injection.

Outbound (client): the serving end-user header is auto-appended to an outbound MCP call ONLY
for operator-allowlisted internal hosts, and NEVER to external hosts (the id is PII). These
pin the ``_is_internal_mcp_target`` / ``_maybe_inject_end_user_header`` decision directly.

Inbound (server): an MCP-triggered run scopes to the end user via the SAME ``resolve_serving_scope``
path /run uses; the streamable endpoint stashes ``request.headers`` in a contextvar and
``handle_call_tool`` replays them through a shim. This proves that shim -> scope contract.
"""

from types import SimpleNamespace

from lfx.base.mcp.util import _is_internal_mcp_target, _maybe_inject_end_user_header

HEADER = "X-End-User-Id"


def _stub_settings(monkeypatch, **overrides):
    base = {"serving_end_user_header": None, "serving_internal_mcp_hosts": None}
    base.update(overrides)
    from lfx.services import deps as deps_module

    monkeypatch.setattr(
        deps_module,
        "get_settings_service",
        lambda: SimpleNamespace(settings=SimpleNamespace(**base)),
    )


# --- outbound: internal-target detection (fail-closed) -----------------------------


def test_empty_allowlist_treats_everything_external(monkeypatch):
    _stub_settings(monkeypatch, serving_internal_mcp_hosts=None)
    assert _is_internal_mcp_target("https://sibling.internal:7860/api/v1/mcp/project/x/streamable") is False


def test_allowlisted_host_is_internal(monkeypatch):
    _stub_settings(monkeypatch, serving_internal_mcp_hosts="sibling.internal:7860, other.host")
    assert _is_internal_mcp_target("https://sibling.internal:7860/api/v1/mcp/project/x/streamable") is True
    assert _is_internal_mcp_target("https://other.host/whatever") is True


def test_bare_host_allowlist_matches_any_port(monkeypatch):
    _stub_settings(monkeypatch, serving_internal_mcp_hosts="sibling.internal")
    assert _is_internal_mcp_target("https://sibling.internal:9000/x") is True
    assert _is_internal_mcp_target("https://sibling.internal/x") is True


def test_host_port_allowlist_does_not_match_other_ports(monkeypatch):
    _stub_settings(monkeypatch, serving_internal_mcp_hosts="sibling.internal:7860")
    assert _is_internal_mcp_target("https://sibling.internal:9999/x") is False


def test_external_host_never_internal(monkeypatch):
    _stub_settings(monkeypatch, serving_internal_mcp_hosts="sibling.internal")
    assert _is_internal_mcp_target("https://evil.example.com/x") is False


def test_userinfo_is_stripped_before_matching(monkeypatch):
    _stub_settings(monkeypatch, serving_internal_mcp_hosts="sibling.internal")
    assert _is_internal_mcp_target("https://user:pass@sibling.internal/x") is True  # pragma: allowlist secret


# --- outbound: injection (fail-closed) ---------------------------------------------


def test_inject_for_internal_target(monkeypatch):
    _stub_settings(monkeypatch, serving_end_user_header=HEADER, serving_internal_mcp_hosts="sibling.internal")
    out = _maybe_inject_end_user_header({"a": "b"}, "https://sibling.internal/x", "alice")
    assert out.get(HEADER.lower()) == "alice" or out.get(HEADER) == "alice"
    assert out.get("a") == "b"


def test_no_injection_for_external_target(monkeypatch):
    _stub_settings(monkeypatch, serving_end_user_header=HEADER, serving_internal_mcp_hosts="sibling.internal")
    out = _maybe_inject_end_user_header({"a": "b"}, "https://evil.example.com/x", "alice")
    # PII never leaves the deployment: the header is absent in any casing, and nothing else changed.
    assert out == {"a": "b"}


def test_no_injection_when_no_end_user(monkeypatch):
    _stub_settings(monkeypatch, serving_end_user_header=HEADER, serving_internal_mcp_hosts="sibling.internal")
    assert _maybe_inject_end_user_header({"a": "b"}, "https://sibling.internal/x", None) == {"a": "b"}


def test_no_injection_when_feature_off(monkeypatch):
    # Header name unset -> feature off -> nothing to inject even for an internal, id-carrying call.
    _stub_settings(monkeypatch, serving_end_user_header=None, serving_internal_mcp_hosts="sibling.internal")
    assert _maybe_inject_end_user_header({"a": "b"}, "https://sibling.internal/x", "alice") == {"a": "b"}


# --- inbound: the contextvar-headers shim drives the same scoping as /run -----------


def test_inbound_header_shim_scopes_like_run(monkeypatch):
    """handle_call_tool builds SimpleNamespace(headers=<request headers>); prove it scopes.

    Mirrors the shim handle_call_tool passes as ``http_request`` to ``simple_run_flow``: a
    header-carrying object whose ``headers.get`` resolve_serving_scope reads.
    """
    from lfx.workflow.end_user_identity import resolve_serving_scope

    _stub_settings(monkeypatch, serving_end_user_header=HEADER)
    # Feature also needs trust on for resolve_serving_scope; extend the stub.
    from lfx.services import deps as deps_module

    monkeypatch.setattr(
        deps_module,
        "get_settings_service",
        lambda: SimpleNamespace(
            settings=SimpleNamespace(
                serving_end_user_header=HEADER,
                serving_trust_proxy_headers=True,
                serving_end_user_required=False,
            )
        ),
    )
    lower = {HEADER.lower(): "alice"}
    shim = SimpleNamespace(headers=SimpleNamespace(get=lambda name, default=None: lower.get(name.lower(), default)))

    scoped = resolve_serving_scope(http_request=shim, requested_session_id="chat-1", default_session_id="flow-1")
    assert scoped is not None
    assert scoped.session_id == "alice::chat-1"
    assert scoped.end_user_id == "alice"
