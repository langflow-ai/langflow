"""Integration coverage for CLI command plugins on the Langflow root app."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any

import typer
from lfx.cli import command_plugins
from typer.testing import CliRunner


@dataclass
class _FakeEntryPoint:
    name: str
    value: str
    target: Any

    def load(self) -> Any:
        return self.target


def test_langflow_root_app_registers_discovered_plugin_commands(monkeypatch):
    import langflow.__main__ as langflow_main

    def register(app: typer.Typer) -> None:
        @app.command(name="fixture-plugin")
        def fixture_plugin() -> None:
            typer.echo("langflow plugin")

    entry_point = _FakeEntryPoint("fixture", "plugins.fixture:register", register)

    with monkeypatch.context() as scoped_patch:
        scoped_patch.setattr(
            command_plugins.metadata,
            "entry_points",
            lambda *, group: [entry_point] if group == "langflow.cli_commands" else [],
        )
        reloaded_main = importlib.reload(langflow_main)
        result = CliRunner().invoke(reloaded_main.app, ["fixture-plugin"])

    importlib.reload(langflow_main)

    assert result.exit_code == 0
    assert result.output == "langflow plugin\n"
