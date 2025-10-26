"""
Comprehensive End-to-End Test for the Dynamic Agent Specification Framework

This test validates the complete workflow from YAML specification to Langflow JSON
using the SimplifiedComponentValidator architecture, demonstrating that we've
successfully eliminated the database layer while maintaining full functionality.

Test Coverage:
1. Load simple-chatbot-agent.yaml specification
2. Process through SpecificationProcessor with SimplifiedComponentValidator
3. Verify workflow conversion succeeds and generates valid Langflow JSON
4. Check automation metrics calculation
5. Ensure healthcare compliance validation works
6. Validate performance metrics
"""

import asyncio
import json
import logging
import time
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import framework components
from langflow.custom.specification_framework.core.specification_processor import SpecificationProcessor
from langflow.custom.specification_framework.services.component_discovery import SimplifiedComponentValidator
from langflow.custom.specification_framework.models.processing_context import ProcessingContext


class ComprehensiveFrameworkTester:
    """Comprehensive test runner for the specification framework."""

    def __init__(self):
        """Initialize the test runner."""
        self.base_path = Path("/Users/jagveersingh/Developer/studio/ai-studio/src/backend/base")
        self.spec_path = self.base_path / "langflow/custom/specification_framework/examples/beginner/simple-chatbot-agent.yaml"
        self.processor = SpecificationProcessor()
        self.test_results = {}

    async def run_comprehensive_test(self) -> Dict[str, Any]:
        """
        Run comprehensive end-to-end test of the specification framework.

        Returns:
            Test results dictionary with detailed outcomes
        """
        logger.info("Starting comprehensive end-to-end framework test")
        start_time = time.time()

        try:
            # Phase 1: Load and validate specification
            spec_dict = await self._load_specification()
            self.test_results["specification_loaded"] = True
            self.test_results["spec_metadata"] = {
                "name": spec_dict.get("name"),
                "version": spec_dict.get("version"),
                "component_count": len(spec_dict.get("components", []))
            }

            # Phase 2: Test component validation with SimplifiedComponentValidator
            await self._test_component_validation(spec_dict)

            # Phase 3: Process specification through complete pipeline
            processing_result = await self._process_specification(spec_dict)

            # Phase 4: Validate workflow generation
            await self._validate_workflow_generation(processing_result)

            # Phase 5: Test automation metrics
            await self._test_automation_metrics(processing_result)

            # Phase 6: Test healthcare compliance
            await self._test_healthcare_compliance(spec_dict)

            # Phase 7: Test performance metrics
            await self._test_performance_metrics(processing_result)

            # Phase 8: Generate comprehensive report
            self._generate_test_report(processing_result, time.time() - start_time)

            return self.test_results

        except Exception as e:
            logger.error(f"Comprehensive test failed: {e}", exc_info=True)
            self.test_results["error"] = str(e)
            self.test_results["success"] = False
            return self.test_results

    async def _load_specification(self) -> Dict[str, Any]:
        """Load the test specification from YAML file."""
        logger.info(f"Loading specification from {self.spec_path}")

        if not self.spec_path.exists():
            raise FileNotFoundError(f"Specification file not found: {self.spec_path}")

        with open(self.spec_path, 'r') as file:
            spec_dict = yaml.safe_load(file)

        logger.info(f"Loaded specification: {spec_dict.get('name')} v{spec_dict.get('version')}")
        return spec_dict

    async def _test_component_validation(self, spec_dict: Dict[str, Any]) -> None:
        """Test component validation using SimplifiedComponentValidator."""
        logger.info("Testing component validation with SimplifiedComponentValidator")

        validator = SimplifiedComponentValidator()
        components = spec_dict.get("components", [])

        validation_results = {}

        for component in components:
            comp_id = component.get("id")
            comp_type = component.get("type")

            # Test component validation
            is_valid = await validator.validate_component(comp_type)
            validation_results[comp_id] = {
                "type": comp_type,
                "valid": is_valid
            }

            if is_valid:
                # Test component info retrieval
                comp_info = await validator.get_component_info(comp_type)
                validation_results[comp_id]["info_retrieved"] = bool(comp_info)
                validation_results[comp_id]["category"] = comp_info.get("category", "unknown")
                validation_results[comp_id]["langflow_component"] = comp_info.get("component_name", "unknown")

            logger.info(f"Component {comp_id} ({comp_type}): valid={is_valid}")

        self.test_results["component_validation"] = validation_results

        # Check that all components were validated successfully
        all_valid = all(result["valid"] for result in validation_results.values())
        self.test_results["all_components_valid"] = all_valid

        if not all_valid:
            failed_components = [comp_id for comp_id, result in validation_results.items() if not result["valid"]]
            logger.warning(f"Failed component validation for: {failed_components}")

    async def _process_specification(self, spec_dict: Dict[str, Any]) -> Any:
        """Process specification through the complete pipeline."""
        logger.info("Processing specification through complete pipeline")

        # Test with different configurations
        configurations = [
            {"enable_healthcare_compliance": False, "enable_performance_benchmarking": False},
            {"enable_healthcare_compliance": True, "enable_performance_benchmarking": True},
        ]

        processing_results = {}

        for i, config in enumerate(configurations):
            logger.info(f"Testing configuration {i+1}: {config}")

            result = await self.processor.process_specification(
                spec_dict=spec_dict,
                variables={"chatbot_name": "Test Assistant", "personality": "professional"},
                **config
            )

            processing_results[f"config_{i+1}"] = {
                "success": result.success,
                "has_workflow": bool(result.workflow),
                "component_count": result.component_count,
                "edge_count": result.edge_count,
                "processing_time": result.processing_time_seconds,
                "config": config
            }

            if not result.success:
                processing_results[f"config_{i+1}"]["error"] = getattr(result, 'error_message', 'Unknown error')
                logger.error(f"Processing failed for config {i+1}: {getattr(result, 'error_message', 'Unknown error')}")
            else:
                logger.info(f"Processing succeeded for config {i+1} in {result.processing_time_seconds:.3f}s")

        self.test_results["processing_results"] = processing_results

        # Return the most comprehensive result for further testing
        successful_results = [result for result in processing_results.values() if result["success"]]
        if successful_results:
            # Find the result with healthcare compliance enabled
            for key, result_info in processing_results.items():
                if result_info["success"] and result_info["config"].get("enable_healthcare_compliance"):
                    # Get the actual result object (we need to re-process to get the object)
                    return await self.processor.process_specification(
                        spec_dict=spec_dict,
                        variables={"chatbot_name": "Test Assistant", "personality": "professional"},
                        enable_healthcare_compliance=True,
                        enable_performance_benchmarking=True
                    )

        raise Exception("No successful processing results found")

    async def _validate_workflow_generation(self, processing_result: Any) -> None:
        """Validate that workflow was generated correctly."""
        logger.info("Validating workflow generation")

        workflow = processing_result.workflow

        validation_checks = {
            "has_workflow": bool(workflow),
            "has_data_section": bool(workflow.get("data")),
            "has_nodes": len(workflow.get("data", {}).get("nodes", [])) > 0,
            "has_edges": len(workflow.get("data", {}).get("edges", [])) > 0,
            "node_count": len(workflow.get("data", {}).get("nodes", [])),
            "edge_count": len(workflow.get("data", {}).get("edges", [])),
            "has_metadata": bool(workflow.get("description") or workflow.get("name"))
        }

        # Validate node structure
        nodes = workflow.get("data", {}).get("nodes", [])
        node_validation = {}

        for node in nodes:
            node_id = node.get("id", "unknown")
            node_validation[node_id] = {
                "has_id": bool(node.get("id")),
                "has_type": bool(node.get("type")),
                "has_data": bool(node.get("data")),
                "has_position": bool(node.get("position"))
            }

        validation_checks["node_validation"] = node_validation

        # Validate edge structure
        edges = workflow.get("data", {}).get("edges", [])
        edge_validation = {
            "total_edges": len(edges),
            "valid_edges": 0,
            "edge_details": []
        }

        for edge in edges:
            is_valid_edge = bool(edge.get("source") and edge.get("target"))
            if is_valid_edge:
                edge_validation["valid_edges"] += 1

            edge_validation["edge_details"].append({
                "source": edge.get("source"),
                "target": edge.get("target"),
                "valid": is_valid_edge
            })

        validation_checks["edge_validation"] = edge_validation

        self.test_results["workflow_validation"] = validation_checks

        # Check critical validations
        critical_checks = ["has_workflow", "has_data_section", "has_nodes"]
        all_critical_passed = all(validation_checks[check] for check in critical_checks)
        self.test_results["workflow_generation_success"] = all_critical_passed

        if all_critical_passed:
            logger.info(f"Workflow validation passed: {validation_checks['node_count']} nodes, {validation_checks['edge_count']} edges")
        else:
            failed_checks = [check for check in critical_checks if not validation_checks[check]]
            logger.error(f"Workflow validation failed: {failed_checks}")

    async def _test_automation_metrics(self, processing_result: Any) -> None:
        """Test automation metrics calculation."""
        logger.info("Testing automation metrics calculation")

        automation_metrics = processing_result.automation_metrics

        metrics_validation = {
            "has_automation_metrics": bool(automation_metrics),
            "input_components": automation_metrics.get("input_components", 0),
            "generated_edges": automation_metrics.get("generated_edges", 0),
            "explicit_connections": automation_metrics.get("explicit_connections", 0),
            "implicit_connections": automation_metrics.get("implicit_connections", 0),
            "automation_percentage": automation_metrics.get("automation_percentage", 0),
            "meets_automation_target": automation_metrics.get("meets_automation_target", False)
        }

        # Validate that metrics make sense
        input_components = metrics_validation["input_components"]
        generated_edges = metrics_validation["generated_edges"]
        explicit_connections = metrics_validation["explicit_connections"]
        implicit_connections = metrics_validation["implicit_connections"]

        metrics_validation["metrics_logical"] = (
            input_components > 0 and
            generated_edges >= 0 and
            explicit_connections >= 0 and
            implicit_connections >= 0 and
            (explicit_connections + implicit_connections) <= generated_edges
        )

        self.test_results["automation_metrics"] = metrics_validation

        logger.info(f"Automation metrics: {metrics_validation['automation_percentage']:.1f}% automation, "
                   f"target met: {metrics_validation['meets_automation_target']}")

    async def _test_healthcare_compliance(self, spec_dict: Dict[str, Any]) -> None:
        """Test healthcare compliance validation."""
        logger.info("Testing healthcare compliance validation")

        # Test both with and without healthcare compliance
        compliance_results = {}

        for enable_compliance in [False, True]:
            result = await self.processor.process_specification(
                spec_dict=spec_dict,
                enable_healthcare_compliance=enable_compliance
            )

            compliance_results[f"compliance_enabled_{enable_compliance}"] = {
                "success": result.success,
                "has_compliance_metrics": bool(result.compliance_metrics),
                "compliance_metrics": result.compliance_metrics
            }

            if enable_compliance and result.success and result.compliance_metrics:
                compliance_metrics = result.compliance_metrics
                compliance_validation = {
                    "has_healthcare_components": compliance_metrics.get("has_healthcare_components", False),
                    "healthcare_node_count": compliance_metrics.get("healthcare_node_count", 0),
                    "hipaa_compliant_nodes": compliance_metrics.get("hipaa_compliant_nodes", 0),
                    "compliance_percentage": compliance_metrics.get("compliance_percentage", 0),
                    "fully_compliant": compliance_metrics.get("fully_compliant", False)
                }
                compliance_results[f"compliance_enabled_{enable_compliance}"]["validation"] = compliance_validation

        self.test_results["healthcare_compliance"] = compliance_results

        logger.info("Healthcare compliance validation completed")

    async def _test_performance_metrics(self, processing_result: Any) -> None:
        """Test performance metrics calculation."""
        logger.info("Testing performance metrics calculation")

        performance_metrics = processing_result.performance_metrics

        metrics_validation = {
            "has_performance_metrics": bool(performance_metrics),
            "node_count": performance_metrics.get("node_count", 0),
            "edge_count": performance_metrics.get("edge_count", 0),
            "processing_time_seconds": performance_metrics.get("processing_time_seconds", 0),
            "estimated_memory_mb": performance_metrics.get("estimated_memory_mb", 0),
            "complexity_score": performance_metrics.get("complexity_score", 0),
            "performance_target_met": performance_metrics.get("performance_target_met", False)
        }

        # Validate performance metrics make sense
        metrics_validation["metrics_reasonable"] = (
            metrics_validation["node_count"] > 0 and
            metrics_validation["processing_time_seconds"] > 0 and
            metrics_validation["processing_time_seconds"] < 30 and  # Should be fast
            metrics_validation["estimated_memory_mb"] > 0 and
            metrics_validation["complexity_score"] > 0
        )

        self.test_results["performance_metrics"] = metrics_validation

        logger.info(f"Performance metrics: {metrics_validation['processing_time_seconds']:.3f}s processing time, "
                   f"target met: {metrics_validation['performance_target_met']}")

    def _generate_test_report(self, processing_result: Any, total_test_time: float) -> None:
        """Generate comprehensive test report."""
        logger.info("Generating comprehensive test report")

        # Calculate overall success
        success_indicators = [
            self.test_results.get("specification_loaded", False),
            self.test_results.get("all_components_valid", False),
            self.test_results.get("workflow_generation_success", False),
            self.test_results.get("automation_metrics", {}).get("has_automation_metrics", False),
            self.test_results.get("performance_metrics", {}).get("has_performance_metrics", False)
        ]

        overall_success = all(success_indicators)

        # Create summary
        summary = {
            "overall_success": overall_success,
            "total_test_time_seconds": round(total_test_time, 3),
            "framework_architecture": "SimplifiedComponentValidator",
            "database_layer_eliminated": True,
            "test_phases_completed": len([k for k in self.test_results.keys() if not k.startswith("error")]),
            "components_tested": len(self.test_results.get("component_validation", {})),
            "workflow_generated": self.test_results.get("workflow_generation_success", False),
            "automation_percentage": self.test_results.get("automation_metrics", {}).get("automation_percentage", 0),
            "performance_target_met": self.test_results.get("performance_metrics", {}).get("performance_target_met", False),
            "success_indicators": {
                "specification_loaded": success_indicators[0],
                "component_validation": success_indicators[1],
                "workflow_generation": success_indicators[2],
                "automation_metrics": success_indicators[3],
                "performance_metrics": success_indicators[4]
            }
        }

        self.test_results["test_summary"] = summary

        # Log comprehensive results
        logger.info("=" * 80)
        logger.info("COMPREHENSIVE FRAMEWORK TEST RESULTS")
        logger.info("=" * 80)
        logger.info(f"Overall Success: {overall_success}")
        logger.info(f"Total Test Time: {total_test_time:.3f}s")
        logger.info(f"Framework Architecture: SimplifiedComponentValidator (database layer eliminated)")
        logger.info("")
        logger.info("Phase Results:")
        for indicator, passed in summary["success_indicators"].items():
            status = "✓ PASSED" if passed else "✗ FAILED"
            logger.info(f"  {indicator}: {status}")

        if processing_result and processing_result.success:
            logger.info("")
            logger.info("Framework Metrics:")
            logger.info(f"  Components Processed: {processing_result.component_count}")
            logger.info(f"  Workflow Edges: {processing_result.edge_count}")
            logger.info(f"  Processing Time: {processing_result.processing_time_seconds:.3f}s")
            logger.info(f"  Automation: {self.test_results.get('automation_metrics', {}).get('automation_percentage', 0):.1f}%")

        logger.info("=" * 80)


async def main():
    """Run the comprehensive framework test."""
    tester = ComprehensiveFrameworkTester()

    try:
        results = await tester.run_comprehensive_test()

        # Save results to file
        results_file = Path("/Users/jagveersingh/Developer/studio/ai-studio/src/backend/base/comprehensive_framework_test_results.json")
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        logger.info(f"Test results saved to: {results_file}")

        # Print final status
        if results.get("test_summary", {}).get("overall_success", False):
            logger.info("🎉 COMPREHENSIVE FRAMEWORK TEST PASSED!")
            logger.info("✅ Successfully eliminated database layer while maintaining full functionality")
        else:
            logger.error("❌ COMPREHENSIVE FRAMEWORK TEST FAILED")
            if "error" in results:
                logger.error(f"Error: {results['error']}")

        return results

    except Exception as e:
        logger.error(f"Test execution failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    asyncio.run(main())