"""Package-source and Docker host-access policy for MCP stdio servers.

Approved MCP launchers such as ``uvx`` and ``npx`` still install code before
starting a server. Their registry/configuration controls therefore belong to
Langflow's execution boundary, not to tenant-authored server configuration.
This module keeps that command-aware policy small and dependency-free so it can
be enforced both when the REST model is written and immediately before spawn.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

PACKAGE_MANAGER_CONFIG_ENV_PREFIXES = ("npm_config_", "pip_", "uv_")
WINDOWS_DRIVE_PREFIX_LENGTH = 3

UVX_BLOCKED_SOURCE_FLAGS = frozenset(
    {
        "--index",
        "--default-index",
        "--index-url",
        "--extra-index-url",
        "--find-links",
        "--no-index",
        "--config-file",
        "--env-file",
        "--with-editable",
        "--with-requirements",
        "--constraints",
        "--build-constraints",
        "--overrides",
        "--directory",
        "--project",
    }
)
UVX_BLOCKED_SHORT_SOURCE_FLAGS = frozenset({"-i", "-f", "-c", "-b"})
UVX_TRUSTED_PACKAGE_FLAGS = frozenset({"--from", "--with", "-w"})

NPX_BLOCKED_SOURCE_FLAGS = frozenset({"--registry", "--userconfig", "--globalconfig"})
NPX_TRUSTED_PACKAGE_FLAGS = frozenset({"--package"})

# ``uvx --from PACKAGE COMMAND`` decouples the package from the executable that
# uvx launches. Only known package-owned entrypoints may be selected.
UVX_SAFE_FROM_ENTRYPOINTS: dict[str, frozenset[str]] = {
    "lfx": frozenset({"lfx-mcp"}),
}

DOCKER_BLOCKED_HOST_ACCESS_FLAGS = frozenset(
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
DOCKER_CLUSTERABLE_SHORT_FLAGS = frozenset({"d", "i", "P", "q", "t"})
DOCKER_NAMESPACE_FLAGS = frozenset({"--pid", "--ipc", "--uts", "--net", "--network"})
DOCKER_DANGEROUS_SECURITY_OPT_SUBSTRINGS = ("unconfined", "disable")
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
DOCKER_HARDENED_NAMESPACE_FLAGS = frozenset({"--pid", "--ipc", "--uts", "--cgroupns", "--userns"})
DOCKER_HARDENED_NETWORK_FLAGS = frozenset({"--net", "--network"})
DOCKER_SAFE_NETWORK_VALUES = frozenset({"none", "bridge", "default"})
SHELL_CONTROL_CHARS = frozenset({";", "|", "&", "$", "`", "<", ">", "\n", "\r"})

HARDENED_ALLOWED_PYTHON_MODULES = frozenset({"langflow.agentic.mcp", "langflow.agentic.mcp.server"})
PYTHON_MODULE_MIN_ARGS = 2

# Options whose following token is a value, not uvx's package/command. Source-
# selecting options are handled separately above. This lets a later URL remain
# a legitimate MCP server argument after the trusted package token.
UVX_VALUE_OPTIONS = frozenset(
    {
        "--python-platform",
        "--torch-backend",
        "--index-strategy",
        "--keyring-provider",
        "--resolution",
        "--prerelease",
        "--fork-strategy",
        "--exclude-newer",
        "--exclude-newer-package",
        "--upgrade-package",
        "-P",
        "--reinstall-package",
        "--link-mode",
        "--config-setting",
        "-C",
        "--config-settings-package",
        "--no-build-isolation-package",
        "--no-build-package",
        "--no-binary-package",
        "--cache-dir",
        "--refresh-package",
        "--python",
        "-p",
        "--color",
        "--allow-insecure-host",
    }
)
NPX_VALUE_OPTIONS = frozenset({"--workspace", "-w", "--allow-scripts"})

_PYTHON_INDEX_REQUIREMENT = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*"
    r"(?:\[[A-Za-z0-9._,-]+\])?"
    r"(?:(?:===|==|~=|!=|<=|>=|<|>)[A-Za-z0-9*_.+!-]+"
    r"(?:,(?:===|==|~=|!=|<=|>=|<|>)[A-Za-z0-9*_.+!-]+)*)?$"
)
_NPM_INDEX_PACKAGE = re.compile(
    r"^(?:@[A-Za-z0-9][A-Za-z0-9._-]*/)?"
    r"[A-Za-z0-9][A-Za-z0-9._-]*"
    r"(?:@[A-Za-z0-9][A-Za-z0-9._+~^<>=*-]*)?$"
)
_LOCAL_ARCHIVE_SUFFIXES = (".whl", ".zip", ".tar.gz", ".tar.bz2", ".tgz")


def is_package_manager_config_env_var(key: str) -> bool:
    """Return whether *key* can reconfigure an approved package launcher."""
    return key.lower().startswith(PACKAGE_MANAGER_CONFIG_ENV_PREFIXES)


def _setting(name: str, *, default):
    """Read an MCP/security setting lazily without making this module import-heavy."""
    try:
        from lfx.services.deps import get_settings_service

        return getattr(get_settings_service().settings, name, default)
    except Exception:  # noqa: BLE001 - settings can be unavailable during early imports
        return default


def _configured_allowed_packages() -> frozenset[str] | None:
    configured = _setting("mcp_server_allowed_packages", default=None)
    if not isinstance(configured, str):
        return None
    return frozenset(_normalize_package_name(item) for item in configured.split(",") if item.strip())


def _normalize_package_name(package_spec: str) -> str:
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


def _base_command(command: str) -> str:
    normalized = command.replace("\\", "/")
    base = Path(normalized).name.lower()
    return base.removesuffix(".exe")


def _looks_like_file_path(command: str) -> bool:
    return (
        command.startswith(("/", "./", "../"))
        or "\\" in command
        or (len(command) >= WINDOWS_DRIVE_PREFIX_LENGTH and command[1:3] == ":\\")
    )


def split_mcp_stdio_command(command: str, args: list[str] | None) -> tuple[str, list[str]]:
    """Normalize a legacy packed command into an executable and argv list."""
    combined_args = list(args or [])
    executable = command
    if command and not _looks_like_file_path(command):
        try:
            command_parts = shlex.split(command)
        except ValueError as exc:
            msg = "MCP stdio command is not allowed because it cannot be parsed safely"
            raise ValueError(msg) from exc
        if command_parts:
            executable = command_parts[0]
            combined_args = command_parts[1:] + combined_args
    return executable, combined_args


def _split_command(command: str, args: list[str] | None) -> tuple[str, list[str]]:
    executable, combined_args = split_mcp_stdio_command(command, args)
    return _base_command(executable), combined_args


def _raise_disallowed(command: str, value: str) -> None:
    msg = f"Argument '{value}' is not allowed for MCP stdio command '{command}'"
    raise ValueError(msg)


def _option_value(args: list[str], index: int, command: str) -> tuple[str, int]:
    _, separator, inline_value = args[index].partition("=")
    if separator:
        if not inline_value:
            _raise_disallowed(command, args[index])
        return inline_value, index + 1
    if index + 1 >= len(args):
        _raise_disallowed(command, args[index])
    return args[index + 1], index + 2


def _validate_python_index_requirement(value: str, command: str) -> None:
    if value.lower().endswith(_LOCAL_ARCHIVE_SUFFIXES) or not _PYTHON_INDEX_REQUIREMENT.fullmatch(value):
        _raise_disallowed(command, value)


def _validate_npm_index_package(value: str, command: str) -> None:
    if value.lower().endswith(_LOCAL_ARCHIVE_SUFFIXES) or not _NPM_INDEX_PACKAGE.fullmatch(value):
        _raise_disallowed(command, value)


def _matches_short_option(arg: str, options: frozenset[str]) -> bool:
    return any(arg.startswith(option) for option in options)


def _package_runner_target(base_command: str, args: list[str]) -> tuple[str | None, str | None]:
    """Extract the installed package and an explicit uvx entrypoint."""
    index = 0
    while index < len(args):
        arg = args[index]
        if arg in {"-y", "--yes"}:
            index += 1
            continue
        if base_command == "uvx" and (arg == "--from" or arg.startswith("--from=")):
            if arg == "--from":
                if index + 2 >= len(args):
                    _raise_disallowed(base_command, arg)
                package = args[index + 1]
                entrypoint = args[index + 2]
            else:
                package = arg.split("=", 1)[1]
                if not package or index + 1 >= len(args):
                    _raise_disallowed(base_command, arg)
                entrypoint = args[index + 1]
            if entrypoint.startswith("-"):
                _raise_disallowed(base_command, entrypoint)
            return package, entrypoint
        if base_command == "npx" and (arg == "--package" or arg.startswith("--package=")):
            package, _ = _option_value(args, index, base_command)
            return package, None
        if arg.startswith("-"):
            index += 2 if arg in UVX_VALUE_OPTIONS | NPX_VALUE_OPTIONS and "=" not in arg else 1
            continue
        return arg, None
    return None, None


def _validate_allowed_package(base_command: str, args: list[str], allowed_packages: frozenset[str] | None) -> None:
    if allowed_packages is None or base_command not in {"npx", "uvx"}:
        return

    target, entrypoint = _package_runner_target(base_command, args)
    normalized_target = _normalize_package_name(target or "")
    if not normalized_target or normalized_target not in allowed_packages:
        allowed = ", ".join(sorted(allowed_packages)) or "<none>"
        msg = (
            f"Package '{target or '<missing>'}' is not allowed for MCP {base_command}. "
            f"Server-approved packages: {allowed}"
        )
        raise ValueError(msg)

    if base_command == "uvx" and entrypoint is not None:
        allowed_entrypoints = UVX_SAFE_FROM_ENTRYPOINTS.get(normalized_target, frozenset({normalized_target}))
        if entrypoint not in allowed_entrypoints:
            msg = (
                f"Entrypoint '{entrypoint}' is not allowed for MCP uvx package '{normalized_target}'. "
                f"Allowed entrypoints: {', '.join(sorted(allowed_entrypoints))}"
            )
            raise ValueError(msg)


def _validate_interpreter_invocation(base_command: str, args: list[str], *, hardened: bool) -> None:
    if not hardened:
        return
    if base_command in {"sh", "bash", "cmd"}:
        if parse_mcp_shell_wrapper(base_command, args) is not None:
            return
        msg = f"Direct shell scripts are not allowed for MCP command '{base_command}'"
        raise ValueError(msg)
    if base_command not in {"node", "python", "python3"}:
        return
    if (
        base_command in {"python", "python3"}
        and len(args) >= PYTHON_MODULE_MIN_ARGS
        and args[0] == "-m"
        and args[1] in HARDENED_ALLOWED_PYTHON_MODULES
    ):
        return
    msg = f"Interpreter command '{base_command}' is not allowed by MCP interpreter hardening"
    raise ValueError(msg)


def _validate_uvx_args(args: list[str]) -> None:
    has_from = False
    consumed_value_indexes: set[int] = set()
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--":
            break

        flag = arg.split("=", 1)[0]
        if flag in UVX_BLOCKED_SOURCE_FLAGS or _matches_short_option(arg, UVX_BLOCKED_SHORT_SOURCE_FLAGS):
            _raise_disallowed("uvx", arg)

        if flag in UVX_TRUSTED_PACKAGE_FLAGS:
            value, next_index = _option_value(args, index, "uvx")
            _validate_python_index_requirement(value, "uvx")
            has_from = has_from or flag == "--from"
            if next_index == index + 2:
                consumed_value_indexes.add(index + 1)
            index = next_index
            continue
        if arg.startswith("-w") and not arg.startswith("--"):
            value = arg[2:].removeprefix("=")
            _validate_python_index_requirement(value, "uvx")
        index += 1

    # Without --from, uvx's first positional is the package source. With a
    # trusted --from package it is merely the console-script name.
    if has_from:
        return

    index = 0
    while index < len(args):
        if index in consumed_value_indexes:
            index += 1
            continue
        arg = args[index]
        if arg == "--":
            if index + 1 < len(args):
                _validate_python_index_requirement(args[index + 1], "uvx")
            return
        flag = arg.split("=", 1)[0]
        if flag in UVX_VALUE_OPTIONS and "=" not in arg:
            index += 2
            continue
        if arg.startswith("-"):
            index += 1
            continue
        _validate_python_index_requirement(arg, "uvx")
        return


def _validate_npx_args(args: list[str]) -> None:
    has_package_option = False
    consumed_value_indexes: set[int] = set()
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--":
            break
        flag = arg.split("=", 1)[0]
        if flag in NPX_BLOCKED_SOURCE_FLAGS:
            _raise_disallowed("npx", arg)
        if flag in NPX_TRUSTED_PACKAGE_FLAGS:
            value, next_index = _option_value(args, index, "npx")
            _validate_npm_index_package(value, "npx")
            has_package_option = True
            if next_index == index + 2:
                consumed_value_indexes.add(index + 1)
            index = next_index
            continue
        index += 1

    # --package pins the installed package; the first positional is then its
    # console command. Otherwise the first positional is the package source.
    if has_package_option:
        return

    index = 0
    while index < len(args):
        if index in consumed_value_indexes:
            index += 1
            continue
        arg = args[index]
        if arg == "--":
            if index + 1 < len(args):
                _validate_npm_index_package(args[index + 1], "npx")
            return
        flag = arg.split("=", 1)[0]
        if flag in NPX_VALUE_OPTIONS and "=" not in arg:
            index += 2
            continue
        if arg.startswith("-"):
            index += 1
            continue
        _validate_npm_index_package(arg, "npx")
        return


def _is_clustered_short_flag(flag: str, target: str, allowed_prefixes: frozenset[str]) -> bool:
    if not flag.startswith("-") or flag.startswith("--"):
        return False
    cluster = flag[1:].split("=", 1)[0]
    index = cluster.find(target)
    return index >= 0 and all(short_flag in allowed_prefixes for short_flag in cluster[:index])


def _validate_docker_args(args: list[str], *, hardened: bool) -> None:
    if hardened and (not args or args[0].lower() != "run"):
        _raise_disallowed("docker", args[0] if args else "<missing run subcommand>")

    for index, arg in enumerate(args):
        flag = arg.split("=", 1)[0]
        has_volume_short_flag = _is_clustered_short_flag(flag, "v", DOCKER_CLUSTERABLE_SHORT_FLAGS)
        if flag in DOCKER_BLOCKED_HOST_ACCESS_FLAGS or has_volume_short_flag:
            _raise_disallowed("docker", arg)
        if flag in DOCKER_NAMESPACE_FLAGS:
            value, _ = _option_value(args, index, "docker")
            value = value.lower()
            if value == "host" or value.startswith("container:"):
                _raise_disallowed("docker", arg)
        if flag == "--security-opt":
            value, _ = _option_value(args, index, "docker")
            if any(part in value.lower() for part in DOCKER_DANGEROUS_SECURITY_OPT_SUBSTRINGS):
                _raise_disallowed("docker", arg)

        if not hardened:
            continue
        if flag in DOCKER_HARDENED_BLOCKED_FLAGS or any(
            _is_clustered_short_flag(flag, publish_flag, frozenset({"d", "i", "t"})) for publish_flag in ("p", "P")
        ):
            _raise_disallowed("docker", arg)
        if flag in DOCKER_HARDENED_NAMESPACE_FLAGS:
            value, _ = _option_value(args, index, "docker")
            if value.lower() == "host" or value.lower().startswith("container:"):
                _raise_disallowed("docker", arg)
        if flag in DOCKER_HARDENED_NETWORK_FLAGS:
            value, _ = _option_value(args, index, "docker")
            if value.lower() not in DOCKER_SAFE_NETWORK_VALUES:
                _raise_disallowed("docker", arg)


def _parse_shell_payload(command: str, payload: str) -> tuple[str, list[str]]:
    if any(char in payload for char in SHELL_CONTROL_CHARS):
        _raise_disallowed(command, payload)
    try:
        parts = shlex.split(payload)
    except ValueError as exc:
        msg = f"Shell wrapper '{command}' payload cannot be parsed safely"
        raise ValueError(msg) from exc
    if not parts:
        _raise_disallowed(command, payload)
    return parts[0], parts[1:]


def parse_mcp_shell_wrapper(command: str, args: list[str]) -> tuple[str, list[str]] | None:
    """Return a shell wrapper's canonical executable and argv payload."""
    command = _base_command(command)
    for index, arg in enumerate(args):
        arg_lower = arg.lower()
        if command == "cmd":
            if arg_lower != "/c" or index + 1 >= len(args):
                continue
            payload = args[index + 1 :]
            if any(char in " ".join(payload) for char in SHELL_CONTROL_CHARS):
                _raise_disallowed(command, " ".join(payload))
            return split_mcp_stdio_command(payload[0], payload[1:])

        is_exec_flag = arg_lower.startswith("-") and not arg_lower.startswith("--") and "c" in arg_lower[1:]
        if not is_exec_flag:
            continue

        # bash/sh accept the command attached to -c or as the next token. Any
        # later tokens become $0/$1 rather than additional command arguments.
        option_cluster = arg[1:]
        attached_command = option_cluster[option_cluster.lower().index("c") + 1 :]
        if attached_command:
            return _parse_shell_payload(command, attached_command)
        if index + 1 < len(args):
            return _parse_shell_payload(command, args[index + 1])
    return None


def validate_mcp_stdio_source_policy(
    command: str | None,
    args: list[str] | None,
    *,
    allowed_packages: frozenset[str] | None = None,
    docker_hardening: bool | None = None,
    interpreter_hardening: bool | None = None,
) -> None:
    """Reject package-source redirection and Docker host access.

    ``uvx --from`` and package-addition flags remain available only for plain
    package requirements resolved through the default trusted index. Direct
    URL, VCS, and filesystem requirements do not match that grammar.
    """
    if not command:
        return
    base_command, combined_args = _split_command(command, args)
    configured_packages = _configured_allowed_packages() if allowed_packages is None else allowed_packages
    use_docker_hardening = (
        bool(_setting("mcp_server_docker_hardening", default=False)) if docker_hardening is None else docker_hardening
    )
    use_interpreter_hardening = (
        bool(_setting("mcp_server_interpreter_hardening", default=False))
        if interpreter_hardening is None
        else interpreter_hardening
    )

    _validate_interpreter_invocation(base_command, combined_args, hardened=use_interpreter_hardening)
    if base_command == "uvx":
        _validate_uvx_args(combined_args)
    elif base_command == "npx":
        _validate_npx_args(combined_args)
    elif base_command == "docker":
        _validate_docker_args(combined_args, hardened=use_docker_hardening)

    _validate_allowed_package(base_command, combined_args, configured_packages)
