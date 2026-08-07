"""Tests for third-party CLI command registration."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any

import pytest
import typer
from lfx.cli import command_plugins
from typer.testing import CliRunner


@dataclass
class _FakeEntryPoint:
    name: str
    value: str
    target: Any = None
    error: Exception | None = None

    def load(self) -> Any:
        if self.error is not None:
            raise self.error
        return self.target


def _command_register(name: str, calls: list[str], output: str = "registered"):
    def register(app: typer.Typer) -> None:
        calls.append(name)

        @app.command(name=name)
        def plugin_command() -> None:
            typer.echo(output)

    return register


def test_plugins_are_discovered_from_the_documented_group_in_deterministic_order(monkeypatch):
    calls: list[str] = []
    requested_groups: list[str] = []
    entry_points = [
        _FakeEntryPoint("zeta", "plugins.zeta:register", _command_register("zeta", calls)),
        _FakeEntryPoint("alpha", "plugins.alpha:register", _command_register("alpha", calls)),
    ]

    def discover(*, group: str):
        requested_groups.append(group)
        return entry_points

    monkeypatch.setattr(command_plugins.metadata, "entry_points", discover)

    command_plugins.register_cli_command_plugins(typer.Typer())

    assert requested_groups == ["lfx.cli_commands"]
    assert calls == ["alpha", "zeta"]


def test_registered_plugin_command_is_invokable(monkeypatch):
    app = typer.Typer()
    entry_point = _FakeEntryPoint(
        "hello",
        "plugins.hello:register",
        _command_register("hello", [], output="hello from plugin"),
    )
    monkeypatch.setattr(
        command_plugins.metadata,
        "entry_points",
        lambda *, group: [entry_point] if group == "lfx.cli_commands" else [],
    )

    command_plugins.register_cli_command_plugins(app)
    result = CliRunner().invoke(app, ["hello"])

    assert result.exit_code == 0
    assert result.output == "hello from plugin\n"


def test_non_callable_plugin_fails_before_mutating_the_app(monkeypatch):
    calls: list[str] = []
    entry_points = [
        _FakeEntryPoint("alpha", "plugins.alpha:register", _command_register("alpha", calls)),
        _FakeEntryPoint("broken", "plugins.broken:not_register", object()),
    ]
    monkeypatch.setattr(
        command_plugins.metadata,
        "entry_points",
        lambda *, group: entry_points if group == "lfx.cli_commands" else [],
    )

    with pytest.raises(command_plugins.CLICommandPluginError, match=r"broken.*not callable"):
        command_plugins.register_cli_command_plugins(typer.Typer())

    assert calls == []


def test_plugin_load_failure_names_the_plugin_and_preserves_the_cause(monkeypatch):
    failure = ImportError("dependency unavailable")
    entry_point = _FakeEntryPoint("broken", "plugins.broken:register", error=failure)
    monkeypatch.setattr(
        command_plugins.metadata,
        "entry_points",
        lambda *, group: [entry_point] if group == "lfx.cli_commands" else [],
    )

    with pytest.raises(command_plugins.CLICommandPluginError, match=r"broken.*plugins.broken:register") as exc_info:
        command_plugins.register_cli_command_plugins(typer.Typer())

    assert exc_info.value.__cause__ is failure


def test_plugin_registration_failure_rolls_back_all_plugin_commands(monkeypatch):
    app = typer.Typer()

    @app.command(name="builtin")
    def builtin() -> None:
        pass

    def broken_register(target_app: typer.Typer) -> None:
        target_app.command(name="partial")(lambda: None)
        msg = "registration exploded"
        raise RuntimeError(msg)

    failure_entry_point = _FakeEntryPoint("broken", "plugins.broken:register", broken_register)
    monkeypatch.setattr(
        command_plugins.metadata,
        "entry_points",
        lambda *, group: [failure_entry_point] if group == "lfx.cli_commands" else [],
    )

    with pytest.raises(command_plugins.CLICommandPluginError, match=r"broken.*plugins.broken:register") as exc_info:
        command_plugins.register_cli_command_plugins(app)

    assert isinstance(exc_info.value.__cause__, RuntimeError)
    assert [command.name for command in app.registered_commands] == ["builtin"]


def test_entry_point_discovery_failure_is_reported_with_its_cause(monkeypatch):
    failure = RuntimeError("metadata unavailable")

    def fail_discovery(*, group: str):
        assert group == "lfx.cli_commands"
        raise failure

    monkeypatch.setattr(command_plugins.metadata, "entry_points", fail_discovery)

    with pytest.raises(command_plugins.CLICommandPluginError, match=r"discover.*lfx.cli_commands") as exc_info:
        command_plugins.register_cli_command_plugins(typer.Typer())

    assert exc_info.value.__cause__ is failure


def test_lfx_root_app_registers_discovered_plugin_commands(monkeypatch):
    import lfx.__main__ as lfx_main

    entry_point = _FakeEntryPoint(
        "fixture",
        "plugins.fixture:register",
        _command_register("fixture-plugin", [], output="lfx plugin"),
    )

    with monkeypatch.context() as scoped_patch:
        scoped_patch.setattr(
            command_plugins.metadata,
            "entry_points",
            lambda *, group: [entry_point] if group == "lfx.cli_commands" else [],
        )
        reloaded_main = importlib.reload(lfx_main)
        result = CliRunner().invoke(reloaded_main.app, ["fixture-plugin"])

    importlib.reload(lfx_main)

    assert result.exit_code == 0
    assert result.output == "lfx plugin\n"
