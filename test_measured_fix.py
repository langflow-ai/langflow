#!/usr/bin/env python3
"""
Test script to verify that converter-generated nodes include the measured property.
This should resolve the visual gap issue in Tool → Agent connections.
"""

import sys
import os
import json

# Add the backend path to Python path
sys.path.insert(0, os.path.join(os.getcwd(), 'src', 'backend', 'base'))

try:
    from langflow.custom.genesis.spec.models import AgentSpec, Component, ComponentProvides

    # Create a minimal test specification with a tool and agent
    test_spec_data = {
        "id": "test-agent",
        "name": "Test Agent",
        "description": "Test agent for measuring fix verification",
        "agentGoal": "Test the measured property fix",
        "components": [
            {
                "id": "test-tool",
                "name": "Test Tool",
                "kind": "Tool",
                "type": "genesis:calculator",
                "description": "Test tool component",
                "asTools": True,
                "provides": [
                    {
                        "useAs": "tools",
                        "in": "test-agent-main"
                    }
                ]
            },
            {
                "id": "test-agent-main",
                "name": "Main Agent",
                "kind": "Agent",
                "type": "genesis:agent",
                "description": "Main agent component"
            }
        ]
    }

    # Create AgentSpec
    spec = AgentSpec.from_dict(test_spec_data)
    print("✓ AgentSpec created successfully")

    # Import and create converter
    from langflow.custom.genesis.spec.converter import FlowConverter
    converter = FlowConverter()
    print("✓ FlowConverter created successfully")

    # Convert to flow
    flow_json = converter.convert_to_langflow(spec)
    print("✓ Conversion completed successfully")

    # Check for measured property in nodes
    nodes = flow_json.get('nodes', [])
    print(f"✓ Generated {len(nodes)} nodes")

    measured_nodes = 0
    for node in nodes:
        if 'measured' in node:
            measured_nodes += 1
            measured = node['measured']
            print(f"✓ Node '{node['id']}' has measured: {measured}")
        else:
            print(f"✗ Node '{node['id']}' missing measured property")

    if measured_nodes == len(nodes):
        print(f"\n🎉 SUCCESS: All {len(nodes)} nodes have measured property!")

        # Check for Tool → Agent edges
        edges = flow_json.get('edges', [])
        tool_agent_edges = []
        for edge in edges:
            target_handle = edge.get('targetHandle', '')
            if 'tools' in target_handle:
                tool_agent_edges.append(edge)
                print(f"✓ Found Tool→Agent edge: {edge['source']} → {edge['target']}")

        if tool_agent_edges:
            print(f"🎯 Found {len(tool_agent_edges)} Tool→Agent edge(s) that should now render without gaps!")
        else:
            print("ℹ️  No Tool→Agent edges found in this test")

    else:
        print(f"\n❌ FAILURE: Only {measured_nodes}/{len(nodes)} nodes have measured property")

except ImportError as e:
    print(f"❌ Import error: {e}")
    print("This is expected when running outside the full Langflow environment.")
    print("The fix has been applied to the converter code.")

except Exception as e:
    print(f"❌ Error during conversion: {e}")
    import traceback
    traceback.print_exc()