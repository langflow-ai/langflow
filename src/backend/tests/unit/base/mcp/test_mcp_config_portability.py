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


class TestUrlResolutionProvenance:
    """Who chooses the outbound target must not be the caller.

    ``request_variables`` on a run come from the inbound ``X-Langflow-Global-Var-*``
    headers. Letting them resolve ``{{MCP_HOST}}/mcp`` hands the destination to whoever
    calls the flow, and the resolved credential headers travel to that destination.
    SSRF validation rejects internal targets, not an arbitrary external one.
    """

    @staticmethod
    def _capture_target(monkeypatch) -> dict:
        """Record the URL at the point it is decided, before any DNS or socket work."""
        seen: dict = {}

        def fake_validate(url):
            seen["url"] = url
            msg = "stop here"
            raise RuntimeError(msg)

        monkeypatch.setattr(util, "validate_connector_url_for_ssrf", fake_validate)
        return seen

    async def test_should_not_resolve_the_url_from_caller_variables(self, monkeypatch):
        seen = self._capture_target(monkeypatch)

        with pytest.raises(Exception, match="stop here"):
            await util.update_tools(
                server_name="billing",
                server_config={"mode": "Streamable_HTTP", "url": "{{MCP_HOST}}/mcp"},
                request_variables={"MCP_HOST": "https://attacker.example"},
            )

        assert seen["url"] == "{{MCP_HOST}}/mcp", "the caller chose the target"

    async def test_should_resolve_the_url_from_database_variables(self, monkeypatch):
        seen = self._capture_target(monkeypatch)

        with pytest.raises(Exception, match="stop here"):
            await util.update_tools(
                server_name="billing",
                server_config={"mode": "Streamable_HTTP", "url": "{{MCP_HOST}}/mcp"},
                request_variables={"MCP_HOST": "https://attacker.example"},
                url_variables={"MCP_HOST": "https://serving.internal"},
            )

        assert seen["url"] == "https://serving.internal/mcp"

    async def test_should_still_resolve_headers_from_caller_variables(self, monkeypatch):
        """Header substitution by inbound request variable is a documented feature."""
        seen = self._capture_target(monkeypatch)
        resolved = util._resolve_global_variables_in_headers(
            {"x-api-key": "CALLER_KEY"}, {"CALLER_KEY": "from-the-caller"}
        )

        assert resolved == {"x-api-key": "from-the-caller"}
        assert seen == {}


class TestEnvVariableResolution:
    """``env`` was left literal, so a stdio server received ``MCP_FOO_...`` as its key.

    The module promised the reference keeps a flow portable. Under Langflow the stored
    server row masks the gap; under ``lfx serve`` or an import elsewhere the subprocess
    is handed the variable name and authenticates with nonsense.
    """

    @staticmethod
    def _capture_env(monkeypatch) -> dict:
        seen: dict = {}

        def fake_validate(command, args, env):  # noqa: ARG001
            seen["env"] = env
            msg = "stop here"
            raise RuntimeError(msg)

        monkeypatch.setattr(util, "validate_mcp_stdio_config", fake_validate)
        return seen

    async def test_should_resolve_env_from_database_variables(self, monkeypatch):
        seen = self._capture_env(monkeypatch)

        with pytest.raises(Exception, match="stop here"):
            await util.update_tools(
                server_name="local",
                server_config={"mode": "Stdio", "command": "uvx", "args": [], "env": {"API_TOKEN": "MCP_LOCAL_TOKEN"}},
                url_variables={"MCP_LOCAL_TOKEN": "sk-from-the-database"},
            )

        assert seen["env"] == {"API_TOKEN": "sk-from-the-database"}

    async def test_should_not_resolve_env_from_caller_variables(self, monkeypatch):
        """Env feeds a subprocess; letting the caller populate it is worse than a URL."""
        seen = self._capture_env(monkeypatch)

        with pytest.raises(Exception, match="stop here"):
            await util.update_tools(
                server_name="local",
                server_config={"mode": "Stdio", "command": "uvx", "args": [], "env": {"API_TOKEN": "MCP_LOCAL_TOKEN"}},
                request_variables={"MCP_LOCAL_TOKEN": "from-the-caller"},
            )

        assert seen["env"] == {"API_TOKEN": "MCP_LOCAL_TOKEN"}

    async def test_should_leave_a_static_env_untouched(self, monkeypatch):
        seen = self._capture_env(monkeypatch)

        with pytest.raises(Exception, match="stop here"):
            await util.update_tools(
                server_name="local",
                server_config={"mode": "Stdio", "command": "uvx", "args": [], "env": {"NODE_ENV": "production"}},
                url_variables={"MCP_LOCAL_TOKEN": "sk-x"},
            )

        assert seen["env"] == {"NODE_ENV": "production"}


class TestEnvOnlyConfigsNeedVariables:
    """A stdio server whose only secret lives in ``env`` never loaded the variables.

    ``persist_and_strip_mcp_secrets`` rewrites ``env`` values to ``MCP_*`` names exactly as
    it does headers, but the gate only looked at ``headers`` and ``url``. The subprocess
    was then handed the literal name instead of the credential.
    """

    def test_should_report_variables_needed_when_only_env_uses_one(self):
        config = {"mode": "Stdio", "command": "uvx", "args": [], "env": {"API_TOKEN": "MCP_LOCAL_API_TOKEN_1A2B3C4D"}}

        assert util.config_uses_global_variables(config) is True

    def test_should_report_variables_needed_for_an_env_placeholder(self):
        config = {"mode": "Stdio", "command": "uvx", "env": {"API_TOKEN": "{{MCP_LOCAL_TOKEN}}"}}

        assert util.config_uses_global_variables(config) is True

    def test_should_report_no_variables_needed_for_an_empty_env(self):
        assert util.config_uses_global_variables({"mode": "Stdio", "command": "uvx", "env": {}}) is False


def _raise_for_status_error(status: int, url: str) -> httpx.HTTPStatusError:
    """Build the error httpx actually raises, whose message embeds the request URL."""
    request = httpx.Request("POST", url)
    response = httpx.Response(status, request=request)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        return exc
    msg = "raise_for_status did not raise"
    raise AssertionError(msg)


CREDENTIAL_URL = "https://user:hunter2@serving.internal/mcp?api_key=secret"


class TestFailureMessagesNeverCarryCredentials:
    """Both describers append the cause verbatim, and httpx puts the request URL in it.

    Stripping userinfo and query from the target we format ourselves is not enough: the
    message httpx builds for a 401 already contains the whole URL, credentials included.
    """

    def test_connection_failure_should_not_leak_the_url_inside_the_cause(self):
        message = util.describe_mcp_connection_failure(
            "billing-mcp", CREDENTIAL_URL, _raise_for_status_error(401, CREDENTIAL_URL)
        )

        assert "hunter2" not in message
        assert "secret" not in message

    def test_tool_failure_should_not_leak_the_target_url(self):
        message = util.describe_mcp_tool_failure("charge", CREDENTIAL_URL, RuntimeError("HTTP 401"))

        assert "hunter2" not in message
        assert "secret" not in message

    def test_tool_failure_should_not_leak_the_url_inside_the_cause(self):
        message = util.describe_mcp_tool_failure("charge", CREDENTIAL_URL, _raise_for_status_error(401, CREDENTIAL_URL))

        assert "hunter2" not in message
        assert "secret" not in message

    def test_tool_failure_should_still_name_the_target_and_status(self):
        message = util.describe_mcp_tool_failure("charge", CREDENTIAL_URL, _raise_for_status_error(401, CREDENTIAL_URL))

        assert "charge" in message
        assert "serving.internal" in message
        assert "401" in message
