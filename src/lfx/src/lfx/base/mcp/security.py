"""Shared security policy for MCP stdio server configurations.

MCP server configs can come from the database or be embedded directly in a flow/tweak.
Keeping the policy in ``lfx`` lets both the REST schema and the execution boundary call the
same validation without requiring the full Langflow package in standalone LFX deployments.
"""

from pathlib import Path

from lfx.base.mcp.source_policy import (
    is_package_manager_config_env_var,
    parse_mcp_shell_wrapper,
    validate_mcp_stdio_source_policy,
)

# Shell wrappers remain supported for existing cross-platform configurations, but may only
# wrap another command from this allowlist.
ALLOWED_MCP_COMMANDS = frozenset(
    {
        "node",
        "python",
        "python3",
        "npx",
        "uvx",
        "docker",
        "cmd",
        "sh",
        "bash",
    }
)

DANGEROUS_SHELL_CHARS = frozenset({";", "|", "&", "$", "`", "<", ">", "(", ")", "\n", "\r"})
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

# Environment variables that can make an allowlisted executable load attacker-controlled code
# or configuration. Comparisons are case-insensitive.
DANGEROUS_ENV_VARS = frozenset(
    {
        "ld_preload",
        "ld_library_path",
        "ld_audit",
        "dyld_insert_libraries",
        "dyld_library_path",
        "gconv_path",
        "path",
        "node_options",
        "node_extra_ca_certs",
        "pythonstartup",
        "pythonpath",
        "home",
        "xdg_config_home",
        "xdg_data_home",
        "tmpdir",
        "tmp",
        "temp",
        "hostaliases",
        "localdomain",
        "res_options",
        "getconf_dir",
        "bash_env",
        "env",
        "bash_func_",
        "shellopts",
        "bashopts",
        "ps4",
        "ifs",
        "cdpath",
    }
)

# Backward-compatible name previously exported by ``lfx.base.mcp.util``.
DANGEROUS_MCP_ENV_VARS = DANGEROUS_ENV_VARS

SHELL_WRAPPERS = frozenset({"cmd", "sh", "bash"})
SHELL_EXEC_FLAGS = frozenset({"-c", "/c"})
MAX_SHELL_WRAPPER_DEPTH = 4


class MCPStdioSecurityError(ValueError):
    """Raised when an MCP stdio config violates the execution policy."""


def is_dangerous_mcp_env_var(key: str) -> bool:
    """Return whether an environment variable can alter MCP process execution."""
    lower_key = key.lower()
    return (
        lower_key in DANGEROUS_ENV_VARS
        or lower_key.startswith("bash_func_")
        or is_package_manager_config_env_var(lower_key)
    )


def extract_base_command(command: str) -> str:
    r"""Extract an executable name from a validated platform-specific path."""
    base_command = Path(command.replace("\\", "/")).name
    return base_command[:-4] if base_command.lower().endswith(".exe") else base_command


def validate_mcp_stdio_config(
    command: str | None,
    args: list[str] | None,
    env: dict[str, str] | None,
) -> None:
    """Validate an MCP stdio command, arguments, and environment before use.

    This mirrors the established ``MCPServerConfig`` policy at the execution boundary so
    flow-embedded and tweak-provided configs cannot bypass database/API validation.

    Raises:
        MCPStdioSecurityError: If the config violates the command, argument, environment,
            shell-wrapper, or Docker policy.
    """
    if command:
        # The command field is exactly one executable. Options belong in the structured args
        # list so every policy layer sees the same argv. Parent-directory spaces remain valid
        # for paths such as ``C:\Program Files\node.exe`` and ``/opt/Node Tools/node``.
        normalized = command.replace("\\", "/")
        executable_name = normalized.rsplit("/", 1)[-1]
        first_space = command.find(" ")
        first_separator = min((index for index, char in enumerate(command) if char in "/\\"), default=-1)
        invalid_whitespace = command != command.strip() or any(char.isspace() and char != " " for char in command)
        space_without_path_prefix = first_space >= 0 and not 0 <= first_separator < first_space
        if (
            not executable_name
            or invalid_whitespace
            or space_without_path_prefix
            or any(char.isspace() for char in executable_name)
        ):
            msg = (
                "MCP stdio command must be a single executable name or path; "
                "put options and arguments in the 'args' field"
            )
            raise MCPStdioSecurityError(msg)

    _validate_mcp_stdio_config(command, args, env, depth=0, seen=frozenset())


def _validate_mcp_stdio_config(
    command: str | None,
    args: list[str] | None,
    env: dict[str, str] | None,
    *,
    depth: int,
    seen: frozenset[tuple[str, tuple[str, ...]]],
) -> None:
    executable = command
    combined_args = list(args or [])
    if command:
        signature = (executable, tuple(combined_args))
        if signature in seen:
            msg = "MCP stdio shell wrapper recursion is not allowed"
            raise MCPStdioSecurityError(msg)
        seen = seen | {signature}

        base_command = extract_base_command(executable)
        if base_command not in ALLOWED_MCP_COMMANDS:
            allowed_list = ", ".join(sorted(ALLOWED_MCP_COMMANDS))
            msg = f"Command '{base_command}' is not allowed for security reasons. Allowed commands: {allowed_list}"
            raise MCPStdioSecurityError(msg)

    if executable and combined_args:
        base_command = extract_base_command(executable)
        has_shell_exec_flag = any(arg in SHELL_EXEC_FLAGS for arg in combined_args)
        if has_shell_exec_flag and base_command not in SHELL_WRAPPERS:
            msg = f"Flag -c or /c is only allowed with shell wrappers (cmd/sh/bash), not with '{base_command}'"
            raise MCPStdioSecurityError(msg)

    if combined_args:
        for arg in combined_args:
            for char in DANGEROUS_SHELL_CHARS:
                if char in arg:
                    msg = f"Argument contains dangerous shell metacharacter '{char}': {arg}"
                    raise MCPStdioSecurityError(msg)

        for arg in combined_args:
            arg_lower = arg.lower()
            if arg_lower in DANGEROUS_KEYWORDS and arg_lower not in SHELL_EXEC_FLAGS:
                msg = f"Argument '{arg}' is not allowed for security reasons"
                raise MCPStdioSecurityError(msg)

    if env:
        for key in env:
            if is_dangerous_mcp_env_var(key):
                msg = f"Environment variable '{key}' is not allowed for security reasons"
                raise MCPStdioSecurityError(msg)

    # Package launchers and Docker have command-aware policy beyond the generic
    # argument checks above. Keep that policy in source_policy and call it here
    # so API, embedded, legacy, and pre-spawn validation cannot drift.
    try:
        validate_mcp_stdio_source_policy(executable, combined_args)
    except ValueError as exc:
        raise MCPStdioSecurityError(str(exc)) from exc

    if executable and extract_base_command(executable) in SHELL_WRAPPERS:
        try:
            wrapped = parse_mcp_shell_wrapper(executable, combined_args)
        except ValueError as exc:
            raise MCPStdioSecurityError(str(exc)) from exc
        if wrapped:
            if depth >= MAX_SHELL_WRAPPER_DEPTH:
                msg = f"MCP stdio shell wrapper nesting exceeds {MAX_SHELL_WRAPPER_DEPTH} levels"
                raise MCPStdioSecurityError(msg)
            _validate_mcp_stdio_config(wrapped[0], wrapped[1], env, depth=depth + 1, seen=seen)
