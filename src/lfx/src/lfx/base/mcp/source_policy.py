"""Package-source and Docker host-mount policy for MCP stdio servers.

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

DOCKER_HOST_MOUNT_FLAGS = frozenset({"-v", "--volume", "--mount"})
DOCKER_CLUSTERABLE_SHORT_FLAGS = frozenset({"d", "i", "P", "q", "t"})
SHELL_WRAPPERS = frozenset({"sh", "bash", "cmd"})
APPROVED_SHELL_PAYLOAD_COMMANDS = frozenset({"node", "python", "python3", "npx", "uvx", "docker"})
SHELL_CONTROL_CHARS = frozenset({";", "|", "&", "$", "`", "<", ">", "\n", "\r"})

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


def _split_command(command: str, args: list[str] | None) -> tuple[str, list[str]]:
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


def _validate_docker_args(args: list[str]) -> None:
    for arg in args:
        flag = arg.split("=", 1)[0]
        short_flag_cluster = flag[1:] if flag.startswith("-") and not flag.startswith("--") else ""
        volume_index = short_flag_cluster.find("v")
        has_volume_short_flag = volume_index >= 0 and all(
            short_flag in DOCKER_CLUSTERABLE_SHORT_FLAGS for short_flag in short_flag_cluster[:volume_index]
        )
        if flag in DOCKER_HOST_MOUNT_FLAGS or has_volume_short_flag:
            _raise_disallowed("docker", arg)


def _shell_wrapped_command(command: str, args: list[str]) -> tuple[str, list[str]] | None:
    """Return a shell's explicit command payload without executing it."""
    for index, arg in enumerate(args):
        arg_lower = arg.lower()
        if command == "cmd":
            if arg_lower != "/c" or index + 1 >= len(args):
                continue
            return args[index + 1], args[index + 2 :]

        is_exec_flag = arg_lower.startswith("-") and not arg_lower.startswith("--") and "c" in arg_lower[1:]
        if not is_exec_flag:
            continue

        # bash/sh accept the command attached to -c or as the next token. Any
        # later tokens become $0/$1 rather than additional command arguments.
        option_cluster = arg[1:]
        attached_command = option_cluster[option_cluster.lower().index("c") + 1 :]
        if attached_command:
            return attached_command, []
        if index + 1 < len(args):
            return args[index + 1], []
    return None


def validate_mcp_stdio_source_policy(command: str | None, args: list[str] | None) -> None:
    """Reject package-source redirection and Docker host mounts.

    ``uvx --from`` and package-addition flags remain available only for plain
    package requirements resolved through the default trusted index. Direct
    URL, VCS, and filesystem requirements do not match that grammar.
    """
    if not command:
        return
    base_command, combined_args = _split_command(command, args)
    if base_command in SHELL_WRAPPERS:
        wrapped = _shell_wrapped_command(base_command, combined_args)
        if wrapped:
            wrapped_command, wrapped_args = wrapped
            if any(char in wrapped_command for char in SHELL_CONTROL_CHARS):
                _raise_disallowed(base_command, wrapped_command)
            wrapped_base, _ = _split_command(wrapped_command, wrapped_args)
            if wrapped_base not in APPROVED_SHELL_PAYLOAD_COMMANDS:
                _raise_disallowed(base_command, wrapped_command)
            validate_mcp_stdio_source_policy(*wrapped)
    elif base_command == "uvx":
        _validate_uvx_args(combined_args)
    elif base_command == "npx":
        _validate_npx_args(combined_args)
    elif base_command == "docker":
        _validate_docker_args(combined_args)
