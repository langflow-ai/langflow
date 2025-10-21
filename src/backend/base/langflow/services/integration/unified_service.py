"""
Unified Genesis Service - Phase 4 Seamless Integration.

Provides a unified service interface that seamlessly integrates all Phase 1-3
components with Phase 4 enhancements to deliver an exceptional developer experience.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Callable
from dataclasses import dataclass, field
from enum import Enum

import yaml
from rich.console import Console

# Phase 1-3 Imports
from langflow.services.spec.service import SpecService
from langflow.services.runtime import RuntimeType, ValidationOptions, converter_factory
from langflow.services.runtime.performance_optimizer import OptimizationLevel

# Phase 4 Imports
from langflow.services.cli.enhanced_cli import EnhancedCLI, CLIConfig
from langflow.services.ide.language_server import GenesisLanguageServer
from langflow.services.developer.debug_tools import GenesisDebugger, DebugLevel
from langflow.services.dashboard.performance_dashboard import PerformanceDashboard, DashboardConfig
from langflow.services.testing.integration_tester import IntegrationTester

logger = logging.getLogger(__name__)
console = Console()


class GenesisMode(Enum):
    """Genesis service operating modes."""
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"
    DEBUGGING = "debugging"


@dataclass
class GenesisConfig:
    """Unified configuration for Genesis service."""
    # Core settings
    mode: GenesisMode = GenesisMode.DEVELOPMENT
    default_runtime: RuntimeType = RuntimeType.LANGFLOW
    optimization_level: OptimizationLevel = OptimizationLevel.BALANCED

    # Validation settings
    validation_mode: str = "comprehensive"  # "quick", "comprehensive", "runtime"
    auto_validation: bool = True
    real_time_validation: bool = True

    # Performance settings
    performance_monitoring: bool = True
    performance_optimization: bool = True
    cache_enabled: bool = True

    # Developer experience settings
    cli_enhanced: bool = True
    ide_integration: bool = True
    debug_enabled: bool = True
    interactive_mode: bool = True

    # Testing settings
    auto_testing: bool = False
    regression_testing: bool = True
    performance_testing: bool = True

    # Output settings
    verbose_output: bool = True
    rich_formatting: bool = True
    save_artifacts: bool = True

    # Advanced settings
    experimental_features: bool = False
    telemetry_enabled: bool = True
    plugin_support: bool = True


class UnifiedGenesisService:
    """
    Unified Genesis Service - Seamless Integration of All Phases.

    This service provides a single, comprehensive interface for all Genesis
    specification development operations, integrating all Phase 1-3 components
    with Phase 4 enhancements to deliver an exceptional developer experience.
    """

    def __init__(self, config: Optional[GenesisConfig] = None):
        """
        Initialize the unified Genesis service.

        Args:
            config: Service configuration
        """
        self.config = config or GenesisConfig()

        # Initialize Phase 1-3 services
        self.spec_service = SpecService()

        # Initialize Phase 4 services
        self.enhanced_cli = EnhancedCLI(CLIConfig(
            auto_save=True,
            validation_mode=self.config.validation_mode,
            default_runtime=self.config.default_runtime,
            optimization_level=self.config.optimization_level,
            performance_monitoring=self.config.performance_monitoring,
            interactive_mode=self.config.interactive_mode
        )) if self.config.cli_enhanced else None

        self.language_server = GenesisLanguageServer() if self.config.ide_integration else None

        self.debugger = GenesisDebugger() if self.config.debug_enabled else None

        self.dashboard = PerformanceDashboard(DashboardConfig(
            enable_real_time=self.config.performance_monitoring,
            auto_optimize=self.config.performance_optimization,
            save_history=True
        )) if self.config.performance_monitoring else None

        self.tester = IntegrationTester() if self.config.auto_testing else None

        # Service state
        self.is_initialized = False
        self.session_id = None
        self.start_time = None
        self.metrics = {
            "operations_performed": 0,
            "validations_completed": 0,
            "conversions_completed": 0,
            "errors_handled": 0,
            "total_processing_time": 0.0
        }

        # Event handlers
        self.event_handlers: Dict[str, List[Callable]] = {}

        logger.info(f"Unified Genesis Service initialized in {self.config.mode.value} mode")

    async def initialize(self) -> Dict[str, Any]:
        """
        Initialize the unified service and all components.

        Returns:
            Initialization result
        """
        if self.is_initialized:
            return {"success": True, "message": "Service already initialized"}

        self.start_time = datetime.now(timezone.utc)
        self.session_id = f"genesis_{int(time.time())}"

        initialization_results = {}

        try:
            console.print("[bold blue]🚀 Initializing Unified Genesis Service[/bold blue]")

            # Initialize Phase 4 components
            if self.dashboard:
                await self.dashboard.start_monitoring()
                initialization_results["performance_monitoring"] = "active"

            if self.language_server and self.config.ide_integration:
                # Language server initialization would be handled externally
                initialization_results["language_server"] = "ready"

            # Initialize database-driven component mappings (Phase 2)
            components_info = await self.spec_service.get_all_available_components()
            initialization_results["component_mappings"] = {
                "total_mapped": components_info.get("discovery_stats", {}).get("total_mapped", 0),
                "mapping_coverage": components_info.get("discovery_stats", {}).get("mapping_coverage", 0)
            }

            # Initialize runtime converters (Phase 3)
            runtime_status = await self._verify_runtime_support()
            initialization_results["runtime_support"] = runtime_status

            self.is_initialized = True

            console.print("[green]✅ Unified Genesis Service initialized successfully[/green]")

            return {
                "success": True,
                "session_id": self.session_id,
                "mode": self.config.mode.value,
                "initialization_results": initialization_results,
                "features_enabled": self._get_enabled_features()
            }

        except Exception as e:
            logger.error(f"Failed to initialize Unified Genesis Service: {e}")
            return {
                "success": False,
                "error": str(e),
                "partial_results": initialization_results
            }

    async def process_specification_comprehensive(
        self,
        spec_input: Union[str, Path, Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive specification processing with all Phase 1-4 capabilities.

        Args:
            spec_input: Specification file path, content, or dictionary
            options: Processing options

        Returns:
            Comprehensive processing results
        """
        if not self.is_initialized:
            await self.initialize()

        processing_start = time.time()
        options = options or {}

        try:
            # Load specification
            spec_content, spec_dict = await self._load_specification(spec_input)
            if not spec_content:
                return {"success": False, "error": "Failed to load specification"}

            console.print(f"[blue]🔄 Processing specification comprehensively...[/blue]")

            # Phase 1: Enhanced Validation (comprehensive multi-layer)
            validation_result = await self._perform_enhanced_validation(
                spec_content, options.get("validation_options", {})
            )

            # Phase 2: Dynamic Component Analysis
            component_analysis = await self._perform_component_analysis(spec_dict)

            # Phase 3: Multi-Runtime Conversion
            conversion_results = await self._perform_multi_runtime_conversion(
                spec_content, options.get("target_runtimes", [self.config.default_runtime])
            )

            # Phase 4: Enhanced Developer Experience
            developer_insights = await self._provide_developer_insights(
                spec_content, validation_result, conversion_results
            )

            # Performance monitoring
            performance_metrics = {}
            if self.dashboard:
                perf_result = await self.dashboard.monitor_specification_processing(
                    str(spec_input) if isinstance(spec_input, Path) else "<content>",
                    self.config.default_runtime,
                    include_optimization=True
                )
                performance_metrics = perf_result.get("performance_metrics", {})

            total_time = time.time() - processing_start
            self.metrics["operations_performed"] += 1
            self.metrics["total_processing_time"] += total_time

            # Trigger event handlers
            await self._trigger_event("specification_processed", {
                "validation_result": validation_result,
                "conversion_results": conversion_results,
                "processing_time": total_time
            })

            return {
                "success": True,
                "session_id": self.session_id,
                "processing_time": total_time,
                "validation_result": validation_result,
                "component_analysis": component_analysis,
                "conversion_results": conversion_results,
                "developer_insights": developer_insights,
                "performance_metrics": performance_metrics,
                "recommendations": await self._generate_recommendations(
                    validation_result, conversion_results, performance_metrics
                )
            }

        except Exception as e:
            total_time = time.time() - processing_start
            self.metrics["errors_handled"] += 1

            logger.error(f"Error in comprehensive processing: {e}")

            return {
                "success": False,
                "error": str(e),
                "processing_time": total_time,
                "session_id": self.session_id
            }

    async def create_specification_interactive(
        self,
        template: Optional[str] = None,
        guided_mode: bool = True
    ) -> Dict[str, Any]:
        """
        Interactive specification creation with enhanced guidance.

        Args:
            template: Template to use (single-agent, multi-agent, etc.)
            guided_mode: Whether to use guided creation

        Returns:
            Creation result with specification
        """
        if not self.enhanced_cli:
            return {"success": False, "error": "Enhanced CLI not available"}

        try:
            console.print("[blue]🎯 Starting interactive specification creation...[/blue]")

            if guided_mode:
                # Use enhanced CLI interactive builder
                spec_result = await self.enhanced_cli.interactive_spec_builder()

                if spec_result:
                    # Auto-validate created specification
                    spec_yaml = yaml.dump(spec_result, default_flow_style=False)
                    validation_result = await self.spec_service.validate_spec(spec_yaml, detailed=True)

                    return {
                        "success": True,
                        "specification": spec_result,
                        "specification_yaml": spec_yaml,
                        "validation_result": validation_result,
                        "recommendations": self._get_creation_recommendations(spec_result)
                    }
                else:
                    return {"success": False, "error": "Specification creation cancelled"}
            else:
                # Provide template-based creation
                template_spec = self._get_specification_template(template)
                return {
                    "success": True,
                    "template": template_spec,
                    "next_steps": [
                        "Customize the template components",
                        "Add specific configuration",
                        "Validate the specification",
                        "Convert to target runtime"
                    ]
                }

        except Exception as e:
            logger.error(f"Error in interactive creation: {e}")
            return {"success": False, "error": str(e)}

    async def debug_specification_comprehensive(
        self,
        spec_input: Union[str, Path],
        debug_options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive specification debugging with all capabilities.

        Args:
            spec_input: Specification file path
            debug_options: Debug configuration options

        Returns:
            Debug results with detailed analysis
        """
        if not self.debugger:
            return {"success": False, "error": "Debugger not available"}

        debug_options = debug_options or {}

        try:
            console.print(f"[blue]🔬 Starting comprehensive debugging...[/blue]")

            # Use enhanced debugger
            debug_result = await self.debugger.debug_specification_file(
                str(spec_input),
                debug_options.get("target_runtime", self.config.default_runtime),
                debug_options.get("debug_level", DebugLevel.INFO),
                debug_options.get("watch_expressions", [])
            )

            # Enhance with performance analysis
            if self.dashboard:
                perf_analysis = await self.dashboard.monitor_specification_processing(
                    str(spec_input),
                    self.config.default_runtime,
                    include_optimization=True
                )
                debug_result["performance_analysis"] = perf_analysis

            # Add optimization suggestions
            debug_result["optimization_suggestions"] = await self._get_optimization_suggestions(
                str(spec_input)
            )

            return debug_result

        except Exception as e:
            logger.error(f"Error in comprehensive debugging: {e}")
            return {"success": False, "error": str(e)}

    async def get_development_insights(self) -> Dict[str, Any]:
        """
        Get comprehensive development insights and analytics.

        Returns:
            Development insights and recommendations
        """
        try:
            insights = {
                "session_info": {
                    "session_id": self.session_id,
                    "uptime": (datetime.now(timezone.utc) - self.start_time).total_seconds() if self.start_time else 0,
                    "mode": self.config.mode.value
                },
                "performance_metrics": self.metrics.copy(),
                "system_status": await self._get_system_status(),
                "recommendations": await self._get_development_recommendations()
            }

            # Add dashboard insights if available
            if self.dashboard:
                dashboard_summary = await self.dashboard.get_performance_summary()
                insights["performance_summary"] = dashboard_summary

            # Add component mapping insights
            components_info = await self.spec_service.get_all_available_components()
            insights["component_status"] = {
                "total_mapped": components_info.get("discovery_stats", {}).get("total_mapped", 0),
                "mapping_coverage": components_info.get("discovery_stats", {}).get("mapping_coverage", 0),
                "unmapped_count": components_info.get("discovery_stats", {}).get("unmapped_count", 0)
            }

            return {
                "success": True,
                "insights": insights,
                "generated_at": datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting development insights: {e}")
            return {"success": False, "error": str(e)}

    async def run_comprehensive_testing(
        self,
        test_specs: Optional[List[str]] = None,
        test_options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Run comprehensive testing suite.

        Args:
            test_specs: Specific specifications to test
            test_options: Testing configuration options

        Returns:
            Testing results
        """
        if not self.tester:
            return {"success": False, "error": "Testing framework not available"}

        test_options = test_options or {}

        try:
            console.print("[blue]🧪 Running comprehensive testing suite...[/blue]")

            if test_specs:
                # Test specific specifications
                results = []
                for spec_path in test_specs:
                    result = await self.tester.test_specification_file(spec_path)
                    results.append(result)

                return {
                    "success": True,
                    "test_type": "specification_tests",
                    "results": results,
                    "summary": self._summarize_spec_test_results(results)
                }
            else:
                # Run full integration test suite
                suite_result = await self.tester.run_comprehensive_test_suite(
                    include_performance=test_options.get("include_performance", True)
                )

                return {
                    "success": suite_result.get("success", False),
                    "test_type": "comprehensive_suite",
                    "results": suite_result
                }

        except Exception as e:
            logger.error(f"Error in comprehensive testing: {e}")
            return {"success": False, "error": str(e)}

    async def export_session_data(
        self,
        output_path: str,
        format: str = "json",
        include_artifacts: bool = True
    ) -> Dict[str, Any]:
        """
        Export session data and artifacts.

        Args:
            output_path: Output file path
            format: Export format (json, yaml, html)
            include_artifacts: Whether to include artifacts

        Returns:
            Export result
        """
        try:
            export_data = {
                "session_info": {
                    "session_id": self.session_id,
                    "start_time": self.start_time.isoformat() if self.start_time else None,
                    "export_time": datetime.now(timezone.utc).isoformat(),
                    "mode": self.config.mode.value,
                    "configuration": self._serialize_config()
                },
                "metrics": self.metrics,
                "insights": await self.get_development_insights()
            }

            if include_artifacts and self.dashboard:
                # Export performance metrics
                perf_export = await self.dashboard.export_metrics(
                    f"{output_path}_metrics.json", "json"
                )
                export_data["performance_data_exported"] = perf_export

            # Write export data
            output_file = Path(output_path)

            if format.lower() == "json":
                with open(output_file, 'w') as f:
                    json.dump(export_data, f, indent=2, default=str)
            elif format.lower() == "yaml":
                with open(output_file, 'w') as f:
                    yaml.dump(export_data, f, default_flow_style=False)
            elif format.lower() == "html":
                html_content = self._generate_html_report(export_data)
                with open(output_file, 'w') as f:
                    f.write(html_content)

            console.print(f"[green]✅ Session data exported to {output_path}[/green]")

            return {
                "success": True,
                "output_path": str(output_file),
                "format": format,
                "size_bytes": output_file.stat().st_size
            }

        except Exception as e:
            logger.error(f"Error exporting session data: {e}")
            return {"success": False, "error": str(e)}

    def add_event_handler(self, event_type: str, handler: Callable) -> None:
        """Add event handler for service events."""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)

    # Private methods

    async def _load_specification(
        self,
        spec_input: Union[str, Path, Dict[str, Any]]
    ) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
        """Load specification from various input types."""
        try:
            if isinstance(spec_input, dict):
                spec_dict = spec_input
                spec_content = yaml.dump(spec_dict, default_flow_style=False)
            elif isinstance(spec_input, (str, Path)):
                if Path(spec_input).exists():
                    with open(spec_input, 'r', encoding='utf-8') as f:
                        spec_content = f.read()
                    spec_dict = yaml.safe_load(spec_content)
                else:
                    # Treat as YAML content
                    spec_content = str(spec_input)
                    spec_dict = yaml.safe_load(spec_content)
            else:
                return None, None

            return spec_content, spec_dict

        except Exception as e:
            logger.error(f"Error loading specification: {e}")
            return None, None

    async def _perform_enhanced_validation(
        self,
        spec_content: str,
        validation_options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Perform enhanced multi-layer validation."""
        if validation_options.get("runtime_validation", True):
            result = await self.spec_service.validate_spec_with_runtime(
                spec_content,
                self.config.default_runtime,
                ValidationOptions(
                    strict_mode=validation_options.get("strict_mode", True),
                    performance_checks=validation_options.get("performance_checks", True),
                    detailed_errors=validation_options.get("detailed_errors", True)
                )
            )
        else:
            result = await self.spec_service.validate_spec(
                spec_content,
                detailed=validation_options.get("detailed", True)
            )

        self.metrics["validations_completed"] += 1
        return result

    async def _perform_component_analysis(self, spec_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Perform dynamic component analysis."""
        components = spec_dict.get("components", {})

        analysis = {
            "component_count": len(components),
            "component_types": {},
            "complexity_score": 0,
            "patterns_detected": [],
            "optimization_opportunities": []
        }

        # Analyze component types and patterns
        for comp_id, comp_data in components.items():
            comp_type = comp_data.get("type", "unknown")

            if comp_type not in analysis["component_types"]:
                analysis["component_types"][comp_type] = 0
            analysis["component_types"][comp_type] += 1

        # Calculate complexity score
        edge_count = sum(len(comp.get("provides", [])) for comp in components.values())
        analysis["complexity_score"] = len(components) * 2 + edge_count

        # Detect patterns
        if "genesis:crewai_agent" in analysis["component_types"]:
            analysis["patterns_detected"].append("multi_agent_crewai")

        if any("knowledge" in comp_type for comp_type in analysis["component_types"]):
            analysis["patterns_detected"].append("knowledge_enhanced")

        # Identify optimization opportunities
        if analysis["complexity_score"] > 20:
            analysis["optimization_opportunities"].append("Consider breaking into smaller workflows")

        return analysis

    async def _perform_multi_runtime_conversion(
        self,
        spec_content: str,
        target_runtimes: List[RuntimeType]
    ) -> Dict[str, Any]:
        """Perform conversion to multiple runtimes."""
        conversion_results = {}

        for runtime in target_runtimes:
            try:
                result = await self.spec_service.convert_spec_to_flow_enhanced(
                    spec_content,
                    target_runtime=runtime,
                    optimization_level=self.config.optimization_level.value
                )
                conversion_results[runtime.value] = result

                if result.get("success", False):
                    self.metrics["conversions_completed"] += 1

            except Exception as e:
                conversion_results[runtime.value] = {
                    "success": False,
                    "error": str(e)
                }

        return conversion_results

    async def _provide_developer_insights(
        self,
        spec_content: str,
        validation_result: Dict[str, Any],
        conversion_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Provide enhanced developer insights."""
        insights = {
            "quality_score": self._calculate_quality_score(validation_result),
            "best_practices": self._check_best_practices(spec_content),
            "improvement_suggestions": [],
            "learning_resources": []
        }

        # Add validation-based insights
        if not validation_result.get("valid", False):
            insights["improvement_suggestions"].extend([
                "Review and fix validation errors",
                "Check component type accuracy",
                "Validate connection patterns"
            ])

        # Add conversion-based insights
        failed_conversions = [
            runtime for runtime, result in conversion_results.items()
            if not result.get("success", False)
        ]

        if failed_conversions:
            insights["improvement_suggestions"].append(
                f"Fix conversion issues for: {', '.join(failed_conversions)}"
            )

        return insights

    async def _generate_recommendations(
        self,
        validation_result: Dict[str, Any],
        conversion_results: Dict[str, Any],
        performance_metrics: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate comprehensive recommendations."""
        recommendations = []

        # Validation recommendations
        if not validation_result.get("valid", False):
            recommendations.append({
                "category": "validation",
                "priority": "high",
                "title": "Fix Validation Issues",
                "description": "Resolve specification validation errors",
                "action": "Review errors and update specification"
            })

        # Performance recommendations
        validation_time = performance_metrics.get("validation_time", 0)
        if validation_time > 3.0:
            recommendations.append({
                "category": "performance",
                "priority": "medium",
                "title": "Optimize Validation Performance",
                "description": f"Validation took {validation_time:.2f}s",
                "action": "Consider simplifying specification structure"
            })

        # Conversion recommendations
        conversion_time = performance_metrics.get("conversion_time", 0)
        if conversion_time > 5.0:
            recommendations.append({
                "category": "performance",
                "priority": "medium",
                "title": "Optimize Conversion Performance",
                "description": f"Conversion took {conversion_time:.2f}s",
                "action": "Review component complexity and connections"
            })

        return recommendations

    async def _trigger_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Trigger event handlers."""
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                try:
                    await handler(data)
                except Exception as e:
                    logger.warning(f"Error in event handler for {event_type}: {e}")

    def _get_enabled_features(self) -> Dict[str, bool]:
        """Get list of enabled features."""
        return {
            "enhanced_cli": self.config.cli_enhanced,
            "ide_integration": self.config.ide_integration,
            "debug_tools": self.config.debug_enabled,
            "performance_monitoring": self.config.performance_monitoring,
            "auto_testing": self.config.auto_testing,
            "real_time_validation": self.config.real_time_validation,
            "performance_optimization": self.config.performance_optimization
        }

    def _serialize_config(self) -> Dict[str, Any]:
        """Serialize configuration for export."""
        return {
            "mode": self.config.mode.value,
            "default_runtime": self.config.default_runtime.value,
            "optimization_level": self.config.optimization_level.value,
            "validation_mode": self.config.validation_mode,
            "features": self._get_enabled_features()
        }

    async def _verify_runtime_support(self) -> Dict[str, bool]:
        """Verify runtime support status."""
        runtime_status = {}

        for runtime in RuntimeType:
            try:
                # Check if converter is available
                converter = converter_factory.registry.get_converter(runtime)
                runtime_status[runtime.value] = converter is not None
            except Exception:
                runtime_status[runtime.value] = False

        return runtime_status

    async def _get_system_status(self) -> Dict[str, Any]:
        """Get overall system status."""
        return {
            "service_initialized": self.is_initialized,
            "session_active": self.session_id is not None,
            "components_available": {
                "spec_service": True,
                "enhanced_cli": self.enhanced_cli is not None,
                "language_server": self.language_server is not None,
                "debugger": self.debugger is not None,
                "dashboard": self.dashboard is not None,
                "tester": self.tester is not None
            },
            "runtime_support": await self._verify_runtime_support()
        }

    async def _get_development_recommendations(self) -> List[str]:
        """Get development recommendations."""
        recommendations = []

        if self.metrics["errors_handled"] > 5:
            recommendations.append("High error rate detected - review specification quality")

        if self.metrics["total_processing_time"] / max(self.metrics["operations_performed"], 1) > 10:
            recommendations.append("Average processing time is high - consider optimization")

        return recommendations

    def _calculate_quality_score(self, validation_result: Dict[str, Any]) -> float:
        """Calculate specification quality score."""
        if validation_result.get("valid", False):
            warning_count = len(validation_result.get("warnings", []))
            # Start with 100, deduct for warnings
            score = 100 - (warning_count * 5)
            return max(score, 60)  # Minimum score for valid specs
        else:
            error_count = len(validation_result.get("errors", []))
            # Base score for invalid specs, further reduced by error count
            score = 40 - (error_count * 5)
            return max(score, 0)

    def _check_best_practices(self, spec_content: str) -> List[str]:
        """Check specification against best practices."""
        practices = []

        if "description:" in spec_content and "TODO" not in spec_content:
            practices.append("✅ Includes meaningful descriptions")

        if "provides:" in spec_content:
            practices.append("✅ Defines component connections")

        if "config:" in spec_content:
            practices.append("✅ Includes component configuration")

        return practices

    def _get_specification_template(self, template: Optional[str]) -> Dict[str, Any]:
        """Get specification template."""
        if template == "multi-agent":
            return {
                "id": "urn:agent:genesis:autonomize.ai:template-multi:1.0.0",
                "name": "Multi-Agent Template",
                "description": "Template for multi-agent workflows",
                "kind": "Multi Agent",
                "components": {
                    "input": {"type": "genesis:chat_input"},
                    "researcher": {"type": "genesis:crewai_agent"},
                    "analyst": {"type": "genesis:crewai_agent"},
                    "crew": {"type": "genesis:crewai_sequential_crew"},
                    "output": {"type": "genesis:chat_output"}
                }
            }
        else:
            # Default single-agent template
            return {
                "id": "urn:agent:genesis:autonomize.ai:template-single:1.0.0",
                "name": "Single Agent Template",
                "description": "Template for single-agent workflows",
                "kind": "Single Agent",
                "components": {
                    "input": {"type": "genesis:chat_input"},
                    "agent": {"type": "genesis:agent"},
                    "output": {"type": "genesis:chat_output"}
                }
            }

    def _get_creation_recommendations(self, spec_result: Dict[str, Any]) -> List[str]:
        """Get recommendations for created specification."""
        recommendations = []

        components = spec_result.get("components", {})

        if len(components) < 3:
            recommendations.append("Consider adding more components for richer functionality")

        if not any("provides" in comp for comp in components.values()):
            recommendations.append("Add component connections using 'provides' relationships")

        return recommendations

    async def _get_optimization_suggestions(self, spec_path: str) -> List[Dict[str, Any]]:
        """Get optimization suggestions for specification."""
        suggestions = []

        # This would integrate with the performance optimizer
        # For now, return basic suggestions
        suggestions.append({
            "type": "performance",
            "title": "Enable Caching",
            "description": "Consider enabling component result caching",
            "impact": "Improved response time for repeated operations"
        })

        return suggestions

    def _summarize_spec_test_results(self, results: List) -> Dict[str, Any]:
        """Summarize specification test results."""
        total = len(results)
        passed = sum(1 for r in results if r.status.value == "passed")

        return {
            "total_tests": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": (passed / total * 100) if total > 0 else 0
        }

    def _generate_html_report(self, export_data: Dict[str, Any]) -> str:
        """Generate HTML report from export data."""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Genesis Service Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background: #0066cc; color: white; padding: 20px; }}
        .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; }}
        .metric {{ display: inline-block; margin: 10px; padding: 10px; background: #f5f5f5; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Genesis Service Report</h1>
        <p>Session: {export_data['session_info']['session_id']}</p>
        <p>Generated: {export_data['session_info']['export_time']}</p>
    </div>

    <div class="section">
        <h2>Metrics</h2>
        <div class="metric">Operations: {export_data['metrics']['operations_performed']}</div>
        <div class="metric">Validations: {export_data['metrics']['validations_completed']}</div>
        <div class="metric">Conversions: {export_data['metrics']['conversions_completed']}</div>
        <div class="metric">Errors: {export_data['metrics']['errors_handled']}</div>
    </div>
</body>
</html>
"""
        return html


# Convenience function
async def create_unified_service(config: Optional[GenesisConfig] = None) -> UnifiedGenesisService:
    """
    Create and initialize unified Genesis service.

    Args:
        config: Service configuration

    Returns:
        Initialized unified service
    """
    service = UnifiedGenesisService(config)
    await service.initialize()
    return service


if __name__ == "__main__":
    async def main():
        """Example usage of unified Genesis service."""
        # Create service with development configuration
        config = GenesisConfig(
            mode=GenesisMode.DEVELOPMENT,
            performance_monitoring=True,
            debug_enabled=True,
            cli_enhanced=True
        )

        service = await create_unified_service(config)

        # Get development insights
        insights = await service.get_development_insights()
        console.print("Development Insights:")
        console.print(json.dumps(insights, indent=2, default=str))

    asyncio.run(main())