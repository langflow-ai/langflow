"""Export command for Workflow CLI."""

import json
import yaml
from pathlib import Path
from typing import Optional, Dict, Any

import click

from ..utils.output import success_message, error_message, warning_message, info_message
from ..utils.api_client import APIClient


@click.command(name="export")
@click.argument('input_path', type=click.Path(exists=True))
@click.option(
    "--output", "-o",
    help="Output path for Genesis specification (defaults to input name with .yaml extension)"
)
@click.option(
    "--format", "-f",
    type=click.Choice(['yaml', 'json']),
    default='yaml',
    help="Output format for Genesis specification"
)
@click.option(
    "--name", "-n",
    help="Override flow name in generated specification"
)
@click.option(
    "--description", "-d",
    help="Override flow description in generated specification"
)
@click.option(
    "--domain",
    default="converted",
    help="Domain for the generated specification (default: converted)"
)
@click.option(
    "--preserve-vars", "-p",
    is_flag=True,
    help="Preserve original variable values from flow"
)
@click.option(
    "--include-metadata", "-m",
    is_flag=True,
    help="Include extended metadata in specification"
)
@click.option("--debug", is_flag=True, help="Enable debug output")
@click.pass_context
def export(
    ctx: click.Context,
    input_path: str,
    output: Optional[str],
    format: str,
    name: Optional[str],
    description: Optional[str],
    domain: str,
    preserve_vars: bool,
    include_metadata: bool,
    debug: bool,
):
    """
    Export Langflow flows to Genesis specifications.

    Converts Langflow JSON flows back to Genesis YAML/JSON specifications with
    support for variable preservation, metadata extraction, and batch processing.

    Examples:

        # Export single flow to YAML
        ai-studio workflow export flow.json

        # Export to specific output file
        ai-studio workflow export flow.json -o spec.yaml

        # Export with custom metadata
        ai-studio workflow export flow.json --name "My Agent" --domain healthcare

        # Export preserving variables
        ai-studio workflow export flow.json --preserve-vars

        # Export to JSON format
        ai-studio workflow export flow.json --format json
    """
    try:
        config_manager = ctx.obj['config']
        api_client = APIClient(config_manager)

        input_file = Path(input_path)
        info_message(f"Loading Langflow file: {input_file.name}")

        # Load Langflow JSON
        with open(input_file, 'r') as f:
            langflow_data = json.load(f)

        # Validate input
        if not isinstance(langflow_data, dict):
            error_message("Invalid Langflow file format")
            ctx.exit(1)

        # Extract flow data
        flow_data = langflow_data
        if "data" in langflow_data:
            flow_data = langflow_data["data"]

        if not flow_data.get("nodes") or not flow_data.get("edges"):
            error_message("Invalid flow: missing nodes or edges")
            ctx.exit(1)

        info_message(f"Found {len(flow_data['nodes'])} nodes and {len(flow_data['edges'])} edges")

        # Check API connectivity for conversion
        if not api_client.health_check_sync():
            error_message(f"Cannot connect to AI Studio at {config_manager.ai_studio_url}")
            error_message("API connection required for flow export")
            ctx.exit(1)

        # Convert flow to specification
        info_message("Converting flow to Genesis specification...")
        try:
            export_result = api_client.export_flow_sync(
                flow_data=langflow_data,
                preserve_variables=preserve_vars,
                include_metadata=include_metadata,
                name_override=name,
                description_override=description,
                domain_override=domain
            )

            genesis_spec = export_result.get('specification')
            if not genesis_spec:
                error_message("Export failed: No specification returned")
                ctx.exit(1)

            # Show conversion statistics
            if debug:
                conversion_stats = export_result.get('statistics', {})
                click.echo("\n📊 Conversion Statistics:")
                click.echo(f"  - Components converted: {conversion_stats.get('components_converted', 0)}")
                click.echo(f"  - Edges converted: {conversion_stats.get('edges_converted', 0)}")
                click.echo(f"  - Variables preserved: {conversion_stats.get('variables_preserved', 0)}")

        except Exception as e:
            error_message(f"Export failed: {e}")
            if debug:
                import traceback
                traceback.print_exc()
            ctx.exit(1)

        # Determine output path
        if not output:
            extension = ".yaml" if format == "yaml" else ".json"
            output = input_file.with_suffix(extension)
        else:
            output = Path(output)

        # Save specification
        info_message(f"Saving specification to: {output}")

        with open(output, 'w') as f:
            if format == 'yaml':
                yaml.safe_dump(genesis_spec, f, default_flow_style=False, indent=2)
            else:
                json.dump(genesis_spec, f, indent=2)

        success_message("Flow exported successfully!")

        # Display specification summary
        spec_name = genesis_spec.get('name', 'Unknown')
        spec_components = len(genesis_spec.get('components', {}))
        click.echo(f"📋 Specification: {spec_name}")
        click.echo(f"🧩 Components: {spec_components}")

        if genesis_spec.get('agentGoal'):
            click.echo(f"🎯 Goal: {genesis_spec.get('agentGoal')}")

        # Show warnings if any
        if export_result.get('warnings'):
            warning_message("Export warnings:")
            for warning in export_result.get('warnings', []):
                click.echo(f"  - {warning}")

    except Exception as e:
        error_message(f"Unexpected error: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        ctx.exit(1)