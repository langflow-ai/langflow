"""Main Genesis CLI command group for AI Studio."""

import click
from rich.console import Console

from .config.manager import ConfigManager

console = Console()


@click.group(name="genesis")
@click.pass_context
def genesis(ctx: click.Context) -> None:
    """Genesis Agent specification management commands.

    Manage AI agent specifications, templates, and workflows using the Genesis
    specification system integrated with AI Studio.

    Examples:
        ai-studio genesis create -t template.yaml
        ai-studio genesis validate spec.yaml
        ai-studio genesis list flows
        ai-studio genesis config show
    """
    # Initialize configuration
    try:
        ctx.ensure_object(dict)
        ctx.obj['config'] = ConfigManager()
    except Exception as e:
        console.print(f"[red]Error initializing Genesis configuration: {e}[/red]")
        ctx.exit(1)


# Commands will be registered here
# Import and register commands
def register_commands():
    """Register all Genesis commands."""
    from .commands import create, validate, list_cmd, config, components, templates

    genesis.add_command(create.create)
    genesis.add_command(validate.validate)
    genesis.add_command(list_cmd.list_cmd)
    genesis.add_command(config.config)
    genesis.add_command(components.components)
    genesis.add_command(templates.templates)


# Register commands when module is imported
register_commands()