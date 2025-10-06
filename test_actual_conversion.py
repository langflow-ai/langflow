#!/usr/bin/env python3
"""Test actual conversion with the fixed edge logic."""

import asyncio
import json
import yaml
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "src/backend/base"))

async def test_conversion():
    """Test the actual conversion with fixed edge logic."""
    print("🔄 Testing Actual Conversion System")
    print("=" * 50)

    try:
        # Import after path setup
        from langflow.custom.genesis.spec.converter import FlowConverter
        from langflow.custom.genesis.spec.mapper import ComponentMapper

        # Load YAML
        with open("eoc-check-agent.yaml", "r") as f:
            yaml_content = f.read()

        spec_dict = yaml.safe_load(yaml_content)
        print(f"✅ Loaded YAML: {spec_dict.get('name')}")

        # Create converter
        mapper = ComponentMapper()
        converter = FlowConverter(mapper)

        # Convert
        print("🔄 Converting to Langflow JSON...")
        flow = await converter.convert(spec_dict)

        # Analyze result
        data = flow.get("data", {})
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])

        print(f"✅ Conversion successful!")
        print(f"📊 Generated {len(nodes)} nodes and {len(edges)} edges")

        # Analyze components
        print("\n🔍 Component Analysis:")
        for node in nodes:
            node_id = node.get("id")
            node_type = node.get("data", {}).get("type")
            outputs = node.get("data", {}).get("outputs", [])

            print(f"  📦 {node_id} ({node_type})")

            # Check for tool outputs
            tool_outputs = [o for o in outputs if o.get("name") == "component_as_tool"]
            if tool_outputs:
                tool_output = tool_outputs[0]
                print(f"    🔧 Tool Output: {tool_output.get('display_name')} ({tool_output.get('types')})")

            # Check for tools input
            template = node.get("data", {}).get("node", {}).get("template", {})
            if "tools" in template:
                tools_input = template["tools"]
                print(f"    🔌 Tools Input: {tools_input.get('input_types', [])} (type: {tools_input.get('type', 'unknown')})")

        # Analyze edges
        print("\n🔗 Edge Analysis:")
        tool_edges = []
        for edge in edges:
            edge_id = edge.get("id")
            source = edge.get("source")
            target = edge.get("target")
            source_handle = edge.get("sourceHandle", "")
            target_handle = edge.get("targetHandle", "")

            print(f"  🔗 {source} → {target}")
            print(f"     ID: {edge_id[:80]}...")

            # Check if this is a tool edge
            if "tools" in target_handle:
                tool_edges.append(edge)
                print(f"     🔧 TOOL CONNECTION!")

            # Validate edge ID format
            if edge_id.startswith("reactflow__edge-"):
                print(f"     ✅ Correct edge format")
            else:
                print(f"     ❌ Wrong edge format")

        # Summary
        print(f"\n📊 Summary:")
        print(f"  Total edges: {len(edges)}")
        print(f"  Tool connections: {len(tool_edges)}")

        if len(tool_edges) >= 2:  # Should have 2 tool connections (knowledge search + mcp)
            print("✅ SUCCESS: Tool connections found!")

            # Save result for inspection
            with open("debug_conversion_result.json", "w") as f:
                json.dump(flow, f, indent=2)
            print("💾 Saved result to: debug_conversion_result.json")

        else:
            print("❌ FAILED: Missing tool connections")
            print("🔍 Debugging needed...")

    except Exception as e:
        print(f"❌ Conversion failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_conversion())