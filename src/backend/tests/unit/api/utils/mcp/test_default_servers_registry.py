"""Tests for the default MCP servers registry."""

from langflow.api.utils.mcp.default_servers_specs import DEFAULT_MCP_SERVERS
from langflow.api.v2.schemas import MCPServerConfig


class TestShellExecutionUsesDesktopCommander:
    """The `shell-execution` slot is backed by wonderwhy-er/desktop-commander.

    Why: the previous provider (tumf/mcp-shell-server) was POSIX-only via `import pwd`
    and silently broke on Windows even though our config validator accepted the spec.
    DesktopCommander is cross-platform via `npx`, with explicit Windows support. The
    slot name remains `shell-execution` — capability stays stable, provider can swap.
    """

    def test_shell_execution_spec_launches_desktop_commander_via_npx_yes(self):
        spec = DEFAULT_MCP_SERVERS["shell-execution"]

        assert spec.config.command == "npx"
        assert list(spec.config.args) == ["-y", "@wonderwhy-er/desktop-commander@latest"]
        assert spec.config.env == {}

    def test_shell_execution_spec_passes_mcp_server_config_validation(self):
        """Defense-in-depth: registry payload must clear the production Pydantic validator.

        Exercises the package-allowlisted -y exception in validate_yes_flag_pattern.
        """
        spec = DEFAULT_MCP_SERVERS["shell-execution"]
        payload = {
            "command": spec.config.command,
            "args": list(spec.config.args),
            "env": dict(spec.config.env),
        }

        MCPServerConfig.model_validate(payload)

    def test_shell_execution_spec_declares_60s_startup_timeout(self):
        """Slice E5: spec opts into a 60s startup timeout for first-run.

        First-run of `npx -y @wonderwhy-er/desktop-commander@latest` can take
        30-90s while npm downloads the package + deps. The global default is
        20s; the per-spec override avoids first-click timeouts without raising
        the global default for every other server.
        """
        spec = DEFAULT_MCP_SERVERS["shell-execution"]

        assert spec.startup_timeout_seconds == 60
