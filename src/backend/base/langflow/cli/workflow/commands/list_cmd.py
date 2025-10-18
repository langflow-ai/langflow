"""List command for Genesis CLI."""

from typing import Optional

import click

from ..utils.output import success_message, error_message, warning_message, info_message, format_table
from ..utils.api_client import APIClient


@click.command(name="list")
@click.argument(
    'resource_type',
    type=click.Choice(['flows', 'templates', 'components', 'folders']),
    default='flows'
)
@click.option(
    "--filter", "-f",
    help="Filter results by name or pattern"
)
@click.option(
    "--project", "-p",
    help="Filter flows by project name"
)
@click.option(
    "--category", "-c",
    help="Filter templates by category (e.g., healthcare, fraud-detection)"
)
@click.option(
    "--format",
    type=click.Choice(['table', 'json', 'simple']),
    default='table',
    help="Output format"
)
@click.option(
    "--limit", "-l",
    type=int,
    default=50,
    help="Maximum number of results to show"
)
@click.option("--debug", is_flag=True, help="Enable debug output")
@click.pass_context
def list_cmd(
    ctx: click.Context,
    resource_type: str,
    filter: Optional[str],
    project: Optional[str],
    category: Optional[str],
    format: str,
    limit: int,
    debug: bool,
):
    """
    List Genesis resources (flows, templates, components, folders).

    Examples:

        # List all flows
        ai-studio genesis list flows

        # List templates with category filter
        ai-studio genesis list templates --category healthcare

        # List components with search filter
        ai-studio genesis list components --filter genesis:agent

        # List in JSON format
        ai-studio genesis list flows --format json
    """
    try:
        config_manager = ctx.obj['config']
        api_client = APIClient(config_manager)

        # Check AI Studio connectivity
        if not api_client.health_check_sync():
            error_message(f"Cannot connect to AI Studio at {config_manager.ai_studio_url}")
            error_message("Please check your configuration")
            ctx.exit(1)

        if resource_type == 'flows':
            _list_flows(api_client, filter, project, format, limit, debug)
        elif resource_type == 'templates':
            _list_templates(api_client, filter, category, format, limit, debug)
        elif resource_type == 'components':
            _list_components(api_client, filter, format, limit, debug)
        elif resource_type == 'folders':
            _list_folders(api_client, filter, format, limit, debug)

    except Exception as e:
        error_message(f"Unexpected error: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        ctx.exit(1)


def _list_flows(api_client: APIClient, filter_pattern: Optional[str], project: Optional[str],
               format: str, limit: int, debug: bool):
    """List flows from AI Studio."""
    try:
        info_message("Fetching flows from AI Studio...")
        result = api_client.get_flows_sync()

        flows = result.get('flows', [])
        if not flows:
            warning_message("No flows found")
            return

        # Apply filters
        if filter_pattern:
            flows = [f for f in flows if filter_pattern.lower() in f.get('name', '').lower()]

        if project:
            # Filter by project if specified (assuming flows have project info)
            flows = [f for f in flows if project.lower() in f.get('folder_name', '').lower()]

        # Limit results
        if len(flows) > limit:
            flows = flows[:limit]
            warning_message(f"Showing first {limit} results (use --limit to adjust)")

        if format == 'json':
            import json
            click.echo(json.dumps(flows, indent=2))
        elif format == 'simple':
            for flow in flows:
                click.echo(f"{flow.get('id')} - {flow.get('name')}")
        else:  # table format
            headers = ['ID', 'Name', 'Description', 'Updated']
            rows = []
            for flow in flows:
                description = flow.get('description', '')
                if len(description) > 50:
                    description = description[:47] + "..."
                updated = flow.get('updated_at', '')[:10] if flow.get('updated_at') else ''
                rows.append([
                    str(flow.get('id', ''))[:8],
                    flow.get('name', ''),
                    description,
                    updated
                ])

            table_output = format_table(headers, rows, f'Flows ({len(flows)})')
            click.echo(table_output)

        success_message(f"Listed {len(flows)} flows")

    except Exception as e:
        error_message(f"Failed to list flows: {e}")
        raise


def _list_templates(api_client: APIClient, filter_pattern: Optional[str], category: Optional[str],
                   format: str, limit: int, debug: bool):
    """List available templates from specification library."""
    try:
        info_message("Fetching templates from specification library...")
        result = api_client.list_available_specifications_sync()

        specifications = result.get('specifications', [])
        if not specifications:
            warning_message("No templates found in specification library")
            return

        # Apply filters
        if filter_pattern:
            specifications = [s for s in specifications if filter_pattern.lower() in s.get('name', '').lower()]

        if category:
            specifications = [s for s in specifications if category.lower() in s.get('file_path', '').lower()]

        # Limit results
        if len(specifications) > limit:
            specifications = specifications[:limit]
            warning_message(f"Showing first {limit} results (use --limit to adjust)")

        if format == 'json':
            import json
            click.echo(json.dumps(specifications, indent=2))
        elif format == 'simple':
            for spec in specifications:
                click.echo(f"{spec.get('file_path')} - {spec.get('name')}")
        else:  # table format
            headers = ['Template Path', 'Name', 'Kind', 'Description']
            rows = []
            for spec in specifications:
                description = spec.get('description', '')
                if len(description) > 40:
                    description = description[:37] + "..."
                rows.append([
                    spec.get('file_path', ''),
                    spec.get('name', ''),
                    spec.get('kind', ''),
                    description
                ])

            table_output = format_table(headers, rows, f'Templates ({len(specifications)})')
            click.echo(table_output)

        success_message(f"Listed {len(specifications)} templates")

    except Exception as e:
        error_message(f"Failed to list templates: {e}")
        raise


def _list_components(api_client: APIClient, filter_pattern: Optional[str],
                    format: str, limit: int, debug: bool):
    """List available Genesis components."""
    try:
        info_message("Fetching available components...")
        result = api_client.get_available_components_sync()

        components = result.get('components', {})
        if not components:
            warning_message("No components found")
            return

        # Convert to list for filtering
        component_list = []
        for comp_type, comp_info in components.items():
            component_list.append({
                'type': comp_type,
                'component': comp_info.get('component', ''),
                'description': comp_info.get('description', ''),
                'is_tool': comp_info.get('is_tool', False)
            })

        # Apply filter
        if filter_pattern:
            component_list = [c for c in component_list if filter_pattern.lower() in c['type'].lower()]

        # Limit results
        if len(component_list) > limit:
            component_list = component_list[:limit]
            warning_message(f"Showing first {limit} results (use --limit to adjust)")

        if format == 'json':
            import json
            click.echo(json.dumps(component_list, indent=2))
        elif format == 'simple':
            for comp in component_list:
                click.echo(f"{comp['type']} - {comp['component']}")
        else:  # table format
            headers = ['Genesis Type', 'Langflow Component', 'Tool', 'Description']
            rows = []
            for comp in component_list:
                description = comp.get('description', '')
                if len(description) > 40:
                    description = description[:37] + "..."
                rows.append([
                    comp['type'],
                    comp['component'],
                    '✓' if comp['is_tool'] else '',
                    description
                ])

            table_output = format_table(headers, rows, f'Components ({len(component_list)})')
            click.echo(table_output)

        success_message(f"Listed {len(component_list)} components")

    except Exception as e:
        error_message(f"Failed to list components: {e}")
        raise


def _list_folders(api_client: APIClient, filter_pattern: Optional[str],
                 format: str, limit: int, debug: bool):
    """List folders from AI Studio."""
    try:
        info_message("Fetching folders from AI Studio...")
        result = api_client.get_folders_sync()

        folders = result.get('folders', [])
        if not folders:
            warning_message("No folders found")
            return

        # Apply filter
        if filter_pattern:
            folders = [f for f in folders if filter_pattern.lower() in f.get('name', '').lower()]

        # Limit results
        if len(folders) > limit:
            folders = folders[:limit]
            warning_message(f"Showing first {limit} results (use --limit to adjust)")

        if format == 'json':
            import json
            click.echo(json.dumps(folders, indent=2))
        elif format == 'simple':
            for folder in folders:
                click.echo(f"{folder.get('id')} - {folder.get('name')}")
        else:  # table format
            headers = ['ID', 'Name', 'Description']
            rows = []
            for folder in folders:
                description = folder.get('description', '')
                if len(description) > 50:
                    description = description[:47] + "..."
                rows.append([
                    str(folder.get('id', ''))[:8],
                    folder.get('name', ''),
                    description
                ])

            table_output = format_table(headers, rows, f'Folders ({len(folders)})')
            click.echo(table_output)

        success_message(f"Listed {len(folders)} folders")

    except Exception as e:
        error_message(f"Failed to list folders: {e}")
        raise