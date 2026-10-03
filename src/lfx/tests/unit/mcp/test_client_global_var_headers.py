"""Tests for LangflowClient's X-LANGFLOW-GLOBAL-VAR-* environment pass-through.

``lfx-mcp`` is a stdio MCP server, so a client config can only reach it through
``env`` -- there is no ``headers`` field for a subprocess. These tests pin the one
channel that lets a caller supply per-request global variables.
"""

import pytest
from lfx.mcp.client import LangflowClient


@pytest.fixture
def env(monkeypatch):
    """A clean environment holding only what each test puts in it."""
    for name in list(__import__("os").environ):
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

        A stdio server's environment also holds the API key and the index URL, and
        neither belongs on an outbound request.
        """
        env.setenv("LANGFLOW_API_KEY", "sk-secret")  # pragma: allowlist secret
        env.setenv("UV_INDEX_URL", "https://internal/simple")
        env.setenv("AWS_SECRET_ACCESS_KEY", "nope")  # pragma: allowlist secret

        headers = LangflowClient(server_url="http://localhost:7860")._headers()

        assert "UV_INDEX_URL" not in headers
        assert "AWS_SECRET_ACCESS_KEY" not in headers
        assert "sk-secret" not in set(headers.values()) - {headers.get("x-api-key")}

    def test_empty_values_are_skipped(self, env):
        """An unset placeholder must not send a blank credential.

        The failure it causes downstream looks like a bad token, not a missing one.
        """
        env.setenv("X-LANGFLOW-GLOBAL-VAR-TENANT_ID", "")

        headers = LangflowClient(server_url="http://localhost:7860")._headers()

        assert "X-LANGFLOW-GLOBAL-VAR-TENANT_ID" not in headers

    def test_auth_headers_are_preserved(self, env):
        env.setenv("X-LANGFLOW-GLOBAL-VAR-TENANT_ID", "tenant-42")

        client = LangflowClient(server_url="http://localhost:7860", api_key="sk-test")  # pragma: allowlist secret
        headers = client._headers()

        assert headers["x-api-key"] == "sk-test"  # pragma: allowlist secret
        assert headers["Content-Type"] == "application/json"
        assert headers["X-LANGFLOW-GLOBAL-VAR-TENANT_ID"] == "tenant-42"

    def test_prefix_match_is_case_insensitive(self, env):
        """Clients and shells disagree on env var casing.

        The header name is sent as written, which is fine because Langflow lowercases
        before matching.
        """
        env.setenv("x-langflow-global-var-tenant_id", "lower-value")

        headers = LangflowClient(server_url="http://localhost:7860")._headers()

        assert headers["x-langflow-global-var-tenant_id"] == "lower-value"

    def test_explicit_api_key_argument_still_wins(self, env):
        """Guard the construction-time snapshot.

        Reading the environment must not disturb the existing precedence between
        arguments and env vars.
        """
        env.setenv("LANGFLOW_API_KEY", "from-env")  # pragma: allowlist secret

        client = LangflowClient(server_url="http://localhost:7860", api_key="from-arg")  # pragma: allowlist secret

        assert client._headers()["x-api-key"] == "from-arg"  # pragma: allowlist secret
