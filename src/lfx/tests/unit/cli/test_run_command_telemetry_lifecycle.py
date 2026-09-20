"""``lfx run`` owns the telemetry lifetime of its one-shot process, and the order is the point.

The wire test next door (``test_run_command_otlp_export.py``) proves delivery end to end. This
one pins the ordering cheaply, in-process and without OpenTelemetry installed: the providers
must be bootstrapped before the run (a span created earlier lands on the no-op proxy provider
and is gone), the protocol must be bound while the run executes, and the flush must happen
after the run ends, on every exit path. A flush that only ran on success would lose exactly the
span an operator most needs, the ``status=error`` one from the cron job that broke. The result is
echoed before the flush, so a consumer reading stdout is never held behind the export; that is
asserted as an ordering too, since a stdout check after the fact cannot tell the two apart.
"""

from pathlib import Path

import pytest
import typer
from lfx.cli.run import run
from lfx.observability import get_execution_protocol
from lfx.run.base import RunError


class _RecordingTelemetry:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    def shutdown(self) -> None:
        self._events.append("shutdown")


@pytest.fixture
def events(monkeypatch):
    """Record the order of bootstrap, run, echo, and shutdown; ``run_flow`` itself is stubbed."""
    recorded: list[str] = []

    def fake_bootstrap(**_kwargs):
        recorded.append("bootstrap")
        return _RecordingTelemetry(recorded)

    original_echo = typer.echo

    def recording_echo(*args, **kwargs):
        recorded.append("echo")
        return original_echo(*args, **kwargs)

    monkeypatch.setattr("lfx.cli.run.bootstrap_application_telemetry", fake_bootstrap)
    monkeypatch.setattr("lfx.cli.run.typer.echo", recording_echo)
    return recorded


def _invoke() -> None:
    run(
        script_path=Path("unused.json"),
        input_value=None,
        input_value_option="hello operator",
        output_format="json",
        flow_json=None,
        stdin=False,
    )


def test_bootstrap_precedes_the_run_and_shutdown_follows_it(events, monkeypatch, capsys):
    async def fake_run_flow(**_kwargs):
        events.append(f"run_flow protocol={get_execution_protocol()}")
        return {"result": "hello operator", "success": True}

    monkeypatch.setattr("lfx.cli.run.run_flow", fake_run_flow)

    _invoke()

    # The result is echoed before the flush, so a consumer reading stdout is never held behind
    # the export.
    assert events == ["bootstrap", "run_flow protocol=lfx.run", "echo", "shutdown"]
    assert '"success": true' in capsys.readouterr().out


def test_a_failed_run_still_flushes(events, monkeypatch):
    async def fake_run_flow(**_kwargs):
        events.append("run_flow")
        msg = "component exploded"
        raise RunError(msg)

    monkeypatch.setattr("lfx.cli.run.run_flow", fake_run_flow)

    with pytest.raises(typer.Exit) as exc_info:
        _invoke()

    assert exc_info.value.exit_code == 1
    # The error JSON, too, is out before the flush.
    assert events == ["bootstrap", "run_flow", "echo", "shutdown"]


def test_an_unexpected_exception_still_flushes(events, monkeypatch):
    """Not only the error the command knows how to report: anything that escapes the run."""

    async def fake_run_flow(**_kwargs):
        events.append("run_flow")
        msg = "something the command did not anticipate"
        raise RuntimeError(msg)

    monkeypatch.setattr("lfx.cli.run.run_flow", fake_run_flow)

    with pytest.raises(RuntimeError):
        _invoke()

    # Nothing is echoed for an exception the command does not know how to report; the flush
    # still runs.
    assert events == ["bootstrap", "run_flow", "shutdown"]
