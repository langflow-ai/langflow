"""Unit tests for the ``lfx prewarm`` command. Runs in-process."""

from __future__ import annotations

from lfx.__main__ import app
from typer.testing import CliRunner

runner = CliRunner()


def test_prewarm_command_runs_and_reports_summary():
    """`lfx prewarm` imports the core set and prints a one-line summary."""
    result = runner.invoke(app, ["prewarm"])

    assert result.exit_code == 0, result.stdout
    # Summary reports how many modules were imported.
    assert "imported" in result.stdout.lower()


def test_prewarm_appears_in_help():
    """The command is discoverable from top-level help."""
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "prewarm" in result.stdout


def test_prewarm_freeze_flag_accepted():
    """`--freeze` is a valid flag and the command still succeeds."""
    import gc

    try:
        result = runner.invoke(app, ["prewarm", "--freeze"])

        assert result.exit_code == 0, result.stdout
    finally:
        # The command froze the heap for real; don't leak that into other tests.
        gc.unfreeze()


def test_dangerous_run_flag_replaces_plain_run():
    """The execute path is gated behind an explicit, alarming flag — not a tame --run."""
    # The tame, easy-to-fat-finger flag must not exist.
    assert runner.invoke(app, ["prewarm", "--run", "--skip-run"]).exit_code != 0
    # The explicit dangerous flag parses (no --flow given, so nothing actually executes).
    ok = runner.invoke(app, ["prewarm", "--skip-run", "--unsafe-run-may-leak-connections"])
    assert ok.exit_code == 0, ok.stdout


def test_prewarm_disposes_services_on_fork_safe_path():
    """The default (fork-safe) path tears warmed services down before returning."""
    result = runner.invoke(app, ["prewarm"])

    assert result.exit_code == 0, result.stdout
    assert "Disposed warm services" in result.stdout


def test_unsafe_run_skips_service_teardown():
    """--unsafe-run keeps live connections (Firecracker), so no teardown happens."""
    result = runner.invoke(app, ["prewarm", "--skip-run", "--unsafe-run-may-leak-connections"])

    assert result.exit_code == 0, result.stdout
    assert "Disposed warm services" not in result.stdout


def test_prewarm_flow_build_only(tmp_path):
    """`--flow` builds the given flow (no --run = no execution)."""
    import json

    from lfx.components.input_output import ChatInput, ChatOutput
    from lfx.components.models_and_agents import PromptComponent
    from lfx.graph.graph.base import Graph

    ci = ChatInput(_id="ci")
    pr = PromptComponent(_id="pr")
    pr.set(template="{m}", m=ci.message_response)
    co = ChatOutput(_id="co")
    co.set(input_value=pr.build_prompt)
    flow_path = tmp_path / "hermetic.json"
    flow_path.write_text(json.dumps(Graph(ci, co).dump(name="hermetic")))

    result = runner.invoke(app, ["prewarm", "--skip-run", "--flow", str(flow_path)])

    assert result.exit_code == 0, result.stdout
    assert "built" in result.stdout
