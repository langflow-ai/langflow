"""Validate command for Genesis CLI with Professional Framework Integration."""

import asyncio
import yaml
from pathlib import Path
from typing import Optional

import click

from ..utils.output import success_message, error_message, warning_message, info_message, format_validation_report
from ..utils.api_client import APIClient
from ..utils.service_integration import ServiceIntegration


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
@click.option(
    "--local",
    is_flag=True,
    help="Use local professional framework for validation (offline capability)"
)
@click.option(
    "--healthcare",
    is_flag=True,
    help="Enable healthcare compliance validation"
)
@click.pass_context
def validate(
    ctx: click.Context,
    specification: str,
    detailed: bool,
    quick: bool,
    format: str,
    debug: bool,
    local: bool,
    healthcare: bool,
):
    """
    Validate a Genesis agent specification.

    Performs comprehensive validation of YAML specifications including schema
    validation, component relationships, and semantic analysis.

    Examples:

        # Basic validation
        ai-studio genesis validate template.yaml

        # Local validation without API dependency
        ai-studio genesis validate template.yaml --local

        # Healthcare compliance validation
        ai-studio genesis validate template.yaml --local --healthcare

        # Detailed semantic validation
        ai-studio genesis validate template.yaml --detailed

        # Quick validation for real-time feedback
        ai-studio genesis validate template.yaml --quick

        # JSON output for integration
        ai-studio genesis validate template.yaml --format json
    """
    # Run async main function if local mode
    if local:
        try:
            # Check if there's already an event loop running
            loop = asyncio.get_running_loop()
            # If we have a running loop, use a thread executor
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    async_validate_main(
                        ctx, specification, detailed, quick, format, debug, local, healthcare
                    )
                )
                future.result()
        except RuntimeError:
            # No running event loop, use asyncio.run normally
            asyncio.run(async_validate_main(
                ctx, specification, detailed, quick, format, debug, local, healthcare
            ))
    else:
        sync_validate_main(
            ctx, specification, detailed, quick, format, debug, local, healthcare
        )


def sync_validate_main(
    ctx: click.Context,
    specification: str,
    detailed: bool,
    quick: bool,
    format: str,
    debug: bool,
    local: bool,
    healthcare: bool,
):
    """Synchronous validation using API services."""
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
            error_message("Please check your configuration or use --local for offline validation")
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


async def async_validate_main(
    ctx: click.Context,
    specification: str,
    detailed: bool,
    quick: bool,
    format: str,
    debug: bool,
    local: bool,
    healthcare: bool,
):
    """Asynchronous validation using enhanced service integration."""
    try:
        # Initialize service integration with local mode
        service_integration = ServiceIntegration(local_mode=True)

        if debug:
            success_message("Enhanced service integration initialized for local validation")
            if healthcare:
                info_message("Healthcare compliance validation enabled")

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
            components_count = len(spec_dict.get('components', {}))

            if debug:
                click.echo(f"📋 Specification: {spec_name}")
                if spec_description:
                    click.echo(f"📝 Description: {spec_description}")
                click.echo(f"🧩 Components: {components_count}")

                if healthcare:
                    compliance_info = spec_dict.get('compliance', {})
                    if compliance_info:
                        click.echo(f"🏥 Healthcare Compliance: HIPAA={compliance_info.get('hipaa', False)}")

        except yaml.YAMLError as e:
            error_message(f"Invalid YAML format: {e}")
            ctx.exit(1)

        # Perform validation using enhanced service integration
        try:
            if quick:
                info_message("Performing quick local validation...")
            else:
                info_message("Performing local validation with enhanced framework...")

            validation_result = await service_integration.validate_specification(spec_path)

            # Add local processing indicators
            validation_result["local_processing"] = True
            validation_result["api_bypassed"] = True

        except Exception as e:
            error_message(f"Local validation request failed: {e}")
            if debug:
                import traceback
                traceback.print_exc()
            ctx.exit(1)

        # Process results based on format (enhanced service integration format)
        valid = validation_result.get('success', False)
        validation_details = validation_result.get('validation_details', {})
        errors = []
        warnings = []
        suggestions = []

        # Extract errors from incompatible and missing components
        if not valid and validation_details:
            incompatible = validation_details.get('incompatible_components', [])
            missing = validation_details.get('missing_components', [])

            for comp in incompatible:
                errors.append(f"Component '{comp.get('id')}': {comp.get('error', 'Unknown error')}")

            for comp in missing:
                errors.append(f"Component '{comp.get('id')}': {comp.get('error', 'Unknown error')}")

        # Show component discovery success info
        if valid and debug:
            compatible_count = validation_result.get('compatible_count', 0)
            total_components = validation_result.get('total_components', 0)
            click.echo(f"🧩 Component Discovery: {compatible_count}/{total_components} components resolved successfully")

        # Convert to legacy format for compatibility
        validation_result['valid'] = valid
        validation_result['errors'] = errors
        validation_result['warnings'] = warnings
        validation_result['suggestions'] = suggestions

        # Show performance info if available
        performance = validation_result.get('performance', {})
        if performance.get('validation_time') and debug:
            validation_time = performance['validation_time']
            framework_used = performance.get('framework_used', 'professional')
            click.echo(f"\n⚡ Local validation completed in {validation_time:.3f}s using {framework_used} framework")

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
                ['Suggestions', str(summary.get('suggestion_count', len(suggestions)))],
                ['Processing', 'Local Professional Framework']
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

            # Add local processing indicator
            click.echo("\n💻 Processing: Local Professional Framework")

        # Show healthcare compliance results if enabled
        healthcare_compliance = validation_result.get('healthcare_compliance', {})
        if healthcare and healthcare_compliance and format != 'json':
            click.echo("\n🏥 Healthcare Compliance:")
            compliance_issues = healthcare_compliance.get('compliance_issues', [])
            if compliance_issues:
                for issue in compliance_issues:
                    click.echo(f"  ⚠️ {issue}")
            else:
                click.echo("  ✅ All healthcare components properly configured")

        # Show actionable suggestions if available
        actionable = validation_result.get('actionable_suggestions', [])
        if actionable and format != 'json':
            click.echo("\nActionable Suggestions:")
            for suggestion in actionable:
                click.echo(f"💡 {suggestion}")

        # Exit with appropriate code
        if valid:
            if format != 'json':
                success_message("Local validation passed!")
            ctx.exit(0)
        else:
            if format != 'json':
                error_message("Local validation failed!")
            ctx.exit(1)

    except click.exceptions.Exit:
        # Re-raise Click's Exit exception to allow proper exit codes
        raise
    except Exception as e:
        error_message(f"Unexpected error in local validation: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        ctx.exit(1)