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

from lfx.base.mcp.source_policy import (
    has_leading_cmd_exec_flag,
    is_cmd_exec_flag,
    parse_mcp_shell_wrapper,
    validate_mcp_stdio_source_policy,
)

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
        # -- Locale / message-catalog loading (glibc reads these as file/format paths) --
        "getconf_dir",
        "nlspath",
        "locpath",
        "localedir",
        "termcap",
        "terminfo",
        "terminfo_dirs",
        # -- Commands other tools shell out to. ``git``, ``less``, ``man`` and friends execute
        #    the value of these as a command line, so an approved runner that invokes any of
        #    them turns a tenant string into a spawned process.
        "lessopen",
        "lessclose",
        "lessecho",
        "less",
        "pager",
        "manpager",
        "systemd_less",
        "editor",
        "visual",
        "browser",
        # -- TLS trust-anchor replacement. Substituting the trust store lets a tenant MITM the
        #    package download that an allowlisted uvx/npx runner then executes, so these are a
        #    supply-chain code-execution vector, not merely a confidentiality issue.
        "requests_ca_bundle",
        "ssl_cert_file",
        "ssl_cert_dir",
        # -- Proxy overrides redirect that same fetch to attacker-controlled infrastructure.
        #    ``no_proxy`` only narrows proxy use and is deliberately NOT blocked.
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "ftp_proxy",
        "rsync_proxy",
        # -- Go toolchain (no safe common prefix: ``GO`` also prefixes GOOGLE_* credentials) --
        "goflags",
        "gopath",
        "goroot",
        "gobin",
        "goproxy",
        "goprivate",
        # -- JVM class/agent loading --
        "classpath",
        # -- Windows: ``cmd`` is an allowed wrapper, and these redirect what it resolves --
        "comspec",
        "psmodulepath",
        # -- Langflow-internal trust binding: the agentic MCP server reads the owning user's id
        #    from this env var. It must be injected by Langflow at spawn time from the
        #    authenticated identity, never supplied through a tenant-authored stdio config
        #    (which would let a tenant read/write another tenant's flows). Block it here so a
        #    tenant config that tries to set it is rejected before the server is spawned.
        "langflow_agentic_user_id",
    }
)

# SECURITY: whole environment-variable FAMILIES that a runtime interprets as code-loading,
# option-injection, or package-source directives.
#
# These are prefixes, not exact names, and that is the point. An exact-name blocklist can only
# ever contain the variables somebody thought to enumerate: the original list covered
# ``PYTHONPATH`` and ``NODE_OPTIONS`` but not ``OPENSSL_CONF``, which points libcrypto at a
# config file whose engine/provider sections name a shared object for OpenSSL to ``dlopen`` --
# native code execution inside whatever process the allowlisted runner starts. Denying the
# family instead means a variable nobody has enumerated yet (a new ``OPENSSL_*``, a new
# ``PYTHON*``) is refused by default rather than forwarded.
#
# Only families whose members are interpreted by the *runtime* belong here. Application
# credentials and configuration use arbitrary vendor-chosen names (``GITHUB_TOKEN``,
# ``BRAVE_API_KEY``, ``API_URL``) and must keep working -- see ``SAFE_ENV_VARS`` for the
# benign members that live inside an otherwise-denied family.
DANGEROUS_ENV_VAR_PREFIXES = (
    # -- Dynamic linker / loader (arbitrary native code) --
    "ld_",
    "dyld_",
    # -- glibc module loading --
    "gconv_",
    # -- OpenSSL config, engine and provider loading (OPENSSL_CONF et al.) --
    "openssl_",
    # -- Shell startup / function-export injection --
    "bash_",
    "zsh_",
    # -- Package runners: these redirect an allowlisted package name to attacker-controlled
    #    code by changing the index, config file, or cache the runner resolves through.
    "npm_config_",
    "pip_",
    "uv_",
    "yarn_",
    "pnpm_",
    "bun_",
    "poetry_",
    "cargo_",
    "rustup_",
    "deno_",
    "gem_",
    # -- Interpreter option / module-path injection --
    "python",
    "node_",
    "perl",
    "ruby",
    "lua_",
    "julia_",
    "php_",
    "java_",
    "jdk_",
    "_java_",
    "dotnet_",
    "coreclr_",
    "mono_",
    # -- git executes several of these as helper command lines (GIT_SSH_COMMAND, GIT_ASKPASS,
    #    GIT_PROXY_COMMAND, GIT_EXTERNAL_DIFF) and resolves its config from others.
    "git_",
    # -- TLS trust anchors and curl configuration --
    "ssl_cert_",
    "curl_",
    # -- Native plugin/module search paths honored by common shared libraries --
    "gtk_",
    "qt_",
    "gio_",
    "gst_",
    # -- Config/data directory redirection --
    "xdg_",
)

# Benign members of an otherwise-denied family. Each of these is read by the runtime as plain
# behavior configuration -- it names no file to load, no module to import, and no command to
# run -- so denying it would break ordinary MCP server configs for no security gain.
SAFE_ENV_VARS = frozenset(
    {
        # CPython output/encoding behavior; none of these load code.
        "pythonunbuffered",
        "pythonioencoding",
        "pythondontwritebytecode",
        "pythonhashseed",
        "pythonutf8",
        "pythonfaulthandler",
        # Node's own conventional mode switch (not a loader directive).
        "node_env",
        # git commit attribution and its non-interactive switch.
        "git_author_name",
        "git_author_email",
        "git_author_date",
        "git_committer_name",
        "git_committer_email",
        "git_committer_date",
        "git_terminal_prompt",
        # Headless Qt selection; picks a built-in platform plugin, not a path to load from.
        "qt_qpa_platform",
    }
)

# Backward-compatible name previously exported by ``lfx.base.mcp.util``.
DANGEROUS_MCP_ENV_VARS = DANGEROUS_ENV_VARS

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
# Flags with no safe value for an MCP stdio transport: host filesystem / device access,
# Docker API access, host port exposure, persistence, and privilege escalation.
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
        "--env-file",
        "--label-file",
        "--cidfile",
        "--gpus",
        "--use-api-socket",
        "--link",
        "--runtime",
        "-p",
        "-P",
        "--publish",
        "--publish-all",
        "--restart",
    }
)
# Namespace flags: dangerous only when sharing the host's or another container's namespace.
DOCKER_HARDENED_NAMESPACE_FLAGS = frozenset({"--pid", "--ipc", "--uts", "--cgroupns", "--userns"})
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

# SECURITY: Shell command flags that execute code. cmd.exe accepts more spellings than ``/c``
# (``/k``, ``/r``, and clustered forms such as ``/q/k``); those are recognized by
# ``is_cmd_exec_flag`` rather than listed here, because a bare ``/k`` token is a legitimate
# path operand for the non-cmd commands that also consult this set.
SHELL_EXEC_FLAGS = frozenset({"-c", "/c"})
MAX_SHELL_WRAPPER_DEPTH = 4

# Python modules owned by Langflow whose server identity is rebound from the authenticated
# request in ``update_tools``. No tenant-selected script/module is allowed in interpreter-
# hardened mode.
HARDENED_ALLOWED_PYTHON_MODULES = frozenset({"langflow.agentic.mcp", "langflow.agentic.mcp.server"})
PYTHON_MODULE_MIN_ARGS = 2


def _is_shell_exec_flag(arg: str, base_command: str = "") -> bool:
    """Return whether *arg* makes the shell wrapper execute the tokens that follow it.

    ``base_command`` selects the cmd.exe switch grammar (``/c``, ``/k``, ``/r``, and clustered
    forms such as ``/q/k``). It is opt-in because a ``/``-prefixed token is an ordinary path
    operand for every other command that consults this helper.
    """
    arg_lower = arg.lower()
    if arg_lower in SHELL_EXEC_FLAGS:
        return True
    if base_command == "cmd" and is_cmd_exec_flag(arg_lower):
        return True
    return arg_lower.startswith("-") and not arg_lower.startswith("--") and "c" in arg_lower[1:]


def _has_leading_shell_exec_flag(args: list[str], base_command: str = "") -> bool:
    """Return whether a shell execution flag appears before every script operand."""
    if not args:
        return False
    if extract_base_command(base_command) == "cmd":
        return has_leading_cmd_exec_flag(args)
    return _is_shell_exec_flag(args[0], base_command)


class MCPStdioSecurityError(ValueError):
    """Raised when an MCP stdio server config fails security validation.

    Subclasses ``ValueError`` so existing ``except ValueError`` handlers in the MCP
    connection path still catch it.
    """


def is_dangerous_mcp_env_var(key: str) -> bool:
    """Return whether an environment variable can alter MCP process execution.

    Deny-by-default across the runtime families in ``DANGEROUS_ENV_VAR_PREFIXES``, so an
    unenumerated member of a dangerous family (a newly added ``OPENSSL_*`` or ``PYTHON*``)
    is refused without a code change. ``SAFE_ENV_VARS`` carves out the specific members of
    those families that configure behavior rather than load code.

    This predicate is independent of the opt-in ``mcp_server_env_allowlist``; the allowlist
    is applied by :func:`validate_mcp_stdio_config`.
    """
    lower_key = key.lower()
    if lower_key in SAFE_ENV_VARS:
        return False
    return lower_key in DANGEROUS_ENV_VARS or lower_key.startswith(DANGEROUS_ENV_VAR_PREFIXES)


def _configured_env_allowlist() -> frozenset[str] | None:
    """Resolve the opt-in strict env allowlist, or ``None`` when the operator has not set one.

    ``None`` (the default) keeps the family policy above as the only env control, preserving
    existing configs. An explicitly empty value means "no tenant-supplied environment at all",
    which is the strictest setting -- it is deliberately distinguishable from unset.
    """
    try:
        from lfx.services.deps import get_settings_service

        configured = getattr(get_settings_service().settings, "mcp_server_env_allowlist", None)
    except Exception:  # noqa: BLE001 - settings may be unavailable (e.g. early import)
        return None
    if not isinstance(configured, str):
        return None
    return frozenset(item.strip().lower() for item in configured.split(",") if item.strip())


def _is_file_path(command: str) -> bool:
    """Whether command looks like a filesystem path (Unix/relative/Windows) vs a bare command name."""
    drive_letter_len = 3
    return (
        command.startswith(("/", "./", "../"))
        or "\\" in command
        or (len(command) >= drive_letter_len and command[1:3] in {":\\", ":/"})  # Windows drive letter
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


def _interpreter_hardening_enabled() -> bool:
    """Whether direct Python/Node MCP entrypoints are restricted for multi-tenant use."""
    try:
        from lfx.services.deps import get_settings_service

        return bool(get_settings_service().settings.mcp_server_interpreter_hardening)
    except Exception:  # noqa: BLE001 - settings may be unavailable; preserve the legacy default
        return False


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


def _validate_interpreter_invocation(base_command: str, args: list[str], *, hardened: bool) -> None:
    """Reject tenant-selected interpreter code while preserving validated wrappers/internal code."""
    if not hardened:
        return
    if base_command in SHELL_WRAPPERS:
        if _has_leading_shell_exec_flag(args, base_command):
            return
        msg = (
            f"Shell command '{base_command}' must wrap an approved MCP command when "
            "LANGFLOW_MCP_SERVER_INTERPRETER_HARDENING=true. Direct shell scripts are not allowed."
        )
        raise MCPStdioSecurityError(msg)
    if base_command not in {"node", "python", "python3"}:
        return
    if (
        base_command in {"python", "python3"}
        and len(args) >= PYTHON_MODULE_MIN_ARGS
        and args[0] == "-m"
        and args[1] in HARDENED_ALLOWED_PYTHON_MODULES
    ):
        return
    msg = (
        f"Interpreter command '{base_command}' is not allowed when "
        "LANGFLOW_MCP_SERVER_INTERPRETER_HARDENING=true. Use an operator-approved package runner instead."
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


def _is_docker_short_volume_flag(arg: str) -> bool:
    """Return whether a Docker short-option token contains the ``-v`` volume flag.

    Docker accepts the volume value attached to the shorthand (``-v/:/host``) and accepts
    ``-v`` after bundled boolean flags (``-itv /:/host``). Exact-token matching misses both.
    """
    if not arg.startswith("-") or arg.startswith("--"):
        return False
    short_flags = arg[1:].split("=", 1)[0]
    if short_flags.startswith("v"):
        return True
    volume_index = short_flags.find("v")
    return volume_index > 0 and all(flag in {"d", "i", "P", "t"} for flag in short_flags[:volume_index])


def _is_docker_short_publish_flag(arg: str) -> bool:
    """Return whether a Docker short-option token publishes host ports.

    Docker accepts values attached to ``-p`` and bundles boolean flags before it
    (for example, ``-itp8080:80``), so exact-token checks are insufficient.
    """
    if not arg.startswith("-") or arg.startswith("--"):
        return False
    short_flags = arg[1:].split("=", 1)[0]
    for publish_flag in ("p", "P"):
        publish_index = short_flags.find(publish_flag)
        if publish_index == 0 or (
            publish_index > 0 and all(flag in {"d", "i", "t"} for flag in short_flags[:publish_index])
        ):
            return True
    return False


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
    # MCP Docker transports only need ``docker run``. Other subcommands operate on existing
    # containers/images or invoke broader build/daemon surfaces (e.g. exec/cp/build/context),
    # which defeats the isolation policy when the Docker socket is available. Requiring run as
    # the first token also prevents tenant-controlled global daemon selectors such as ``-H``.
    if not args or args[0].lower() != "run":
        _raise_docker_arg(args[0] if args else "<missing run subcommand>")

    for i, arg in enumerate(args):
        flag = arg.split("=", 1)[0]
        if (
            flag in DOCKER_HARDENED_BLOCKED_FLAGS
            or _is_docker_short_volume_flag(arg)
            or _is_docker_short_publish_flag(arg)
        ):
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


def _validate_docker_invocation(args: list[str], *, hardened: bool | None) -> None:
    """Apply the selected Docker policy to top-level and shell-wrapped invocations."""
    use_hardened_policy = _docker_hardening_enabled() if hardened is None else hardened
    if use_hardened_policy:
        _validate_docker_args_hardened(args)
    else:
        _validate_docker_args_lenient(args)


def validate_mcp_stdio_config(
    command: str | None,
    args: list[str] | None,
    env: dict[str, str] | None,
    *,
    docker_hardening: bool | None = None,
    allowed_packages: Collection[str] | str | None = None,
    interpreter_hardening: bool | None = None,
    _depth: int = 0,
    _seen: frozenset[tuple[str, tuple[str, ...]]] | None = None,
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
        interpreter_hardening: restrict Python/Node entrypoints to Langflow's authenticated
            internal agentic MCP module. ``None`` reads
            ``LANGFLOW_MCP_SERVER_INTERPRETER_HARDENING``; the default is disabled for
            legacy single-tenant compatibility.

    Raises:
        MCPStdioSecurityError: If the command is not allowlisted, the args contain shell
            metacharacters / dangerous keywords / illegal shell-exec flags, a shell wrapper
            wraps a non-allowed command, an env var is in the blocklist, or a docker arg
            breaks container isolation.
    """
    args = list(args or [])
    if interpreter_hardening is None:
        interpreter_hardening = _interpreter_hardening_enabled()

    # The structured command field is exactly one executable. Options belong in args so every
    # policy layer sees the same argv. Parent-directory spaces remain valid for executable paths.
    if command:
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

        signature = (command, tuple(args))
        seen = _seen or frozenset()
        if signature in seen:
            msg = "MCP stdio shell wrapper recursion is not allowed"
            raise MCPStdioSecurityError(msg)
        _seen = seen | {signature}

    # Command allowlist.
    if command:
        base_command = extract_base_command(command)
        if base_command not in ALLOWED_MCP_COMMANDS:
            allowed_list = ", ".join(sorted(ALLOWED_MCP_COMMANDS))
            msg = f"Command '{base_command}' is not allowed for security reasons. Allowed commands: {allowed_list}"
            raise MCPStdioSecurityError(msg)
        _validate_interpreter_invocation(base_command, args, hardened=interpreter_hardening)

    normalized_allowed_packages: frozenset[str] | None = None
    if allowed_packages is not None:
        configured_packages = allowed_packages.split(",") if isinstance(allowed_packages, str) else allowed_packages
        normalized_allowed_packages = frozenset(
            _normalize_package_name(str(package)) for package in configured_packages if str(package).strip()
        )
    try:
        validate_mcp_stdio_source_policy(
            command,
            args,
            allowed_packages=normalized_allowed_packages,
            docker_hardening=docker_hardening,
            interpreter_hardening=interpreter_hardening,
        )
    except ValueError as exc:
        raise MCPStdioSecurityError(str(exc)) from exc

    # Shell-wrapper rules: -c/-/c only with shell wrappers, and a wrapper may only wrap
    # another allowed (non-shell) command. This is what blocks `bash -c '<payload>'`. Checked
    # before the metacharacter scan so a `-c` on a non-shell command is reported as such.
    if command and args:
        base_command = extract_base_command(command)
        # Shells and Python interpret ``-c`` as executable code. Package
        # runners have their own command-aware flag policy; scanning every
        # single-dash token here would misclassify valid uvx values such as
        # ``-wmcp-proxy`` merely because the package name contains a ``c``.
        checks_code_exec_flags = base_command in SHELL_WRAPPERS | {"python", "python3"}
        has_shell_exec_flag = checks_code_exec_flags and any(_is_shell_exec_flag(arg, base_command) for arg in args)

        if has_shell_exec_flag and base_command not in SHELL_WRAPPERS:
            msg = f"Flag -c or /c is only allowed with shell wrappers (cmd/sh/bash), not with '{base_command}'"
            raise MCPStdioSecurityError(msg)

        if base_command in SHELL_WRAPPERS:
            # Derive the payload from the parsed wrapper rather than a fixed argv index:
            # cmd.exe allows benign switches ahead of the execution switch ("/d /c uvx ..."),
            # so args[1] would be "/c" there and this gate would report "cannot execute 'c'".
            # ``_has_leading_shell_exec_flag`` still guards the position, so a script operand
            # cannot precede the execution switch.
            wrapped_command = None
            wrapped_args: list[str] = []
            if _has_leading_shell_exec_flag(args, base_command) and len(args) > 1:
                # cmd.exe allows benign switches ahead of the execution switch ("/d /c uvx ..."),
                # so a fixed args[1] would be "/c" and this gate would report "cannot execute 'c'".
                # Only cmd needs the parsed payload: sh/bash carry their whole command in one
                # argument ("sh -c 'id > /tmp/x'"), and splitting that here would let the gate
                # inspect only the first token instead of the full command string.
                # ``parse_mcp_shell_wrapper`` rejects shell control characters in the cmd
                # payload (and unparseable quoting) with a bare ValueError. This function's
                # contract is MCPStdioSecurityError for every policy denial, so convert it
                # here the same way the source-policy call above does -- otherwise a
                # ``cmd /c "uvx x && calc"`` denial escapes as a different exception type
                # than the equivalent ``sh -c`` denial raised by the metacharacter scan.
                try:
                    parsed_wrapper = parse_mcp_shell_wrapper(base_command, args) if base_command == "cmd" else None
                except ValueError as exc:
                    raise MCPStdioSecurityError(str(exc)) from exc
                if parsed_wrapper is not None:
                    wrapped_command, wrapped_args = parsed_wrapper
                else:
                    wrapped_command = args[1]
                    wrapped_args = args[2:]

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
                    nested_base = extract_base_command(nested_command)
                    _validate_interpreter_invocation(nested_base, nested_args, hardened=interpreter_hardening)
                    if nested_base == "docker":
                        _validate_docker_invocation(nested_args, hardened=docker_hardening)

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

    # Environment-variable policy. Two layers, both fail-safe:
    #   1. Always on: deny whole runtime families (see DANGEROUS_ENV_VAR_PREFIXES).
    #   2. Opt-in: when the operator sets mcp_server_env_allowlist, that list is authoritative
    #      and every name outside it is refused, which is the durable allowlist posture.
    if env:
        env_allowlist = _configured_env_allowlist()
        for key in env:
            if env_allowlist is not None:
                if key.strip().lower() not in env_allowlist:
                    msg = (
                        f"Environment variable '{key}' is not allowed: this deployment restricts "
                        "MCP stdio environments to LANGFLOW_MCP_SERVER_ENV_ALLOWLIST"
                    )
                    raise MCPStdioSecurityError(msg)
                continue
            if is_dangerous_mcp_env_var(key):
                msg = f"Environment variable '{key}' is not allowed for security reasons"
                raise MCPStdioSecurityError(msg)

    # Docker isolation-breaking arguments. The default (lenient) policy preserves the previous
    # behavior; the opt-in hardened policy adds host filesystem/device/namespace coverage. See
    # the DOCKER_* constants above for the rationale of each set.
    if command and args and extract_base_command(command) == "docker":
        _validate_docker_invocation(args, hardened=docker_hardening)

    if command and extract_base_command(command) in SHELL_WRAPPERS:
        try:
            wrapped = parse_mcp_shell_wrapper(command, args)
        except ValueError as exc:
            raise MCPStdioSecurityError(str(exc)) from exc
        if wrapped:
            if _depth >= MAX_SHELL_WRAPPER_DEPTH:
                msg = f"MCP stdio shell wrapper nesting exceeds {MAX_SHELL_WRAPPER_DEPTH} levels"
                raise MCPStdioSecurityError(msg)
            validate_mcp_stdio_config(
                wrapped[0],
                wrapped[1],
                env,
                docker_hardening=docker_hardening,
                allowed_packages=allowed_packages,
                interpreter_hardening=interpreter_hardening,
                _depth=_depth + 1,
                _seen=_seen,
            )
