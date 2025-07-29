"""LFX CLI entry point."""

import typer

from lfx.cli.commands import serve_command
from lfx.cli.execute import execute

app = typer.Typer(
    name="lfx",
    help="lfx - Langflow Executor",
    add_completion=False,
)

# Add commands
app.command(name="serve", help="Serve a flow as an API", no_args_is_help=True)(serve_command)
app.command(name="execute", help="Execute a flow directly", no_args_is_help=True)(execute)


def main():
    """Main entry point for the LFX CLI."""
    app()


if __name__ == "__main__":
    main()
