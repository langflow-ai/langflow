"""Create command for Genesis CLI."""

import json
import yaml
from pathlib import Path
from typing import Optional, Dict, Any

import click

from ..utils.output import success_message, error_message, warning_message, info_message, format_flow_stats
from ..utils.api_client import APIClient


def load_variables_from_file(var_file: str) -> Dict[str, Any]:
    """Load variables from JSON or YAML file."""
    var_path = Path(var_file)

    with open(var_path, 'r') as f:
        if var_path.suffix.lower() in ['.json']:
            return json.load(f)
        else:
            return yaml.safe_load(f) or {}


def parse_cli_variables(var_list: tuple) -> Dict[str, Any]:
    """Parse CLI variables from tuple of key=value strings."""
    variables = {}

    for var_def in var_list:
        if '=' not in var_def:
            raise ValueError(f"Invalid variable format: {var_def}. Expected format: key=value")

        key, value = var_def.split('=', 1)

        # Try to parse value as JSON, fallback to string
        try:
            variables[key] = json.loads(value)
        except json.JSONDecodeError:
            variables[key] = value

    return variables


def parse_cli_tweaks(tweak_list: tuple) -> Dict[str, Any]:
    """Parse CLI tweaks from tuple of component_id.field=value strings."""
    tweaks = {}

    for tweak_def in tweak_list:
        if '=' not in tweak_def:
            raise ValueError(f"Invalid tweak format: {tweak_def}. Expected format: component_id.field=value")

        key, value = tweak_def.split('=', 1)

        # Try to parse value as JSON, fallback to string
        try:
            parsed_value = json.loads(value)
        except json.JSONDecodeError:
            parsed_value = value

        tweaks[key] = parsed_value

    return tweaks


@click.command(name="create")
@click.option(
    "--template", "-t",
    help="Path to agent specification YAML file or library template name"
)
@click.option("--name", "-n", help="Flow name (defaults to template name)")
@click.option("--project", "-p", help="Project name to create flow in (will create if doesn't exist)")
@click.option("--folder", "-f", help="Folder ID to create flow in")
@click.option(
    "--output", "-o",
    help="Save flow to file instead of creating in AI Studio"
)
@click.option(
    "--validate-only", "-v",
    is_flag=True,
    help="Only validate the spec without creating flow"
)
@click.option(
    "--var",
    multiple=True,
    help="Set runtime variable (format: key=value). Can be used multiple times."
)
@click.option(
    "--var-file",
    type=click.Path(exists=True),
    help="Load variables from JSON or YAML file"
)
@click.option(
    "--tweak",
    multiple=True,
    help="Apply tweaks to components (format: component_id.field=value)"
)
@click.option("--debug", is_flag=True, help="Enable debug output")
@click.pass_context
def create(
    ctx: click.Context,
    template: Optional[str],
    name: Optional[str],
    project: Optional[str],
    folder: Optional[str],
    output: Optional[str],
    validate_only: bool,
    var: tuple,
    var_file: Optional[str],
    tweak: tuple,
    debug: bool,
):
    """
    Create a Genesis flow from an agent specification.

    Creates flows from YAML specifications, with support for variable substitution,
    component tweaks, and integration with AI Studio backend.

    Examples:

        # Create flow from local specification
        ai-studio genesis create -t templates/healthcare/medication-extractor.yaml

        # Create flow from library template
        ai-studio genesis create -t healthcare/eligibility-checker

        # Create flow in specific project
        ai-studio genesis create -t template.yaml --project "Healthcare Agents"

        # Validate only
        ai-studio genesis create -t template.yaml --validate-only

        # Save flow to file
        ai-studio genesis create -t template.yaml -o flow.json

        # Use variables and tweaks
        ai-studio genesis create -t template.yaml --var api_key=test --tweak agent.temperature=0.5
    """
    try:
        config_manager = ctx.obj['config']
        api_client = APIClient(config_manager)

        # Check if template is required and provided
        if not template:
            error_message("Template file or library name is required")
            ctx.exit(1)

        # Determine if template is a file path or library template
        template_path = Path(template)
        is_library_template = not template_path.exists() and '/' in template

        if template_path.exists():
            # Load from file
            info_message(f"Loading specification: {template_path.name}")
            with open(template_path, 'r') as f:
                spec_yaml = f.read()

        elif is_library_template:
            # Try to use library template
            info_message(f"Using library template: {template}")
            try:
                if validate_only:
                    error_message("Library templates cannot be validated without creating. Use --output to save locally first.")
                    ctx.exit(1)

                # Create flow from library directly
                result = api_client.create_flow_from_library_sync(template, folder)
                if result.get('success'):
                    success_message(f"Flow created from library template: {template}")
                    info_message(f"Flow ID: {result.get('flow_id')}")
                    info_message(f"Flow Name: {result.get('flow_name')}")

                    # Display URL if available
                    base_url = config_manager.ai_studio_url
                    if base_url and result.get('flow_id'):
                        flow_url = f"{base_url}/flow/{result['flow_id']}"
                        info_message(f"Open in AI Studio: {flow_url}")
                else:
                    error_message(f"Failed to create flow from library: {result.get('message', 'Unknown error')}")
                    if debug and result.get('details'):
                        click.echo(f"Details: {result['details']}")
                return

            except Exception as e:
                error_message(f"Failed to use library template: {e}")
                ctx.exit(1)

        else:
            error_message(f"Template file not found: {template}")
            ctx.exit(1)

        # Parse spec to get metadata
        spec_dict = yaml.safe_load(spec_yaml)
        spec_name = spec_dict.get('name', 'Unknown')
        spec_description = spec_dict.get('description', '')
        components_count = len(spec_dict.get('components', []))

        click.echo(f"📋 Specification: {spec_name}")
        if spec_description:
            click.echo(f"📝 Description: {spec_description}")
        click.echo(f"🧩 Components: {components_count}")

        # Show enhanced metadata if available
        if 'agentGoal' in spec_dict:
            click.echo(f"🎯 Goal: {spec_dict.get('agentGoal')}")
            click.echo(f"👥 Target User: {spec_dict.get('targetUser', 'N/A')}")
            click.echo(f"💼 Value Generation: {spec_dict.get('valueGeneration', 'N/A')}")

        # Prepare variables
        variables = {}

        # Load variables from file
        if var_file:
            info_message(f"Loading variables from: {var_file}")
            variables.update(load_variables_from_file(var_file))

        # Parse CLI variables
        if var:
            cli_vars = parse_cli_variables(var)
            variables.update(cli_vars)

        # Show loaded variables if debug
        if debug and variables:
            click.echo("\n🔧 Variables:")
            for key, value in variables.items():
                click.echo(f"  - {key}: {value}")

        # Prepare tweaks
        tweaks = {}
        if tweak:
            tweaks = parse_cli_tweaks(tweak)
            if debug:
                click.echo("\n⚙️ Tweaks:")
                for key, value in tweaks.items():
                    click.echo(f"  - {key}: {value}")

        # Check AI Studio connectivity
        if not validate_only and not output:
            if not api_client.health_check_sync():
                error_message(f"Cannot connect to AI Studio at {config_manager.ai_studio_url}")
                error_message("Please check your configuration or use --output to save locally")
                ctx.exit(1)

        # Validate specification
        info_message("Validating specification...")
        try:
            validation_result = api_client.validate_spec_sync(spec_yaml)

            if not validation_result.get('valid'):
                error_message("Specification validation failed:")
                for error in validation_result.get('errors', []):
                    if isinstance(error, dict):
                        message = error.get('message', str(error))
                        component = error.get('component_id', '')
                        field = error.get('field', '')
                        location = f" ({component}.{field})" if component and field else f" ({component})" if component else ""
                        click.echo(f"  - {message}{location}")
                    else:
                        click.echo(f"  - {error}")
                ctx.exit(1)

            # Show warnings
            warnings = validation_result.get('warnings', [])
            if warnings:
                warning_message("Validation warnings:")
                for warning in warnings:
                    if isinstance(warning, dict):
                        message = warning.get('message', str(warning))
                        click.echo(f"  - {message}")
                    else:
                        click.echo(f"  - {warning}")

            success_message("Specification validation passed!")

        except Exception as e:
            error_message(f"Validation failed: {e}")
            if debug:
                import traceback
                traceback.print_exc()
            ctx.exit(1)

        # If validate-only, stop here
        if validate_only:
            success_message("Validation complete (--validate-only flag set)")
            return

        # Convert specification to flow
        info_message("Converting specification to flow...")
        try:
            convert_result = api_client.convert_spec_sync(
                spec_yaml=spec_yaml,
                variables=variables if variables else None,
                tweaks=tweaks if tweaks else None
            )

            flow = convert_result.get('flow')
            if not flow:
                error_message("Conversion failed: No flow data returned")
                ctx.exit(1)

            # Show flow statistics
            click.echo(f"\n{format_flow_stats(flow)}")

        except Exception as e:
            error_message(f"Conversion failed: {e}")
            if debug:
                import traceback
                traceback.print_exc()
            ctx.exit(1)

        # Set flow name
        flow_name = name or spec_name or template_path.stem.replace("-", " ").title()

        # Save to file or create in AI Studio
        if output:
            # Save to file
            output_path = Path(output)
            info_message(f"Saving flow to: {output_path}")

            # Update flow name in JSON
            flow["name"] = flow_name

            with open(output_path, "w") as f:
                json.dump(flow, f, indent=2)

            success_message("Flow saved successfully!")

        else:
            # Create flow in AI Studio
            info_message("Creating flow in AI Studio...")

            try:
                flow_data = flow.get("data", {})
                create_result = api_client.create_flow_sync(
                    name=flow_name,
                    data=flow_data,
                    description=spec_description,
                    folder_id=folder
                )

                flow_id = create_result.get('id')
                success_message("Flow created successfully!")
                info_message(f"Flow ID: {flow_id}")

                # Display URL if available
                base_url = config_manager.ai_studio_url
                if base_url and flow_id:
                    flow_url = f"{base_url}/flow/{flow_id}"
                    info_message(f"Open in AI Studio: {flow_url}")

            except Exception as e:
                error_message(f"Failed to create flow in AI Studio: {e}")
                if debug:
                    import traceback
                    traceback.print_exc()
                ctx.exit(1)

    except Exception as e:
        error_message(f"Unexpected error: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        ctx.exit(1)