"""Components command for Genesis CLI."""

from typing import Optional

import click

from ..utils.output import success_message, error_message, warning_message, info_message, format_table
from ..utils.api_client import APIClient


@click.command(name="components")
@click.option(
    "--search", "-s",
    help="Search for components by name or type"
)
@click.option(
    "--info", "-i",
    help="Show detailed information for specific component type"
)
@click.option(
    "--category", "-c",
    type=click.Choice(['all', 'agents', 'tools', 'data', 'prompts', 'healthcare']),
    default='all',
    help="Filter by component category"
)
@click.option(
    "--format",
    type=click.Choice(['table', 'json', 'simple']),
    default='table',
    help="Output format"
)
@click.option(
    "--tools-only",
    is_flag=True,
    help="Show only components that can be used as tools"
)
@click.option("--debug", is_flag=True, help="Enable debug output")
@click.pass_context
def components(
    ctx: click.Context,
    search: Optional[str],
    info: Optional[str],
    category: str,
    format: str,
    tools_only: bool,
    debug: bool,
):
    """
    Discover and explore Genesis components.

    Shows available Genesis component types, their mappings to Langflow components,
    and detailed configuration information.

    Examples:

        # List all available components
        ai-studio genesis components

        # Search for agent components
        ai-studio genesis components --search agent

        # Show only tool components
        ai-studio genesis components --tools-only

        # Get detailed info for specific component
        ai-studio genesis components --info genesis:agent

        # Filter by category
        ai-studio genesis components --category healthcare
    """
    try:
        config_manager = ctx.obj['config']
        api_client = APIClient(config_manager)

        # Check AI Studio connectivity
        if not api_client.health_check_sync():
            error_message(f"Cannot connect to AI Studio at {config_manager.ai_studio_url}")
            error_message("Please check your configuration")
            ctx.exit(1)

        if info:
            _show_component_info(api_client, info, format, debug)
        else:
            _list_components(api_client, search, category, format, tools_only, debug)

    except Exception as e:
        error_message(f"Unexpected error: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        ctx.exit(1)


def _show_component_info(api_client: APIClient, component_type: str, format: str, debug: bool):
    """Show detailed information for a specific component."""
    try:
        info_message(f"Getting detailed information for: {component_type}")

        result = api_client.get_component_mapping_sync(component_type)

        if format == 'json':
            import json
            click.echo(json.dumps(result, indent=2))
            return

        # Format detailed component information
        click.echo(f"\n📦 Component: {component_type}")
        click.echo("=" * 50)
        click.echo(f"Langflow Component: {result.get('langflow_component', 'N/A')}")
        click.echo(f"Is Tool: {'Yes' if result.get('is_tool', False) else 'No'}")
        click.echo(f"Input Field: {result.get('input_field', 'N/A')}")
        click.echo(f"Output Field: {result.get('output_field', 'N/A')}")

        output_types = result.get('output_types', [])
        if output_types:
            click.echo(f"Output Types: {', '.join(output_types)}")

        config = result.get('config', {})
        if config:
            click.echo("\nConfiguration:")
            for key, value in config.items():
                click.echo(f"  {key}: {value}")

        success_message("Component information retrieved successfully")

    except Exception as e:
        error_message(f"Failed to get component information: {e}")
        raise


def _list_components(api_client: APIClient, search: Optional[str], category: str,
                    format: str, tools_only: bool, debug: bool):
    """List available components with filtering."""
    try:
        info_message("Fetching available components...")
        result = api_client.get_available_components_sync()

        components = result.get('components', {})
        if not components:
            warning_message("No components found")
            return

        # Convert to list for processing
        component_list = []
        for comp_type, comp_info in components.items():
            component_data = {
                'type': comp_type,
                'component': comp_info.get('component', ''),
                'description': comp_info.get('description', ''),
                'is_tool': comp_info.get('is_tool', False),
                'category': _get_component_category(comp_type),
                'config': comp_info.get('config', {})
            }
            component_list.append(component_data)

        # Apply filters
        if search:
            component_list = [
                c for c in component_list
                if search.lower() in c['type'].lower() or search.lower() in c['component'].lower()
            ]

        if category != 'all':
            component_list = [c for c in component_list if c['category'] == category]

        if tools_only:
            component_list = [c for c in component_list if c['is_tool']]

        if not component_list:
            warning_message("No components found matching criteria")
            return

        # Sort by type
        component_list.sort(key=lambda x: x['type'])

        if format == 'json':
            import json
            click.echo(json.dumps(component_list, indent=2))
        elif format == 'simple':
            for comp in component_list:
                tool_indicator = " (Tool)" if comp['is_tool'] else ""
                click.echo(f"{comp['type']} -> {comp['component']}{tool_indicator}")
        else:  # table format
            headers = ['Genesis Type', 'Langflow Component', 'Category', 'Tool', 'Description']
            rows = []
            for comp in component_list:
                description = comp.get('description', '')
                if len(description) > 30:
                    description = description[:27] + "..."
                rows.append([
                    comp['type'],
                    comp['component'],
                    comp['category'].title(),
                    '✓' if comp['is_tool'] else '',
                    description
                ])

            table_output = format_table(headers, rows, f'Genesis Components ({len(component_list)})')
            click.echo(table_output)

        success_message(f"Listed {len(component_list)} components")

        # Show category breakdown
        if debug:
            categories = {}
            for comp in component_list:
                cat = comp['category']
                categories[cat] = categories.get(cat, 0) + 1

            click.echo("\nCategory Breakdown:")
            for cat, count in sorted(categories.items()):
                click.echo(f"  {cat.title()}: {count}")

    except Exception as e:
        error_message(f"Failed to list components: {e}")
        raise


def _get_component_category(component_type: str) -> str:
    """Determine component category based on type."""
    type_lower = component_type.lower()

    if 'agent' in type_lower or 'crewai' in type_lower:
        return 'agents'
    elif any(tool_keyword in type_lower for tool_keyword in ['tool', 'search', 'api', 'mcp']):
        return 'tools'
    elif any(data_keyword in type_lower for data_keyword in ['input', 'output', 'loader', 'splitter']):
        return 'data'
    elif 'prompt' in type_lower:
        return 'prompts'
    elif any(health_keyword in type_lower for health_keyword in ['ehr', 'clinical', 'medical', 'healthcare', 'autonomize']):
        return 'healthcare'
    else:
        return 'other'