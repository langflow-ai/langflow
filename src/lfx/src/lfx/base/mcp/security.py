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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection

# Env var through which Langflow binds the agentic MCP server to an authenticated user's id.
# Langflow injects it at spawn time from the request identity; it is in DANGEROUS_ENV_VARS so a
# tenant-authored stdio config cannot set it. The agentic MCP tools read it and fail closed when
# it is absent. Single source of truth for both the injector (lfx.base.mcp.util.update_tools) and
# the reader (langflow.agentic.mcp.server).
AGENTIC_USER_ID_ENV_VAR = "LANGFLOW_AGENTIC_USER_ID"

# Substring identifying the agentic MCP server module in a stdio command, so update_tools knows
# when to inject AGENTIC_USER_ID_ENV_VAR.
AGENTIC_MCP_MODULE = "langflow.agentic.mcp"

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
# These are blocked by default unless explicitly allowed via COMMAND_SAFE_FLAGS.
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

# SECURITY: Per-command allowlist of flags that would otherwise be considered dangerous.
# This enables fine-grained control over which flags are safe for specific commands.
# For example, -y/--yes are in DANGEROUS_KEYWORDS but are safe for package managers
# like npx/uvx (non-interactive mode), so they're explicitly allowed here.
COMMAND_SAFE_FLAGS: dict[str, frozenset[str]] = {
    "npx": frozenset({"-y", "--yes"}),
    "uvx": frozenset({"-y", "--yes"}),
}

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
        # -- Langflow-internal trust binding: the agentic MCP server reads the owning user's id
        #    from this env var. It must be injected by Langflow at spawn time from the
        #    authenticated identity, never supplied through a tenant-authored stdio config
        #    (which would let a tenant read/write another tenant's flows). Block it here so a
        #    tenant config that tries to set it is rejected before the server is spawned.
        "langflow_agentic_user_id",
    }
)

# SECURITY: docker-flag policy for MCP stdio servers. ``docker`` is allowlisted but several flags
# turn a container run into host access. Two modes, selected by LANGFLOW_MCP_SERVER_DOCKER_HARDENING
# (default off = lenient/previous behavior, on = strict multi-tenant policy) -- the
# mcp_server_docker_hardening setting docstring has the operator-facing description; the per-set
# comments below cover what each blocks. Both modes handle the inline (``--volume=/:/host``) and
# space-separated (``--volume /:/host``) forms.

# -- Default (lenient / previous behavior) --
DOCKER_DANGEROUS_ARGS = frozenset({"--privileged", "--cap-add"})
DOCKER_DANGEROUS_ARG_PREFIXES = ("--net=", "--network=", "--pid=", "--cap-add=", "--privileged=")

# -- Hardened (opt-in) --
# Flags with no safe value: host filesystem / device access and privilege escalation.
DOCKER_HARDENED_BLOCKED_FLAGS = frozenset(
    {
        "--privileged",
        "--cap-add",
        "-v",
        "--volume",
        "--volumes-from",
        "--mount",
        "--device",
        "--device-cgroup-rule",
    }
)
# Namespace flags: dangerous only when sharing the host's or another container's namespace.
DOCKER_HARDENED_NAMESPACE_FLAGS = frozenset({"--pid", "--ipc", "--uts"})
# Network flags: only the default-isolated values are safe. ``host`` / ``container:*`` break
# isolation, and a *named* network can be the operator's internal bridge (lateral movement), so
# anything outside this allowlist is rejected.
DOCKER_HARDENED_NETWORK_FLAGS = frozenset({"--net", "--network"})
DOCKER_SAFE_NETWORK_VALUES = frozenset({"none", "bridge", "default"})
# ``--security-opt`` values that downgrade the sandbox (seccomp=unconfined, apparmor=unconfined,
# systempaths=unconfined, label:disable). The hardening value ``no-new-privileges`` is allowed.
DOCKER_DANGEROUS_SECURITY_OPT_SUBSTRINGS = ("unconfined", "disable")

# SECURITY: Shell wrapper commands that can execute other commands.
SHELL_WRAPPERS = frozenset({"cmd", "sh", "bash"})

# SECURITY: Shell command flags that execute code.
SHELL_EXEC_FLAGS = frozenset({"-c", "/c"})


def _is_shell_exec_flag(arg: str) -> bool:
    arg_lower = arg.lower()
    if arg_lower in SHELL_EXEC_FLAGS:
        return True
    return arg_lower.startswith("-") and not arg_lower.startswith("--") and "c" in arg_lower[1:]


class MCPStdioSecurityError(ValueError):
    """Raised when an MCP stdio server config fails security validation.

    Subclasses ``ValueError`` so existing ``except ValueError`` handlers in the MCP
    connection path still catch it.
    """


def _is_file_path(command: str) -> bool:
    """Whether command looks like a filesystem path (Unix/relative/Windows) vs a bare command name."""
    drive_letter_len = 3
    return (
        command.startswith(("/", "./", "../"))
        or "\\" in command
        or (len(command) >= drive_letter_len and command[1:3] == ":\\")  # Windows drive letter
    )


def extract_base_command(command: str) -> str:
    r"""Extract the base command name from a possibly fully-qualified path.

    Handles Unix paths (``/usr/bin/node``), Windows paths
    (``C:\\Program Files\\nodejs\\node.exe``), and bare names (``node``). Also handles
    commands with arguments (e.g. ``uvx mcp-server-fetch``) by taking the first token,
    unless the value is an actual file path.
    """
    command_only = command.split()[0] if not _is_file_path(command) and command.strip() else command

    normalized_path = command_only.replace("\\", "/")
    base_command = Path(normalized_path).name

    if base_command.lower().endswith(".exe"):
        base_command = base_command[:-4]

    return base_command


def _docker_hardening_enabled() -> bool:
    """Whether the opt-in MCP docker-arg hardening policy is active.

    Reads ``LANGFLOW_MCP_SERVER_DOCKER_HARDENING`` (default False). Fails safe to False if the
    settings service is unavailable -- the hardening is an opt-in multi-tenant control, not a
    default, so an unreadable setting must not start rejecting previously-valid docker configs.
    """
    try:
        from lfx.services.deps import get_settings_service

        return bool(get_settings_service().settings.mcp_server_docker_hardening)
    except Exception:  # noqa: BLE001 - settings may be unavailable (e.g. early import); default off
        return False


def _configured_allowed_packages() -> frozenset[str] | None:
    """Return the operator-controlled package allowlist, or ``None`` when disabled."""
    try:
        from lfx.services.deps import get_settings_service

        configured = get_settings_service().settings.mcp_server_allowed_packages
    except Exception:  # noqa: BLE001 - settings may be unavailable during early import
        return None
    if not isinstance(configured, str):
        return None
    return frozenset(_normalize_package_name(item) for item in configured.split(",") if item.strip())


def _normalize_package_name(package_spec: str) -> str:
    """Normalize npm/Python package specs to the package identity used by the allowlist."""
    package = package_spec.strip().lower()
    if package.startswith("@"):
        slash_index = package.find("/")
        version_index = package.rfind("@")
        if slash_index >= 0 and version_index > slash_index:
            package = package[:version_index]
    else:
        package = package.split("@", 1)[0]

    for separator in ("==", "~=", ">=", "<=", "!=", ">", "<", "["):
        package = package.split(separator, 1)[0]
    return package.strip()


def _package_runner_target(base_command: str, args: list[str]) -> str | None:
    """Extract the package downloaded by a strict ``npx`` or ``uvx`` invocation."""
    index = 0
    while index < len(args):
        arg = args[index]
        if arg in COMMAND_SAFE_FLAGS.get(base_command, frozenset()):
            index += 1
            continue
        if base_command == "uvx" and arg == "--from":
            if index + 1 >= len(args):
                return None
            if index + 2 < len(args) and args[index + 2].startswith("-"):
                msg = f"Package runner option '{args[index + 2]}' is not allowed after --from"
                raise MCPStdioSecurityError(msg)
            return args[index + 1]
        if base_command == "uvx" and arg.startswith("--from="):
            if index + 1 < len(args) and args[index + 1].startswith("-"):
                msg = f"Package runner option '{args[index + 1]}' is not allowed after --from"
                raise MCPStdioSecurityError(msg)
            return arg.split("=", 1)[1]
        if arg.startswith("-"):
            msg = f"Package runner option '{arg}' is not allowed before the package name"
            raise MCPStdioSecurityError(msg)
        return arg
    return None


def _validate_registry_package_spec(package_spec: str) -> None:
    """Reject direct URLs, paths, aliases, and whitespace-smuggled package specs."""
    lowered = package_spec.strip().lower()
    direct_reference_markers = ("://", "file:", "git+", "github:", "npm:")
    if (
        any(marker in lowered for marker in direct_reference_markers)
        or any(char.isspace() for char in lowered)
        or lowered.startswith((".", "/", "\\"))
    ):
        msg = f"Package reference '{package_spec}' must be a registry package name or version"
        raise MCPStdioSecurityError(msg)


def _validate_package_runner(
    base_command: str,
    args: list[str],
    allowed_packages: Collection[str] | str | None,
) -> None:
    """Restrict package runners to packages selected by the server operator."""
    if allowed_packages is None or base_command not in {"npx", "uvx"}:
        return

    configured = allowed_packages.split(",") if isinstance(allowed_packages, str) else allowed_packages
    allowed = {_normalize_package_name(package) for package in configured if str(package).strip()}
    target = _package_runner_target(base_command, args)
    if target:
        _validate_registry_package_spec(target)
    normalized_target = _normalize_package_name(target or "")
    if not normalized_target or normalized_target not in allowed:
        msg = (
            f"Package '{target or '<missing>'}' is not allowed for MCP {base_command}. "
            "Configure LANGFLOW_MCP_SERVER_ALLOWED_PACKAGES with server-approved package names."
        )
        raise MCPStdioSecurityError(msg)


def _docker_arg_value(arg: str, args: list[str], index: int) -> str:
    """Return the lowercased value bound to a docker flag token.

    Handles both the inline ``--flag=value`` form and the space-separated ``--flag value`` form
    (where the value is the following token).
    """
    _, sep, inline = arg.partition("=")
    if sep:
        return inline.lower()
    return args[index + 1].lower() if index + 1 < len(args) else ""


def _raise_docker_arg(arg: str) -> None:
    msg = f"Docker argument '{arg}' is not allowed for security reasons"
    raise MCPStdioSecurityError(msg)


def _validate_docker_args_lenient(args: list[str]) -> None:
    """Default policy: only privilege/cap flags and host-namespace ``=`` forms (previous behavior)."""
    for arg in args:
        if arg in DOCKER_DANGEROUS_ARGS or arg.startswith(DOCKER_DANGEROUS_ARG_PREFIXES):
            _raise_docker_arg(arg)


def _validate_docker_args_hardened(args: list[str]) -> None:
    """Opt-in strict docker policy.

    Blocks host filesystem/device mounts, privilege flags, host/another-container namespaces,
    non-default networks, and sandbox-downgrading ``--security-opt`` -- while allowing benign
    network/namespace/security values.
    """
    for i, arg in enumerate(args):
        flag = arg.split("=", 1)[0]
        if flag in DOCKER_HARDENED_BLOCKED_FLAGS:
            _raise_docker_arg(arg)
        elif flag in DOCKER_HARDENED_NAMESPACE_FLAGS:
            value = _docker_arg_value(arg, args, i)
            if value == "host" or value.startswith("container:"):
                _raise_docker_arg(arg)
        elif flag in DOCKER_HARDENED_NETWORK_FLAGS:
            if _docker_arg_value(arg, args, i) not in DOCKER_SAFE_NETWORK_VALUES:
                _raise_docker_arg(arg)
        elif flag == "--security-opt":
            value = _docker_arg_value(arg, args, i)
            if any(s in value for s in DOCKER_DANGEROUS_SECURITY_OPT_SUBSTRINGS):
                _raise_docker_arg(arg)


def validate_mcp_stdio_config(
    command: str | None,
    args: list[str] | None,
    env: dict[str, str] | None,
    *,
    docker_hardening: bool | None = None,
    allowed_packages: Collection[str] | str | None = None,
) -> None:
    """Validate an MCP stdio command/args/env triple against the security policy.

    Mirrors the ``MCPServerConfig`` pydantic validators so the same protections apply at the
    flow-execution sink, where a tenant-embedded config never instantiates that model.

    Args:
        command: the stdio server command (allowlisted base command, optionally a file path).
        args: the command arguments to scan for metacharacters / dangerous keywords / docker flags.
        env: the environment overrides to scan against the reserved-name blocklist.
        docker_hardening: select the docker-arg policy. ``None`` (default) reads the
            ``LANGFLOW_MCP_SERVER_DOCKER_HARDENING`` setting; pass an explicit bool to override
            (used by tests). ``False`` is the lenient/previous behavior; ``True`` is the
            comprehensive multi-tenant policy.
        allowed_packages: exact package identities that ``npx``/``uvx`` may execute.
            ``None`` reads ``LANGFLOW_MCP_SERVER_ALLOWED_PACKAGES``; when neither is set,
            legacy single-tenant package-runner behavior is preserved.

    Raises:
        MCPStdioSecurityError: If the command is not allowlisted, the args contain shell
            metacharacters / dangerous keywords / illegal shell-exec flags, a shell wrapper
            wraps a non-allowed command, an env var is in the blocklist, or a docker arg
            breaks container isolation.
    """
    # Split commands with embedded arguments (e.g. "bash -c 'payload'") into separate tokens
    # so security checks can scan them. Without this, an attacker could bypass validation by
    # packing everything into the command string with empty args. File paths with spaces
    # (e.g. "C:\\Program Files\\nodejs\\node.exe") are not split since they're not shell commands.
    args = list(args or [])
    if allowed_packages is None:
        allowed_packages = _configured_allowed_packages()
    if command and not _is_file_path(command):
        try:
            command_tokens = shlex.split(command)
        except ValueError:
            # Unbalanced quotes etc. -- fall back to whitespace splitting (fail toward more checks).
            command_tokens = command.split()
        if command_tokens:
            command = command_tokens[0]
            args = command_tokens[1:] + args

    # Command allowlist.
    if command:
        base_command = extract_base_command(command)
        if base_command not in ALLOWED_MCP_COMMANDS:
            allowed_list = ", ".join(sorted(ALLOWED_MCP_COMMANDS))
            msg = f"Command '{base_command}' is not allowed for security reasons. Allowed commands: {allowed_list}"
            raise MCPStdioSecurityError(msg)

    # Shell-wrapper rules: -c/-/c only with shell wrappers, and a wrapper may only wrap
    # another allowed (non-shell) command. This is what blocks `bash -c '<payload>'`. Checked
    # before the metacharacter scan so a `-c` on a non-shell command is reported as such.
    if command and args:
        base_command = extract_base_command(command)
        has_shell_exec_flag = any(_is_shell_exec_flag(arg) for arg in args)

        if has_shell_exec_flag and base_command not in SHELL_WRAPPERS:
            msg = f"Flag -c or /c is only allowed with shell wrappers (cmd/sh/bash), not with '{base_command}'"
            raise MCPStdioSecurityError(msg)

        if base_command in SHELL_WRAPPERS:
            wrapped_command = None
            wrapped_args: list[str] = []
            for i, arg in enumerate(args):
                if _is_shell_exec_flag(arg) and i + 1 < len(args):
                    wrapped_command = args[i + 1]
                    wrapped_args = args[i + 2 :]
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

                # Validate the wrapped package runner too. The command may be one string
                # (``sh -c 'uvx package'``) or split tokens (``cmd /c uvx package``).
                try:
                    wrapped_tokens = shlex.split(wrapped_command)
                except ValueError:
                    wrapped_tokens = wrapped_command.split()
                if wrapped_tokens:
                    nested_command = wrapped_tokens[0]
                    nested_args = wrapped_tokens[1:] + wrapped_args
                    _validate_package_runner(extract_base_command(nested_command), nested_args, allowed_packages)

        _validate_package_runner(base_command, args, allowed_packages)

    # Argument metacharacters and dangerous keywords.
    if args:
        # Shell metacharacters enable command injection by breaking out of argument context
        for arg in args:
            for char in DANGEROUS_SHELL_CHARS:
                if char in arg:
                    msg = f"Argument contains dangerous shell metacharacter '{char}': {arg}"
                    raise MCPStdioSecurityError(msg)

        # SECURITY FIX: Tokenize arguments to catch combined dangerous keywords
        # like "pip install requests" that bypass whole-string matching.
        base_command = extract_base_command(command) if command else ""
        for arg in args:
            arg_lower = arg.lower()

            # Shell exec flags require special validation context to prevent code injection
            if arg_lower in SHELL_EXEC_FLAGS:
                continue

            # Some flags are dangerous in general but safe for specific commands (allowlist)
            safe_flags = COMMAND_SAFE_FLAGS.get(base_command, frozenset())
            if arg_lower in safe_flags:
                continue

            # Use shell-style parsing to handle quotes and escapes properly
            try:
                tokens = shlex.split(arg)
            except ValueError:
                # Malformed input still needs checking; whitespace split is safer than skipping
                tokens = arg.split()

            # Attackers may use separators like commas/semicolons to bypass tokenization
            expanded_tokens = []
            for token in tokens:
                import re

                subtokens = re.split(r"[,;|&]+", token)
                expanded_tokens.extend(t for t in subtokens if t)

            for token in expanded_tokens:
                token_lower = token.lower()
                if token_lower in DANGEROUS_KEYWORDS:
                    msg = f"Argument '{arg}' contains dangerous keyword '{token}' and is not allowed"
                    raise MCPStdioSecurityError(msg)

    # Environment-variable blocklist.
    if env:
        for key in env:
            lower_key = key.lower()
            if lower_key in DANGEROUS_ENV_VARS or lower_key.startswith("bash_func_"):
                msg = f"Environment variable '{key}' is not allowed for security reasons"
                raise MCPStdioSecurityError(msg)

    # Docker isolation-breaking arguments. The default (lenient) policy preserves the previous
    # behavior; the opt-in hardened policy adds host filesystem/device/namespace coverage. See
    # the DOCKER_* constants above for the rationale of each set.
    if command and args and extract_base_command(command) == "docker":
        hardened = _docker_hardening_enabled() if docker_hardening is None else docker_hardening
        if hardened:
            _validate_docker_args_hardened(args)
        else:
            _validate_docker_args_lenient(args)
