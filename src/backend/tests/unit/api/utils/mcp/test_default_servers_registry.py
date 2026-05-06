"""Tests for the default MCP servers registry (specs and per-OS configurations)."""

import pytest
from langflow.api.utils.mcp.default_servers import _detect_os_kind
from langflow.api.utils.mcp.default_servers_specs import (
    DEFAULT_MCP_SERVERS,
    UNIX_SHELL_ALLOWED_COMMANDS,
    WINDOWS_SHELL_ALLOWED_COMMANDS,
)
from langflow.api.v2.schemas import MCPServerConfig

# Commands that, if reachable from the shell server's whitelist, would defeat the
# purpose of having a whitelist (they let the caller execute anything else).
DANGEROUS_SHELL_WHITELIST_COMMANDS = frozenset(
    {
        "bash",
        "sh",
        "zsh",
        "fish",
        "ksh",
        "csh",
        "tcsh",
        "python",
        "python3",
        "node",
        "perl",
        "ruby",
        "php",
        "eval",
        "exec",
        "sudo",
        "su",
        "doas",
        "curl",
        "wget",
        "ssh",
        "scp",
        "rsync",
        "rm",
        "mv",
        "dd",
        "chmod",
        "chown",
        "kill",
        "pkill",
        "killall",
        "powershell",
        "pwsh",
        "cmd",
        "cscript",
        "wscript",
        "regedit",
        "reg",
    }
)


class TestUnixShellDefaultSpec:
    def test_unix_shell_default_spec_passes_mcp_server_config_validation(self):
        """The Unix shell-execution spec must satisfy the production Pydantic validator.

        Why: defends against a future commit dropping a forbidden command/arg/env into
        the registry — the registry is internal but still re-validated as defense in depth.
        """
        spec = DEFAULT_MCP_SERVERS["shell-execution"]
        payload = {
            "command": spec.unix.command,
            "args": list(spec.unix.args),
            "env": dict(spec.unix.env),
        }

        MCPServerConfig.model_validate(payload)


class TestWindowsShellDefaultSpec:
    def test_windows_shell_default_spec_passes_mcp_server_config_validation(self):
        """The Windows shell-execution spec must satisfy the production Pydantic validator.

        Why: Windows requires the `cmd /c uvx ...` wrapper pattern; that wrapper must
        survive validate_command + validate_shell_wrapper_args without raising.
        """
        spec = DEFAULT_MCP_SERVERS["shell-execution"]
        payload = {
            "command": spec.windows.command,
            "args": list(spec.windows.args),
            "env": dict(spec.windows.env),
        }

        MCPServerConfig.model_validate(payload)


class TestShellWhitelistsAreSafe:
    """Audits the shell server's per-OS allowed-commands list.

    The mcp-shell-server enforces ALLOW_COMMANDS at runtime; if we ship a whitelist
    that reintroduces a shell or interpreter, the user effectively gets arbitrary
    execution. These tests are the durable spec of "what may never be in defaults".
    """

    def test_unix_allow_commands_does_not_contain_shell_or_eval(self):
        cmds = {c.strip() for c in UNIX_SHELL_ALLOWED_COMMANDS.split(",") if c.strip()}
        forbidden = cmds & DANGEROUS_SHELL_WHITELIST_COMMANDS
        assert not forbidden, (
            f"Unix shell-execution whitelist contains forbidden commands: {sorted(forbidden)}. "
            "These would let the caller bypass the whitelist."
        )

    def test_windows_allow_commands_does_not_contain_shell_or_eval(self):
        cmds = {c.strip() for c in WINDOWS_SHELL_ALLOWED_COMMANDS.split(",") if c.strip()}
        forbidden = cmds & DANGEROUS_SHELL_WHITELIST_COMMANDS
        assert not forbidden, (
            f"Windows shell-execution whitelist contains forbidden commands: {sorted(forbidden)}. "
            "These would let the caller bypass the whitelist."
        )


class TestDetectOsKind:
    """`_detect_os_kind()` collapses platform.system() into the two buckets we ship for.

    Why: WSL reports Linux, *BSD reports its own name; mcp-shell-server runs on POSIX
    via uvx in all of those. Only Windows truly needs the cmd /c wrapper.
    """

    @pytest.mark.parametrize(
        ("system_value", "expected"),
        [
            ("Linux", "unix"),
            ("Darwin", "unix"),
            ("FreeBSD", "unix"),
            ("OpenBSD", "unix"),
            ("Windows", "windows"),
        ],
    )
    def test_should_return_expected_kind_when_platform_system_returns(self, monkeypatch, system_value, expected):
        monkeypatch.setattr("platform.system", lambda: system_value)

        assert _detect_os_kind() == expected
