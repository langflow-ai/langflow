"""LFX CLI entry point."""

import typer

from lfx.cli._authoring_commands import register as _register_authoring
from lfx.cli._remote_commands import register as _register_remote
from lfx.cli._running_commands import register as _register_running
from lfx.cli._setup_commands import register as _register_setup

app = typer.Typer(
    name="lfx",
    help="lfx - Langflow Executor",
    add_completion=False,
)

# Register command groups (order determines help-panel ordering)
_register_setup(app)
_register_authoring(app)
_register_running(app)
_register_remote(app)


def main():
    """Main entry point for the LFX CLI."""
    app()


if __name__ == "__main__":
    main()
