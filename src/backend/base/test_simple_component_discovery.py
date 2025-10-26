#!/usr/bin/env python3
"""
Focused test for component discovery with simple-agent.yaml

This script tests just the component discovery phase to verify that the
simplified framework can correctly discover and map all components from
the simple-agent.yaml specification.
"""

import asyncio
import logging
import yaml
import json
import sys
from pathlib import Path
from typing import Dict, Any

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the langflow path to sys.path for imports
sys.path.insert(0, str(Path(__file__).parent))

from langflow.custom.specification_framework.services.component_discovery import SimplifiedComponentValidator
from langflow.custom.specification_framework.models.processing_context import ProcessingContext


async def test_simple_agent_component_discovery():
    """Test component discovery specifically for simple-agent.yaml."""
    logger.info("Testing component discovery for simple-agent.yaml")

    # Load the simple-agent.yaml specification
    simple_agent_path = Path(__file__).parent / "examples" / "simple-agent.yaml"

    if not simple_agent_path.exists():
        logger.error(f"simple-agent.yaml not found at: {simple_agent_path}")
        return False

    with open(simple_agent_path, 'r', encoding='utf-8') as file:
        spec_dict = yaml.safe_load(file)

    logger.info(f"Loaded specification: {spec_dict.get('name', 'Unknown')}")
    logger.info(f"Components to discover: {len(spec_dict.get('components', []))}")

    # Create validator and processing context
    validator = SimplifiedComponentValidator()
    context = ProcessingContext(
        specification=spec_dict,
        variables={},
        healthcare_compliance=False,
        performance_benchmarking=True
    )

    # Discover components
    discovery_results = await validator.discover_enhanced_components(spec_dict, context)

    # Analyze results
    logger.info("="*60)
    logger.info("COMPONENT DISCOVERY RESULTS")
    logger.info("="*60)

    total_components = len(spec_dict.get('components', []))
    discovered_components = len(discovery_results)

    logger.info(f"Total components in spec: {total_components}")
    logger.info(f"Successfully discovered: {discovered_components}")
    logger.info(f"Discovery success rate: {(discovered_components/total_components)*100:.1f}%")

    # Show detailed results for each component
    for comp_id, comp_info in discovery_results.items():
        logger.info(f"\nComponent: {comp_id}")
        logger.info(f"  Genesis Type: {comp_info['genesis_type']}")
        logger.info(f"  Langflow Component: {comp_info['langflow_component']}")
        logger.info(f"  Category: {comp_info['category']}")
        logger.info(f"  Display Name: {comp_info['display_name']}")
        logger.info(f"  Discovery Method: {comp_info['discovery_method']}")
        logger.info(f"  Tool Capabilities: {comp_info['tool_capabilities']}")

    # Check expected components from simple-agent.yaml
    expected_components = ["main_agent", "web_api", "math_tool", "search_tool"]
    missing_components = [comp for comp in expected_components if comp not in discovery_results]

    if missing_components:
        logger.warning(f"Missing expected components: {missing_components}")
    else:
        logger.info("✓ All expected components discovered successfully!")

    # Save detailed results
    results_file = Path(__file__).parent / "component_discovery_test_results.json"
    with open(results_file, 'w') as f:
        json.dump({
            "specification_name": spec_dict.get('name'),
            "total_components": total_components,
            "discovered_components": discovered_components,
            "success_rate": (discovered_components/total_components)*100,
            "discovery_results": discovery_results,
            "missing_components": missing_components,
            "test_passed": len(missing_components) == 0 and discovered_components == total_components
        }, f, indent=2, default=str)

    logger.info(f"\nDetailed results saved to: {results_file}")

    # Test result
    test_passed = len(missing_components) == 0 and discovered_components == total_components

    if test_passed:
        logger.info("🎉 Component discovery test PASSED!")
        logger.info("The simplified framework can successfully discover all components from simple-agent.yaml")
    else:
        logger.error("❌ Component discovery test FAILED!")
        logger.error(f"Issues: {discovered_components}/{total_components} discovered, missing: {missing_components}")

    return test_passed


if __name__ == "__main__":
    success = asyncio.run(test_simple_agent_component_discovery())
    sys.exit(0 if success else 1)