"""
CLI Commands for Enhanced Genesis Specification Development - Phase 4.

Provides comprehensive command-line interface for Genesis specifications with:
- Real-time validation and feedback
- Interactive specification creation
- Performance monitoring and optimization
- Integration with Phase 1-3 enhancements
"""

import asyncio
import sys
from pathlib import Path
from typing import List, Optional

import click
from rich.console import Console

from .enhanced_cli import EnhancedCLI, CLIConfig
from langflow.services.runtime import RuntimeType
from langflow.services.runtime.performance_optimizer import OptimizationLevel

console = Console()


def async_command(f):
    """Decorator to run async functions in click commands."""
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper


@click.group()
@click.option('--config-file', type=click.Path(exists=True), help='Configuration file path')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.option('--performance-monitoring/--no-performance-monitoring', default=True,
              help='Enable performance monitoring')
@click.pass_context
def cli(ctx, config_file, verbose, performance_monitoring):
    """
    Enhanced Genesis CLI - Phase 4 Implementation.

    Advanced specification development environment with real-time validation,
    performance optimization, and comprehensive developer tooling.
    """
    # Initialize CLI configuration
    config = CLIConfig(
        performance_monitoring=performance_monitoring,
        interactive_mode=True
    )

    # Create enhanced CLI instance
    ctx.ensure_object(dict)
    ctx.obj['cli'] = EnhancedCLI(config)
    ctx.obj['verbose'] = verbose


@cli.group()
@click.pass_context
def spec(ctx):
    """Specification management commands."""
    pass


@spec.command()
@click.argument('spec_path', type=click.Path(exists=True))
@click.option('--real-time/--no-real-time', default=True,
              help='Enable real-time validation feedback')
@click.option('--suggestions/--no-suggestions', default=True,
              help='Show improvement suggestions')
@click.option('--runtime-validation', is_flag=True,
              help='Validate against specific runtime')
@click.option('--runtime', type=click.Choice(['langflow', 'temporal', 'kafka']),
              default='langflow', help='Target runtime for validation')
@click.pass_context
@async_command
async def validate(ctx, spec_path, real_time, suggestions, runtime_validation, runtime):
    """
    Validate Genesis specification with enhanced feedback.

    SPEC_PATH: Path to the specification file to validate
    """
    enhanced_cli: EnhancedCLI = ctx.obj['cli']

    # Convert runtime string to enum
    runtime_type = RuntimeType(runtime) if runtime_validation else None

    # Set runtime in config if specified
    if runtime_type:
        enhanced_cli.config.default_runtime = runtime_type

    console.print(f"[blue]🔍 Validating specification: {spec_path}[/blue]")

    result = await enhanced_cli.validate_specification_enhanced(
        spec_path=spec_path,
        real_time=real_time,
        show_suggestions=suggestions,
        runtime_validation=runtime_validation
    )

    # Exit with error code if validation failed
    if not result.get("valid", False):
        sys.exit(1)


@spec.command()
@click.argument('spec_path', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), help='Output file path')
@click.option('--runtime', type=click.Choice(['langflow', 'temporal', 'kafka']),
              default='langflow', help='Target runtime')
@click.option('--optimization', type=click.Choice(['fast', 'balanced', 'thorough']),
              default='balanced', help='Optimization level')
@click.option('--preview', is_flag=True, help='Preview conversion without saving')
@click.pass_context
@async_command
async def convert(ctx, spec_path, output, runtime, optimization, preview):
    """
    Convert Genesis specification to target runtime format.

    SPEC_PATH: Path to the specification file to convert
    """
    enhanced_cli: EnhancedCLI = ctx.obj['cli']

    # Convert string enums
    runtime_type = RuntimeType(runtime)
    opt_level = OptimizationLevel(optimization)

    console.print(f"[blue]🔄 Converting specification: {spec_path}[/blue]")
    console.print(f"[blue]Target: {runtime} | Optimization: {optimization}[/blue]")

    result = await enhanced_cli.convert_specification_enhanced(
        spec_path=spec_path,
        output_path=output,
        runtime=runtime_type,
        optimization=opt_level,
        preview_only=preview
    )

    # Exit with error code if conversion failed
    if not result.get("success", False):
        sys.exit(1)


@spec.command()
@click.pass_context
@async_command
async def create(ctx):
    """
    Interactive specification builder with guided creation.

    Launch an interactive wizard to create Genesis specifications step by step.
    """
    enhanced_cli: EnhancedCLI = ctx.obj['cli']

    console.print("[blue]🎯 Starting interactive specification builder...[/blue]")

    result = await enhanced_cli.interactive_spec_builder()

    if result:
        console.print("[green]✓ Specification created successfully[/green]")
    else:
        console.print("[yellow]Specification creation cancelled[/yellow]")


@spec.command()
@click.argument('spec_paths', nargs=-1, type=click.Path(exists=True), required=True)
@click.pass_context
@async_command
async def watch(ctx, spec_paths):
    """
    Watch specifications for changes with real-time validation.

    SPEC_PATHS: One or more specification files to monitor
    """
    enhanced_cli: EnhancedCLI = ctx.obj['cli']

    # Convert to list
    paths = list(spec_paths)

    console.print(f"[blue]👀 Starting watch mode for {len(paths)} specification(s)...[/blue]")

    await enhanced_cli.watch_mode(paths)


@cli.command()
@click.pass_context
@async_command
async def dashboard(ctx):
    """
    Display comprehensive performance and usage dashboard.

    Shows session statistics, component mapping status, and optimization suggestions.
    """
    enhanced_cli: EnhancedCLI = ctx.obj['cli']

    await enhanced_cli.performance_dashboard()


@cli.command()
@click.option('--format', type=click.Choice(['json', 'yaml', 'table']), default='table',
              help='Output format')
@click.option('--output', '-o', type=click.Path(), help='Save report to file')
@click.pass_context
def report(ctx, format, output):
    """
    Generate comprehensive usage and performance report.
    """
    enhanced_cli: EnhancedCLI = ctx.obj['cli']

    report_data = enhanced_cli.generate_usage_report()

    if format == 'json':
        import json
        output_text = json.dumps(report_data, indent=2)
    elif format == 'yaml':
        import yaml
        output_text = yaml.dump(report_data, default_flow_style=False)
    else:  # table
        from rich.table import Table

        table = Table(title="Genesis CLI Usage Report")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        # Session info
        table.add_row("Session Duration", f"{report_data['duration_seconds']:.1f}s")
        table.add_row("Specs Validated", str(report_data['statistics']['specs_validated']))
        table.add_row("Specs Converted", str(report_data['statistics']['specs_converted']))
        table.add_row("Errors Fixed", str(report_data['statistics']['errors_fixed']))

        # Configuration
        config = report_data['configuration']
        table.add_row("Validation Mode", config['validation_mode'])
        table.add_row("Default Runtime", config['default_runtime'])
        table.add_row("Optimization Level", config['optimization_level'])

        console.print(table)
        return

    if output:
        with open(output, 'w') as f:
            f.write(output_text)
        console.print(f"[green]✓ Report saved to: {output}[/green]")
    else:
        console.print(output_text)


@cli.group()
@click.pass_context
def dev(ctx):
    """Developer tools and debugging commands."""
    pass


@dev.command()
@click.option('--component-type', help='Filter by component type')
@click.option('--show-unmapped', is_flag=True, help='Show unmapped components')
@click.pass_context
@async_command
async def components(ctx, component_type, show_unmapped):
    """
    List available components and mapping status.
    """
    enhanced_cli: EnhancedCLI = ctx.obj['cli']

    console.print("[blue]📦 Analyzing component mappings...[/blue]")

    components_data = await enhanced_cli.spec_service.get_all_available_components()

    from rich.table import Table

    # Genesis mapped components
    genesis_table = Table(title="Genesis Mapped Components")
    genesis_table.add_column("Genesis Type", style="cyan")
    genesis_table.add_column("Langflow Component", style="green")
    genesis_table.add_column("Category", style="yellow")

    genesis_mapped = components_data.get("genesis_mapped", {})
    for genesis_type, mapping in genesis_mapped.items():
        if component_type and component_type not in genesis_type:
            continue

        component = mapping.get("component", "Unknown")
        category = mapping.get("category", "Unknown")
        genesis_table.add_row(genesis_type, component, category)

    console.print(genesis_table)

    # Show unmapped if requested
    if show_unmapped:
        unmapped = components_data.get("unmapped", [])
        if unmapped:
            unmapped_table = Table(title="Unmapped Components")
            unmapped_table.add_column("Component", style="red")
            unmapped_table.add_column("Category", style="yellow")
            unmapped_table.add_column("Priority", style="blue")
            unmapped_table.add_column("Suggestion", style="cyan")

            for comp in unmapped[:20]:  # Limit to first 20
                unmapped_table.add_row(
                    comp["name"],
                    comp["category"],
                    comp["priority"],
                    comp["suggestion"]
                )

            console.print(unmapped_table)
        else:
            console.print("[green]✓ All components are mapped![/green]")

    # Statistics
    stats = components_data.get("discovery_stats", {})
    console.print(f"\n[blue]📊 Mapping Coverage: {stats.get('mapping_coverage', 0):.1f}%[/blue]")


@dev.command()
@click.argument('spec_path', type=click.Path(exists=True))
@click.option('--detailed', is_flag=True, help='Show detailed type analysis')
@click.pass_context
@async_command
async def analyze(ctx, spec_path, detailed):
    """
    Analyze specification structure and performance characteristics.

    SPEC_PATH: Path to the specification file to analyze
    """
    enhanced_cli: EnhancedCLI = ctx.obj['cli']

    console.print(f"[blue]🔬 Analyzing specification: {spec_path}[/blue]")

    # Load and analyze specification
    spec_content = enhanced_cli._load_specification(spec_path)
    if not spec_content:
        console.print("[red]❌ Could not load specification[/red]")
        sys.exit(1)

    import yaml
    spec_dict = yaml.safe_load(spec_content)

    from rich.tree import Tree
    from rich.table import Table

    # Structure analysis
    tree = Tree(f"[bold blue]Specification Structure[/bold blue]")

    # Metadata
    metadata_node = tree.add("[cyan]Metadata[/cyan]")
    metadata_node.add(f"Name: {spec_dict.get('name', 'Unknown')}")
    metadata_node.add(f"Kind: {spec_dict.get('kind', 'Unknown')}")
    metadata_node.add(f"ID: {spec_dict.get('id', 'Unknown')}")

    # Components
    components = spec_dict.get("components", {})
    comp_node = tree.add(f"[green]Components ({len(components)})[/green]")

    for comp_id, comp_data in components.items():
        comp_type = comp_data.get("type", "Unknown")
        comp_node.add(f"{comp_id}: {comp_type}")

    console.print(tree)

    # Performance characteristics
    if detailed:
        perf_table = Table(title="Performance Characteristics")
        perf_table.add_column("Metric", style="cyan")
        perf_table.add_column("Value", style="green")
        perf_table.add_column("Assessment", style="yellow")

        # Analyze complexity
        component_count = len(components)
        edge_count = sum(len(comp.get("provides", [])) for comp in components.values())

        perf_table.add_row("Component Count", str(component_count),
                          "High" if component_count > 10 else "Normal")
        perf_table.add_row("Connection Count", str(edge_count),
                          "Complex" if edge_count > 15 else "Simple")

        # Analyze component types
        component_types = [comp.get("type", "") for comp in components.values()]
        agent_count = sum(1 for t in component_types if "agent" in t.lower())
        tool_count = sum(1 for comp in components.values() if comp.get("asTools", False))

        perf_table.add_row("Agent Count", str(agent_count),
                          "Multi-agent" if agent_count > 1 else "Single-agent")
        perf_table.add_row("Tool Count", str(tool_count),
                          "Tool-heavy" if tool_count > 3 else "Standard")

        console.print(perf_table)


# Command aliases for convenience
spec_commands = spec
dev_commands = dev


if __name__ == "__main__":
    cli()