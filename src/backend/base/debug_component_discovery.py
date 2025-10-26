#!/usr/bin/env python3
"""
Debug script to investigate component discovery issues.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the langflow path to sys.path for imports
sys.path.insert(0, str(Path(__file__).parent))

from langflow.custom.specification_framework.services.component_discovery import SimplifiedComponentValidator


async def debug_component_validation():
    """Debug component validation to understand the /all endpoint structure."""
    validator = SimplifiedComponentValidator()

    # Get all components to inspect the structure
    all_components = await validator.get_all_components()

    print(f"Total categories found: {len(all_components)}")
    for category, components in all_components.items():
        if isinstance(components, dict):
            print(f"Category '{category}': {len(components)} components")
            # Show first few component names in each category
            comp_names = list(components.keys())[:3]
            print(f"  Sample components: {comp_names}")

            # Check if any of our test components are in this category
            test_components = ["Agent", "APIRequest", "Calculator", "WebSearch"]
            for test_comp in test_components:
                if test_comp in components:
                    comp_info = components[test_comp]
                    print(f"  Found {test_comp} in {category}:")
                    print(f"    Display name: {comp_info.get('display_name', 'N/A')}")
                    print(f"    Base classes: {comp_info.get('base_classes', [])}")

    print("\n" + "="*50)
    print("Testing individual component lookups:")

    test_components = ["Agent", "APIRequest", "Calculator", "WebSearch"]
    for comp in test_components:
        print(f"\nTesting component: {comp}")
        is_valid = await validator.validate_component(comp)
        print(f"  Validation result: {is_valid}")

        if is_valid:
            comp_info = await validator.get_component_info(comp)
            if comp_info:
                print(f"  Info found: {comp_info.get('component_name')} in {comp_info.get('category')}")
            else:
                print(f"  No info found despite validation success")


if __name__ == "__main__":
    asyncio.run(debug_component_validation())