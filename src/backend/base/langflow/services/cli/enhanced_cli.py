"""
Enhanced CLI Service for Genesis Specification Development - Phase 4 Implementation.

This service provides an exceptional CLI experience with:
- Real-time validation with detailed feedback
- Interactive specification creation and editing
- Performance monitoring and optimization suggestions
- Integration with all Phase 1-3 components
- Comprehensive error handling and user guidance
"""

import asyncio
import json
import os
import sys
import time
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from datetime import datetime
import logging
import click
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.prompt import Prompt, Confirm
from rich.tree import Tree
from rich.markup import escape

from langflow.services.spec.service import SpecService
from langflow.services.runtime import (
    RuntimeType, ValidationOptions, converter_factory
)
from langflow.services.runtime.performance_optimizer import (
    OptimizationLevel, PerformanceOptimizer
)

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

console = Console()


@dataclass
class CLIConfig:
    """Configuration for CLI operations."""
    auto_save: bool = True
    validation_mode: str = "comprehensive"  # "quick", "comprehensive", "runtime"
    default_runtime: RuntimeType = RuntimeType.LANGFLOW
    optimization_level: OptimizationLevel = OptimizationLevel.BALANCED
    output_format: str = "rich"  # "rich", "json", "yaml"
    interactive_mode: bool = True
    watch_mode: bool = False
    performance_monitoring: bool = True


class EnhancedCLI:
    """Enhanced CLI for Genesis specification development with Phase 4 features."""

    def __init__(self, config: Optional[CLIConfig] = None):
        """Initialize the enhanced CLI."""
        self.config = config or CLIConfig()
        self.spec_service = SpecService()
        self.performance_optimizer = PerformanceOptimizer()
        self.session_stats = {
            "specs_validated": 0,
            "specs_converted": 0,
            "errors_fixed": 0,
            "start_time": datetime.now()
        }

    async def validate_specification_enhanced(
        self,
        spec_path: str,
        real_time: bool = True,
        show_suggestions: bool = True,
        runtime_validation: bool = False
    ) -> Dict[str, Any]:
        """
        Enhanced specification validation with real-time feedback.

        Args:
            spec_path: Path to specification file
            real_time: Enable real-time validation feedback
            show_suggestions: Show improvement suggestions
            runtime_validation: Validate against specific runtime

        Returns:
            Comprehensive validation result
        """
        try:
            # Load specification
            spec_content = self._load_specification(spec_path)
            if not spec_content:
                return {"valid": False, "error": "Could not load specification"}

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:

                if runtime_validation:
                    # Use Phase 3 runtime validation
                    task = progress.add_task("Validating with runtime...", total=100)
                    progress.update(task, advance=30)

                    result = await self.spec_service.validate_spec_with_runtime(
                        spec_content,
                        self.config.default_runtime,
                        ValidationOptions(
                            strict_mode=True,
                            performance_checks=self.config.performance_monitoring,
                            detailed_errors=True
                        )
                    )
                    progress.update(task, advance=70)
                else:
                    # Use enhanced comprehensive validation
                    task = progress.add_task("Running comprehensive validation...", total=100)
                    progress.update(task, advance=50)

                    result = await self.spec_service.validate_spec(
                        spec_content,
                        detailed=self.config.validation_mode == "comprehensive"
                    )
                    progress.update(task, advance=50)

            # Display results with rich formatting
            self._display_validation_results(result, spec_path, show_suggestions)

            # Update session statistics
            self.session_stats["specs_validated"] += 1
            if not result.get("valid", False):
                self.session_stats["errors_fixed"] += len(result.get("errors", []))

            return result

        except Exception as e:
            console.print(f"[red]Error during validation: {e}[/red]")
            logger.error(f"Validation error: {e}")
            return {"valid": False, "error": str(e)}

    async def convert_specification_enhanced(
        self,
        spec_path: str,
        output_path: Optional[str] = None,
        runtime: Optional[RuntimeType] = None,
        optimization: Optional[OptimizationLevel] = None,
        preview_only: bool = False
    ) -> Dict[str, Any]:
        """
        Enhanced specification conversion with performance monitoring.

        Args:
            spec_path: Path to specification file
            output_path: Output path for converted flow
            runtime: Target runtime (default from config)
            optimization: Optimization level (default from config)
            preview_only: Only preview conversion without saving

        Returns:
            Conversion result with performance metrics
        """
        try:
            # Load and validate specification first
            spec_content = self._load_specification(spec_path)
            if not spec_content:
                return {"success": False, "error": "Could not load specification"}

            # Set defaults
            target_runtime = runtime or self.config.default_runtime
            opt_level = optimization or self.config.optimization_level

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                console=console,
            ) as progress:

                # Phase 1: Validation
                validate_task = progress.add_task("Validating specification...", total=100)
                validation_result = await self.spec_service.validate_spec_with_runtime(
                    spec_content, target_runtime
                )
                progress.update(validate_task, completed=100)

                if not validation_result.get("valid", False):
                    console.print("[red]Specification validation failed. Fix errors before conversion.[/red]")
                    self._display_validation_results(validation_result, spec_path, True)
                    return {"success": False, "validation_result": validation_result}

                # Phase 2: Enhanced conversion with optimization
                convert_task = progress.add_task("Converting with optimization...", total=100)
                progress.update(convert_task, advance=20)

                conversion_result = await self.spec_service.convert_spec_to_flow_enhanced(
                    spec_content,
                    target_runtime=target_runtime,
                    optimization_level=opt_level.value
                )
                progress.update(convert_task, advance=60)

                # Phase 3: Performance analysis
                perf_task = progress.add_task("Analyzing performance...", total=100)
                performance_metrics = conversion_result.get("performance_metrics", {})
                optimization_suggestions = await self._analyze_performance(
                    conversion_result, target_runtime
                )
                progress.update(perf_task, completed=100)
                progress.update(convert_task, completed=100)

            # Display conversion results
            self._display_conversion_results(
                conversion_result, performance_metrics, optimization_suggestions,
                preview_only
            )

            # Save if not preview only
            if not preview_only and conversion_result.get("success", False):
                output_file = output_path or self._generate_output_path(spec_path, target_runtime)
                await self._save_conversion_result(conversion_result, output_file)
                console.print(f"[green]✓ Converted specification saved to: {output_file}[/green]")

            # Update session statistics
            self.session_stats["specs_converted"] += 1

            return conversion_result

        except Exception as e:
            console.print(f"[red]Error during conversion: {e}[/red]")
            logger.error(f"Conversion error: {e}")
            return {"success": False, "error": str(e)}

    async def interactive_spec_builder(self) -> Dict[str, Any]:
        """
        Interactive specification builder with guided creation.

        Returns:
            Created specification dictionary
        """
        console.print(Panel.fit(
            "[bold blue]Genesis Specification Interactive Builder[/bold blue]\n"
            "This wizard will guide you through creating a Genesis specification",
            title="🚀 Welcome"
        ))

        spec = {}

        try:
            # Basic metadata
            console.print("\n[bold]Step 1: Basic Information[/bold]")
            spec["name"] = Prompt.ask("Specification name")
            spec["description"] = Prompt.ask("Description")
            spec["agentGoal"] = Prompt.ask("Agent goal")

            # Generate ID
            domain = Prompt.ask("Domain", default="autonomize.ai")
            name_slug = spec["name"].lower().replace(" ", "-")
            spec["id"] = f"urn:agent:genesis:{domain}:{name_slug}:1.0.0"

            # Agent type and complexity
            console.print("\n[bold]Step 2: Workflow Type[/bold]")
            agent_types = ["Single Agent", "Multi-Agent (CrewAI)", "Knowledge-based Agent"]
            agent_type = self._prompt_choice("Select agent type", agent_types)

            # Build components based on selection
            console.print(f"\n[bold]Step 3: Building Components for {agent_type}[/bold]")
            spec["components"] = await self._build_components_interactive(agent_type)

            # Additional configuration
            console.print("\n[bold]Step 4: Configuration[/bold]")
            spec["kind"] = "Multi Agent" if "Multi" in agent_type else "Single Agent"
            spec["targetUser"] = self._prompt_choice(
                "Target user type",
                ["internal", "external", "customer"]
            )

            # Preview and confirmation
            console.print("\n[bold]Step 5: Preview[/bold]")
            preview_yaml = yaml.dump(spec, default_flow_style=False, sort_keys=False)
            syntax = Syntax(preview_yaml, "yaml", theme="monokai", line_numbers=True)
            console.print(Panel(syntax, title="Generated Specification Preview"))

            if Confirm.ask("Save this specification?"):
                filename = f"{name_slug}.yaml"
                filepath = Path.cwd() / filename

                with open(filepath, 'w') as f:
                    yaml.dump(spec, f, default_flow_style=False, sort_keys=False)

                console.print(f"[green]✓ Specification saved to: {filepath}[/green]")

                # Offer validation
                if Confirm.ask("Validate the specification now?"):
                    await self.validate_specification_enhanced(str(filepath))

            return spec

        except KeyboardInterrupt:
            console.print("\n[yellow]Specification builder cancelled[/yellow]")
            return {}
        except Exception as e:
            console.print(f"[red]Error in interactive builder: {e}[/red]")
            return {}

    async def watch_mode(self, spec_paths: List[str]) -> None:
        """
        Watch mode for real-time validation of specifications.

        Args:
            spec_paths: List of specification file paths to watch
        """
        console.print(Panel.fit(
            f"[bold green]Watch Mode Active[/bold green]\n"
            f"Monitoring {len(spec_paths)} specification(s) for changes...\n"
            f"Press Ctrl+C to stop",
            title="👀 Real-time Validation"
        ))

        try:
            import watchfiles

            async for changes in watchfiles.awatch(*spec_paths):
                for change_type, file_path in changes:
                    if str(file_path).endswith(('.yaml', '.yml')):
                        console.print(f"\n[blue]📝 Change detected: {file_path}[/blue]")
                        await self.validate_specification_enhanced(
                            str(file_path),
                            real_time=True,
                            show_suggestions=True
                        )

        except KeyboardInterrupt:
            console.print("\n[yellow]Watch mode stopped[/yellow]")
        except ImportError:
            console.print("[red]Watch mode requires 'watchfiles' package. Install with: pip install watchfiles[/red]")
        except Exception as e:
            console.print(f"[red]Error in watch mode: {e}[/red]")

    async def performance_dashboard(self) -> None:
        """
        Display comprehensive performance dashboard.
        """
        console.clear()

        # Session statistics
        session_table = Table(title="Session Statistics")
        session_table.add_column("Metric", style="cyan")
        session_table.add_column("Value", style="green")

        duration = datetime.now() - self.session_stats["start_time"]
        session_table.add_row("Session Duration", str(duration).split('.')[0])
        session_table.add_row("Specifications Validated", str(self.session_stats["specs_validated"]))
        session_table.add_row("Specifications Converted", str(self.session_stats["specs_converted"]))
        session_table.add_row("Errors Fixed", str(self.session_stats["errors_fixed"]))

        # Component mapping statistics
        mapping_stats = await self.spec_service.get_all_available_components()
        discovery_stats = mapping_stats.get("discovery_stats", {})

        mapping_table = Table(title="Component Mapping Status")
        mapping_table.add_column("Component Type", style="cyan")
        mapping_table.add_column("Count", style="green")

        mapping_table.add_row("Total Langflow Components", str(discovery_stats.get("total_langflow_components", 0)))
        mapping_table.add_row("Genesis Mapped", str(discovery_stats.get("total_mapped", 0)))
        mapping_table.add_row("Unmapped Components", str(discovery_stats.get("unmapped_count", 0)))
        mapping_table.add_row("Mapping Coverage", f"{discovery_stats.get('mapping_coverage', 0):.1f}%")

        console.print(session_table)
        console.print("\n")
        console.print(mapping_table)

        # Performance optimization suggestions
        console.print("\n[bold]🚀 Performance Optimization Suggestions[/bold]")
        suggestions = [
            "Use 'genesis:chat_input' and 'genesis:chat_output' for optimal performance",
            "Consider multi-agent patterns for complex workflows",
            "Enable performance monitoring for detailed metrics",
            "Use database-driven component mappings for scalability"
        ]

        for i, suggestion in enumerate(suggestions, 1):
            console.print(f"  {i}. {suggestion}")

    def generate_usage_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive usage report for analysis.

        Returns:
            Usage report dictionary
        """
        return {
            "session_id": id(self),
            "start_time": self.session_stats["start_time"].isoformat(),
            "duration_seconds": (datetime.now() - self.session_stats["start_time"]).total_seconds(),
            "statistics": self.session_stats.copy(),
            "configuration": {
                "validation_mode": self.config.validation_mode,
                "default_runtime": self.config.default_runtime.value,
                "optimization_level": self.config.optimization_level.value,
                "performance_monitoring": self.config.performance_monitoring
            },
            "timestamp": datetime.now().isoformat()
        }

    # Helper Methods

    def _load_specification(self, spec_path: str) -> Optional[str]:
        """Load specification content from file."""
        try:
            with open(spec_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            console.print(f"[red]Error loading specification: {e}[/red]")
            return None

    def _display_validation_results(
        self,
        result: Dict[str, Any],
        spec_path: str,
        show_suggestions: bool = True
    ) -> None:
        """Display validation results with rich formatting."""

        if result.get("valid", False):
            console.print(f"[green]✅ Specification validation passed: {spec_path}[/green]")

            # Show summary
            summary = result.get("summary", {})
            if summary.get("warning_count", 0) > 0:
                console.print(f"[yellow]⚠️  {summary['warning_count']} warnings found[/yellow]")

            return

        # Display errors
        errors = result.get("errors", [])
        warnings = result.get("warnings", [])
        summary = result.get("summary", {})

        # Error summary
        error_panel = Panel.fit(
            f"[red]❌ Validation Failed[/red]\n"
            f"Errors: {summary.get('error_count', len(errors))}\n"
            f"Warnings: {summary.get('warning_count', len(warnings))}",
            title=f"📋 {Path(spec_path).name}"
        )
        console.print(error_panel)

        # Detailed errors
        if errors:
            error_table = Table(title="Errors", show_header=True, header_style="bold red")
            error_table.add_column("Component", style="cyan", width=15)
            error_table.add_column("Error", style="red")
            error_table.add_column("Suggestion", style="yellow", width=30)

            for error in errors[:10]:  # Limit to first 10 errors
                component = error.get("component_id", "Global")
                message = error.get("message", str(error))
                suggestion = error.get("suggestion", "")

                error_table.add_row(
                    escape(component),
                    escape(message),
                    escape(suggestion)
                )

            console.print(error_table)

        # Show suggestions if requested
        if show_suggestions:
            suggestions = self.spec_service.get_validation_suggestions(result)
            if suggestions:
                console.print("\n[bold blue]💡 Actionable Suggestions:[/bold blue]")
                for i, suggestion in enumerate(suggestions[:5], 1):
                    console.print(f"  {i}. {suggestion}")

    def _display_conversion_results(
        self,
        result: Dict[str, Any],
        performance_metrics: Dict[str, Any],
        optimization_suggestions: List[str],
        preview_only: bool = False
    ) -> None:
        """Display conversion results with performance metrics."""

        if not result.get("success", False):
            console.print("[red]❌ Conversion failed[/red]")
            errors = result.get("errors", [])
            for error in errors:
                console.print(f"  • {error}")
            return

        # Success message
        mode = "Preview" if preview_only else "Conversion"
        console.print(f"[green]✅ {mode} completed successfully[/green]")

        # Performance metrics table
        if performance_metrics:
            perf_table = Table(title="Performance Metrics")
            perf_table.add_column("Metric", style="cyan")
            perf_table.add_column("Value", style="green")

            for key, value in performance_metrics.items():
                if isinstance(value, (int, float)):
                    if "time" in key.lower() or "duration" in key.lower():
                        value = f"{value:.2f}s"
                    elif "memory" in key.lower():
                        value = f"{value}MB"

                perf_table.add_row(key.replace("_", " ").title(), str(value))

            console.print(perf_table)

        # Optimization suggestions
        if optimization_suggestions:
            console.print("\n[bold blue]🚀 Optimization Suggestions:[/bold blue]")
            for i, suggestion in enumerate(optimization_suggestions, 1):
                console.print(f"  {i}. {suggestion}")

    def _prompt_choice(self, question: str, choices: List[str]) -> str:
        """Prompt user to select from choices."""
        for i, choice in enumerate(choices, 1):
            console.print(f"  {i}. {choice}")

        while True:
            try:
                selection = int(Prompt.ask(f"{question} (1-{len(choices)})"))
                if 1 <= selection <= len(choices):
                    return choices[selection - 1]
                else:
                    console.print(f"[red]Please enter a number between 1 and {len(choices)}[/red]")
            except ValueError:
                console.print("[red]Please enter a valid number[/red]")

    async def _build_components_interactive(self, agent_type: str) -> Dict[str, Any]:
        """Build components based on agent type selection."""
        components = {}

        # Always start with input
        components["input"] = {
            "type": "genesis:chat_input",
            "name": "User Input",
            "description": "Receives user queries"
        }

        if agent_type == "Single Agent":
            # Single agent workflow
            components["agent"] = {
                "type": "genesis:agent",
                "name": "Main Agent",
                "description": "Primary processing agent",
                "config": {
                    "provider": "Azure OpenAI",
                    "temperature": 0.7
                },
                "provides": [
                    {"useAs": "response", "in": "output", "description": "Agent response to output"}
                ]
            }

            # Add tools if requested
            if Confirm.ask("Add tools to the agent?"):
                tool_types = ["Knowledge Search", "API Request", "MCP Tool"]
                selected_tool = self._prompt_choice("Select tool type", tool_types)

                if selected_tool == "Knowledge Search":
                    components["knowledge_tool"] = {
                        "type": "genesis:knowledge_hub_search",
                        "name": "Knowledge Search",
                        "description": "Search knowledge base",
                        "asTools": True,
                        "provides": [
                            {"useAs": "tools", "in": "agent", "description": "Knowledge search capability"}
                        ]
                    }

        elif agent_type == "Multi-Agent (CrewAI)":
            # Multi-agent CrewAI workflow
            agent_count = int(Prompt.ask("Number of agents", default="2"))

            for i in range(agent_count):
                agent_id = f"agent_{i+1}"
                role = Prompt.ask(f"Role for agent {i+1}")
                goal = Prompt.ask(f"Goal for agent {i+1}")

                components[agent_id] = {
                    "type": "genesis:crewai_agent",
                    "name": f"Agent {i+1}",
                    "description": f"CrewAI agent: {role}",
                    "config": {
                        "role": role,
                        "goal": goal,
                        "backstory": f"Expert {role.lower()} with specialized knowledge"
                    }
                }

            # Add crew coordination
            components["crew"] = {
                "type": "genesis:crewai_sequential_crew",
                "name": "Agent Crew",
                "description": "Coordinates multiple agents",
                "config": {
                    "agents": [f"agent_{i+1}" for i in range(agent_count)],
                    "process": "sequential"
                },
                "provides": [
                    {"useAs": "response", "in": "output", "description": "Crew result to output"}
                ]
            }

        # Always end with output
        components["output"] = {
            "type": "genesis:chat_output",
            "name": "Response Output",
            "description": "Displays the final response"
        }

        # Connect input to first processing component
        if "agent" in components:
            components["input"]["provides"] = [
                {"useAs": "input", "in": "agent", "description": "User input to agent"}
            ]
        elif "crew" in components:
            components["input"]["provides"] = [
                {"useAs": "input", "in": "crew", "description": "User input to crew"}
            ]

        return components

    async def _analyze_performance(
        self,
        conversion_result: Dict[str, Any],
        runtime: RuntimeType
    ) -> List[str]:
        """Analyze performance and generate optimization suggestions."""
        suggestions = []

        # Analyze based on conversion result
        metadata = conversion_result.get("metadata", {})
        component_count = metadata.get("component_count", 0)
        edge_count = metadata.get("edge_count", 0)

        if component_count > 10:
            suggestions.append("Consider breaking down large workflows into smaller sub-workflows")

        if edge_count > 15:
            suggestions.append("Complex connection patterns detected - review component relationships")

        # Runtime-specific suggestions
        if runtime == RuntimeType.LANGFLOW:
            suggestions.append("Optimize for Langflow visual representation")
        elif runtime == RuntimeType.TEMPORAL:
            suggestions.append("Consider workflow persistence for long-running processes")

        return suggestions

    def _generate_output_path(self, spec_path: str, runtime: RuntimeType) -> str:
        """Generate appropriate output path for converted specification."""
        spec_file = Path(spec_path)
        base_name = spec_file.stem

        if runtime == RuntimeType.LANGFLOW:
            return str(spec_file.parent / f"{base_name}_langflow.json")
        elif runtime == RuntimeType.TEMPORAL:
            return str(spec_file.parent / f"{base_name}_temporal.py")
        else:
            return str(spec_file.parent / f"{base_name}_converted.json")

    async def _save_conversion_result(self, result: Dict[str, Any], output_path: str) -> None:
        """Save conversion result to file."""
        try:
            flow_data = result.get("flow_data", {})

            with open(output_path, 'w', encoding='utf-8') as f:
                if output_path.endswith('.json'):
                    json.dump(flow_data, f, indent=2)
                elif output_path.endswith('.yaml') or output_path.endswith('.yml'):
                    yaml.dump(flow_data, f, default_flow_style=False)
                else:
                    json.dump(flow_data, f, indent=2)

        except Exception as e:
            console.print(f"[red]Error saving conversion result: {e}[/red]")
            raise


# CLI Integration Functions
def create_enhanced_cli() -> EnhancedCLI:
    """Create enhanced CLI instance with default configuration."""
    return EnhancedCLI(CLIConfig())


async def main():
    """Main CLI entry point for testing."""
    cli = create_enhanced_cli()

    # Example usage
    console.print(Panel.fit(
        "[bold blue]Genesis Enhanced CLI - Phase 4[/bold blue]\n"
        "Advanced specification development environment",
        title="🚀 Welcome"
    ))

    # Show performance dashboard
    await cli.performance_dashboard()


if __name__ == "__main__":
    asyncio.run(main())