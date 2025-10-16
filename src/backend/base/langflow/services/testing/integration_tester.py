"""
End-to-End Integration Testing Framework - Phase 4.

Provides comprehensive integration testing for Genesis specifications with:
- Complete workflow validation
- Phase 1-3 integration verification
- Performance and reliability testing
- Automated test suite execution
- Continuous integration support
"""

import asyncio
import json
import logging
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Callable
from dataclasses import dataclass, field
from enum import Enum

import yaml
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from langflow.services.spec.service import SpecService
from langflow.services.runtime import RuntimeType, ValidationOptions, converter_factory
from langflow.services.cli.enhanced_cli import EnhancedCLI, CLIConfig
from langflow.services.developer.debug_tools import GenesisDebugger, DebugLevel
from langflow.services.dashboard.performance_dashboard import PerformanceDashboard

logger = logging.getLogger(__name__)
console = Console()


class TestStatus(Enum):
    """Test execution status."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class TestCategory(Enum):
    """Test categories for organization."""
    UNIT = "unit"
    INTEGRATION = "integration"
    SYSTEM = "system"
    PERFORMANCE = "performance"
    REGRESSION = "regression"
    SMOKE = "smoke"


@dataclass
class TestResult:
    """Individual test result."""
    test_id: str
    name: str
    category: TestCategory
    status: TestStatus
    duration: float
    message: str = ""
    error_details: Optional[str] = None
    artifacts: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TestSuite:
    """Test suite definition."""
    name: str
    description: str
    tests: List[Callable] = field(default_factory=list)
    setup_hooks: List[Callable] = field(default_factory=list)
    teardown_hooks: List[Callable] = field(default_factory=list)
    parallel_execution: bool = False
    timeout: Optional[float] = None


class IntegrationTester:
    """
    Comprehensive integration testing framework for Genesis specifications.

    Provides end-to-end testing capabilities that verify the complete Genesis
    development workflow from specification creation to runtime execution.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize integration tester.

        Args:
            config: Testing configuration
        """
        self.config = config or {}
        self.spec_service = SpecService()
        self.enhanced_cli = EnhancedCLI(CLIConfig())
        self.debugger = GenesisDebugger()
        self.dashboard = PerformanceDashboard()

        # Test state
        self.test_results: List[TestResult] = []
        self.current_suite: Optional[TestSuite] = None
        self.test_artifacts_dir = Path(self.config.get("artifacts_dir", "./test_artifacts"))
        self.test_artifacts_dir.mkdir(exist_ok=True)

        # Test data
        self.sample_specifications = self._load_sample_specifications()

        # Metrics
        self.execution_metrics = {
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "error_tests": 0,
            "skipped_tests": 0,
            "total_duration": 0.0,
            "average_duration": 0.0
        }

    async def run_comprehensive_test_suite(self, include_performance: bool = True) -> Dict[str, Any]:
        """
        Run comprehensive test suite covering all Genesis functionality.

        Args:
            include_performance: Whether to include performance tests

        Returns:
            Test suite results
        """
        console.print(Panel.fit(
            "[bold blue]Genesis Comprehensive Integration Testing[/bold blue]\n"
            "Testing Phase 1-3 integration with Phase 4 enhancements",
            title="🧪 Testing Framework"
        ))

        start_time = time.time()

        try:
            # Start performance monitoring
            await self.dashboard.start_monitoring()

            # Run test phases
            await self._run_test_phase("Phase 1: Core Functionality Tests", self._test_core_functionality)
            await self._run_test_phase("Phase 2: Integration Tests", self._test_phase_integration)
            await self._run_test_phase("Phase 3: CLI and Developer Tools", self._test_cli_and_tools)
            await self._run_test_phase("Phase 4: End-to-End Workflows", self._test_end_to_end_workflows)

            if include_performance:
                await self._run_test_phase("Phase 5: Performance Tests", self._test_performance)

            # Generate comprehensive report
            total_duration = time.time() - start_time
            self.execution_metrics["total_duration"] = total_duration

            report = await self._generate_test_report()

            console.print(f"\n[green]✅ Testing completed in {total_duration:.2f}s[/green]")
            return report

        except Exception as e:
            console.print(f"[red]❌ Testing failed: {e}[/red]")
            logger.error(f"Test suite execution failed: {e}")
            return {"success": False, "error": str(e)}

        finally:
            await self.dashboard.stop_monitoring()

    async def test_specification_file(
        self,
        spec_path: str,
        test_scenarios: Optional[List[str]] = None
    ) -> TestResult:
        """
        Test individual specification file comprehensively.

        Args:
            spec_path: Path to specification file
            test_scenarios: Specific test scenarios to run

        Returns:
            Test result
        """
        test_id = str(uuid.uuid4())
        start_time = time.time()

        try:
            # Default test scenarios
            if test_scenarios is None:
                test_scenarios = [
                    "syntax_validation",
                    "semantic_validation",
                    "conversion_validation",
                    "performance_check"
                ]

            artifacts = {}
            all_passed = True
            messages = []

            for scenario in test_scenarios:
                scenario_result = await self._run_scenario_test(spec_path, scenario)
                artifacts[scenario] = scenario_result

                if not scenario_result.get("success", False):
                    all_passed = False
                    messages.append(f"{scenario}: {scenario_result.get('error', 'Failed')}")

            duration = time.time() - start_time

            result = TestResult(
                test_id=test_id,
                name=f"Specification Test: {Path(spec_path).name}",
                category=TestCategory.INTEGRATION,
                status=TestStatus.PASSED if all_passed else TestStatus.FAILED,
                duration=duration,
                message="; ".join(messages) if messages else "All scenarios passed",
                artifacts=artifacts
            )

            self.test_results.append(result)
            return result

        except Exception as e:
            duration = time.time() - start_time
            result = TestResult(
                test_id=test_id,
                name=f"Specification Test: {Path(spec_path).name}",
                category=TestCategory.INTEGRATION,
                status=TestStatus.ERROR,
                duration=duration,
                message=str(e),
                error_details=str(e)
            )

            self.test_results.append(result)
            return result

    async def validate_phase_integration(self) -> Dict[str, Any]:
        """
        Validate that all phases (1-3) integrate correctly with Phase 4.

        Returns:
            Integration validation results
        """
        integration_results = {
            "phase_1_validation": await self._test_phase_1_integration(),
            "phase_2_mapping": await self._test_phase_2_integration(),
            "phase_3_conversion": await self._test_phase_3_integration(),
            "phase_4_enhancement": await self._test_phase_4_enhancement()
        }

        # Overall integration status
        all_phases_pass = all(
            result.get("success", False) for result in integration_results.values()
        )

        return {
            "success": all_phases_pass,
            "phase_results": integration_results,
            "summary": self._generate_integration_summary(integration_results)
        }

    async def run_regression_tests(self, baseline_specs: List[str]) -> Dict[str, Any]:
        """
        Run regression tests against baseline specifications.

        Args:
            baseline_specs: List of baseline specification paths

        Returns:
            Regression test results
        """
        console.print("[blue]🔄 Running regression tests...[/blue]")

        regression_results = []

        for spec_path in baseline_specs:
            try:
                # Test current behavior
                current_result = await self.test_specification_file(spec_path, [
                    "syntax_validation",
                    "conversion_validation"
                ])

                # Load baseline results if available
                baseline_file = self.test_artifacts_dir / f"{Path(spec_path).stem}_baseline.json"
                baseline_result = None

                if baseline_file.exists():
                    with open(baseline_file) as f:
                        baseline_result = json.load(f)

                # Compare results
                comparison = self._compare_test_results(current_result, baseline_result)
                regression_results.append({
                    "spec_path": spec_path,
                    "current_result": current_result,
                    "baseline_result": baseline_result,
                    "comparison": comparison,
                    "regression_detected": comparison.get("has_regression", False)
                })

                # Save current result as new baseline
                with open(baseline_file, 'w') as f:
                    json.dump({
                        "status": current_result.status.value,
                        "duration": current_result.duration,
                        "artifacts": current_result.artifacts
                    }, f, indent=2)

            except Exception as e:
                regression_results.append({
                    "spec_path": spec_path,
                    "error": str(e),
                    "regression_detected": True
                })

        # Calculate regression summary
        total_tests = len(regression_results)
        regressions = sum(1 for r in regression_results if r.get("regression_detected", False))

        return {
            "success": regressions == 0,
            "total_tests": total_tests,
            "regressions_detected": regressions,
            "regression_rate": (regressions / total_tests) * 100 if total_tests > 0 else 0,
            "detailed_results": regression_results
        }

    # Private test phase methods

    async def _run_test_phase(self, phase_name: str, test_function: Callable) -> None:
        """Run test phase with progress tracking."""
        console.print(f"\n[bold cyan]{phase_name}[/bold cyan]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(f"Running {phase_name}...", total=100)

            try:
                result = await test_function()
                progress.update(task, completed=100)

                if result.get("success", False):
                    console.print(f"[green]✅ {phase_name} completed successfully[/green]")
                else:
                    console.print(f"[red]❌ {phase_name} failed[/red]")

            except Exception as e:
                progress.update(task, completed=100)
                console.print(f"[red]❌ {phase_name} failed with error: {e}[/red]")

    async def _test_core_functionality(self) -> Dict[str, Any]:
        """Test core Genesis functionality."""
        tests = []

        # Test 1: Basic specification validation
        test_result = await self._run_test(
            "basic_validation",
            self._test_basic_validation,
            TestCategory.UNIT
        )
        tests.append(test_result)

        # Test 2: Component mapping
        test_result = await self._run_test(
            "component_mapping",
            self._test_component_mapping,
            TestCategory.UNIT
        )
        tests.append(test_result)

        # Test 3: Conversion functionality
        test_result = await self._run_test(
            "basic_conversion",
            self._test_basic_conversion,
            TestCategory.UNIT
        )
        tests.append(test_result)

        return self._summarize_test_results(tests)

    async def _test_phase_integration(self) -> Dict[str, Any]:
        """Test integration between all phases."""
        tests = []

        # Test 1: Phase 1-2 integration
        test_result = await self._run_test(
            "phase_1_2_integration",
            self._test_validation_mapping_integration,
            TestCategory.INTEGRATION
        )
        tests.append(test_result)

        # Test 2: Phase 2-3 integration
        test_result = await self._run_test(
            "phase_2_3_integration",
            self._test_mapping_conversion_integration,
            TestCategory.INTEGRATION
        )
        tests.append(test_result)

        # Test 3: End-to-end integration
        test_result = await self._run_test(
            "end_to_end_integration",
            self._test_complete_workflow_integration,
            TestCategory.INTEGRATION
        )
        tests.append(test_result)

        return self._summarize_test_results(tests)

    async def _test_cli_and_tools(self) -> Dict[str, Any]:
        """Test CLI and developer tools."""
        tests = []

        # Test 1: Enhanced CLI validation
        test_result = await self._run_test(
            "cli_validation",
            self._test_cli_validation,
            TestCategory.SYSTEM
        )
        tests.append(test_result)

        # Test 2: Debugging tools
        test_result = await self._run_test(
            "debug_tools",
            self._test_debug_tools,
            TestCategory.SYSTEM
        )
        tests.append(test_result)

        # Test 3: Performance dashboard
        test_result = await self._run_test(
            "performance_dashboard",
            self._test_performance_dashboard,
            TestCategory.SYSTEM
        )
        tests.append(test_result)

        return self._summarize_test_results(tests)

    async def _test_end_to_end_workflows(self) -> Dict[str, Any]:
        """Test complete end-to-end workflows."""
        tests = []

        for spec_name, spec_content in self.sample_specifications.items():
            test_result = await self._run_test(
                f"e2e_{spec_name}",
                lambda sc=spec_content: self._test_complete_workflow(sc),
                TestCategory.SYSTEM
            )
            tests.append(test_result)

        return self._summarize_test_results(tests)

    async def _test_performance(self) -> Dict[str, Any]:
        """Test performance characteristics."""
        tests = []

        # Test 1: Validation performance
        test_result = await self._run_test(
            "validation_performance",
            self._test_validation_performance,
            TestCategory.PERFORMANCE
        )
        tests.append(test_result)

        # Test 2: Conversion performance
        test_result = await self._run_test(
            "conversion_performance",
            self._test_conversion_performance,
            TestCategory.PERFORMANCE
        )
        tests.append(test_result)

        # Test 3: Memory usage
        test_result = await self._run_test(
            "memory_usage",
            self._test_memory_usage,
            TestCategory.PERFORMANCE
        )
        tests.append(test_result)

        return self._summarize_test_results(tests)

    # Individual test implementations

    async def _test_basic_validation(self) -> Dict[str, Any]:
        """Test basic specification validation."""
        try:
            # Create a simple test specification
            test_spec = """
id: urn:agent:genesis:autonomize.ai:test:1.0.0
name: Test Agent
description: Test specification
agentGoal: Test goal
kind: Single Agent

components:
  input:
    type: genesis:chat_input
    name: User Input

  agent:
    type: genesis:agent
    name: Main Agent

  output:
    type: genesis:chat_output
    name: Response Output
"""

            # Validate using enhanced validation
            result = await self.spec_service.validate_spec(test_spec, detailed=True)

            if result.get("valid", False):
                return {"success": True, "message": "Basic validation passed"}
            else:
                return {
                    "success": False,
                    "message": "Basic validation failed",
                    "errors": result.get("errors", [])
                }

        except Exception as e:
            return {"success": False, "message": str(e)}

    async def _test_component_mapping(self) -> Dict[str, Any]:
        """Test component mapping functionality."""
        try:
            # Get available components
            components = await self.spec_service.get_all_available_components()

            genesis_mapped = components.get("genesis_mapped", {})
            discovery_stats = components.get("discovery_stats", {})

            # Check if core components are mapped
            required_components = [
                "genesis:chat_input",
                "genesis:chat_output",
                "genesis:agent",
                "genesis:crewai_agent"
            ]

            missing_components = [
                comp for comp in required_components
                if comp not in genesis_mapped
            ]

            if missing_components:
                return {
                    "success": False,
                    "message": f"Missing component mappings: {missing_components}"
                }

            mapping_coverage = discovery_stats.get("mapping_coverage", 0)
            if mapping_coverage < 50:  # Threshold for acceptable coverage
                return {
                    "success": False,
                    "message": f"Low mapping coverage: {mapping_coverage:.1f}%"
                }

            return {
                "success": True,
                "message": f"Component mapping passed ({mapping_coverage:.1f}% coverage)",
                "stats": discovery_stats
            }

        except Exception as e:
            return {"success": False, "message": str(e)}

    async def _test_basic_conversion(self) -> Dict[str, Any]:
        """Test basic specification conversion."""
        try:
            # Create a test specification
            test_spec = """
id: urn:agent:genesis:autonomize.ai:test-conversion:1.0.0
name: Test Conversion
description: Test specification for conversion
agentGoal: Test conversion goal
kind: Single Agent

components:
  input:
    type: genesis:chat_input
    name: User Input
    provides:
    - useAs: input
      in: agent

  agent:
    type: genesis:agent
    name: Main Agent
    config:
      provider: Azure OpenAI
      temperature: 0.7
    provides:
    - useAs: response
      in: output

  output:
    type: genesis:chat_output
    name: Response Output
"""

            # Convert to Langflow
            conversion_result = await self.spec_service.convert_spec_to_flow_enhanced(
                test_spec,
                target_runtime=RuntimeType.LANGFLOW
            )

            if conversion_result.get("success", False):
                return {
                    "success": True,
                    "message": "Basic conversion passed",
                    "flow_data": conversion_result.get("flow_data", {})
                }
            else:
                return {
                    "success": False,
                    "message": "Basic conversion failed",
                    "errors": conversion_result.get("errors", [])
                }

        except Exception as e:
            return {"success": False, "message": str(e)}

    async def _test_complete_workflow(self, spec_content: str) -> Dict[str, Any]:
        """Test complete workflow from specification to execution."""
        try:
            # Create temporary specification file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.genesis.yaml', delete=False) as f:
                f.write(spec_content)
                temp_spec_path = f.name

            try:
                # Step 1: Validate specification
                validation_result = await self.enhanced_cli.validate_specification_enhanced(
                    temp_spec_path,
                    real_time=False,
                    show_suggestions=False,
                    runtime_validation=True
                )

                if not validation_result.get("valid", False):
                    return {
                        "success": False,
                        "message": "Workflow validation failed",
                        "step": "validation",
                        "errors": validation_result.get("errors", [])
                    }

                # Step 2: Convert specification
                conversion_result = await self.enhanced_cli.convert_specification_enhanced(
                    temp_spec_path,
                    runtime=RuntimeType.LANGFLOW,
                    preview_only=True
                )

                if not conversion_result.get("success", False):
                    return {
                        "success": False,
                        "message": "Workflow conversion failed",
                        "step": "conversion",
                        "errors": conversion_result.get("errors", [])
                    }

                # Step 3: Debug analysis
                debug_result = await self.debugger.debug_specification_file(
                    temp_spec_path,
                    RuntimeType.LANGFLOW,
                    debug_level=DebugLevel.INFO
                )

                if not debug_result.get("success", False):
                    return {
                        "success": False,
                        "message": "Workflow debug failed",
                        "step": "debug",
                        "error": debug_result.get("error", "Unknown debug error")
                    }

                # Step 4: Performance monitoring
                perf_result = await self.dashboard.monitor_specification_processing(
                    temp_spec_path,
                    RuntimeType.LANGFLOW,
                    include_optimization=True
                )

                if not perf_result.get("success", False):
                    return {
                        "success": False,
                        "message": "Workflow performance monitoring failed",
                        "step": "performance",
                        "error": perf_result.get("error", "Unknown performance error")
                    }

                return {
                    "success": True,
                    "message": "Complete workflow test passed",
                    "validation_time": validation_result.get("validation_time", 0),
                    "conversion_time": conversion_result.get("conversion_time", 0),
                    "performance_metrics": perf_result.get("performance_metrics", {})
                }

            finally:
                # Clean up temporary file
                Path(temp_spec_path).unlink(missing_ok=True)

        except Exception as e:
            return {"success": False, "message": str(e)}

    # Additional test implementations...

    async def _run_test(
        self,
        test_name: str,
        test_function: Callable,
        category: TestCategory
    ) -> TestResult:
        """Run individual test with timing and error handling."""
        test_id = str(uuid.uuid4())
        start_time = time.time()

        try:
            result = await test_function()
            duration = time.time() - start_time

            if result.get("success", False):
                status = TestStatus.PASSED
                message = result.get("message", "Test passed")
            else:
                status = TestStatus.FAILED
                message = result.get("message", "Test failed")

            test_result = TestResult(
                test_id=test_id,
                name=test_name,
                category=category,
                status=status,
                duration=duration,
                message=message,
                artifacts=result
            )

        except Exception as e:
            duration = time.time() - start_time
            test_result = TestResult(
                test_id=test_id,
                name=test_name,
                category=category,
                status=TestStatus.ERROR,
                duration=duration,
                message=str(e),
                error_details=str(e)
            )

        self.test_results.append(test_result)
        self._update_metrics(test_result)

        return test_result

    async def _run_scenario_test(self, spec_path: str, scenario: str) -> Dict[str, Any]:
        """Run specific test scenario."""
        if scenario == "syntax_validation":
            return await self._test_syntax_validation(spec_path)
        elif scenario == "semantic_validation":
            return await self._test_semantic_validation(spec_path)
        elif scenario == "conversion_validation":
            return await self._test_conversion_validation(spec_path)
        elif scenario == "performance_check":
            return await self._test_performance_check(spec_path)
        else:
            return {"success": False, "error": f"Unknown scenario: {scenario}"}

    async def _test_syntax_validation(self, spec_path: str) -> Dict[str, Any]:
        """Test syntax validation for specification."""
        try:
            with open(spec_path, 'r') as f:
                spec_content = f.read()

            # Parse YAML
            yaml.safe_load(spec_content)

            return {"success": True, "message": "Syntax validation passed"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _test_semantic_validation(self, spec_path: str) -> Dict[str, Any]:
        """Test semantic validation for specification."""
        try:
            with open(spec_path, 'r') as f:
                spec_content = f.read()

            result = await self.spec_service.validate_spec(spec_content, detailed=True)

            return {
                "success": result.get("valid", False),
                "errors": result.get("errors", []),
                "warnings": result.get("warnings", [])
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _test_conversion_validation(self, spec_path: str) -> Dict[str, Any]:
        """Test conversion validation for specification."""
        try:
            with open(spec_path, 'r') as f:
                spec_content = f.read()

            result = await self.spec_service.convert_spec_to_flow_enhanced(
                spec_content,
                target_runtime=RuntimeType.LANGFLOW
            )

            return {
                "success": result.get("success", False),
                "errors": result.get("errors", []),
                "flow_data": result.get("flow_data", {})
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _test_performance_check(self, spec_path: str) -> Dict[str, Any]:
        """Test performance characteristics of specification."""
        try:
            result = await self.dashboard.monitor_specification_processing(
                spec_path,
                RuntimeType.LANGFLOW,
                include_optimization=True
            )

            metrics = result.get("performance_metrics", {})
            validation_time = metrics.get("validation_time", 0)
            conversion_time = metrics.get("conversion_time", 0)

            # Check performance thresholds
            performance_issues = []
            if validation_time > 5.0:
                performance_issues.append("High validation time")
            if conversion_time > 10.0:
                performance_issues.append("High conversion time")

            return {
                "success": len(performance_issues) == 0,
                "performance_metrics": metrics,
                "issues": performance_issues
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _summarize_test_results(self, test_results: List[TestResult]) -> Dict[str, Any]:
        """Summarize test results."""
        total = len(test_results)
        passed = sum(1 for t in test_results if t.status == TestStatus.PASSED)
        failed = sum(1 for t in test_results if t.status == TestStatus.FAILED)
        errors = sum(1 for t in test_results if t.status == TestStatus.ERROR)

        return {
            "success": failed == 0 and errors == 0,
            "total_tests": total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "pass_rate": (passed / total) * 100 if total > 0 else 0,
            "test_results": test_results
        }

    def _update_metrics(self, test_result: TestResult) -> None:
        """Update execution metrics."""
        self.execution_metrics["total_tests"] += 1

        if test_result.status == TestStatus.PASSED:
            self.execution_metrics["passed_tests"] += 1
        elif test_result.status == TestStatus.FAILED:
            self.execution_metrics["failed_tests"] += 1
        elif test_result.status == TestStatus.ERROR:
            self.execution_metrics["error_tests"] += 1
        elif test_result.status == TestStatus.SKIPPED:
            self.execution_metrics["skipped_tests"] += 1

        # Update average duration
        total_duration = sum(r.duration for r in self.test_results)
        self.execution_metrics["average_duration"] = total_duration / len(self.test_results)

    async def _generate_test_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report."""
        return {
            "execution_summary": self.execution_metrics,
            "test_results": [
                {
                    "test_id": r.test_id,
                    "name": r.name,
                    "category": r.category.value,
                    "status": r.status.value,
                    "duration": r.duration,
                    "message": r.message,
                    "timestamp": r.timestamp.isoformat()
                }
                for r in self.test_results
            ],
            "category_breakdown": self._get_category_breakdown(),
            "performance_summary": await self._get_performance_summary(),
            "recommendations": self._get_test_recommendations()
        }

    def _get_category_breakdown(self) -> Dict[str, Dict[str, int]]:
        """Get test results breakdown by category."""
        breakdown = {}

        for category in TestCategory:
            category_tests = [r for r in self.test_results if r.category == category]
            breakdown[category.value] = {
                "total": len(category_tests),
                "passed": sum(1 for t in category_tests if t.status == TestStatus.PASSED),
                "failed": sum(1 for t in category_tests if t.status == TestStatus.FAILED),
                "errors": sum(1 for t in category_tests if t.status == TestStatus.ERROR)
            }

        return breakdown

    async def _get_performance_summary(self) -> Dict[str, Any]:
        """Get performance testing summary."""
        performance_tests = [r for r in self.test_results if r.category == TestCategory.PERFORMANCE]

        if not performance_tests:
            return {"message": "No performance tests executed"}

        total_duration = sum(t.duration for t in performance_tests)
        avg_duration = total_duration / len(performance_tests)

        return {
            "performance_tests": len(performance_tests),
            "total_duration": total_duration,
            "average_duration": avg_duration,
            "fastest_test": min(performance_tests, key=lambda t: t.duration).duration,
            "slowest_test": max(performance_tests, key=lambda t: t.duration).duration
        }

    def _get_test_recommendations(self) -> List[str]:
        """Get recommendations based on test results."""
        recommendations = []

        # Check pass rate
        pass_rate = (self.execution_metrics["passed_tests"] /
                    max(self.execution_metrics["total_tests"], 1)) * 100

        if pass_rate < 90:
            recommendations.append("Consider improving test coverage and fixing failing tests")

        # Check average duration
        if self.execution_metrics["average_duration"] > 5.0:
            recommendations.append("Some tests are taking longer than expected - consider optimization")

        # Check error rate
        error_rate = (self.execution_metrics["error_tests"] /
                     max(self.execution_metrics["total_tests"], 1)) * 100

        if error_rate > 5:
            recommendations.append("High error rate detected - review test implementation")

        return recommendations

    def _load_sample_specifications(self) -> Dict[str, str]:
        """Load sample specifications for testing."""
        return {
            "simple_agent": """
id: urn:agent:genesis:autonomize.ai:test-simple:1.0.0
name: Simple Test Agent
description: Simple test specification
agentGoal: Test simple agent functionality
kind: Single Agent

components:
  input:
    type: genesis:chat_input
    name: User Input
    provides:
    - useAs: input
      in: agent

  agent:
    type: genesis:agent
    name: Main Agent
    config:
      provider: Azure OpenAI
      temperature: 0.7
    provides:
    - useAs: response
      in: output

  output:
    type: genesis:chat_output
    name: Response Output
""",

            "multi_agent": """
id: urn:agent:genesis:autonomize.ai:test-multi:1.0.0
name: Multi Agent Test
description: Multi-agent test specification
agentGoal: Test multi-agent functionality
kind: Multi Agent

components:
  input:
    type: genesis:chat_input
    name: User Input
    provides:
    - useAs: input
      in: crew

  researcher:
    type: genesis:crewai_agent
    name: Researcher
    config:
      role: Research Specialist
      goal: Research information thoroughly
      backstory: Expert researcher

  analyst:
    type: genesis:crewai_agent
    name: Analyst
    config:
      role: Data Analyst
      goal: Analyze and interpret data
      backstory: Experienced data analyst

  crew:
    type: genesis:crewai_sequential_crew
    name: Research Crew
    config:
      agents: [researcher, analyst]
      process: sequential
    provides:
    - useAs: response
      in: output

  output:
    type: genesis:chat_output
    name: Response Output
"""
        }

    # Additional integration test methods would be implemented here...
    # This includes phase-specific integration tests, CLI testing, debugging tools testing, etc.


if __name__ == "__main__":
    async def main():
        """Example usage of integration tester."""
        tester = IntegrationTester()

        # Run comprehensive test suite
        results = await tester.run_comprehensive_test_suite(include_performance=True)

        console.print("Test Results:")
        console.print(json.dumps(results, indent=2, default=str))

    asyncio.run(main())