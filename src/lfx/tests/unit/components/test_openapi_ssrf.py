"""OpenAPI tools apply the outbound policy to every verb and redirect."""

import ipaddress
import json
import os
import socket
from types import SimpleNamespace
from unittest.mock import Mock

import httpcore
import httpx
import pytest
from lfx.base.langchain_utilities.requests import SSRFSafeTextRequestsWrapper
from lfx.components.langchain_utilities import openapi
from lfx.utils import ssrf_protection
from lfx.utils.ssrf_protection import SSRFProtectionError
from lfx.utils.ssrf_transport import SSRFProtectedSyncTransport

METHODS = ("get", "post", "patch", "put", "delete")
BODY = {"item": "fixture"}
URL = "https://api.example.test/items"


@pytest.fixture(autouse=True)
def outbound_policy(monkeypatch):
    """Isolate policy settings and prevent unit tests from opening network connections."""
    monkeypatch.delenv("LANGFLOW_SSRF_PROTECTION_ENABLED", raising=False)
    monkeypatch.delenv("LANGFLOW_SSRF_ALLOWED_HOSTS", raising=False)
    settings = SimpleNamespace(
        ssrf_protection_enabled=True,
        ssrf_allowed_hosts=[],
        connector_ssrf_validation_enabled=False,
        connector_ssrf_allow_loopback=True,
    )
    monkeypatch.setattr(ssrf_protection, "get_settings_service", lambda: SimpleNamespace(settings=settings))

    def resolve(host, *_args, **_kwargs):
        """Resolve fixture hostnames while retaining literal addresses for policy checks."""
        try:
            ipaddress.ip_address(host)
        except ValueError:
            host = "93.184.216.34"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (host, 443))]

    def deny_network(*_args, **_kwargs):
        pytest.fail("OpenAPI unit tests must not open network connections")

    monkeypatch.setattr(socket.socket, "connect", deny_network)
    monkeypatch.setattr(socket.socket, "connect_ex", deny_network)
    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    for name in tuple(os.environ):
        if name.lower().endswith("_proxy"):
            monkeypatch.delenv(name)
    return settings


@pytest.fixture
def outbound_request(monkeypatch):
    send = Mock(return_value=httpx.Response(200, content=b"fixture response"))
    monkeypatch.setattr(httpx.Client, "request", send)
    return send


def call_args(method):
    """Supply a JSON body only for the wrapper methods that accept one."""
    return (BODY,) if method in {"post", "patch", "put"} else ()


@pytest.mark.parametrize("method", METHODS)
def test_sync_tools_preserve_requests(method, outbound_request):
    """Keep caller headers, parameters, timeouts, and JSON bodies on protected requests."""
    wrapper = SSRFSafeTextRequestsWrapper(headers={"X-Request": "fixture"})

    assert getattr(wrapper, method)(URL, *call_args(method), params={"page": 1}, timeout=9) == "fixture response"

    args, kwargs = outbound_request.call_args
    assert args == (method.upper(), f"{URL}?page=1")
    assert kwargs["headers"]["X-Request"] == "fixture"
    assert kwargs["timeout"] == 9
    assert kwargs["follow_redirects"] is False
    if call_args(method):
        assert json.loads(kwargs["content"]) == BODY


@pytest.mark.parametrize("method", METHODS)
async def test_async_tools_use_the_protected_transport(method, outbound_request):
    wrapper = SSRFSafeTextRequestsWrapper()

    assert await getattr(wrapper, f"a{method}")(URL, *call_args(method)) == "fixture response"

    assert outbound_request.call_args.args[0] == method.upper()


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("async_call", [False, True])
@pytest.mark.parametrize(("timeout_kwargs", "expected"), [({}, 30), ({"timeout": None}, 30), ({"timeout": 7}, 7)])
async def test_tools_use_bounded_default_timeout(method, async_call, timeout_kwargs, expected, outbound_request):
    wrapper = SSRFSafeTextRequestsWrapper()

    if async_call:
        await getattr(wrapper, f"a{method}")(URL, *call_args(method), **timeout_kwargs)
    else:
        getattr(wrapper, method)(URL, *call_args(method), **timeout_kwargs)

    assert outbound_request.call_args.kwargs["timeout"] == expected


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("async_call", [False, True])
async def test_tools_reject_disallowed_destination_before_transport(method, async_call, outbound_request):
    """Reject disallowed destinations before sync or async tools reach a transport."""
    wrapper = SSRFSafeTextRequestsWrapper()

    if async_call:
        with pytest.raises(SSRFProtectionError):
            await getattr(wrapper, f"a{method}")("http://127.0.0.1/", *call_args(method))
    else:
        with pytest.raises(SSRFProtectionError):
            getattr(wrapper, method)("http://127.0.0.1/", *call_args(method))

    outbound_request.assert_not_called()


@pytest.mark.parametrize("method", METHODS)
def test_redirect_destination_is_checked_before_following(method, outbound_request):
    outbound_request.return_value = httpx.Response(307, headers={"Location": "http://127.0.0.1/"})

    with pytest.raises(SSRFProtectionError):
        getattr(SSRFSafeTextRequestsWrapper(), method)(URL, *call_args(method))

    assert outbound_request.call_count == 1


@pytest.mark.parametrize(("status", "expected_method"), [(302, "GET"), (307, "POST")])
def test_valid_redirects_preserve_method_rules_and_cookies(status, expected_method, outbound_request):
    """Retain Requests method conversion and cookies across validated redirects."""
    outbound_request.side_effect = [
        httpx.Response(status, headers={"Location": "/next", "Set-Cookie": "fixture=value; Path=/"}),
        httpx.Response(200, content=b"done"),
    ]

    assert SSRFSafeTextRequestsWrapper().post(URL, BODY) == "done"

    args, kwargs = outbound_request.call_args
    assert args == (expected_method, "https://api.example.test/next")
    assert kwargs["headers"]["Cookie"] == "fixture=value"
    if expected_method == "POST":
        assert json.loads(kwargs["content"]) == BODY
    else:
        assert kwargs["content"] is None


def test_redirect_strips_cross_origin_credentials(outbound_request):
    outbound_request.side_effect = [
        httpx.Response(302, headers={"Location": "https://other.example.test/next"}),
        httpx.Response(200, content=b"done"),
    ]

    SSRFSafeTextRequestsWrapper(auth=("fixture", "password")).get(URL)

    assert "Authorization" not in outbound_request.call_args.kwargs["headers"]


def test_request_transport_pins_the_validated_address(monkeypatch):
    from lfx.utils import ssrf_requests

    transport_factory = Mock(wraps=SSRFProtectedSyncTransport)
    monkeypatch.setattr(ssrf_requests, "SSRFProtectedSyncTransport", transport_factory)
    connect_tcp = Mock(side_effect=RuntimeError("stop after pin check"))
    monkeypatch.setattr(httpcore.SyncBackend, "connect_tcp", connect_tcp)

    with pytest.raises(RuntimeError, match="stop after pin check"):
        SSRFSafeTextRequestsWrapper().get(URL)

    assert transport_factory.call_args.kwargs["pinned_ips"] == {"api.example.test": ["93.184.216.34"]}
    assert connect_tcp.call_args.kwargs["host"] == "93.184.216.34"


@pytest.mark.parametrize("allowlisted", [False, True])
def test_operator_exemptions_retain_the_requests_transport(monkeypatch, outbound_policy, outbound_request, allowlisted):
    """Keep the standard transport when operators disable protection or allow a host."""
    import requests

    if allowlisted:
        outbound_policy.ssrf_allowed_hosts = ["api.example.test"]
    else:
        outbound_policy.ssrf_protection_enabled = False
    response = requests.Response()
    response.status_code = 200
    response._content = b"unrestricted fixture"
    send = Mock(return_value=response)
    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)

    assert SSRFSafeTextRequestsWrapper().get(URL) == "unrestricted fixture"

    send.assert_called_once()
    outbound_request.assert_not_called()


def test_agent_installs_protected_wrapper(tmp_path, monkeypatch):
    spec = tmp_path / "api.json"
    spec.write_text('{"openapi": "3.0.0"}')
    component = openapi.OpenAPIAgentComponent()
    component.set(path=str(spec), allow_dangerous_requests=True)
    monkeypatch.setattr(openapi.OpenAPIAgentComponent, "_get_llm", lambda _self: object())
    monkeypatch.setattr(
        openapi.OpenAPIAgentComponent,
        "get_agent_kwargs",
        lambda _self: {"agent_executor_kwargs": {"max_iterations": 2}},
    )
    monkeypatch.setattr(openapi, "enforce_local_file_access", lambda path, **_kwargs: path)
    toolkit = Mock()
    monkeypatch.setattr(openapi.OpenAPIToolkit, "from_llm", toolkit)
    monkeypatch.setattr(openapi, "create_openapi_agent", Mock())

    component.build_agent()

    assert isinstance(toolkit.call_args.kwargs["requests_wrapper"], SSRFSafeTextRequestsWrapper)
    assert toolkit.call_args.kwargs["allow_dangerous_requests"] is True
