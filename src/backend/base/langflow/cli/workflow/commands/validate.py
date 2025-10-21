"""Validate command for Genesis CLI."""

import yaml
from pathlib import Path
from typing import Optional

import click

from ..utils.output import success_message, error_message, warning_message, info_message, format_validation_report
from ..utils.api_client import APIClient


@click.command(name="validate")
@click.argument('specification', type=click.Path(exists=True))
@click.option(
    "--detailed", "-d",
    is_flag=True,
    help="Perform detailed semantic validation"
)
@click.option(
    "--quick", "-q",
    is_flag=True,
    help="Perform quick validation optimized for speed"
)
@click.option(
    "--format", "-f",
    type=click.Choice(['table', 'report', 'json']),
    default='report',
    help="Output format for validation results"
)
@click.option("--debug", is_flag=True, help="Enable debug output")
@click.pass_context
def validate(
    ctx: click.Context,
    specification: str,
    detailed: bool,
    quick: bool,
    format: str,
    debug: bool,
):
    """
    Validate a Genesis agent specification.

    Performs comprehensive validation of YAML specifications including schema
    validation, component relationships, and semantic analysis.

    Examples:

        # Basic validation
        ai-studio genesis validate template.yaml

        # Detailed semantic validation
        ai-studio genesis validate template.yaml --detailed

        # Quick validation for real-time feedback
        ai-studio genesis validate template.yaml --quick

        # JSON output for integration
        ai-studio genesis validate template.yaml --format json
    """
    try:
        config_manager = ctx.obj['config']
        api_client = APIClient(config_manager)

        spec_path = Path(specification)
        info_message(f"Validating specification: {spec_path.name}")

        # Load specification
        try:
            with open(spec_path, 'r') as f:
                spec_yaml = f.read()
        except Exception as e:
            error_message(f"Failed to read specification file: {e}")
            ctx.exit(1)

        # Parse spec to show basic info
        try:
            spec_dict = yaml.safe_load(spec_yaml)
            spec_name = spec_dict.get('name', 'Unknown')
            spec_description = spec_dict.get('description', '')
            components_count = len(spec_dict.get('components', []))

            if debug:
                click.echo(f"📋 Specification: {spec_name}")
                if spec_description:
                    click.echo(f"📝 Description: {spec_description}")
                click.echo(f"🧩 Components: {components_count}")

        except yaml.YAMLError as e:
            error_message(f"Invalid YAML format: {e}")
            ctx.exit(1)

        # Check AI Studio connectivity
        if not api_client.health_check_sync():
            error_message(f"Cannot connect to AI Studio at {config_manager.ai_studio_url}")
            error_message("Please check your configuration")
            ctx.exit(1)

        # Perform validation
        try:
            if quick:
                info_message("Performing quick validation...")
                # Use quick validation endpoint when implemented
                validation_result = api_client.validate_spec_sync(spec_yaml, detailed=False)
            else:
                if detailed:
                    info_message("Performing detailed validation with semantic analysis...")
                else:
                    info_message("Performing standard validation...")
                validation_result = api_client.validate_spec_sync(spec_yaml, detailed=detailed)

        except Exception as e:
            error_message(f"Validation request failed: {e}")
            if debug:
                import traceback
                traceback.print_exc()
            ctx.exit(1)

        # Process results based on format
        valid = validation_result.get('valid', False)
        errors = validation_result.get('errors', [])
        warnings = validation_result.get('warnings', [])
        suggestions = validation_result.get('suggestions', [])

        if format == 'json':
            # Output raw JSON
            import json
            click.echo(json.dumps(validation_result, indent=2))

        elif format == 'table':
            # Output table format
            from ..utils.output import format_table

            # Summary table
            summary = validation_result.get('summary', {})
            summary_rows = [
                ['Status', '✅ VALID' if valid else '❌ INVALID'],
                ['Errors', str(summary.get('error_count', len(errors)))],
                ['Warnings', str(summary.get('warning_count', len(warnings)))],
                ['Suggestions', str(summary.get('suggestion_count', len(suggestions)))]
            ]

            table_output = format_table(['Metric', 'Value'], summary_rows, 'Validation Summary')
            click.echo(table_output)

            # Issues table if any
            if errors or warnings:
                issue_rows = []
                for error in errors:
                    if isinstance(error, dict):
                        message = error.get('message', str(error))
                        component = error.get('component_id', '')
                        issue_rows.append(['Error', message, component])
                    else:
                        issue_rows.append(['Error', str(error), ''])

                for warning in warnings:
                    if isinstance(warning, dict):
                        message = warning.get('message', str(warning))
                        component = warning.get('component_id', '')
                        issue_rows.append(['Warning', message, component])
                    else:
                        issue_rows.append(['Warning', str(warning), ''])

                if issue_rows:
                    issues_table = format_table(['Type', 'Message', 'Component'], issue_rows, 'Validation Issues')
                    click.echo(issues_table)

        else:  # report format (default)
            # Output formatted report
            report = format_validation_report(validation_result)
            click.echo(report)

        # Show actionable suggestions if available
        actionable = validation_result.get('actionable_suggestions', [])
        if actionable and format != 'json':
            click.echo("\nActionable Suggestions:")
            for suggestion in actionable:
                click.echo(f"💡 {suggestion}")

        # Exit with appropriate code
        if valid:
            if format != 'json':
                success_message("Validation passed!")
            ctx.exit(0)
        else:
            if format != 'json':
                error_message("Validation failed!")
            ctx.exit(1)

    except click.exceptions.Exit:
        # Re-raise Click's Exit exception to allow proper exit codes
        raise
    except Exception as e:
        error_message(f"Unexpected error: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        ctx.exit(1)