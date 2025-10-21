"""Main Workflow CLI command group for AI Studio."""

import click
from rich.console import Console

from .config.manager import ConfigManager

console = Console()


@click.group(name="workflow")
@click.pass_context
def workflow(ctx: click.Context) -> None:
    """Workflow specification management commands.

    Manage AI agent specifications, templates, and workflows using the Genesis
    specification system integrated with AI Studio.

    Examples:
        ai-studio workflow create -t template.yaml
        ai-studio workflow validate spec.yaml
        ai-studio workflow export flow.json
        ai-studio workflow list flows
        ai-studio workflow config show
    """
    # Initialize configuration
    try:
        ctx.ensure_object(dict)
        ctx.obj['config'] = ConfigManager()
    except Exception as e:
        console.print(f"[red]Error initializing Workflow configuration: {e}[/red]")
        ctx.exit(1)


# Commands will be registered here
# Import and register commands
def register_commands():
    """Register all Workflow commands."""
    from .commands import create, validate, export, list_cmd, config, components, templates

    workflow.add_command(create.create)
    workflow.add_command(validate.validate)
    workflow.add_command(export.export)
    workflow.add_command(list_cmd.list_cmd)
    workflow.add_command(config.config)
    workflow.add_command(components.components)
    workflow.add_command(templates.templates)


# Register commands when module is imported
register_commands()