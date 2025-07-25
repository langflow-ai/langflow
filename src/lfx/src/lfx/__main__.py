"""LFX CLI entry point."""

import typer

from lfx.cli.commands import serve_command

app = typer.Typer(
    name="lfx",
    help="lfx CLI - Serve Langflow projects",
    add_completion=False,
)

# Add the serve command
app.command(name="serve", help="Serve a flow as an API")(serve_command)


def main():
    """Main entry point for the LFX CLI."""
    app()


if __name__ == "__main__":
    main()
