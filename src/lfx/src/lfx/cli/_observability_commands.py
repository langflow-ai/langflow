"""Observability commands: ``observability doctor``.

A sub-app rather than a flat ``lfx doctor``, so the verb stays scoped to telemetry instead of
claiming to check the whole runtime.
"""

from __future__ import annotations

import typer

observability_app = typer.Typer(
    name="observability",
    help="Inspect and test the OTLP telemetry pipeline.",
    no_args_is_help=True,
    add_completion=False,
)


def register(app: typer.Typer) -> None:
    """Mount the ``observability`` sub-app on *app*."""
    app.add_typer(observability_app, name="observability", rich_help_panel="Setup")


@observability_app.command(
    name="doctor",
    help="Send a synthetic span, metric and log to the configured OTLP endpoint and report the result.",
)
def doctor_command(
    timeout: float | None = typer.Option(
        None,
        "--timeout",
        help=(
            "Per-export timeout in seconds. Defaults to OTEL_EXPORTER_OTLP_TIMEOUT or the SDK default. "
            "An unreachable endpoint consumes the full budget for each signal."
        ),
    ),
) -> None:
    """Confirm telemetry actually reaches the backend, instead of trusting a silent exporter."""
    from rich.console import Console

    from lfx.observability_doctor import FAILED, OK, SKIPPED, run_doctor

    # highlight=False: the captured exporter messages are full of URLs and numbers, and rich's
    # auto-highlighting turns the one thing the operator needs to read into confetti.
    console = Console(highlight=False)
    report = run_doctor(timeout=timeout)

    if report.error:
        console.print(f"[red]{report.error}[/red]")
        raise typer.Exit(1)

    console.print(f"service.name: [cyan]{report.service_name}[/cyan]")
    console.print(f"headers: [cyan]{', '.join(report.header_keys) or 'none configured'}[/cyan]\n")

    marks = {OK: "[green]OK[/green]", FAILED: "[red]FAILED[/red]", SKIPPED: "[yellow]SKIPPED[/yellow]"}
    for signal in report.signals:
        console.print(f"{marks[signal.status]} {signal.signal}: {signal.detail}")
        for message in signal.exporter_logs:
            console.print(f"    [dim]{message}[/dim]")

    if not report.ok:
        raise typer.Exit(1)
    if all(signal.status == SKIPPED for signal in report.signals):
        console.print("\n[yellow]No OTLP endpoint is configured, so nothing was sent.[/yellow]")
        raise typer.Exit(1)
    console.print(f"\nLook for [cyan]{report.service_name}[/cyan] items named [cyan]lfx.observability.doctor[/cyan].")
