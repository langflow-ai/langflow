"""Upgrade commands: upgrade."""

import typer


def register(app: typer.Typer) -> None:
    """Register upgrade commands on *app*."""

    @app.command(
        name="upgrade",
        help="Check (and optionally upgrade) a flow's component compatibility",
        no_args_is_help=True,
        rich_help_panel="Authoring",
    )
    def upgrade_command_wrapper(
        flow_path: str = typer.Argument(help="Path to the flow JSON file to check"),
        *,
        write: bool = typer.Option(
            False,  # noqa: FBT003
            "--write",
            "-w",
            help="Apply safe upgrades and write the updated flow back to the file.",
        ),
        strict: bool = typer.Option(
            False,  # noqa: FBT003
            "--strict",
            help=(
                "Exit non-zero if any component is not up to date. Without --strict, pending "
                "safe upgrades exit 0 (only breaking/blocked components fail the command)."
            ),
        ),
    ) -> None:
        """Check component compatibility and optionally apply safe upgrades (lazy-loaded)."""
        from pathlib import Path

        from lfx.cli.upgrade import upgrade_command

        upgrade_command(Path(flow_path), write=write, strict=strict)
