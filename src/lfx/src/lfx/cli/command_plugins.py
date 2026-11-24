"""Discovery and registration for third-party CLI commands.

Packages can extend the ``langflow`` root CLI by exposing a registration
callable through the ``langflow.cli_commands`` entry-point group::

    [project.entry-points."langflow.cli_commands"]
    example = "example_package.cli:register"

The callable receives the root :class:`typer.Typer` application and registers
one or more commands on it.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from importlib import metadata
from typing import TypeAlias

import typer
from typer.main import get_command_name, solve_typer_info_defaults

CLI_COMMAND_ENTRY_POINT_GROUP = "langflow.cli_commands"

CLICommandRegister: TypeAlias = Callable[[typer.Typer], None]


class CLICommandPluginError(RuntimeError):
    """Raised when installed CLI command plugins cannot be registered safely."""


def _plugin_label(entry_point: metadata.EntryPoint) -> str:
    return f"{entry_point.name!r} ({entry_point.value})"


def _load_plugins() -> list[tuple[metadata.EntryPoint, CLICommandRegister]]:
    try:
        entry_points = sorted(
            metadata.entry_points(group=CLI_COMMAND_ENTRY_POINT_GROUP),
            key=lambda entry_point: (entry_point.name, entry_point.value),
        )
    except Exception as exc:
        msg = f"Failed to discover CLI command plugins from {CLI_COMMAND_ENTRY_POINT_GROUP!r}."
        raise CLICommandPluginError(msg) from exc

    loaded_plugins: list[tuple[metadata.EntryPoint, CLICommandRegister]] = []
    for entry_point in entry_points:
        try:
            register = entry_point.load()
        except Exception as exc:
            msg = f"Failed to load CLI command plugin {_plugin_label(entry_point)}."
            raise CLICommandPluginError(msg) from exc

        if not callable(register):
            msg = f"CLI command plugin {_plugin_label(entry_point)} is not callable."
            raise CLICommandPluginError(msg)

        loaded_plugins.append((entry_point, register))

    return loaded_plugins


def _top_level_command_names(app: typer.Typer) -> list[str]:
    """Return command and named-group names as Typer exposes them at this level."""
    names = [
        command_info.name or get_command_name(command_info.callback.__name__)
        for command_info in app.registered_commands
        if command_info.callback is not None
    ]
    for group_info in app.registered_groups:
        solved_group_info = solve_typer_info_defaults(group_info)
        if solved_group_info.name:
            names.append(solved_group_info.name)
        elif group_info.typer_instance is not None:
            names.extend(_top_level_command_names(group_info.typer_instance))
    return names


def _restore_app(
    app: typer.Typer,
    commands: list[typer.models.CommandInfo],
    groups: list[typer.models.TyperInfo],
    callback: typer.models.TyperInfo | None,
) -> None:
    app.registered_commands[:] = commands
    app.registered_groups[:] = groups
    app.registered_callback = callback


def register_cli_command_plugins(app: typer.Typer) -> None:
    """Discover installed command plugins and register them on ``app``.

    Loading and validation finish before the app is mutated. Registration is
    transactional for Typer's command, group, and callback registries so a
    broken plugin cannot leave a partially configured CLI behind.
    """
    loaded_plugins = _load_plugins()
    original_commands = list(app.registered_commands)
    original_groups = list(app.registered_groups)
    original_callback = app.registered_callback
    registered_names = Counter(_top_level_command_names(app))
    registered_callback = original_callback

    for entry_point, register in loaded_plugins:
        try:
            register(app)
            current_names = Counter(_top_level_command_names(app))
        except Exception as exc:
            _restore_app(app, original_commands, original_groups, original_callback)
            msg = f"Failed to register CLI command plugin {_plugin_label(entry_point)}."
            raise CLICommandPluginError(msg) from exc

        collisions = sorted(
            name for name, count in current_names.items() if count > 1 and count > registered_names.get(name, 0)
        )
        if collisions:
            _restore_app(app, original_commands, original_groups, original_callback)
            names = ", ".join(repr(name) for name in collisions)
            msg = (
                f"CLI command plugin {_plugin_label(entry_point)} attempted to register command or group name "
                f"{names}, which is already registered."
            )
            raise CLICommandPluginError(msg)

        if registered_callback is not None and app.registered_callback is not registered_callback:
            _restore_app(app, original_commands, original_groups, original_callback)
            msg = (
                f"CLI command plugin {_plugin_label(entry_point)} attempted to replace a callback "
                "that is already registered."
            )
            raise CLICommandPluginError(msg)

        registered_names = current_names
        registered_callback = app.registered_callback
