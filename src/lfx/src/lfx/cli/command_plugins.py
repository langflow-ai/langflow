"""Discovery and registration for third-party CLI commands.

Packages can extend both the ``lfx`` and ``langflow`` root CLIs by exposing a
registration callable through the ``lfx.cli_commands`` entry-point group::

    [project.entry-points."lfx.cli_commands"]
    example = "example_package.cli:register"

The callable receives the root :class:`typer.Typer` application and registers
one or more commands on it.
"""

from __future__ import annotations

from collections.abc import Callable
from importlib import metadata
from typing import TypeAlias

import typer

CLI_COMMAND_ENTRY_POINT_GROUP = "lfx.cli_commands"

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

    for entry_point, register in loaded_plugins:
        try:
            register(app)
        except Exception as exc:
            app.registered_commands[:] = original_commands
            app.registered_groups[:] = original_groups
            app.registered_callback = original_callback
            msg = f"Failed to register CLI command plugin {_plugin_label(entry_point)}."
            raise CLICommandPluginError(msg) from exc
