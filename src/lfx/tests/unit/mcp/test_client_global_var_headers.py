"""Tests for LangflowClient's X-LANGFLOW-GLOBAL-VAR-* environment pass-through.

``lfx-mcp`` is a stdio MCP server, so a client config can only reach it through
``env`` -- there is no ``headers`` field for a subprocess. These tests pin the one
channel that lets a caller supply per-request global variables.
"""

import os
from functools import partial

import httpx
import pytest
from lfx.mcp.client import LangflowClient


@pytest.fixture
def env(monkeypatch):
    """Clear client configuration inherited from the test runner."""
    monkeypatch.delenv("LANGFLOW_API_KEY", raising=False)
    for name in list(os.environ):
        if name.upper().startswith("X-LANGFLOW-GLOBAL-VAR-"):
            monkeypatch.delenv(name, raising=False)
    return monkeypatch


class TestGlobalVarHeaders:
    def test_prefixed_env_vars_become_headers(self, env):
        env.setenv("X-LANGFLOW-GLOBAL-VAR-TENANT_ID", "tenant-42")
        env.setenv("X-LANGFLOW-GLOBAL-VAR-REGION", "eu-west-1")

        headers = LangflowClient(server_url="http://localhost:7860")._headers()

        assert headers["X-LANGFLOW-GLOBAL-VAR-TENANT_ID"] == "tenant-42"
        assert headers["X-LANGFLOW-GLOBAL-VAR-REGION"] == "eu-west-1"

    def test_unprefixed_env_vars_are_not_forwarded(self, env):
        """The prefix is the whole allowlist.

        The API key is sent only through the existing authentication header.
        Package index configuration and cloud credentials must stay local.
        """
        env.setenv("LANGFLOW_API_KEY", "sk-secret")  # pragma: allowlist secret
        env.setenv("UV_INDEX_URL", "https://internal/simple")
        env.setenv("AWS_SECRET_ACCESS_KEY", "nope")  # pragma: allowlist secret

        headers = LangflowClient(server_url="http://localhost:7860")._headers()

        assert headers == {"Content-Type": "application/json", "x-api-key": "sk-secret"}

    def test_empty_values_are_skipped(self, env):
        """An empty placeholder must not override a stored global variable."""
        env.setenv("X-LANGFLOW-GLOBAL-VAR-TENANT_ID", "")

        headers = LangflowClient(server_url="http://localhost:7860")._headers()

        assert "X-LANGFLOW-GLOBAL-VAR-TENANT_ID" not in headers

    def test_auth_headers_are_preserved(self, env):
        env.setenv("X-LANGFLOW-GLOBAL-VAR-TENANT_ID", "tenant-42")

        client = LangflowClient(
            server_url="http://localhost:7860",
            api_key="sk-test",  # pragma: allowlist secret
            access_token="test-token",  # noqa: S106  # pragma: allowlist secret
        )
        headers = client._headers()

        assert headers["x-api-key"] == "sk-test"  # pragma: allowlist secret
        assert headers["Content-Type"] == "application/json"
        assert headers["Authorization"] == "Bearer test-token"
        assert headers["X-LANGFLOW-GLOBAL-VAR-TENANT_ID"] == "tenant-42"

    @pytest.mark.parametrize("name", ["x-langflow-global-var-tenant_id", "X-Langflow-Global-Var-Tenant_ID"])
    def test_prefix_match_is_case_insensitive(self, env, name):
        """Clients and shells disagree on env var casing.

        The header name is sent as written, which is fine because Langflow lowercases
        before matching.
        """
        env.setenv(name, "tenant-value")

        headers = LangflowClient(server_url="http://localhost:7860")._headers()

        assert headers[name] == "tenant-value"

    def test_explicit_api_key_argument_still_wins(self, env):
        """Guard the construction-time snapshot.

        Reading the environment must not disturb the existing precedence between
        arguments and env vars.
        """
        env.setenv("LANGFLOW_API_KEY", "from-env")  # pragma: allowlist secret

        client = LangflowClient(server_url="http://localhost:7860", api_key="from-arg")  # pragma: allowlist secret

        assert client._headers()["x-api-key"] == "from-arg"  # pragma: allowlist secret

    def test_variables_are_snapshotted_per_client(self, env):
        env.setenv("X-LANGFLOW-GLOBAL-VAR-ENVIRONMENT", "staging")
        staging_client = LangflowClient(server_url="http://localhost:7860")

        env.setenv("X-LANGFLOW-GLOBAL-VAR-ENVIRONMENT", "production")
        production_client = LangflowClient(server_url="http://localhost:7860")

        assert staging_client._headers()["X-LANGFLOW-GLOBAL-VAR-ENVIRONMENT"] == "staging"
        assert production_client._headers()["X-LANGFLOW-GLOBAL-VAR-ENVIRONMENT"] == "production"

    @pytest.mark.parametrize("stream", [False, True])
    async def test_flow_requests_forward_global_variables(self, env, stream):
        env.setenv("X-LANGFLOW-GLOBAL-VAR-ENVIRONMENT", "staging")
        env.setenv("X-LANGFLOW-GLOBAL-VAR-EMPTY", "")
        env.setenv("AWS_SECRET_ACCESS_KEY", "unrelated-secret")  # pragma: allowlist secret
        client = LangflowClient(server_url="http://langflow.test", api_key="test-key")  # pragma: allowlist secret
        requests = []

        def handle_request(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            assert request.method == "POST"
            assert request.url.path == "/api/v1/run/flow-123"
            assert request.headers["X-LANGFLOW-GLOBAL-VAR-ENVIRONMENT"] == "staging"
            assert request.headers["x-api-key"] == "test-key"  # pragma: allowlist secret
            assert "X-LANGFLOW-GLOBAL-VAR-EMPTY" not in request.headers
            assert "AWS_SECRET_ACCESS_KEY" not in request.headers
            if stream:
                return httpx.Response(200, text='data: {"event": "end", "data": {"result": "ok"}}\n\n')
            return httpx.Response(200, json={"result": "ok"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle_request)) as http:
            client._http = http
            if stream:
                events = [event async for event in client.stream_post("/run/flow-123?stream=true")]
                assert events == [{"event": "end", "data": {"result": "ok"}}]
            else:
                assert await client.post("/run/flow-123") == {"result": "ok"}

        assert len(requests) == 1


class TestGlobalVarHeaderSafety:
    @pytest.mark.parametrize(
        "name",
        [
            "X-LANGFLOW-GLOBAL-VAR-",
            "X-LANGFLOW-GLOBAL-VAR-INVALID NAME",
            "X-LANGFLOW-GLOBAL-VAR-INVALID:NAME",
            "X-LANGFLOW-GLOBAL-VAR-INVALID\nNAME",
            "X-LANGFLOW-GLOBAL-VAR-NON_ASCII_é",
        ],
    )
    def test_invalid_header_names_fail_without_exposing_values(self, env, name):
        value = "synthetic-private-key"
        env.setenv(name, value)

        with pytest.raises(ValueError, match="Global variable override names") as exc_info:
            LangflowClient(server_url="http://langflow.test")

        assert name not in str(exc_info.value)
        assert value not in str(exc_info.value)

    @pytest.mark.parametrize(
        "value", ["secret\n", "secret\r", "secret\x1f", "secret\x7f", " secret", "secret ", "sëcret"]
    )
    def test_invalid_header_values_fail_without_exposing_values(self, env, value):
        env.setenv("X-LANGFLOW-GLOBAL-VAR-API_KEY", value)

        with pytest.raises(ValueError, match="Global variable override values") as exc_info:
            LangflowClient(server_url="http://langflow.test")

        assert value not in str(exc_info.value)
        assert "secret" not in str(exc_info.value)

    @pytest.mark.parametrize("stream", [False, True])
    @pytest.mark.parametrize(
        "location",
        [
            "http://external.test/run",
            "//external.test/run",
            "https://langflow.test/run",
            "http://langflow.test:8080/run",
        ],
    )
    async def test_cross_origin_redirects_do_not_forward_overrides(self, env, stream, location):
        env.setenv("X-LANGFLOW-GLOBAL-VAR-API_KEY", "synthetic-private-key")
        requests = []

        def handle_request(request):
            requests.append(request)
            if len(requests) == 1:
                return httpx.Response(307, headers={"Location": location})
            return httpx.Response(200, json={"result": "ok"})

        env.setattr(httpx, "AsyncClient", partial(httpx.AsyncClient, transport=httpx.MockTransport(handle_request)))
        client = LangflowClient(server_url="http://langflow.test")

        async def send_request():
            if stream:
                return [event async for event in client.stream_post("/run/flow")]
            return await client.post("/run/flow")

        try:
            with pytest.raises(RuntimeError, match="outside the Langflow server origin") as exc_info:
                await send_request()
        finally:
            await client.close()

        assert len(requests) == 1
        assert "synthetic-private-key" not in str(exc_info.value)
        assert location not in str(exc_info.value)

    @pytest.mark.parametrize("location", ["/api/v1/run/redirected", "http://langflow.test:80/api/v1/run/redirected"])
    async def test_same_origin_redirects_preserve_overrides(self, env, location):
        value = "synthetic-private-key"
        env.setenv("X-LANGFLOW-GLOBAL-VAR-API_KEY", value)
        requests = []

        def handle_request(request):
            requests.append(request)
            if len(requests) == 1:
                return httpx.Response(307, headers={"Location": location})
            assert request.headers["X-LANGFLOW-GLOBAL-VAR-API_KEY"] == value
            assert request.headers["Authorization"] == "Bearer test-token"
            return httpx.Response(200, json={"result": "ok"})

        env.setattr(httpx, "AsyncClient", partial(httpx.AsyncClient, transport=httpx.MockTransport(handle_request)))
        client = LangflowClient(server_url="http://langflow.test", access_token="test-token")  # noqa: S106  # pragma: allowlist secret
        try:
            assert await client.post("/run/flow") == {"result": "ok"}
        finally:
            await client.close()

        assert len(requests) == 2

    async def test_no_overrides_preserve_existing_redirect_behavior(self, env):
        requests = []

        def handle_request(request):
            requests.append(request)
            if len(requests) == 1:
                return httpx.Response(307, headers={"Location": "http://external.test/run"})
            return httpx.Response(200, json={"result": "ok"})

        env.setattr(httpx, "AsyncClient", partial(httpx.AsyncClient, transport=httpx.MockTransport(handle_request)))
        client = LangflowClient(server_url="http://langflow.test")
        try:
            assert await client.post("/run/flow") == {"result": "ok"}
        finally:
            await client.close()

        assert len(requests) == 2
