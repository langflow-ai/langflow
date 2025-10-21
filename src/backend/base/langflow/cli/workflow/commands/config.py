"""Config command for Genesis CLI."""

from typing import Optional

import click

from ..utils.output import success_message, error_message, warning_message, info_message


@click.group(name="config")
@click.pass_context
def config(ctx: click.Context):
    """
    Manage Genesis CLI configuration.

    Configure AI Studio connection, default settings, and import existing
    genesis-agent-cli configurations.

    Examples:

        # Show current configuration
        ai-studio genesis config show

        # Set AI Studio URL
        ai-studio genesis config set ai_studio_url http://localhost:7860

        # Set API key
        ai-studio genesis config set ai_studio_api_key your-api-key

        # Import from genesis-agent-cli
        ai-studio genesis config import
    """
    pass


@config.command(name="show")
@click.option("--format", type=click.Choice(['table', 'yaml', 'json']), default='table', help="Output format")
@click.pass_context
def show_config(ctx: click.Context, format: str):
    """Show current configuration."""
    try:
        config_manager = ctx.obj['config']

        if format == 'json':
            import json
            config_dict = config_manager.get_config().model_dump(exclude_none=True)
            click.echo(json.dumps(config_dict, indent=2))
        elif format == 'yaml':
            import yaml
            config_dict = config_manager.get_config().model_dump(exclude_none=True)
            click.echo(yaml.dump(config_dict, default_flow_style=False))
        else:  # table format
            config_info = config_manager.show_config()
            click.echo(config_info)

    except Exception as e:
        error_message(f"Failed to show configuration: {e}")
        ctx.exit(1)


@config.command(name="set")
@click.argument('key')
@click.argument('value')
@click.pass_context
def set_config(ctx: click.Context, key: str, value: str):
    """Set a configuration value.

    Available keys:
        ai_studio_url       - AI Studio URL
        ai_studio_api_key   - API key for authentication
        default_project     - Default project for flows
        default_folder      - Default folder for flows
        templates_path      - Custom templates directory
        verbose             - Enable verbose output (true/false)
    """
    try:
        config_manager = ctx.obj['config']

        # Convert boolean strings
        if value.lower() in ['true', 'false']:
            value = value.lower() == 'true'

        # Update configuration
        config_manager.update_config(**{key: value})

        success_message(f"Configuration updated: {key} = {value}")

    except Exception as e:
        error_message(f"Failed to set configuration: {e}")
        ctx.exit(1)


@config.command(name="import")
@click.option(
    "--from-file",
    type=click.Path(exists=True),
    help="Import from specific genesis-agent-cli config file"
)
@click.pass_context
def import_config(ctx: click.Context, from_file: Optional[str]):
    """Import configuration from existing genesis-agent-cli."""
    try:
        config_manager = ctx.obj['config']

        if from_file:
            info_message(f"Importing configuration from: {from_file}")
            # TODO: Implement import from specific file
            warning_message("Import from specific file not yet implemented")
        else:
            info_message("Searching for existing genesis-agent-cli configuration...")
            imported = config_manager.import_genesis_agent_config()

            if imported:
                success_message("Configuration imported successfully from genesis-agent-cli")
                click.echo("\nUpdated configuration:")
                config_info = config_manager.show_config()
                click.echo(config_info)
            else:
                warning_message("No genesis-agent-cli configuration found to import")
                info_message("Looked for:")
                info_message("  - ~/.genesis-agent.yaml")
                info_message("  - ./.genesis-agent.yaml")
                info_message("  - ./.env")

    except Exception as e:
        error_message(f"Failed to import configuration: {e}")
        ctx.exit(1)


@config.command(name="test")
@click.pass_context
def test_config(ctx: click.Context):
    """Test current configuration by connecting to AI Studio."""
    try:
        config_manager = ctx.obj['config']
        from ..utils.api_client import APIClient

        info_message("Testing connection to AI Studio...")

        api_client = APIClient(config_manager)

        # Test health check
        if api_client.health_check_sync():
            success_message(f"Successfully connected to AI Studio at {config_manager.ai_studio_url}")

            # Test authentication if API key is set
            if config_manager.api_key:
                try:
                    # Try to fetch components to test API key
                    api_client.get_available_components_sync()
                    success_message("API key authentication successful")
                except Exception as e:
                    warning_message(f"API key authentication failed: {e}")
            else:
                info_message("No API key configured (authentication may be required for some operations)")

        else:
            error_message(f"Failed to connect to AI Studio at {config_manager.ai_studio_url}")
            error_message("Please check:")
            error_message("  - AI Studio is running")
            error_message("  - URL is correct")
            error_message("  - Network connectivity")
            ctx.exit(1)

    except Exception as e:
        error_message(f"Configuration test failed: {e}")
        ctx.exit(1)


@config.command(name="reset")
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def reset_config(ctx: click.Context, confirm: bool):
    """Reset configuration to defaults."""
    try:
        if not confirm:
            if not click.confirm("This will reset all Genesis CLI configuration to defaults. Continue?"):
                info_message("Configuration reset cancelled")
                return

        config_manager = ctx.obj['config']

        # Delete config file
        if config_manager.config_file.exists():
            config_manager.config_file.unlink()

        # Reload with defaults
        config_manager._load_config()

        success_message("Configuration reset to defaults")

        click.echo("\nDefault configuration:")
        config_info = config_manager.show_config()
        click.echo(config_info)

    except Exception as e:
        error_message(f"Failed to reset configuration: {e}")
        ctx.exit(1)