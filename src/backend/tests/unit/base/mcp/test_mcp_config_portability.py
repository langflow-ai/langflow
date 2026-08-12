"""An MCP server config must move between environments unchanged.

``config.headers`` resolved global variables; ``config.url`` was read raw, and matching
was exact whole-value only, so a base URL could not be composed with a preserved project
id. A flow therefore had to be edited by hand on every promotion between planes.
"""

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
