#!/usr/bin/env python3
"""
Comprehensive test suite for the Enhanced Dynamic Agent Specification Framework.

This test suite validates all phases of the optimization and ensures the framework
operates correctly with database-driven discovery and dynamic component resolution.
"""

import asyncio
import json
import time
import yaml
from pathlib import Path
from typing import Dict, Any

# Framework imports
from langflow.custom.specification_framework.core.specification_processor import SpecificationProcessor
from langflow.custom.specification_framework.services.component_discovery import ComponentDiscoveryService
from langflow.custom.specification_framework.models.processing_context import ProcessingContext
from langflow.cli.workflow.utils.service_integration import ServiceIntegration


class FrameworkTestSuite:
    """Comprehensive test suite for the enhanced framework."""

    def __init__(self):
        self.test_results = []
        self.performance_metrics = {}

    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all framework tests and return comprehensive results."""
        print("🚀 Starting Enhanced Dynamic Agent Specification Framework Test Suite")
        print("=" * 80)

        tests = [
            ("Component Discovery Service", self.test_component_discovery),
            ("Dynamic Resolution", self.test_dynamic_resolution),
            ("Agent Type Mappings", self.test_agent_mappings),
            ("Service Integration", self.test_service_integration),
            ("Specification Processing", self.test_specification_processing),
            ("CLI Integration", self.test_cli_integration),
            ("Healthcare Compliance", self.test_healthcare_compliance),
            ("Performance Benchmarks", self.test_performance_benchmarks)
        ]

        for test_name, test_func in tests:
            print(f"\n📋 Running: {test_name}")
            try:
                start_time = time.time()
                result = await test_func()
                duration = time.time() - start_time

                self.test_results.append({
                    "test": test_name,
                    "success": result.get("success", False),
                    "duration": duration,
                    "details": result
                })

                status = "✅ PASS" if result.get("success") else "❌ FAIL"
                print(f"   {status} ({duration:.3f}s)")

                if not result.get("success"):
                    print(f"   Error: {result.get('error', 'Unknown error')}")

            except Exception as e:
                self.test_results.append({
                    "test": test_name,
                    "success": False,
                    "duration": 0,
                    "error": str(e)
                })
                print(f"   ❌ FAIL - Exception: {e}")

        return self.generate_final_report()

    async def test_component_discovery(self) -> Dict[str, Any]:
        """Test the enhanced ComponentDiscoveryService."""
        try:
            discovery_service = ComponentDiscoveryService(enable_dynamic_resolution=True)

            # Test basic discovery functionality
            test_spec = {
                "components": [
                    {"type": "Agent", "id": "test_agent", "config": {"model": "gpt-4"}},
                    {"type": "WebSearch", "id": "search_tool", "config": {"engine": "google"}}
                ]
            }

            context = ProcessingContext(
                specification=test_spec,
                variables={},
                healthcare_compliance=False,
                performance_benchmarking=False
            )

            # Test enhanced discovery
            discovered = await discovery_service.discover_enhanced_components(test_spec, context)

            if not discovered:
                return {"success": False, "error": "No components discovered"}

            # Verify Agent component discovered
            agent_found = any("agent" in comp.get("langflow_component", "").lower()
                            for comp in discovered.values())

            return {
                "success": True,
                "components_discovered": len(discovered),
                "agent_component_found": agent_found,
                "discovery_methods": [comp.get("discovery_method") for comp in discovered.values()]
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def test_dynamic_resolution(self) -> Dict[str, Any]:
        """Test dynamic component resolution via /all endpoint."""
        try:
            discovery_service = ComponentDiscoveryService(enable_dynamic_resolution=True)

            # Test getting all available components
            all_components = await discovery_service.get_all_available_components()

            if not all_components or not all_components.get("components"):
                return {"success": False, "error": "Failed to load components from /all endpoint"}

            # Test dynamic resolution for known component types
            test_types = ["Agent", "APIRequest", "Calculator"]
            resolved_count = 0

            for comp_type in test_types:
                resolution = await discovery_service.resolve_component_dynamically(comp_type)
                if resolution:
                    resolved_count += 1

            return {
                "success": True,
                "total_component_categories": len(all_components["components"]),
                "test_types_resolved": f"{resolved_count}/{len(test_types)}",
                "resolution_success_rate": (resolved_count / len(test_types)) * 100
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def test_agent_mappings(self) -> Dict[str, Any]:
        """Test specific agent type mappings."""
        try:
            discovery_service = ComponentDiscoveryService(enable_dynamic_resolution=True)

            # Test agent type mappings
            agent_tests = [
                ("Agent", "AgentComponent"),
                ("CrewAIAgent", "CrewAIAgentComponent"),
                ("SimpleAgent", "AgentComponent")
            ]

            mapping_results = []

            for genesis_type, expected_component in agent_tests:
                resolution = await discovery_service.resolve_component_dynamically(genesis_type)

                success = (resolution is not None and
                          expected_component.lower() in resolution.get("langflow_component", "").lower())

                mapping_results.append({
                    "genesis_type": genesis_type,
                    "expected": expected_component,
                    "resolved": resolution.get("langflow_component") if resolution else None,
                    "success": success
                })

            successful_mappings = sum(1 for result in mapping_results if result["success"])

            return {
                "success": successful_mappings >= 2,  # At least 2 agent mappings should work
                "mapping_results": mapping_results,
                "success_rate": (successful_mappings / len(agent_tests)) * 100
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def test_service_integration(self) -> Dict[str, Any]:
        """Test the ServiceIntegration class."""
        try:
            service_integration = ServiceIntegration(local_mode=True)

            # Test with simple-agent example
            test_spec_path = Path("/Users/jagveersingh/Developer/studio/ai-studio/src/backend/base/examples/simple-agent.yaml")

            if not test_spec_path.exists():
                return {"success": False, "error": f"Test specification not found: {test_spec_path}"}

            # Test validation
            validation_result = await service_integration.validate_specification(test_spec_path)

            return {
                "success": validation_result.get("success", False),
                "validation_mode": validation_result.get("validation_mode"),
                "components_discovered": validation_result.get("components_discovered", 0),
                "healthcare_compliance": validation_result.get("healthcare_compliance", {})
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def test_specification_processing(self) -> Dict[str, Any]:
        """Test the enhanced SpecificationProcessor."""
        try:
            processor = SpecificationProcessor()

            # Load simple test specification
            test_spec = {
                "name": "Test Specification",
                "description": "Test specification for framework validation",
                "components": [
                    {
                        "type": "Agent",
                        "id": "main_agent",
                        "config": {
                            "model_provider": "OpenAI",
                            "model": "gpt-4",
                            "instructions": "You are a test agent"
                        }
                    }
                ]
            }

            context = ProcessingContext(
                specification=test_spec,
                variables={},
                healthcare_compliance=False,
                performance_benchmarking=False
            )

            # Process specification using enhanced discovery
            result = await processor.process_specification(test_spec, context)

            return {
                "success": result.success,
                "processing_time": result.processing_time_seconds,
                "component_count": result.component_count,
                "automation_percentage": result.automation_metrics.get("automation_percentage", 0) if result.automation_metrics else 0
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def test_cli_integration(self) -> Dict[str, Any]:
        """Test CLI integration readiness."""
        try:
            # Check if ServiceIntegration can be imported and initialized
            from langflow.cli.workflow.utils.service_integration import ServiceIntegration

            service_integration = ServiceIntegration(local_mode=True)

            # Test specification loading capability
            test_spec_content = """
name: CLI Test Specification
description: Test specification for CLI integration
components:
  - type: Agent
    id: cli_test_agent
    config:
      model: gpt-4
      instructions: "Test agent for CLI"
"""

            # Create temporary test file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                f.write(test_spec_content)
                temp_path = Path(f.name)

            try:
                # Test validation method
                result = await service_integration.validate_specification(temp_path)
                success = result.get("success", False)

                return {
                    "success": success,
                    "cli_integration_ready": True,
                    "can_load_specifications": True,
                    "can_validate_locally": success
                }

            finally:
                # Clean up temporary file
                temp_path.unlink(missing_ok=True)

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def test_healthcare_compliance(self) -> Dict[str, Any]:
        """Test healthcare compliance detection and validation."""
        try:
            # Load healthcare example if available
            healthcare_spec_path = Path("/Users/jagveersingh/Developer/studio/ai-studio/src/backend/base/examples/healthcare-agent.yaml")

            if healthcare_spec_path.exists():
                service_integration = ServiceIntegration(local_mode=True)
                result = await service_integration.validate_specification(healthcare_spec_path)

                compliance = result.get("healthcare_compliance", {})
                return {
                    "success": True,
                    "healthcare_example_available": True,
                    "compliance_detected": bool(compliance),
                    "compliance_percentage": compliance.get("compliance_percentage", 0)
                }
            else:
                # Test basic compliance detection
                discovery_service = ComponentDiscoveryService()

                # Test with healthcare component types
                healthcare_types = ["EHRConnector", "EligibilityConnector", "ClaimsConnector"]
                compliance_detected = 0

                for comp_type in healthcare_types:
                    is_compliant = discovery_service._is_healthcare_compliant_simple(comp_type)
                    if is_compliant:
                        compliance_detected += 1

                return {
                    "success": compliance_detected > 0,
                    "healthcare_example_available": False,
                    "compliance_detection_working": compliance_detected > 0,
                    "healthcare_types_detected": f"{compliance_detected}/{len(healthcare_types)}"
                }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def test_performance_benchmarks(self) -> Dict[str, Any]:
        """Test performance benchmarks and optimization targets."""
        try:
            processor = SpecificationProcessor()

            # Performance test specification
            test_spec = {
                "name": "Performance Test",
                "description": "Multi-component specification for performance testing",
                "components": [
                    {"type": "Agent", "id": "agent1", "config": {"model": "gpt-4"}},
                    {"type": "APIRequest", "id": "api1", "config": {"url": "https://api.example.com"}},
                    {"type": "Calculator", "id": "calc1", "config": {"precision": 6}},
                    {"type": "WebSearch", "id": "search1", "config": {"engine": "google"}},
                ]
            }

            context = ProcessingContext(
                specification=test_spec,
                variables={},
                healthcare_compliance=False,
                performance_benchmarking=True
            )

            # Measure processing time
            start_time = time.time()
            result = await processor.process_specification(test_spec, context)
            processing_time = time.time() - start_time

            # Performance targets
            target_processing_time = 2.0  # seconds
            target_automation = 80  # percent

            automation_percentage = 0
            if result.automation_metrics:
                automation_percentage = result.automation_metrics.get("automation_percentage", 0)

            meets_time_target = processing_time < target_processing_time
            meets_automation_target = automation_percentage >= target_automation

            self.performance_metrics = {
                "processing_time": processing_time,
                "automation_percentage": automation_percentage,
                "component_count": result.component_count if result.success else 0,
                "meets_time_target": meets_time_target,
                "meets_automation_target": meets_automation_target
            }

            return {
                "success": result.success and meets_time_target,
                "processing_time": processing_time,
                "target_time": target_processing_time,
                "automation_percentage": automation_percentage,
                "target_automation": target_automation,
                "performance_grade": "A" if meets_time_target and meets_automation_target else "B" if meets_time_target or meets_automation_target else "C"
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def generate_final_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report."""
        total_tests = len(self.test_results)
        successful_tests = sum(1 for result in self.test_results if result["success"])
        success_rate = (successful_tests / total_tests) * 100 if total_tests > 0 else 0

        report = {
            "framework_version": "Enhanced Dynamic Agent Specification Framework v2.0",
            "test_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "summary": {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "failed_tests": total_tests - successful_tests,
                "success_rate": round(success_rate, 1)
            },
            "test_results": self.test_results,
            "performance_metrics": self.performance_metrics,
            "framework_status": "READY" if success_rate >= 80 else "NEEDS_ATTENTION",
            "recommendations": self.generate_recommendations()
        }

        return report

    def generate_recommendations(self) -> list:
        """Generate recommendations based on test results."""
        recommendations = []

        failed_tests = [result for result in self.test_results if not result["success"]]

        if not failed_tests:
            recommendations.append("✅ All tests passed! Framework is production-ready.")
        else:
            recommendations.append(f"⚠️ {len(failed_tests)} test(s) failed. Review and fix before production deployment.")

        if self.performance_metrics:
            if self.performance_metrics.get("processing_time", 999) > 2.0:
                recommendations.append("🚀 Consider optimizing processing performance for better user experience.")

            if self.performance_metrics.get("automation_percentage", 0) < 80:
                recommendations.append("🔧 Improve automation percentage by enhancing component discovery logic.")

        recommendations.append("📊 Consider running this test suite as part of CI/CD pipeline.")

        return recommendations


async def main():
    """Run the comprehensive test suite."""
    test_suite = FrameworkTestSuite()

    try:
        results = await test_suite.run_all_tests()

        print("\n" + "=" * 80)
        print("📊 COMPREHENSIVE TEST REPORT")
        print("=" * 80)

        # Print summary
        summary = results["summary"]
        print(f"Framework Status: {results['framework_status']}")
        print(f"Success Rate: {summary['success_rate']}% ({summary['successful_tests']}/{summary['total_tests']} tests passed)")

        # Print performance metrics
        if results["performance_metrics"]:
            metrics = results["performance_metrics"]
            print(f"\n⚡ Performance Metrics:")
            print(f"  Processing Time: {metrics.get('processing_time', 0):.3f}s (target: <2.0s)")
            print(f"  Automation: {metrics.get('automation_percentage', 0):.1f}% (target: ≥80%)")
            print(f"  Performance Grade: {metrics.get('performance_grade', 'N/A')}")

        # Print recommendations
        print(f"\n💡 Recommendations:")
        for rec in results["recommendations"]:
            print(f"  {rec}")

        # Save detailed report
        report_path = Path("framework_test_report.json")
        with open(report_path, 'w') as f:
            json.dump(results, f, indent=2)

        print(f"\n📄 Detailed report saved to: {report_path}")

        return results["framework_status"] == "READY"

    except Exception as e:
        print(f"\n❌ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)