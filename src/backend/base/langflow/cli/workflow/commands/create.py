"""Create command for Genesis CLI with Professional Framework Integration."""

import asyncio
import json
import yaml
import glob
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

import click

from ..utils.output import success_message, error_message, warning_message, info_message, format_flow_stats
from ..utils.api_client import APIClient
from ..utils.professional_service_integration import ProfessionalServiceIntegration


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


def show_batch_summary(results: List[Dict[str, Any]]):
    """Show summary of batch processing results."""
    successful = [r for r in results if r.get("success", True)]
    failed = [r for r in results if not r.get("success", True)]

    click.echo("\n" + "="*50)
    click.echo("BATCH PROCESSING SUMMARY")
    click.echo("="*50)
    click.echo(f"✅ Successful: {len(successful)}")
    click.echo(f"❌ Failed: {len(failed)}")

    if failed:
        click.echo("\nFailed files:")
        for result in failed:
            click.echo(f"  - {result.get('file', 'Unknown')}: {result.get('error', 'Unknown error')}")


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
@click.option(
    "--local",
    is_flag=True,
    help="Use local professional framework for conversion (bypasses API calls)"
)
@click.option(
    "--healthcare",
    is_flag=True,
    help="Enable healthcare compliance mode with HIPAA validation"
)
@click.option(
    "--benchmark",
    is_flag=True,
    help="Enable performance benchmarking and detailed metrics"
)
@click.option(
    "--batch",
    is_flag=True,
    help="Process multiple YAML files (use with wildcards in template path)"
)
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
    local: bool,
    healthcare: bool,
    benchmark: bool,
    batch: bool,
):
    """
    Create a Genesis flow from an agent specification.

    Creates flows from YAML specifications, with support for variable substitution,
    component tweaks, and integration with AI Studio backend.

    Examples:

        # Create flow from local specification
        ai-studio genesis create -t templates/healthcare/medication-extractor.yaml

        # Use local professional framework for fast conversion
        ai-studio genesis create -t template.yaml --local

        # Healthcare compliance mode with benchmarking
        ai-studio genesis create -t healthcare_agent.yaml --local --healthcare --benchmark

        # Local validation without API dependency
        ai-studio genesis create -t template.yaml --local --validate-only

        # Batch processing multiple files
        ai-studio genesis create -t "templates/*.yaml" --local --batch

        # Create flow from library template
        ai-studio genesis create -t healthcare/eligibility-checker

        # Create flow in specific project
        ai-studio genesis create -t template.yaml --project "Healthcare Agents"

        # Save flow to file
        ai-studio genesis create -t template.yaml -o flow.json

        # Use variables and tweaks
        ai-studio genesis create -t template.yaml --var api_key=test --tweak agent.temperature=0.5
    """
    # Prepare variables from file and CLI
    variables = {}
    if var_file:
        info_message(f"Loading variables from: {var_file}")
        variables.update(load_variables_from_file(var_file))
    if var:
        cli_vars = parse_cli_variables(var)
        variables.update(cli_vars)

    # Prepare tweaks
    tweaks = {}
    if tweak:
        tweaks = parse_cli_tweaks(tweak)

    # Run async main function
    try:
        # Check if there's already an event loop running
        loop = asyncio.get_running_loop()
        # If we have a running loop, create a task instead of asyncio.run
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(
                asyncio.run,
                async_create_main(
                    ctx, template, name, project, folder, output, validate_only,
                    variables, tweaks, debug, local, healthcare, benchmark, batch
                )
            )
            future.result()
    except RuntimeError:
        # No running event loop, use asyncio.run normally
        asyncio.run(async_create_main(
            ctx, template, name, project, folder, output, validate_only,
            variables, tweaks, debug, local, healthcare, benchmark, batch
        ))


async def async_create_main(
    ctx: click.Context,
    template: Optional[str],
    name: Optional[str],
    project: Optional[str],
    folder: Optional[str],
    output: Optional[str],
    validate_only: bool,
    variables: Dict[str, Any],
    tweaks: Dict[str, Any],
    debug: bool,
    local: bool,
    healthcare: bool,
    benchmark: bool,
    batch: bool,
):
    """Async main function for create command."""
    try:
        config_manager = ctx.obj['config']
        api_client = APIClient(config_manager)
        professional_integration = ProfessionalServiceIntegration()

        # Initialize professional framework services if local mode requested
        if local:
            if professional_integration.is_service_available():
                if debug:
                    success_message("Professional framework services initialized for local processing")
                    if benchmark:
                        info_message("Performance benchmarking enabled")
                    if healthcare:
                        info_message("Healthcare compliance mode enabled")
            else:
                error_message(f"Professional framework services unavailable: {professional_integration.get_last_error()}")
                error_message("Please use API mode (remove --local flag) or check service configuration")
                ctx.exit(1)

        # Check if template is required and provided
        if not template:
            error_message("Template file or library name is required")
            ctx.exit(1)

        # Handle batch processing
        template_files = []
        if batch:
            template_files = glob.glob(template)
            if not template_files:
                error_message(f"No files found matching pattern: {template}")
                ctx.exit(1)
            info_message(f"Batch processing {len(template_files)} files")
        else:
            template_files = [template]

        # Process each template file
        results = []
        total_start_time = time.time()

        for template_file in template_files:
            try:
                result = await process_single_template(
                    template_file, config_manager, api_client, professional_integration,
                    name, project, folder, output, validate_only,
                    variables, tweaks, debug, local, healthcare, benchmark
                )
                results.append(result)

                if batch and result.get("success"):
                    click.echo(f"✅ {template_file}")
                elif batch:
                    click.echo(f"❌ {template_file}: {result.get('error', 'Unknown error')}")

            except Exception as e:
                error_msg = str(e)
                error_message(f"Failed to process {template_file}: {error_msg}")
                if not batch:  # Exit immediately if not batch mode
                    ctx.exit(1)
                results.append({"file": template_file, "success": False, "error": error_msg})

        # Show batch results summary
        if batch:
            total_time = time.time() - total_start_time
            show_batch_summary(results)

            if benchmark:
                successful_results = [r for r in results if r.get("success")]
                if successful_results:
                    avg_time = total_time / len(template_files)
                    click.echo(f"\n⚡ Performance: {len(template_files)} files in {total_time:.2f}s (avg: {avg_time:.3f}s/file)")

            failed_count = len([r for r in results if not r.get("success", True)])
            if failed_count > 0:
                ctx.exit(1)
        elif results and not results[0].get("success", True):
            ctx.exit(1)

    except Exception as e:
        error_message(f"Unexpected error: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        ctx.exit(1)


async def process_single_template(
    template: str, config_manager, api_client, professional_integration,
    name: Optional[str], project: Optional[str], folder: Optional[str],
    output: Optional[str], validate_only: bool,
    variables: Dict[str, Any], tweaks: Dict[str, Any],
    debug: bool, local: bool, healthcare: bool, benchmark: bool
) -> Dict[str, Any]:
    """Process a single template file."""
    start_time = time.time()

    # Determine if template is a file path or library template
    template_path = Path(template)
    is_library_template = not template_path.exists() and '/' in template

    if template_path.exists():
        # Load from file
        info_message(f"Loading specification: {template_path.name}")
        with open(template_path, 'r') as f:
            spec_yaml = f.read()

    elif is_library_template:
        # Try to use library template (API mode only for now)
        if local:
            raise ValueError("Library templates not supported in local mode. Use file paths with --local.")

        info_message(f"Using library template: {template}")
        try:
            if validate_only:
                raise ValueError("Library templates cannot be validated without creating. Use --output to save locally first.")

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

                return {"success": True, "flow_id": result.get('flow_id')}
            else:
                raise ValueError(f"Failed to create flow from library: {result.get('message', 'Unknown error')}")

        except Exception as e:
            raise ValueError(f"Failed to use library template: {e}")

    else:
        raise ValueError(f"Template file not found: {template}")

    # Parse spec to get metadata
    spec_dict = yaml.safe_load(spec_yaml)
    spec_name = spec_dict.get('name', 'Unknown')
    spec_description = spec_dict.get('description', '')
    components_count = len(spec_dict.get('components', {}))

    click.echo(f"📋 Specification: {spec_name}")
    if spec_description:
        click.echo(f"📝 Description: {spec_description}")
    click.echo(f"🧩 Components: {components_count}")

    # Show enhanced metadata if available
    if 'agentGoal' in spec_dict:
        click.echo(f"🎯 Goal: {spec_dict.get('agentGoal')}")
        click.echo(f"👥 Target User: {spec_dict.get('targetUser', 'N/A')}")
        click.echo(f"💼 Value Generation: {spec_dict.get('valueGeneration', 'N/A')}")

    # Show healthcare compliance info if enabled
    if healthcare and local:
        compliance_info = spec_dict.get('compliance', {})
        if compliance_info:
            click.echo(f"🏥 Healthcare Mode: HIPAA={compliance_info.get('hipaa', False)}, Audit={compliance_info.get('audit_logging', False)}")

    # Show loaded variables if debug
    if debug and variables:
        click.echo("\n🔧 Variables:")
        for key, value in variables.items():
            click.echo(f"  - {key}: {value}")

    # Show tweaks if debug
    if debug and tweaks:
        click.echo("\n⚙️ Tweaks:")
        for key, value in tweaks.items():
            click.echo(f"  - {key}: {value}")

    # Check AI Studio connectivity (skip if using local mode)
    if not local and not validate_only and not output:
        if not api_client.health_check_sync():
            error_message(f"Cannot connect to AI Studio at {config_manager.ai_studio_url}")
            error_message("Please check your configuration, use --local for offline processing, or use --output to save locally")
            raise RuntimeError("AI Studio connectivity check failed")

    # Validate specification
    info_message("Validating specification...")
    try:
        if local:
            # Use professional framework services for validation
            validation_result = await professional_integration.validate_specification_local(
                spec_yaml, healthcare_mode=healthcare
            )
        else:
            # Use API for validation
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
            raise ValueError("Specification validation failed")

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

        # Show validation performance if local mode with benchmarking
        if local and benchmark:
            perf = validation_result.get('performance', {})
            if perf.get('validation_time'):
                click.echo(f"⚡ Validation time: {perf['validation_time']:.3f}s (local)")

        success_message("Specification validation passed!")

    except Exception as e:
        if "validation failed" not in str(e).lower():
            error_message(f"Validation failed: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        raise e

    # If validate-only, stop here
    if validate_only:
        success_message("Validation complete (--validate-only flag set)")
        return {"success": True, "validated": True}

    # Convert specification to flow
    info_message("Converting specification to flow...")
    try:
        if local:
            # Use professional framework services for conversion
            convert_result = await professional_integration.convert_specification_local(
                spec_yaml=spec_yaml,
                variables=variables if variables else None,
                tweaks=tweaks if tweaks else None,
                healthcare_mode=healthcare,
                benchmark=benchmark
            )

            if not convert_result.get('success'):
                raise ValueError(f"Local conversion failed: {convert_result.get('error', 'Unknown error')}")

            flow = convert_result.get('flow')

            # Show performance metrics if benchmarking
            if benchmark:
                perf = convert_result.get('performance', {})
                benchmark_data = convert_result.get('benchmark', {})

                conversion_time = perf.get('total_conversion_time', 0)
                grade = benchmark_data.get('performance_summary', {}).get('performance_grade', 'N/A')

                click.echo(f"\n⚡ Performance Results:")
                click.echo(f"  - Conversion time: {conversion_time:.4f}s")
                click.echo(f"  - Performance grade: {grade}")
                click.echo(f"  - Target met: {'✅' if perf.get('performance_target_met') else '❌'}")

                if conversion_time < 0.001:
                    click.echo("🚀 Ultra-fast conversion achieved!")

        else:
            # Use API for conversion
            convert_result = api_client.convert_spec_sync(
                spec_yaml=spec_yaml,
                variables=variables if variables else None,
                tweaks=tweaks if tweaks else None
            )

            flow = convert_result.get('flow')
            if not flow:
                raise ValueError("Conversion failed: No flow data returned")

        # Show flow statistics
        click.echo(f"\n{format_flow_stats(flow)}")

    except Exception as e:
        error_message(f"Conversion failed: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        raise e

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
        return {"success": True, "output_file": str(output_path)}

    else:
        # Create flow in AI Studio
        if local:
            error_message("Cannot create flow in AI Studio from local mode. Use --output to save to file.")
            raise ValueError("AI Studio creation not supported in local mode")

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

            total_time = time.time() - start_time
            if benchmark:
                click.echo(f"⚡ Total processing time: {total_time:.2f}s")

            return {"success": True, "flow_id": flow_id}

        except Exception as e:
            error_message(f"Failed to create flow in AI Studio: {e}")
            if debug:
                import traceback
                traceback.print_exc()
            raise e