"""Security validation for MCP (Model Context Protocol) stdio server configs.

Background
----------
A tenant-built flow can embed an MCP server config directly in the ``MCPTools`` component
value (``{"name": ..., "config": {"command": ..., "args": [...], "env": {...}}}``). When the
flow runs, that config is handed straight to a stdio transport that executes
``bash -c "exec <command> <args>"`` on the server. The pydantic ``MCPServerConfig`` validators
(command allowlist, shell-metacharacter block, env blocklist, docker-arg block) only run at
the REST ``/api/v2/mcp/servers`` layer, so the flow-execution path was completely unguarded —
any authenticated tenant could embed an arbitrary command and get RCE on the host.

This module is the single source of truth for the allowlist/blocklist data and provides
``validate_mcp_stdio_config`` so the same checks can be enforced at the execution sink (in
``lfx.base.mcp.util.update_tools``), independent of how the config arrived. The langflow
``MCPServerConfig`` pydantic validators import the constants/helper from here so the two
enforcement points can never drift.
"""

from __future__ import annotations

import shlex
from pathlib import Path

# SECURITY: Allowlist of approved MCP stdio commands. Shell wrappers (cmd/sh/bash) are
# allowed ONLY to wrap another allowed command (validated below).
ALLOWED_MCP_COMMANDS = frozenset(
    {
        "node",
        "python",
        "python3",
        "npx",
        "uvx",
        "docker",
        "cmd",  # Windows command processor (used in starter projects: cmd /c uvx ...)
        "sh",  # Unix shell (used in starter projects: sh -c uvx ...)
        "bash",  # Bash shell (alternative to sh on Unix/Linux)
    }
)

# SECURITY: Shell metacharacters that enable command injection.
DANGEROUS_SHELL_CHARS = frozenset({";", "|", "&", "$", "`", "<", ">", "(", ")", "\n", "\r"})

# SECURITY: Keywords that enable code execution or package installation.
DANGEROUS_KEYWORDS = frozenset(
    {
        "-c",
        "-e",
        "-y",
        "--yes",
        "pip",
        "install",
        "npm",
        "yarn",
        "pnpm",
        "eval",
        "exec",
    }
)

# SECURITY: Environment variables that enable code injection via approved commands.
# All comparisons are case-insensitive.
DANGEROUS_ENV_VARS = frozenset(
    {
        # -- Shared-object / dylib injection (arbitrary native code execution) --
        "ld_preload",
        "ld_library_path",
        "ld_audit",
        "dyld_insert_libraries",
        "dyld_library_path",
        # -- glibc iconv module injection --
        "gconv_path",
        # -- Command resolution override --
        "path",
        # -- Shell startup-script injection --
        "bash_env",
        "env",
        "bash_func_",  # Shellshock-style function export prefix
        "shellopts",
        "bashopts",
        "ps4",
        # -- Shell word-splitting / globbing manipulation --
        "ifs",
        "cdpath",
        # -- Node.js code injection --
        "node_options",
        "node_extra_ca_certs",
        # -- Python code injection --
        "pythonstartup",
        "pythonpath",
        # -- Home / config directory redirection --
        "home",
        "xdg_config_home",
        "xdg_data_home",
        # -- Temp directory redirection --
        "tmpdir",
        "tmp",
        "temp",
        # -- DNS / network manipulation --
        "hostaliases",
        "localdomain",
        "res_options",
        # -- Locale / getconf injection --
        "getconf_dir",
    }
)

# SECURITY: Docker-specific arguments that break container isolation.
DOCKER_DANGEROUS_ARGS = frozenset({"--privileged", "--cap-add"})
DOCKER_DANGEROUS_ARG_PREFIXES = ("--net=", "--network=", "--pid=", "--cap-add=", "--privileged=")

# SECURITY: Shell wrapper commands that can execute other commands.
SHELL_WRAPPERS = frozenset({"cmd", "sh", "bash"})

# SECURITY: Shell command flags that execute code.
SHELL_EXEC_FLAGS = frozenset({"-c", "/c"})


class MCPStdioSecurityError(ValueError):
    """Raised when an MCP stdio server config fails security validation.

    Subclasses ``ValueError`` so existing ``except ValueError`` handlers in the MCP
    connection path still catch it.
    """


def extract_base_command(command: str) -> str:
    r"""Extract the base command name from a possibly fully-qualified path.

    Handles Unix paths (``/usr/bin/node``), Windows paths
    (``C:\\Program Files\\nodejs\\node.exe``), and bare names (``node``). Also handles
    commands with arguments (e.g. ``uvx mcp-server-fetch``) by taking the first token,
    unless the value is an actual file path.
    """
    drive_letter_len = 3
    is_file_path = (
        command.startswith(("/", "./", "../"))
        or "\\" in command
        or (len(command) >= drive_letter_len and command[1:3] == ":\\")  # Windows drive letter
    )

    command_only = command.split()[0] if not is_file_path and command.strip() else command

    normalized_path = command_only.replace("\\", "/")
    base_command = Path(normalized_path).name

    if base_command.lower().endswith(".exe"):
        base_command = base_command[:-4]

    return base_command


def validate_mcp_stdio_config(
    command: str | None,
    args: list[str] | None,
    env: dict[str, str] | None,
) -> None:
    """Validate an MCP stdio command/args/env triple against the security policy.

    Mirrors the ``MCPServerConfig`` pydantic validators so the same protections apply at the
    flow-execution sink, where a tenant-embedded config never instantiates that model.

    Raises:
        MCPStdioSecurityError: If the command is not allowlisted, the args contain shell
            metacharacters / dangerous keywords / illegal shell-exec flags, a shell wrapper
            wraps a non-allowed command, an env var is in the blocklist, or a docker arg
            breaks container isolation.
    """
    # 0) Tokenize a command that carries its own arguments (e.g. "bash -c '<payload>'").
    #    Without this, a tenant can pack the whole payload into ``command`` with empty ``args``:
    #    extract_base_command() only inspects the first token for the allowlist, the metacharacter
    #    scan only iterates ``args``, and the shell-wrapper check is skipped when ``args`` is empty
    #    -- so the embedded ``-c '<payload>'`` would never be examined. Splitting here folds those
    #    embedded tokens into ``args`` so every check below sees them. Applies to ALL callers
    #    (update_tools, the REST MCPServerConfig, the legacy stdio component), keeping the
    #    REST-layer and execution-time enforcement identical.
    #    Do NOT split file-path commands: an absolute/relative/Windows path may legitimately
    #    contain spaces (e.g. "C:\\Program Files\\nodejs\\node.exe") and carries no embedded
    #    shell arguments -- extract_base_command resolves those directly.
    args = list(args or [])
    if command:
        drive_letter_len = 3
        is_file_path = (
            command.startswith(("/", "./", "../"))
            or "\\" in command
            or (len(command) >= drive_letter_len and command[1:3] == ":\\")  # Windows drive letter
        )
        if not is_file_path:
            try:
                command_tokens = shlex.split(command)
            except ValueError:
                # Unbalanced quotes etc. -- fall back to whitespace splitting (fail toward more checks).
                command_tokens = command.split()
            if command_tokens:
                command = command_tokens[0]
                args = command_tokens[1:] + args

    # 1) Command allowlist.
    if command:
        base_command = extract_base_command(command)
        if base_command not in ALLOWED_MCP_COMMANDS:
            allowed_list = ", ".join(sorted(ALLOWED_MCP_COMMANDS))
            msg = f"Command '{base_command}' is not allowed for security reasons. Allowed commands: {allowed_list}"
            raise MCPStdioSecurityError(msg)

    # 2) Shell-wrapper rules: -c/-/c only with shell wrappers, and a wrapper may only wrap
    #    another allowed (non-shell) command. This is what blocks `bash -c '<payload>'`. Checked
    #    before the metacharacter scan so a `-c` on a non-shell command is reported as such.
    if command and args:
        base_command = extract_base_command(command)
        has_shell_exec_flag = any(arg in SHELL_EXEC_FLAGS for arg in args)

        if has_shell_exec_flag and base_command not in SHELL_WRAPPERS:
            msg = f"Flag -c or /c is only allowed with shell wrappers (cmd/sh/bash), not with '{base_command}'"
            raise MCPStdioSecurityError(msg)

        if base_command in SHELL_WRAPPERS:
            wrapped_command = None
            for i, arg in enumerate(args):
                if arg in SHELL_EXEC_FLAGS and i + 1 < len(args):
                    wrapped_command = args[i + 1]
                    break

            if wrapped_command:
                wrapped_base = extract_base_command(wrapped_command)
                allowed_wrapped = ALLOWED_MCP_COMMANDS - SHELL_WRAPPERS
                if wrapped_base not in allowed_wrapped:
                    msg = (
                        f"Shell wrapper '{base_command}' cannot execute '{wrapped_base}'. "
                        f"Only these commands can be wrapped: {', '.join(sorted(allowed_wrapped))}"
                    )
                    raise MCPStdioSecurityError(msg)

    # 3) Argument metacharacters and dangerous keywords.
    if args:
        for arg in args:
            for char in DANGEROUS_SHELL_CHARS:
                if char in arg:
                    msg = f"Argument contains dangerous shell metacharacter '{char}': {arg}"
                    raise MCPStdioSecurityError(msg)
        for arg in args:
            arg_lower = arg.lower()
            if arg_lower in DANGEROUS_KEYWORDS and arg_lower not in SHELL_EXEC_FLAGS:
                msg = f"Argument '{arg}' is not allowed for security reasons"
                raise MCPStdioSecurityError(msg)

    # 4) Environment-variable blocklist.
    if env:
        for key in env:
            lower_key = key.lower()
            if lower_key in DANGEROUS_ENV_VARS or lower_key.startswith("bash_func_"):
                msg = f"Environment variable '{key}' is not allowed for security reasons"
                raise MCPStdioSecurityError(msg)

    # 5) Docker isolation-breaking arguments.
    if command and args and extract_base_command(command) == "docker":
        for arg in args:
            if arg in DOCKER_DANGEROUS_ARGS or arg.startswith(DOCKER_DANGEROUS_ARG_PREFIXES):
                msg = f"Docker argument '{arg}' is not allowed for security reasons"
                raise MCPStdioSecurityError(msg)
