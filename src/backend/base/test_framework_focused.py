"""
Focused Test for the Dynamic Agent Specification Framework

This test focuses on the core functionality in isolation to identify and fix issues.
"""

import asyncio
import json
import logging
import yaml
from pathlib import Path
from typing import Dict, Any

# Set up logging with less verbose output
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import framework components
from langflow.custom.specification_framework.core.specification_processor import SpecificationProcessor
from langflow.custom.specification_framework.services.component_discovery import SimplifiedComponentValidator


async def test_component_validation():
    """Test component validation in isolation."""
    print("=" * 60)
    print("Testing SimplifiedComponentValidator")
    print("=" * 60)

    validator = SimplifiedComponentValidator()

    # Test component types from simple chatbot
    test_components = ["genesis:chat_input", "genesis:openai", "genesis:chat_output"]

    results = {}
    for comp_type in test_components:
        print(f"\nTesting component: {comp_type}")

        # Test validation
        is_valid = await validator.validate_component(comp_type)
        print(f"  Valid: {is_valid}")

        if is_valid:
            # Test component info retrieval
            comp_info = await validator.get_component_info(comp_type)
            print(f"  Info retrieved: {bool(comp_info)}")
            if comp_info:
                print(f"  Category: {comp_info.get('category', 'unknown')}")
                print(f"  Langflow component: {comp_info.get('component_name', 'unknown')}")

        results[comp_type] = is_valid

    print(f"\nComponent validation results: {results}")
    return all(results.values())


async def test_specification_validation():
    """Test specification validation in isolation."""
    print("\n" + "=" * 60)
    print("Testing Specification Validation")
    print("=" * 60)

    spec_path = Path("/Users/jagveersingh/Developer/studio/ai-studio/src/backend/base/langflow/custom/specification_framework/examples/beginner/simple-chatbot-agent.yaml")

    # Load specification
    with open(spec_path, 'r') as file:
        spec_dict = yaml.safe_load(file)

    print(f"Loaded specification: {spec_dict.get('name')} v{spec_dict.get('version')}")

    # Test basic validation (no healthcare compliance)
    processor = SpecificationProcessor()

    validation_result = await processor.validate_specification_only(spec_dict, healthcare_compliance=False)

    print(f"Validation result: {validation_result}")

    return validation_result.get("valid", False)


async def test_basic_processing():
    """Test basic specification processing without complex features."""
    print("\n" + "=" * 60)
    print("Testing Basic Specification Processing")
    print("=" * 60)

    spec_path = Path("/Users/jagveersingh/Developer/studio/ai-studio/src/backend/base/langflow/custom/specification_framework/examples/beginner/simple-chatbot-agent.yaml")

    # Load specification
    with open(spec_path, 'r') as file:
        spec_dict = yaml.safe_load(file)

    # Process with minimal configuration
    processor = SpecificationProcessor()

    try:
        result = await processor.process_specification(
            spec_dict=spec_dict,
            variables={"chatbot_name": "Test Bot"},
            enable_healthcare_compliance=False,  # Disable to avoid healthcare validation issues
            enable_performance_benchmarking=False
        )

        print(f"Processing success: {result.success}")
        if result.success:
            print(f"Component count: {result.component_count}")
            print(f"Edge count: {result.edge_count}")
            print(f"Processing time: {result.processing_time_seconds:.3f}s")

            # Check workflow structure
            if result.workflow:
                data = result.workflow.get("data", {})
                nodes = data.get("nodes", [])
                edges = data.get("edges", [])
                print(f"Generated nodes: {len(nodes)}")
                print(f"Generated edges: {len(edges)}")

                # Print node details
                for i, node in enumerate(nodes):
                    print(f"  Node {i+1}: {node.get('type', 'unknown')} - {node.get('data', {}).get('display_name', 'unnamed')}")
        else:
            print(f"Processing failed: {getattr(result, 'error_message', 'Unknown error')}")

        return result.success

    except Exception as e:
        print(f"Processing failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run focused tests."""
    print("🔧 Starting focused framework tests...")

    # Test 1: Component validation
    component_test_passed = await test_component_validation()

    # Test 2: Specification validation
    spec_test_passed = await test_specification_validation()

    # Test 3: Basic processing
    processing_test_passed = await test_basic_processing()

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Component validation: {'✓ PASSED' if component_test_passed else '✗ FAILED'}")
    print(f"Specification validation: {'✓ PASSED' if spec_test_passed else '✗ FAILED'}")
    print(f"Basic processing: {'✓ PASSED' if processing_test_passed else '✗ FAILED'}")

    overall_success = component_test_passed and spec_test_passed and processing_test_passed
    print(f"\nOverall result: {'🎉 ALL TESTS PASSED' if overall_success else '❌ SOME TESTS FAILED'}")

    # Save results
    results = {
        "component_validation": component_test_passed,
        "specification_validation": spec_test_passed,
        "basic_processing": processing_test_passed,
        "overall_success": overall_success
    }

    results_file = Path("/Users/jagveersingh/Developer/studio/ai-studio/src/backend/base/focused_test_results.json")
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: {results_file}")

    return overall_success


if __name__ == "__main__":
    asyncio.run(main())