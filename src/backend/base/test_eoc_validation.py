#!/usr/bin/env python3
"""
Simple test script to validate EOC specification.
"""

import yaml
import logging

# Set up logging to see detailed output
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(name)s:%(message)s')

# Import the converter directly
from langflow.custom.genesis.spec.converter import FlowConverter
from langflow.custom.genesis.spec.models import AgentSpec

async def test_eoc_validation():
    """Test EOC specification validation."""

    # Load the EOC specification
    with open('/Users/jagveersingh/Developer/studio/genesis-agent-cli/examples/agents/eoc-check-agent.yaml', 'r') as f:
        spec_data = yaml.safe_load(f)

    print("=== EOC Specification Validation Test ===")
    print(f"Spec Name: {spec_data.get('name')}")
    print(f"Components: {len(spec_data.get('components', []))}")

    # Create spec object
    try:
        spec = AgentSpec.from_dict(spec_data)
        print("✅ Spec parsed successfully")
    except Exception as e:
        print(f"❌ Spec parsing failed: {e}")
        return

    # Create converter and test conversion
    converter = FlowConverter()

    try:
        # This will test our fixed tool connection logic
        flow = await converter.convert(spec_data)
        print("✅ Conversion successful!")
        print(f"Generated {len(flow['data']['nodes'])} nodes and {len(flow['data']['edges'])} edges")

        # Check for tool connections
        for edge in flow['data']['edges']:
            if 'tools' in edge.get('targetHandle', ''):
                print(f"✅ Tool connection found: {edge['source']} -> {edge['target']}")

    except Exception as e:
        print(f"❌ Conversion failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_eoc_validation())