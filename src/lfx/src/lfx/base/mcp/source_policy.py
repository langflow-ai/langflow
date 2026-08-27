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
UVX_ATTACHED_VALUE_SHORT_FLAGS = frozenset({"-C", "-P", "-p"})
UVX_CLUSTERABLE_BOOLEAN_SHORT_FLAGS = frozenset({"U", "V", "h", "n", "q", "v"})
UVX_SAFE_BOOLEAN_FLAGS = frozenset(
    {
        "-U",
        "-V",
        "-h",
        "-n",
        "-q",
        "-v",
        "-y",
        "--compile-bytecode",
        "--help",
        "--isolated",
        "--lfs",
        "--managed-python",
        "--native-tls",
        "--no-binary",
        "--no-build",
        "--no-build-isolation",
        "--no-cache",
        "--no-config",
        "--no-env-file",
        "--no-managed-python",
        "--no-progress",
        "--no-python-downloads",
        "--no-sources",
        "--offline",
        "--quiet",
        "--refresh",
        "--reinstall",
        "--upgrade",
        "--verbose",
        "--version",
        "--yes",
    }
)

NPX_BLOCKED_SOURCE_FLAGS = frozenset(
    {
        "--registry",
        "--userconfig",
        "--globalconfig",
        "--call",
        "-c",
        "--shell",
        "--script-shell",
        "--dangerously-allow-all-scripts",
    }
)
NPX_TRUSTED_PACKAGE_FLAGS = frozenset({"--package", "-p"})
NPX_SAFE_BOOLEAN_FLAGS = frozenset(
    {"-y", "--yes", "--workspaces", "--include-workspace-root", "--strict-allow-scripts"}
)

# Explicit ``--package`` mode decouples installation from command selection, so
# only package-owned executables verified by Langflow may be selected. Packages
# without an entry here remain usable through the safer direct ``npx PACKAGE``
# form, where npx derives the executable from that package's metadata.
NPX_SAFE_PACKAGE_ENTRYPOINTS: dict[str, frozenset[str]] = {
    "mcp-proxy": frozenset({"mcp-proxy"}),
}

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
        "--no-sources-package",
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
        or (len(command) >= WINDOWS_DRIVE_PREFIX_LENGTH and command[1:3] in {":\\", ":/"})
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
    return not arg.startswith("--") and any(arg.startswith(option) for option in options)


def _is_uvx_safe_boolean_flag(arg: str) -> bool:
    """Accept known uvx booleans, including clap-compatible short clusters."""
    return arg in UVX_SAFE_BOOLEAN_FLAGS or (
        arg.startswith("-")
        and not arg.startswith("--")
        and len(arg) > 1
        and set(arg[1:]) <= UVX_CLUSTERABLE_BOOLEAN_SHORT_FLAGS
    )


def _uvx_package_selection(args: list[str]) -> tuple[list[str], list[str], str | None]:
    """Return all --from/--with packages and the selected uvx command."""
    from_packages: list[str] = []
    with_packages: list[str] = []
    command: str | None = None
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--":
            if index + 1 < len(args):
                command = args[index + 1]
            break

        flag = arg.split("=", 1)[0]
        if flag in UVX_BLOCKED_SOURCE_FLAGS or _matches_short_option(arg, UVX_BLOCKED_SHORT_SOURCE_FLAGS):
            _raise_disallowed("uvx", arg)

        if arg.startswith("-w") and not arg.startswith("--") and arg != "-w":
            package = arg[2:].removeprefix("=")
            if not package:
                _raise_disallowed("uvx", arg)
            with_packages.append(package)
            index += 1
            continue
        if flag in UVX_TRUSTED_PACKAGE_FLAGS:
            package, index = _option_value(args, index, "uvx")
            if flag == "--from":
                from_packages.append(package)
            else:
                with_packages.append(package)
            continue
        if flag in UVX_VALUE_OPTIONS:
            _, index = _option_value(args, index, "uvx")
            continue
        attached_value_flag = next(
            (option for option in UVX_ATTACHED_VALUE_SHORT_FLAGS if arg.startswith(option) and arg != option), None
        )
        if attached_value_flag is not None:
            if not arg[len(attached_value_flag) :].removeprefix("="):
                _raise_disallowed("uvx", arg)
            index += 1
            continue
        if _is_uvx_safe_boolean_flag(arg):
            index += 1
            continue
        if arg.startswith("-"):
            # Fail closed: uvx can add value-taking options without exposing
            # them in concise help. Skipping an unknown flag could mistake its
            # value for the package while uvx executes the following operand.
            _raise_disallowed("uvx", arg)
        command = arg
        break
    return from_packages, with_packages, command


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


def _npx_package_selection(args: list[str]) -> tuple[list[str], str | None]:
    """Return every explicit npx package and the command selected from them."""
    packages: list[str] = []
    entrypoint: str | None = None
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--":
            if entrypoint is None and index + 1 < len(args):
                entrypoint = args[index + 1]
            break

        flag = arg.split("=", 1)[0]
        if flag in NPX_TRUSTED_PACKAGE_FLAGS:
            package, index = _option_value(args, index, "npx")
            packages.append(package)
            continue
        if flag in NPX_VALUE_OPTIONS:
            _, index = _option_value(args, index, "npx")
            continue
        if flag in NPX_SAFE_BOOLEAN_FLAGS:
            index += 1
            continue
        if arg.startswith("-"):
            _raise_disallowed("npx", arg)
        entrypoint = arg
        break
    return packages, entrypoint


def _validate_npx_package_selection(args: list[str], allowed_packages: frozenset[str]) -> bool:
    """Validate all explicit packages and their selected npx executable."""
    packages, entrypoint = _npx_package_selection(args)
    if not packages:
        return False

    normalized_packages: list[str] = []
    for package in packages:
        normalized_package = _normalize_package_name(package)
        if not normalized_package or normalized_package not in allowed_packages:
            allowed = ", ".join(sorted(allowed_packages)) or "<none>"
            msg = f"Package '{package or '<missing>'}' is not allowed for MCP npx. Server-approved packages: {allowed}"
            raise ValueError(msg)
        normalized_packages.append(normalized_package)

    # An explicit --package decouples installation from command selection. Keep
    # the command tied to one of those packages instead of letting npx launch an
    # arbitrary executable already present on PATH.
    unverified_packages = [package for package in normalized_packages if package not in NPX_SAFE_PACKAGE_ENTRYPOINTS]
    if unverified_packages:
        msg = (
            f"Package '{unverified_packages[0]}' has no verified entrypoint for explicit MCP npx package selection; "
            "use the direct npx package form"
        )
        raise ValueError(msg)
    allowed_entrypoints = set().union(
        *(NPX_SAFE_PACKAGE_ENTRYPOINTS.get(package, frozenset()) for package in normalized_packages)
    )
    if entrypoint not in allowed_entrypoints:
        allowed = ", ".join(sorted(allowed_entrypoints)) or "<none>"
        msg = (
            f"Entrypoint '{entrypoint or '<missing>'}' is not allowed for MCP npx packages "
            f"'{', '.join(normalized_packages)}'. Allowed entrypoints: {allowed}"
        )
        raise ValueError(msg)
    return True


def _validate_allowed_package(base_command: str, args: list[str], allowed_packages: frozenset[str] | None) -> None:
    if allowed_packages is None or base_command not in {"npx", "uvx"}:
        return

    if base_command == "uvx":
        from_packages, with_packages, command = _uvx_package_selection(args)
        selected_packages = [*from_packages, *with_packages]
        if not from_packages:
            selected_packages.append(command or "<missing>")

        for package in selected_packages:
            normalized_package = _normalize_package_name(package)
            if not normalized_package or normalized_package not in allowed_packages:
                allowed = ", ".join(sorted(allowed_packages)) or "<none>"
                msg = f"Package '{package}' is not allowed for MCP uvx. Server-approved packages: {allowed}"
                raise ValueError(msg)

        if from_packages:
            if len(from_packages) != 1:
                msg = "Multiple --from packages are not allowed for MCP uvx"
                raise ValueError(msg)
            primary_package = _normalize_package_name(from_packages[0])
            allowed_entrypoints = UVX_SAFE_FROM_ENTRYPOINTS.get(primary_package, frozenset({primary_package}))
            if command not in allowed_entrypoints:
                msg = (
                    f"Entrypoint '{command or '<missing>'}' is not allowed for MCP uvx package '{primary_package}'. "
                    f"Allowed entrypoints: {', '.join(sorted(allowed_entrypoints))}"
                )
                raise ValueError(msg)
        return

    if base_command == "npx" and _validate_npx_package_selection(args, allowed_packages):
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
        first_arg = args[0].lower() if args else ""
        has_leading_exec_flag = (
            first_arg == "/c"
            if base_command == "cmd"
            else first_arg.startswith("-") and not first_arg.startswith("--") and "c" in first_arg[1:]
        )
        if has_leading_exec_flag and parse_mcp_shell_wrapper(base_command, args) is not None:
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
    from_packages, with_packages, command = _uvx_package_selection(args)
    for package in [*from_packages, *with_packages]:
        _validate_python_index_requirement(package, "uvx")
    if not from_packages and command is not None:
        _validate_python_index_requirement(command, "uvx")


def _validate_npx_args(args: list[str]) -> None:
    has_package_option = False
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--":
            if not has_package_option and index + 1 < len(args):
                _validate_npm_index_package(args[index + 1], "npx")
            return
        flag = arg.split("=", 1)[0]
        if flag in NPX_BLOCKED_SOURCE_FLAGS:
            _raise_disallowed("npx", arg)
        if flag in NPX_TRUSTED_PACKAGE_FLAGS:
            value, next_index = _option_value(args, index, "npx")
            _validate_npm_index_package(value, "npx")
            has_package_option = True
            index = next_index
            continue
        if flag in NPX_VALUE_OPTIONS:
            _, index = _option_value(args, index, "npx")
            continue
        if flag in NPX_SAFE_BOOLEAN_FLAGS:
            index += 1
            continue
        if arg.startswith("-"):
            _raise_disallowed("npx", arg)
        if not has_package_option:
            _validate_npm_index_package(arg, "npx")
        return


def _is_clustered_short_flag(flag: str, target: str, allowed_prefixes: frozenset[str]) -> bool:
    if not flag.startswith("-") or flag.startswith("--"):
        return False
    cluster = flag[1:].split("=", 1)[0]
    index = cluster.find(target)
    return index >= 0 and all(short_flag in allowed_prefixes for short_flag in cluster[:index])


def _validate_docker_args(args: list[str], *, hardened: bool) -> None:
    # Docker is allowlisted only as an isolated MCP server launcher. Other
    # subcommands operate on the shared daemon and bypass the run-argument policy.
    if not args or args[0].lower() != "run":
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
