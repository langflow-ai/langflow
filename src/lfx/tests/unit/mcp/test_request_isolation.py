"""Request-scoped MCP clients and registries must not contaminate other sessions."""

import httpx
import pytest
from lfx.mcp.client import LangflowClient


@pytest.fixture(autouse=True)
def reset_server_context():
    from lfx.mcp import server as srv

    client_token = srv._client_var.set(None)
    registry_token = srv._registry_var.set(None)
    try:
        yield
    finally:
        srv._client_var.reset(client_token)
        srv._registry_var.reset(registry_token)


def _capture_login_requests(monkeypatch, *, fail_login=False) -> list[httpx.Request]:
    requests: list[httpx.Request] = []
    real_async_client = httpx.AsyncClient

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/login"):
            if fail_login:
                return httpx.Response(401)
            return httpx.Response(200, json={"access_token": "caller-token"})
        if request.url.path.endswith("/api_key/"):
            return httpx.Response(200, json={"api_key": "login-generated-key"})  # pragma: allowlist secret
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **_kwargs: real_async_client(transport=transport))
    return requests


async def test_login_with_explicit_url_does_not_send_process_api_key(monkeypatch):
    from lfx.mcp import server as srv

    monkeypatch.setenv("LANGFLOW_API_KEY", "process-key")
    monkeypatch.setattr(srv, "_shared_client", None)
    monkeypatch.setattr(srv, "_shared_registry", None)
    requests = _capture_login_requests(monkeypatch)

    await srv.login("caller", "password", "http://caller.example")

    assert [request.headers.get("x-api-key") for request in requests] == [None, None]


async def test_login_with_default_server_keeps_environment_configuration(monkeypatch):
    from lfx.mcp import server as srv

    monkeypatch.setenv("LANGFLOW_API_KEY", "process-key")
    monkeypatch.setattr(srv, "_shared_client", None)
    monkeypatch.setattr(srv, "_shared_registry", None)
    requests = _capture_login_requests(monkeypatch)

    await srv.login("caller", "password")

    assert [request.headers.get("x-api-key") for request in requests] == [None, "process-key"]


async def test_scoped_login_preserves_shared_client_and_registry(monkeypatch):
    from lfx.mcp import server as srv

    shared_client = LangflowClient(use_env_api_key=False)
    shared_registry = {"SharedComponent": {}}
    monkeypatch.setattr(srv, "_shared_client", shared_client)
    monkeypatch.setattr(srv, "_shared_registry", shared_registry)
    _capture_login_requests(monkeypatch)

    async with srv.client_scope(LangflowClient(use_env_api_key=False)):
        await srv.login("caller", "password", "http://caller.example")
        assert srv._get_client() is not shared_client

    assert srv._get_client() is shared_client
    assert srv._shared_registry is shared_registry


async def test_each_client_scope_loads_only_its_own_registry(monkeypatch):
    from lfx.mcp import server as srv

    shared_registry = {"SharedComponent": {}}
    first_client = LangflowClient(use_env_api_key=False)
    second_client = LangflowClient(use_env_api_key=False)
    first_registry = {"FirstComponent": {}}
    second_registry = {"SecondComponent": {}}
    registries = {first_client: first_registry, second_client: second_registry}
    loaded_for = []
    monkeypatch.setattr(srv, "_shared_registry", shared_registry)

    async def fake_load_registry(client):
        loaded_for.append(client)
        return registries[client]

    monkeypatch.setattr(srv, "load_registry", fake_load_registry)

    async with srv.client_scope(first_client):
        assert await srv._get_registry() is first_registry
        assert await srv._get_registry() is first_registry
    async with srv.client_scope(second_client):
        assert await srv._get_registry() is second_registry

    assert loaded_for == [first_client, second_client]
    assert srv._shared_registry is shared_registry


async def test_batch_preserves_allowed_actions_and_references(monkeypatch):
    from lfx.mcp import server as srv

    async def echo(value):
        return {"value": value}

    monkeypatch.setattr(srv, "_TOOL_MAP", {"echo": echo})

    results = await srv.batch(
        [
            {"tool": "echo", "args": {"value": "first"}},
            {"tool": "echo", "args": {"value": "$0.value"}},
        ]
    )

    assert results == [{"value": "first"}, {"value": "first"}]


async def test_client_scope_closes_replacement_after_successful_login(monkeypatch):
    from lfx.mcp import server as srv

    original = LangflowClient(use_env_api_key=False)
    _capture_login_requests(monkeypatch)

    async with srv.client_scope(original):
        await srv.login("caller", "password", "http://caller.example")
        replacement_pool = srv._get_client()._http

    assert replacement_pool.is_closed
    assert srv._client_var.get() is None


async def test_client_scope_closes_replacement_after_failed_login(monkeypatch):
    from lfx.mcp import server as srv

    original = LangflowClient(use_env_api_key=False)
    _capture_login_requests(monkeypatch, fail_login=True)
    replacement_pool = None

    async def run_failed_login():
        async with srv.client_scope(original):
            try:
                await srv.login("caller", "password", "http://caller.example")
            finally:
                nonlocal replacement_pool
                replacement_pool = srv._get_client()._http

    with pytest.raises(RuntimeError, match="Login failed"):
        await run_failed_login()

    assert replacement_pool.is_closed
    assert srv._client_var.get() is None


async def test_login_with_explicit_url_does_not_send_global_headers(monkeypatch):
    from lfx.mcp import server as srv

    monkeypatch.setenv("X-LANGFLOW-GLOBAL-VAR-TENANT", "process-global")
    requests = _capture_login_requests(monkeypatch)

    await srv.login("caller", "password", "http://caller.example")

    assert [request.headers.get("x-langflow-global-var-tenant") for request in requests] == [None, None]


async def test_login_with_default_server_keeps_global_headers(monkeypatch):
    from lfx.mcp import server as srv

    monkeypatch.setenv("X-LANGFLOW-GLOBAL-VAR-TENANT", "process-global")
    requests = _capture_login_requests(monkeypatch)

    await srv.login("caller", "password")

    assert [request.headers.get("x-langflow-global-var-tenant") for request in requests] == [None, "process-global"]
