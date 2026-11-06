"""Synthetic MCP responses exercise the native component and real SDK transport."""

import asyncio
import json
import sys
import traceback
from types import SimpleNamespace

import anyio
import httpx
import pytest
from lfx_bundles.parallel import ParallelSearchComponent
from lfx_bundles.parallel import parallel_search as module
from mcp.types import CallToolResult, TextContent

if sys.version_info < (3, 11):
    from exceptiongroup import ExceptionGroup

PAYLOAD = {"results": [{"title": "Python", "url": "https://docs.python.org/3/", "excerpts": ["one\u2028two", "three"]}]}


def test_parser_structured_text_limits_and_unicode():
    payload = {"results": PAYLOAD["results"] * 3}
    for result in (
        CallToolResult(content=[], structuredContent=payload),
        CallToolResult(content=[TextContent(type="text", text=json.dumps(payload))]),
    ):
        rows = ParallelSearchComponent._result_data(result, 2)
        assert len(rows) == 2
        assert rows[0].text == "one\u2028two\n\nthree"
        assert rows[0].data["url"] == "https://docs.python.org/3/"
    assert ParallelSearchComponent._result_data(CallToolResult(content=[], structuredContent={"results": []}), 1) == []


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"results": {}},
        {"results": [None]},
        {"results": [{"url": "file:///x", "excerpts": []}]},
        {"results": [{"url": "https://x", "excerpts": [1]}]},
    ],
)
def test_parser_rejects_malformed(payload):
    with pytest.raises(ValueError, match="invalid"):
        ParallelSearchComponent._result_data(CallToolResult(content=[], structuredContent=payload), 2)


def test_service_error_is_not_empty_success():
    with pytest.raises(ValueError, match="failed"):
        ParallelSearchComponent._result_data(CallToolResult(content=[], isError=True), 2)


@pytest.mark.asyncio
@pytest.mark.parametrize("settings", [{"enabled": False}, {"query": " "}, {"max_results": 0}, {"max_results": 21}])
async def test_disabled_and_invalid_inputs_never_connect(monkeypatch, settings):
    def fail(_url):
        pytest.fail("Network setup should not run")

    monkeypatch.setattr(module, "ssrf_protected_strict_httpx_client_kwargs_for_url", fail)
    component = ParallelSearchComponent().set(query="Python", **{k: v for k, v in settings.items() if k != "query"})
    if "query" in settings:
        component.set(query=settings["query"])
    if settings.get("enabled") is False:
        results, _ = await component.build_results()
        assert results["dataframe"].empty
    else:
        with pytest.raises(ValueError, match=r"Search Query|Max Results"):
            await component.fetch_content_dataframe()


@pytest.mark.asyncio
@pytest.mark.parametrize("credential", ["", "synthetic-key"])
async def test_native_output_sdk_and_all_transport_headers(monkeypatch, credential):
    requests = []

    def handler(request):
        requests.append(request)
        assert request.headers["user-agent"] == module.USER_AGENT
        assert request.headers.get("authorization") == (f"Bearer {credential}" if credential else None)
        if request.method != "POST":
            return httpx.Response(405)
        rpc = json.loads(request.content)
        method = rpc["method"]
        if method == "notifications/initialized":
            return httpx.Response(202)
        if method == "initialize":
            result = {
                "protocolVersion": "2025-11-25",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "synthetic", "version": "1"},
            }
        elif method == "tools/list":
            result = {"tools": [{"name": "web_search", "inputSchema": {"type": "object"}}]}
        else:
            assert rpc["params"] == {
                "name": "web_search",
                "arguments": {"objective": "Python", "search_queries": ["Python"]},
            }
            result = {"content": [], "structuredContent": PAYLOAD}
        return httpx.Response(
            200,
            headers={"mcp-session-id": "synthetic-session"},
            json={"jsonrpc": "2.0", "id": rpc["id"], "result": result},
        )

    monkeypatch.setattr(
        module,
        "ssrf_protected_strict_httpx_client_kwargs_for_url",
        lambda _: ({}, {"transport": httpx.MockTransport(handler)}),
    )
    component = ParallelSearchComponent().set(query="Python", api_key=credential)
    results, _ = await component.build_results()
    assert results["dataframe"].iloc[0]["url"] == PAYLOAD["results"][0]["url"]
    assert {r.method for r in requests} == {"POST", "GET", "DELETE"}
    assert {json.loads(r.content)["method"] for r in requests if r.method == "POST"} == {
        "initialize",
        "notifications/initialized",
        "tools/list",
        "tools/call",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 429])
async def test_initialization_http_status_is_safe_and_not_retried(monkeypatch, status):
    requests = []

    def handler(request):
        requests.append(request)
        assert request.headers["authorization"] == "Bearer synthetic-invalid"
        return httpx.Response(status, text="synthetic-sensitive-body")

    monkeypatch.setattr(
        module,
        "ssrf_protected_strict_httpx_client_kwargs_for_url",
        lambda _: ({}, {"transport": httpx.MockTransport(handler)}),
    )
    component = ParallelSearchComponent().set(query="Python", api_key="synthetic-invalid")
    with pytest.raises(ValueError, match=rf"Parallel MCP request failed \(HTTP {status}\)") as caught:
        await component.build_results()
    displayed = "".join(traceback.format_exception(caught.value))
    assert "synthetic-invalid" not in displayed
    assert "synthetic-sensitive-body" not in displayed
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_ssrf_denial_propagates(monkeypatch):
    from lfx.utils.ssrf_protection import SSRFProtectionError

    def deny(url):
        assert url == module.MCP_URL
        msg = "blocked"
        raise SSRFProtectionError(msg)

    monkeypatch.setattr(module, "ssrf_protected_strict_httpx_client_kwargs_for_url", deny)
    with pytest.raises(SSRFProtectionError, match="blocked"):
        await ParallelSearchComponent().set(query="Python").fetch_content()


@pytest.mark.asyncio
@pytest.mark.parametrize("location", ["/synthetic-sensitive-target", "https://example.com/synthetic-sensitive-target"])
async def test_redirects_are_refused(monkeypatch, location):
    requests = []

    def handler(request):
        requests.append(request)
        assert request.headers["user-agent"] == module.USER_AGENT
        return httpx.Response(307, headers={"location": location})

    monkeypatch.setattr(
        module,
        "ssrf_protected_strict_httpx_client_kwargs_for_url",
        lambda _: ({}, {"transport": httpx.MockTransport(handler)}),
    )
    with pytest.raises(ValueError, match=r"Parallel MCP refused a redirect \(HTTP 307\)") as caught:
        await ParallelSearchComponent().set(query="Python").build_results()
    assert "synthetic-sensitive-target" not in "".join(traceback.format_exception(caught.value))
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_default_ssrf_validation_rejects_private_resolution(monkeypatch):
    from lfx.utils import ssrf_protection

    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_SSRF_ALLOWED_HOSTS", "")
    # An empty environment value falls back to settings cached by other bundle tests.
    monkeypatch.setattr(
        ssrf_protection,
        "get_settings_service",
        lambda: SimpleNamespace(settings=SimpleNamespace(ssrf_allowed_hosts=[])),
    )
    resolved_hosts = []

    def resolve(hostname):
        resolved_hosts.append(hostname)
        return ["127.0.0.1"]

    def fail_client(**_kwargs):
        pytest.fail("Private resolution must be rejected before creating an HTTP client")

    monkeypatch.setattr(ssrf_protection, "resolve_hostname", resolve)
    monkeypatch.setattr(module.httpx, "AsyncClient", fail_client)
    with pytest.raises(ssrf_protection.SSRFProtectionError, match=r"SSRF|blocked|private"):
        await ParallelSearchComponent().set(query="Python").fetch_content()
    assert resolved_hosts == ["mcp.parallel.ai"]


@pytest.mark.asyncio
async def test_tool_mode_keeps_disabled_setting():
    component = ParallelSearchComponent().set(enabled=False)
    tools = await component.to_toolkit()
    assert len(tools) == 1
    assert set(tools[0].args) == {"query"}
    assert (await tools[0].ainvoke({"query": "Python"})).empty


def test_non_json_response_fails():
    with pytest.raises(ValueError, match="invalid search response"):
        ParallelSearchComponent._result_data(
            CallToolResult(content=[TextContent(type="text", text="not JSON")]),
            1,
        )


@pytest.mark.asyncio
async def test_search_deadline_cancels_sdk_and_closes_client(monkeypatch):
    deadline = module.fail_after
    budgets = []
    cancelled = []
    closed = []

    def short_deadline(seconds):
        budgets.append(seconds)
        return deadline(0.05)

    async def handler(_request):
        try:
            await anyio.sleep_forever()
        finally:
            cancelled.append(True)

    class ClosingTransport(httpx.MockTransport):
        async def aclose(self):
            closed.append(True)
            await super().aclose()

    transport = ClosingTransport(handler)
    monkeypatch.setattr(module, "fail_after", short_deadline)
    monkeypatch.setattr(
        module,
        "ssrf_protected_strict_httpx_client_kwargs_for_url",
        lambda _: ({}, {"transport": transport}),
    )
    with pytest.raises(TimeoutError):
        await ParallelSearchComponent().set(query="Python").fetch_content()
    assert budgets == [90]
    assert cancelled == [True]
    assert closed == [True]


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["connection", "timeout", "other", "mixed"])
async def test_initialization_non_status_errors_stay_intact(monkeypatch, kind):
    original = None

    def handler(request):
        nonlocal original
        errors = {
            "connection": httpx.ConnectError("synthetic connection failure", request=request),
            "timeout": httpx.ReadTimeout("synthetic timeout", request=request),
            "other": RuntimeError("synthetic SDK failure"),
            "mixed": ExceptionGroup(
                "synthetic mixed failure",
                [
                    httpx.HTTPStatusError("synthetic HTTP failure", request=request, response=httpx.Response(429)),
                    RuntimeError("synthetic unrelated failure"),
                ],
            ),
        }
        original = errors[kind]
        raise original

    monkeypatch.setattr(
        module,
        "ssrf_protected_strict_httpx_client_kwargs_for_url",
        lambda _: ({}, {"transport": httpx.MockTransport(handler)}),
    )
    with pytest.raises(ExceptionGroup) as caught:
        await ParallelSearchComponent().set(query="Python").fetch_content_dataframe()
    error = caught.value
    while isinstance(error, ExceptionGroup) and len(error.exceptions) == 1:
        error = error.exceptions[0]
    assert error is original


@pytest.mark.asyncio
async def test_caller_cancellation_stays_cancelled_and_closes_client(monkeypatch):
    started = asyncio.Event()
    closed = []

    async def handler(_request):
        started.set()
        await anyio.sleep_forever()

    class ClosingTransport(httpx.MockTransport):
        async def aclose(self):
            closed.append(True)
            await super().aclose()

    monkeypatch.setattr(
        module,
        "ssrf_protected_strict_httpx_client_kwargs_for_url",
        lambda _: ({}, {"transport": ClosingTransport(handler)}),
    )
    task = asyncio.create_task(ParallelSearchComponent().set(query="Python").fetch_content_dataframe())
    await asyncio.wait_for(started.wait(), timeout=2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert closed == [True]
