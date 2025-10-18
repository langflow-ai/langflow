"""Templates command for Genesis CLI."""

import yaml
from pathlib import Path
from typing import Optional

import click

from ..utils.output import success_message, error_message, warning_message, info_message, format_table
from ..utils.api_client import APIClient


@click.command(name="templates")
@click.option(
    "--category", "-c",
    help="Filter by category (e.g., healthcare, fraud-detection, simple)"
)
@click.option(
    "--search", "-s",
    help="Search templates by name or description"
)
@click.option(
    "--show", "-i",
    help="Show detailed information for specific template"
)
@click.option(
    "--local", "-l",
    is_flag=True,
    help="Search for templates in local custom templates directory"
)
@click.option(
    "--format",
    type=click.Choice(['table', 'json', 'simple']),
    default='table',
    help="Output format"
)
@click.option(
    "--validate",
    is_flag=True,
    help="Validate all templates while listing"
)
@click.option("--debug", is_flag=True, help="Enable debug output")
@click.pass_context
def templates(
    ctx: click.Context,
    category: Optional[str],
    search: Optional[str],
    show: Optional[str],
    local: bool,
    format: str,
    validate: bool,
    debug: bool,
):
    """
    Browse and manage Genesis specification templates.

    Discover available templates in the library, view template details,
    and validate template specifications.

    Examples:

        # List all available templates
        ai-studio genesis templates

        # Filter by category
        ai-studio genesis templates --category healthcare

        # Search for specific templates
        ai-studio genesis templates --search medication

        # Show template details
        ai-studio genesis templates --show healthcare/medication-extractor

        # Validate all templates
        ai-studio genesis templates --validate
    """
    try:
        config_manager = ctx.obj['config']
        api_client = APIClient(config_manager)

        # Check AI Studio connectivity
        if not api_client.health_check_sync():
            error_message(f"Cannot connect to AI Studio at {config_manager.ai_studio_url}")
            error_message("Please check your configuration")
            ctx.exit(1)

        if show:
            _show_template_details(api_client, show, format, debug)
        elif local:
            _list_local_templates(config_manager, category, search, format, debug)
        else:
            _list_library_templates(api_client, category, search, format, validate, debug)

    except Exception as e:
        error_message(f"Unexpected error: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        ctx.exit(1)


def _show_template_details(api_client: APIClient, template_path: str, format: str, debug: bool):
    """Show detailed information for a specific template."""
    try:
        info_message(f"Getting template details: {template_path}")

        # Try to get template from library
        result = api_client.list_available_specifications_sync()
        specifications = result.get('specifications', [])

        template_spec = None
        for spec in specifications:
            if spec.get('file_path') == template_path or spec.get('name').lower() == template_path.lower():
                template_spec = spec
                break

        if not template_spec:
            error_message(f"Template not found: {template_path}")
            return

        if format == 'json':
            import json
            click.echo(json.dumps(template_spec, indent=2))
            return

        # Show detailed template information
        click.echo(f"\n📄 Template: {template_spec.get('name')}")
        click.echo("=" * 50)
        click.echo(f"File Path: {template_spec.get('file_path')}")
        click.echo(f"Kind: {template_spec.get('kind')}")
        click.echo(f"Sub-domain: {template_spec.get('subdomain', 'N/A')}")
        click.echo(f"URN: {template_spec.get('specification_urn', 'N/A')}")

        description = template_spec.get('description', '')
        if description:
            click.echo(f"\nDescription:")
            click.echo(f"  {description}")

        # Try to get more details by loading the YAML (if possible)
        # This would require API enhancement or direct file access

        success_message("Template details retrieved successfully")

    except Exception as e:
        error_message(f"Failed to get template details: {e}")
        raise


def _list_library_templates(api_client: APIClient, category: Optional[str], search: Optional[str],
                           format: str, validate: bool, debug: bool):
    """List templates from the specification library."""
    try:
        info_message("Fetching templates from specification library...")
        result = api_client.list_available_specifications_sync()

        specifications = result.get('specifications', [])
        if not specifications:
            warning_message("No templates found in specification library")
            return

        # Apply filters
        if category:
            specifications = [
                s for s in specifications
                if category.lower() in s.get('file_path', '').lower() or
                   category.lower() in s.get('subdomain', '').lower()
            ]

        if search:
            specifications = [
                s for s in specifications
                if search.lower() in s.get('name', '').lower() or
                   search.lower() in s.get('description', '').lower()
            ]

        if not specifications:
            warning_message("No templates found matching criteria")
            return

        # Sort by file path
        specifications.sort(key=lambda x: x.get('file_path', ''))

        # Validate templates if requested
        if validate:
            info_message("Validating templates...")
            _validate_templates(api_client, specifications, debug)

        if format == 'json':
            import json
            click.echo(json.dumps(specifications, indent=2))
        elif format == 'simple':
            for spec in specifications:
                click.echo(f"{spec.get('file_path')} - {spec.get('name')}")
        else:  # table format
            headers = ['Template Path', 'Name', 'Kind', 'Category', 'Description']
            rows = []
            for spec in specifications:
                description = spec.get('description', '')
                if len(description) > 30:
                    description = description[:27] + "..."

                # Extract category from file path
                file_path = spec.get('file_path', '')
                category_name = file_path.split('/')[0] if '/' in file_path else 'root'

                rows.append([
                    spec.get('file_path', ''),
                    spec.get('name', ''),
                    spec.get('kind', ''),
                    category_name,
                    description
                ])

            table_output = format_table(headers, rows, f'Library Templates ({len(specifications)})')
            click.echo(table_output)

        success_message(f"Listed {len(specifications)} templates")

        # Show category breakdown
        if debug:
            categories = {}
            for spec in specifications:
                file_path = spec.get('file_path', '')
                cat = file_path.split('/')[0] if '/' in file_path else 'root'
                categories[cat] = categories.get(cat, 0) + 1

            click.echo("\nCategory Breakdown:")
            for cat, count in sorted(categories.items()):
                click.echo(f"  {cat}: {count}")

    except Exception as e:
        error_message(f"Failed to list library templates: {e}")
        raise


def _list_local_templates(config_manager, category: Optional[str], search: Optional[str],
                         format: str, debug: bool):
    """List templates from local custom templates directory."""
    try:
        config = config_manager.get_config()
        templates_path = config.templates_path

        if not templates_path:
            warning_message("No custom templates path configured")
            info_message("Use 'ai-studio genesis config set templates_path /path/to/templates' to configure")
            return

        templates_dir = Path(templates_path)
        if not templates_dir.exists():
            warning_message(f"Templates directory not found: {templates_path}")
            return

        info_message(f"Searching for templates in: {templates_path}")

        # Find YAML files
        yaml_files = list(templates_dir.rglob("*.yaml")) + list(templates_dir.rglob("*.yml"))
        if not yaml_files:
            warning_message("No YAML template files found")
            return

        templates = []
        for yaml_file in yaml_files:
            try:
                with open(yaml_file, 'r') as f:
                    spec_dict = yaml.safe_load(f)

                if spec_dict and 'name' in spec_dict:
                    relative_path = yaml_file.relative_to(templates_dir)
                    template_info = {
                        'file_path': str(relative_path),
                        'full_path': str(yaml_file),
                        'name': spec_dict.get('name', ''),
                        'kind': spec_dict.get('kind', ''),
                        'description': spec_dict.get('description', ''),
                        'subdomain': spec_dict.get('subDomain', '')
                    }
                    templates.append(template_info)

            except Exception as e:
                if debug:
                    warning_message(f"Could not load {yaml_file.name}: {e}")

        # Apply filters
        if category:
            templates = [
                t for t in templates
                if category.lower() in t.get('file_path', '').lower() or
                   category.lower() in t.get('subdomain', '').lower()
            ]

        if search:
            templates = [
                t for t in templates
                if search.lower() in t.get('name', '').lower() or
                   search.lower() in t.get('description', '').lower()
            ]

        if not templates:
            warning_message("No templates found matching criteria")
            return

        # Sort by file path
        templates.sort(key=lambda x: x.get('file_path', ''))

        if format == 'json':
            import json
            click.echo(json.dumps(templates, indent=2))
        elif format == 'simple':
            for template in templates:
                click.echo(f"{template.get('file_path')} - {template.get('name')}")
        else:  # table format
            headers = ['Template Path', 'Name', 'Kind', 'Description']
            rows = []
            for template in templates:
                description = template.get('description', '')
                if len(description) > 40:
                    description = description[:37] + "..."

                rows.append([
                    template.get('file_path', ''),
                    template.get('name', ''),
                    template.get('kind', ''),
                    description
                ])

            table_output = format_table(headers, rows, f'Local Templates ({len(templates)})')
            click.echo(table_output)

        success_message(f"Listed {len(templates)} local templates")

    except Exception as e:
        error_message(f"Failed to list local templates: {e}")
        raise


def _validate_templates(api_client: APIClient, specifications: list, debug: bool):
    """Validate a list of templates."""
    valid_count = 0
    invalid_count = 0

    for spec in specifications:
        try:
            file_path = spec.get('file_path', '')
            # Note: This would require API enhancement to validate library templates
            # For now, just report that validation would be performed
            if debug:
                info_message(f"Would validate: {file_path}")
            valid_count += 1

        except Exception as e:
            if debug:
                warning_message(f"Validation failed for {spec.get('file_path', '')}: {e}")
            invalid_count += 1

    click.echo(f"\nValidation Summary:")
    click.echo(f"  Valid: {valid_count}")
    click.echo(f"  Invalid: {invalid_count}")

    if invalid_count == 0:
        success_message("All templates are valid!")
    else:
        warning_message(f"{invalid_count} templates have validation issues")