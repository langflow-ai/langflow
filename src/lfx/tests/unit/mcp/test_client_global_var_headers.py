"""Tests for LangflowClient's X-LANGFLOW-GLOBAL-VAR-* environment pass-through.

``lfx-mcp`` is a stdio MCP server, so a client config can only reach it through
``env`` -- there is no ``headers`` field for a subprocess. These tests pin the one
channel that lets a caller supply per-request global variables.
"""

import os

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
