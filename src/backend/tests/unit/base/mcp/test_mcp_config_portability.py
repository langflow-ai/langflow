"""An MCP server config must move between environments unchanged.

``config.headers`` resolved global variables; ``config.url`` was read raw, and matching
was exact whole-value only, so a base URL could not be composed with a preserved project
id. A flow therefore had to be edited by hand on every promotion between planes.
"""

import httpx
import pytest
from lfx.base.mcp import util


class TestUrlVariableResolution:
    def test_should_resolve_whole_url_when_value_is_a_variable_name(self):
        resolved = util.resolve_global_variables_in_url("MCP_TARGET_URL", {"MCP_TARGET_URL": "https://a.example/mcp"})

        assert resolved == "https://a.example/mcp"

    def test_should_resolve_placeholder_inside_url(self):
        """The project id must survive while only the host moves."""
        resolved = util.resolve_global_variables_in_url(
            "{{MCP_HOST}}/api/v1/mcp/project/abc-123/streamable",
            {"MCP_HOST": "https://serving.internal"},
        )

        assert resolved == "https://serving.internal/api/v1/mcp/project/abc-123/streamable"

    def test_should_resolve_multiple_placeholders(self):
        resolved = util.resolve_global_variables_in_url(
            "{{SCHEME}}://{{HOST}}/mcp", {"SCHEME": "https", "HOST": "serving.internal"}
        )

        assert resolved == "https://serving.internal/mcp"

    def test_should_leave_unknown_placeholder_untouched(self):
        """Silently blanking an unset variable would produce a URL that half works."""
        resolved = util.resolve_global_variables_in_url("{{MISSING}}/mcp", {"HOST": "x"})

        assert resolved == "{{MISSING}}/mcp"

    def test_should_return_url_unchanged_when_no_variables_available(self):
        assert util.resolve_global_variables_in_url("https://a.example/mcp", None) == "https://a.example/mcp"

    def test_should_tolerate_empty_url(self):
        assert util.resolve_global_variables_in_url("", {"HOST": "x"}) == ""


class TestHeaderVariableResolution:
    def test_should_preserve_whole_value_match(self):
        """The documented ``{"x-api-key": "x-api-key"}`` form must keep working."""
        resolved = util._resolve_global_variables_in_headers({"x-api-key": "x-api-key"}, {"x-api-key": "secret"})

        assert resolved == {"x-api-key": "secret"}

    def test_should_resolve_placeholder_inside_header_value(self):
        resolved = util._resolve_global_variables_in_headers({"authorization": "Bearer {{TOKEN}}"}, {"TOKEN": "abc123"})

        assert resolved == {"authorization": "Bearer abc123"}

    def test_should_leave_value_untouched_when_variable_is_unknown(self):
        resolved = util._resolve_global_variables_in_headers({"authorization": "Bearer {{NOPE}}"}, {"TOKEN": "abc"})

        assert resolved == {"authorization": "Bearer {{NOPE}}"}

    def test_should_return_headers_unchanged_without_variables(self):
        headers = {"authorization": "Bearer static"}

        assert util._resolve_global_variables_in_headers(headers, None) == headers


class TestHasVariablesGate:
    """The component skipped loading global variables unless headers existed."""

    def test_should_report_variables_needed_when_only_the_url_uses_one(self):
        assert util.config_uses_global_variables({"url": "{{MCP_HOST}}/mcp"}) is True

    def test_should_report_variables_needed_when_headers_exist(self):
        assert util.config_uses_global_variables({"url": "https://a.example", "headers": {"x-api-key": "k"}}) is True

    def test_should_report_no_variables_needed_for_a_static_config(self):
        assert util.config_uses_global_variables({"url": "https://a.example/mcp"}) is False

    def test_should_report_no_variables_needed_for_an_empty_config(self):
        assert util.config_uses_global_variables({}) is False


class TestOutboundAuthFailureReporting:
    @pytest.mark.parametrize("status", [401, 403])
    def test_should_name_target_and_status(self, status):
        """``unhandled errors in a TaskGroup`` gave the operator nothing to act on."""
        message = util.describe_mcp_connection_failure(
            "billing-mcp", "https://serving.internal/mcp", RuntimeError(f"HTTP {status}")
        )

        assert "billing-mcp" in message
        assert str(status) in message
        assert "serving.internal" in message

    def test_should_not_leak_credentials_from_the_url(self):
        message = util.describe_mcp_connection_failure(
            "billing-mcp", "https://user:hunter2@serving.internal/mcp?api_key=secret", RuntimeError("HTTP 401")
        )

        assert "hunter2" not in message
        assert "secret" not in message

    def test_should_still_describe_a_non_http_failure(self):
        message = util.describe_mcp_connection_failure(
            "billing-mcp", "https://serving.internal/mcp", OSError("connection refused")
        )

        assert "billing-mcp" in message
        assert "connection refused" in message


def _grouped(exc: BaseException) -> BaseException:
    """Wrap as the MCP SDK does: via anyio, the real failure never arrives bare.

    Built through ``util`` so the test exercises the same group type the runtime sees —
    the builtin on 3.11+, the ``exceptiongroup`` backport that anyio raises on 3.10.
    """
    group_type = util._EXCEPTION_GROUP_TYPES[0]
    return group_type("unhandled errors in a TaskGroup", [exc])


def _status_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://serving.internal/mcp")
    return httpx.HTTPStatusError(
        f"Server error '{status}'", request=request, response=httpx.Response(status, request=request)
    )


class TestGroupedAuthFailureReporting:
    """The status lives on a leaf inside a TaskGroup; the group's own str() carries nothing."""

    @pytest.mark.parametrize("status", [401, 403])
    def test_should_report_status_buried_in_a_task_group(self, status):
        message = util.describe_mcp_connection_failure(
            "billing-mcp", "https://serving.internal/mcp", _grouped(_status_error(status))
        )

        assert str(status) in message
        assert "billing-mcp" in message
        assert "serving.internal" in message

    @pytest.mark.parametrize("status", [401, 403])
    def test_should_name_authentication_as_the_cause(self, status):
        """Without this the operator reads a transport fault and checks the network."""
        message = util.describe_mcp_connection_failure(
            "billing-mcp", "https://serving.internal/mcp", _grouped(_status_error(status))
        )

        assert "credential" in message.lower()

    def test_should_not_claim_authentication_for_a_server_error(self):
        """A 500 is the server's problem — sending the operator to rotate a key wastes the outage."""
        message = util.describe_mcp_connection_failure(
            "billing-mcp", "https://serving.internal/mcp", _grouped(_status_error(500))
        )

        assert "500" in message
        assert "credential" not in message.lower()

    def test_should_read_status_from_a_nested_group(self):
        """Anyio nests groups when a subtask group fails inside another."""
        message = util.describe_mcp_connection_failure(
            "billing-mcp", "https://serving.internal/mcp", _grouped(_grouped(_status_error(401)))
        )

        assert "401" in message

    def test_should_describe_a_tool_call_rejected_mid_session(self):
        """A credential can expire after connect; the failure then lands on the call, not the connect."""
        message = util.describe_mcp_tool_failure(
            "read_ledger", "https://serving.internal/mcp", _grouped(_status_error(401))
        )

        assert "read_ledger" in message
        assert "401" in message
        assert "credential" in message.lower()

    def test_should_leave_a_non_http_tool_failure_unchanged(self):
        message = util.describe_mcp_tool_failure(
            "read_ledger", "https://serving.internal/mcp", TimeoutError("timed out")
        )

        assert "read_ledger" in message
        assert "timed out" in message
        assert "credential" not in message.lower()


class TestRunToolReachesTheDescriber:
    """Describing the failure is worthless if run_tool never routes the auth case to it.

    A rejected call raises an ExceptionGroup, which is none of ConnectionError /
    TimeoutError / OSError / ValueError and busts no session, so it fell through every
    branch to a bare re-raise and reached the user as the raw TaskGroup string.
    """

    @staticmethod
    def _client(monkeypatch, exc: BaseException):
        client = util.MCPStreamableHttpClient()
        client._connected = True
        client._connection_params = {"url": "http://127.0.0.1:7890/mcp"}
        client._session_context = "probe"

        class _Session:
            async def call_tool(self, *_args, **_kwargs):
                raise exc

        async def _session(*_args, **_kwargs):
            return _Session()

        monkeypatch.setattr(client, "_get_or_create_session", _session)
        return client

    @pytest.mark.parametrize("status", [401, 403])
    async def test_should_report_a_rejected_tool_call(self, monkeypatch, status):
        client = self._client(monkeypatch, _grouped(_status_error(status)))

        with pytest.raises(Exception, match=str(status)) as excinfo:
            await client.run_tool("read_ledger", {})

        assert "credential" in str(excinfo.value).lower()

    async def test_should_not_blame_the_credential_for_a_server_error(self, monkeypatch):
        client = self._client(monkeypatch, _grouped(_status_error(503)))

        with pytest.raises(Exception, match="503") as excinfo:
            await client.run_tool("read_ledger", {})

        assert "credential" not in str(excinfo.value).lower()

    def test_should_keep_the_port_in_the_named_target(self):
        """``hostname`` drops the port, so a non-443 plane was named as the wrong target."""
        message = util.describe_mcp_connection_failure(
            "billing-mcp", "http://127.0.0.1:7890/mcp", _grouped(_status_error(401))
        )

        assert "127.0.0.1:7890" in message

    def test_should_keep_the_underlying_cause_visible(self):
        message = util.describe_mcp_connection_failure(
            "billing-mcp", "https://serving.internal/mcp", _grouped(_status_error(401))
        )

        assert "TaskGroup" in message or "Server error" in message
