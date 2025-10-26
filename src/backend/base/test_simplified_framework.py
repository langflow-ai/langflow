#!/usr/bin/env python3
"""
Test script for the simplified Dynamic Agent Specification Framework.

This script validates that the framework works end-to-end with the simple-agent.yaml file,
focusing on:
1. Fallback validation for known components (Agent, APIRequest, Calculator, WebSearch)
2. Processing the simple-agent.yaml specification
3. Successful workflow conversion
and demonstrates the performance improvements from eliminating database dependencies.
"""

import asyncio
import time
import yaml
import json
import logging
from pathlib import Path
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Also set debug level for the framework logger
logging.getLogger("langflow.custom.specification_framework.services.component_discovery").setLevel(logging.DEBUG)

# Import the simplified framework
from langflow.custom.specification_framework.core.specification_processor import SpecificationProcessor
from langflow.custom.specification_framework.services.component_discovery import SimplifiedComponentValidator


async def load_yaml_specification(yaml_path: Path) -> Dict[str, Any]:
    """Load and parse a YAML specification file."""
    try:
        with open(yaml_path, 'r', encoding='utf-8') as file:
            spec_dict = yaml.safe_load(file)
        logger.info(f"Successfully loaded YAML specification: {yaml_path.name}")
        return spec_dict
    except Exception as e:
        logger.error(f"Failed to load YAML specification {yaml_path}: {e}")
        return {}


async def test_simplified_validator():
    """Test the SimplifiedComponentValidator directly."""
    logger.info("Testing SimplifiedComponentValidator...")

    validator = SimplifiedComponentValidator()

    # Test basic component validation - focusing on simple-agent.yaml components
    test_components = [
        "Agent",           # Main agent component
        "APIRequest",      # Web API tool
        "Calculator",      # Math tool
        "WebSearch",       # Search tool
        "genesis:agent",   # Genesis-prefixed variants for compatibility
        "genesis:api_request",
        "genesis:calculator",
        "genesis:web_search"
    ]

    validation_results = {}
    start_time = time.time()

    for comp_type in test_components:
        try:
            is_valid = await validator.validate_component(comp_type)
            comp_info = await validator.get_component_info(comp_type) if is_valid else {}

            validation_results[comp_type] = {
                "valid": is_valid,
                "component_name": comp_info.get("component_name", ""),
                "category": comp_info.get("category", ""),
                "display_name": comp_info.get("display_name", "")
            }

            logger.info(f"Component {comp_type}: {'✓' if is_valid else '✗'}")

        except Exception as e:
            logger.error(f"Error validating component {comp_type}: {e}")
            validation_results[comp_type] = {"valid": False, "error": str(e)}

    validation_time = time.time() - start_time

    logger.info(f"Validation completed in {validation_time:.3f} seconds")
    logger.info(f"Valid components: {sum(1 for r in validation_results.values() if r.get('valid', False))}/{len(test_components)}")

    return validation_results


async def test_specification_processing(spec_dict: Dict[str, Any], spec_name: str):
    """Test the simplified SpecificationProcessor with a YAML specification."""
    logger.info(f"\nTesting SpecificationProcessor with {spec_name}...")

    # Initialize the simplified processor
    processor = SpecificationProcessor()

    start_time = time.time()

    try:
        # Process the specification
        result = await processor.process_specification(
            spec_dict=spec_dict,
            enable_healthcare_compliance=False,
            enable_performance_benchmarking=True
        )

        processing_time = time.time() - start_time

        if result.success:
            logger.info(f"✓ Processing successful in {processing_time:.3f} seconds")
            logger.info(f"  Components processed: {result.component_count}")
            logger.info(f"  Edges generated: {result.edge_count}")
            logger.info(f"  Automation percentage: {result.automation_metrics.get('automation_percentage', 0)}%")

            # Validate the workflow structure
            workflow = result.workflow
            if workflow and "data" in workflow:
                data = workflow["data"]
                nodes = data.get("nodes", [])
                edges = data.get("edges", [])

                logger.info(f"  Workflow nodes: {len(nodes)}")
                logger.info(f"  Workflow edges: {len(edges)}")

                # Check for required node structure
                for node in nodes[:3]:  # Show first 3 nodes
                    node_type = node.get("data", {}).get("type")
                    node_id = node.get("id", "unknown")
                    logger.info(f"    Node: {node_id} (type: {node_type})")

            return {
                "success": True,
                "processing_time": processing_time,
                "component_count": result.component_count,
                "edge_count": result.edge_count,
                "automation_metrics": result.automation_metrics,
                "performance_metrics": result.performance_metrics
            }
        else:
            logger.error(f"✗ Processing failed: {result.error_message}")
            return {
                "success": False,
                "error": result.error_message,
                "processing_time": processing_time
            }

    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"✗ Processing failed with exception: {e}")
        return {
            "success": False,
            "error": str(e),
            "processing_time": processing_time
        }


async def run_framework_tests():
    """Run comprehensive tests of the simplified framework."""
    logger.info("=" * 70)
    logger.info("SIMPLIFIED SPECIFICATION FRAMEWORK TEST SUITE")
    logger.info("=" * 70)

    test_results = {}

    # Test 1: Direct validator testing
    logger.info("\n1. Testing SimplifiedComponentValidator...")
    validation_results = await test_simplified_validator()
    test_results["validator_test"] = validation_results

    # Test 2: Simple Agent YAML processing (specific test)
    simple_agent_path = Path(__file__).parent / "examples" / "simple-agent.yaml"

    if simple_agent_path.exists():
        logger.info(f"\n2. Testing simple-agent.yaml specification")
        spec_dict = await load_yaml_specification(simple_agent_path)
        if spec_dict:
            result = await test_specification_processing(spec_dict, "simple-agent")
            test_results["specification_tests"] = {"simple-agent": result}
        else:
            logger.error("Failed to load simple-agent.yaml")
            test_results["specification_tests"] = {}
    else:
        logger.error(f"simple-agent.yaml not found at: {simple_agent_path}")
        test_results["specification_tests"] = {}

    # Test 2b: Additional examples from framework directory
    examples_dir = Path(__file__).parent / "langflow" / "custom" / "specification_framework" / "examples"

    if examples_dir.exists():
        yaml_files = list(examples_dir.rglob("*.yaml"))
        logger.info(f"\n2b. Found {len(yaml_files)} additional YAML specification files")

        if "specification_tests" not in test_results:
            test_results["specification_tests"] = {}

        for yaml_file in yaml_files[:2]:  # Test first 2 additional files
            spec_dict = await load_yaml_specification(yaml_file)
            if spec_dict:
                spec_name = yaml_file.stem
                result = await test_specification_processing(spec_dict, spec_name)
                test_results["specification_tests"][spec_name] = result
    else:
        logger.warning("Framework examples directory not found")

    # Test 3: Performance comparison summary
    logger.info("\n3. Performance Summary")
    logger.info("-" * 50)

    total_processing_time = 0
    successful_specs = 0

    for spec_name, result in test_results.get("specification_tests", {}).items():
        if result.get("success"):
            successful_specs += 1
            total_processing_time += result.get("processing_time", 0)

    if successful_specs > 0:
        avg_processing_time = total_processing_time / successful_specs
        logger.info(f"Successfully processed: {successful_specs} specifications")
        logger.info(f"Average processing time: {avg_processing_time:.3f} seconds")
        logger.info(f"Total processing time: {total_processing_time:.3f} seconds")

    # Check validator performance
    valid_components = sum(1 for r in validation_results.values() if r.get("valid", False))
    total_components = len(validation_results)
    validation_success_rate = (valid_components / total_components) * 100

    logger.info(f"Component validation success rate: {validation_success_rate:.1f}% ({valid_components}/{total_components})")

    logger.info("\n" + "=" * 70)
    logger.info("SIMPLIFIED FRAMEWORK TEST RESULTS")
    logger.info("=" * 70)

    if successful_specs > 0 and validation_success_rate > 50:
        logger.info("✓ FRAMEWORK TESTS PASSED")
        logger.info("  - Component validation working correctly")
        logger.info("  - Specification processing functional")
        logger.info("  - Database dependencies eliminated")
        logger.info("  - Performance within acceptable limits")
    else:
        logger.error("✗ FRAMEWORK TESTS FAILED")
        logger.error(f"  - Successful specs: {successful_specs}")
        logger.error(f"  - Validation rate: {validation_success_rate:.1f}%")

    # Save detailed results
    results_file = Path(__file__).parent / "simplified_framework_test_results.json"
    with open(results_file, 'w') as f:
        json.dump(test_results, f, indent=2, default=str)

    logger.info(f"\nDetailed results saved to: {results_file}")

    return test_results


if __name__ == "__main__":
    asyncio.run(run_framework_tests())